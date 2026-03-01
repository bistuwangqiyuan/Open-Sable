"""
LLM integration for Open-Sable - Ollama with native tool calling
Dynamic model switching based on task requirements.
Supports: Ollama (local), OpenAI, Anthropic, DeepSeek, Groq, Together AI,
          xAI (Grok), Mistral, Google Gemini, Cohere, Kimi (Moonshot),
          Qwen (DashScope), OpenRouter — all with full tool calling.
"""

import asyncio
import fcntl
import logging
import json
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Any, AsyncIterator, Optional, Tuple
import ollama

logger = logging.getLogger(__name__)


# ── Inter-process Ollama queue ───────────────────────────────────────
# When multiple agents share the same Ollama instance, concurrent requests
# force the model to context-switch or double-load, causing slowdowns and
# potential OOM.  This file lock serialises access so only one agent
# generates at a time.  The lock is acquired asynchronously (via executor)
# so the event loop stays responsive while waiting.

_OLLAMA_LOCK_PATH = os.environ.get("SABLE_OLLAMA_LOCK", "/tmp/sable-ollama.lock")


@asynccontextmanager
async def _ollama_lock():
    """Async context-manager that acquires an inter-process file lock.

    Uses fcntl.flock (blocking) run in a thread so the event loop isn't
    blocked while another agent holds the lock.
    """
    loop = asyncio.get_running_loop()
    fd = os.open(_OLLAMA_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        # Blocking flock — offloaded to thread so the event loop stays alive
        await loop.run_in_executor(None, fcntl.flock, fd, fcntl.LOCK_EX)
        logger.debug("Ollama lock acquired")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        logger.debug("Ollama lock released")


# ── DeepSeek <think> tag support ─────────────────────────────────────

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def parse_thinking(text: str) -> Tuple[str, Optional[str]]:
    """Extract DeepSeek-style <think>...</think> reasoning from response text.

    Returns:
        (clean_text, reasoning)  --  reasoning is None when no tags found.
    """
    if not text or "<think>" not in text:
        return text, None

    reasoning_parts = _THINK_RE.findall(text)
    clean = _THINK_RE.sub("", text).strip()
    reasoning = "\n".join(p.strip() for p in reasoning_parts if p.strip()) or None
    return clean, reasoning


def _inject_no_think(messages: List[Dict]) -> List[Dict]:
    """For Qwen3 models: append /no_think to the last user message to disable
    chain-of-thought output. This is the official Qwen3 per-turn mechanism.
    Works with any model — non-Qwen3 models simply ignore the token.
    """
    messages = list(messages)  # shallow copy — don't mutate caller's list
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            content = messages[i].get("content", "")
            if "/no_think" not in content:
                messages[i] = dict(messages[i])
                messages[i]["content"] = content + " /no_think"
            break
    return messages


# ── Token & cost tracking ────────────────────────────────────────────

# Approximate costs per 1M tokens (USD) — updated periodically
_COST_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "mistral-large": {"input": 2.00, "output": 6.00},
    "llama-3.1-70b": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b": {"input": 0.05, "output": 0.08},
}


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    provider: str = ""
    estimated_cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


class TokenTracker:
    """Cumulative token usage tracker across all LLM calls."""

    def __init__(self):
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.call_count: int = 0
        self.history: List[TokenUsage] = []

    def record(self, usage: TokenUsage):
        """Record a single LLM call's token usage."""
        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens
        self.total_cost_usd += usage.estimated_cost_usd
        self.call_count += 1
        self.history.append(usage)
        logger.debug(
            f"Tokens: +{usage.total_tokens} ({usage.prompt_tokens}in/{usage.completion_tokens}out) "
            f"| Total: {self.total_tokens} | Cost: ${self.total_cost_usd:.6f}"
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable summary of current usage."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "call_count": self.call_count,
        }

    def reset(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.history.clear()

    @staticmethod
    def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD for a given model and token counts."""
        # Try exact match, then prefix match
        costs = _COST_PER_1M.get(model)
        if not costs:
            for key, val in _COST_PER_1M.items():
                if key in model or model in key:
                    costs = val
                    break
        if not costs:
            return 0.0  # Local model or unknown — free
        return (prompt_tokens * costs["input"] + completion_tokens * costs["output"]) / 1_000_000


# Model capabilities database (using actually available Ollama models)
MODEL_CAPABILITIES = {
    # High-end GPU models (20GB+ VRAM)
    "llama3.1:70b": {"reasoning": 9, "vision": 0, "tools": 8, "speed": 4, "vram": 24},
    "qwen2.5:72b": {"reasoning": 9, "vision": 0, "tools": 8, "speed": 4, "vram": 24},
    "mixtral:8x7b": {"reasoning": 8, "vision": 0, "tools": 7, "speed": 5, "vram": 24},
    # Mid-range GPU models (8GB+ VRAM)
    "llama3.1:8b": {"reasoning": 7, "vision": 0, "tools": 7, "speed": 8, "vram": 5},
    "qwen2.5:7b": {"reasoning": 7, "vision": 0, "tools": 7, "speed": 8, "vram": 4},
    "gemma2:9b": {"reasoning": 7, "vision": 0, "tools": 6, "speed": 8, "vram": 6},
    "phi3:14b": {"reasoning": 8, "vision": 0, "tools": 7, "speed": 6, "vram": 8},
    "mistral:7b": {"reasoning": 7, "vision": 0, "tools": 6, "speed": 8, "vram": 4},
    # CPU/Low RAM models
    "llama3.2:3b": {"reasoning": 6, "vision": 0, "tools": 6, "speed": 9, "vram": 0},
    "gemma2:2b": {"reasoning": 5, "vision": 0, "tools": 5, "speed": 9, "vram": 0},
    "qwen2.5:3b": {"reasoning": 6, "vision": 0, "tools": 6, "speed": 9, "vram": 0},
    "phi3:3.8b": {"reasoning": 6, "vision": 0, "tools": 6, "speed": 9, "vram": 0},
    "llama3.2:1b": {"reasoning": 4, "vision": 0, "tools": 4, "speed": 10, "vram": 0},
    "qwen2.5:0.5b": {"reasoning": 3, "vision": 0, "tools": 3, "speed": 10, "vram": 0},
}


class AdaptiveLLM:
    """LLM that can switch models based on task requirements"""

    # Shared across instances — remember which models don't support native tool calling
    _MODELS_WITHOUT_NATIVE_TOOLS: set = set()

    def __init__(self, config, initial_model: str):
        self.config = config
        self.current_model = initial_model
        self.base_url = config.ollama_base_url
        self.available_models = []
        self.token_tracker = TokenTracker()
        self._update_available_models()

    def _create_llm(self, model: str):
        """Store model name (no external LLM wrapper needed)."""
        self.current_model = model
        return model

    def _update_available_models(self):
        """Update list of available local models"""
        try:
            client = ollama.Client(host=self.base_url)
            models = client.list()
            self.available_models = [
                m.get("name") or m.get("model") or getattr(m, "model", "")
                for m in models.get("models", [])
            ]
            logger.info(f"Available models: {', '.join(self.available_models)}")
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            self.available_models = [self.current_model]

    async def auto_switch_model(self, task_type: str) -> bool:
        """
        Automatically switch to best model for task type
        task_type: 'vision', 'reasoning', 'tools', 'general'
        Returns True if switched, False if kept current
        """
        # Determine requirements based on task
        requirements = {
            "vision": {"vision": 7, "tools": 5},
            "reasoning": {"reasoning": 8, "tools": 6},
            "tools": {"tools": 7, "reasoning": 6},
            "general": {"reasoning": 6, "tools": 5, "speed": 7},
        }

        req = requirements.get(task_type, requirements["general"])

        # Find best model that meets requirements
        best_model = None
        best_score = -1

        for model in MODEL_CAPABILITIES:
            caps = MODEL_CAPABILITIES[model]

            # Check if requirements are met
            meets_req = all(caps.get(k, 0) >= v for k, v in req.items())
            if not meets_req:
                continue

            # Calculate score (prefer speed if tied)
            score = sum(caps.get(k, 0) for k in req.keys()) + caps.get("speed", 0) * 0.1

            if score > best_score:
                best_score = score
                best_model = model

        if best_model and best_model != self.current_model:
            # Block downloading large models (70b+)
            if "70b" in best_model.lower() or "405b" in best_model.lower():
                logger.warning(
                    f"Blocked download of large model {best_model}. Using {self.current_model} instead."
                )
                return False

            # Check if model is available, if not pull it
            if best_model not in self.available_models:
                logger.info(f"Model {best_model} not available, pulling...")
                await self._pull_model(best_model)

            # Switch model
            logger.info(f"Switching from {self.current_model} to {best_model} for {task_type} task")
            self.current_model = best_model
            return True

        return False

    async def _pull_model(self, model_name: str):
        """Download model from Ollama"""
        try:
            client = ollama.Client(host=self.base_url)
            logger.info(f"Downloading {model_name}...")
            client.pull(model_name)
            self.available_models.append(model_name)
            logger.info(f"Model {model_name} downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to pull {model_name}: {e}")
            raise

    async def ainvoke(self, messages):
        """Invoke current LLM (pure ollama, no langchain)."""
        client = ollama.AsyncClient(host=self.base_url)
        plain_msgs = []
        for m in messages:
            role = getattr(m, "type", None) or (m["role"] if isinstance(m, dict) else "user")
            content = getattr(m, "content", None) or (m["content"] if isinstance(m, dict) else str(m))
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
            plain_msgs.append({"role": role, "content": content})
        async with _ollama_lock():
            resp = await client.chat(model=self.current_model, messages=plain_msgs)
        from types import SimpleNamespace
        return SimpleNamespace(content=resp.get("message", {}).get("content", ""))

    def invoke(self, messages):
        """Sync invoke"""
        import asyncio
        return asyncio.run(self.ainvoke(messages))

    async def _invoke_with_text_tool_calling(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        """
        Text-based tool calling for models that don't support native Ollama tools API.
        Injects tool schemas into the system prompt and parses <tool_call> JSON blocks.
        Qwen3 understands this format natively.
        """
        # Build compact tool schema list
        tool_schemas = []
        for t in tools:
            fn = t.get("function", t)
            schema = {
                "name": fn.get("name", ""),
                "description": fn.get("description", "")[:200],
            }
            params = fn.get("parameters", {})
            if params.get("properties"):
                schema["parameters"] = {k: {"type": v.get("type", "string"), "description": v.get("description", "")[:80]}
                                         for k, v in params["properties"].items()}
            tool_schemas.append(schema)

        tools_json = json.dumps(tool_schemas, indent=2)
        tool_instruction = (
            "TOOL USE: To call a tool output EXACTLY this format and nothing else:\n"
            "<tool_call>\n"
            '{"name": "tool_name", "arguments": {"arg": "value"}}\n'
            "</tool_call>\n\n"
            f"Available tools:\n{tools_json}\n\n"
            "Rules: If you need a tool, output the <tool_call> block first and stop. "
            "Never describe what you are about to do — just output the tool call or the final answer."
        )

        # Inject tool instruction into system message
        new_messages = []
        system_injected = False
        for m in messages:
            if m.get("role") == "system" and not system_injected:
                new_messages.append({"role": "system", "content": m["content"] + "\n\n" + tool_instruction})
                system_injected = True
            else:
                new_messages.append(m)
        if not system_injected:
            new_messages.insert(0, {"role": "system", "content": tool_instruction})

        new_messages = _inject_no_think(new_messages)
        client = ollama.AsyncClient(host=self.base_url)
        async with _ollama_lock():
            resp = await client.chat(model=self.current_model, messages=new_messages, think=False)
        raw_text = resp.get("message", {}).get("content", "")
        thinking_field = resp.get("message", {}).get("thinking", "") or ""
        clean_text, reasoning_from_tags = parse_thinking(raw_text)
        reasoning = (thinking_field.strip() or reasoning_from_tags) or None

        # Parse <tool_call>...</tool_call> blocks
        tool_call_re = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
        matches = tool_call_re.findall(clean_text)
        if matches:
            parsed_calls = []
            for raw_call in matches:
                try:
                    call_data = json.loads(raw_call)
                    name = call_data.get("name", "")
                    args = call_data.get("arguments", call_data.get("parameters", {}))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    if name:
                        parsed_calls.append({"name": name, "arguments": args})
                except json.JSONDecodeError:
                    continue
            if parsed_calls:
                logger.info(f"🔧 Text-based tool call parsed: {[c['name'] for c in parsed_calls]}")
                return {
                    "tool_call": parsed_calls[0],
                    "tool_calls": parsed_calls,
                    "text": None,
                }

        # No tool call found — plain text answer
        result = {"tool_call": None, "tool_calls": [], "text": clean_text}
        if reasoning:
            result["reasoning"] = reasoning
        return result

    async def invoke_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        """
        Call Ollama with native tool calling (structured JSON output).

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            tools: List of Ollama tool schemas (OpenAI function calling format)

        Returns:
            Dict with keys:
              - "text": plain text response (if no tool was called)
              - "tool_call": {"name": str, "arguments": dict} if a tool was invoked
        """
        # Fast-path: skip native API for models known not to support it
        if tools and self.current_model in self._MODELS_WITHOUT_NATIVE_TOOLS:
            return await self._invoke_with_text_tool_calling(messages, tools)

        try:
            client = ollama.AsyncClient(host=self.base_url)
            # /no_think injected into last user message: official Qwen3 mechanism to
            # suppress chain-of-thought output while keeping full response quality.
            messages = _inject_no_think(messages)
            async with _ollama_lock():
                response = await client.chat(
                    model=self.current_model,
                    messages=messages,
                    tools=tools,
                    think=False,
                )
            msg = response.get("message", {})

            # Track tokens (Ollama provides prompt_eval_count / eval_count)
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            self.token_tracker.record(TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                model=self.current_model,
                provider="ollama",
                estimated_cost_usd=0.0,  # local model — free
            ))

            # Tool call path — collect ALL tool calls for parallel execution
            raw_calls = msg.get("tool_calls") or []
            if raw_calls:
                parsed: list[dict] = []
                for call in raw_calls:
                    fn = call.get("function", {})
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    parsed.append({"name": fn.get("name", ""), "arguments": args})

                return {
                    "tool_call": parsed[0],  # backward compat
                    "tool_calls": parsed,  # NEW: all tool calls
                    "text": None,
                }

            # Plain text path
            # Ollama places reasoning tokens in msg.thinking (separate from content)
            # when the model supports thinking. Just use content directly.
            raw_text = msg.get("content", "")
            thinking_field = msg.get("thinking", "") or ""
            # Also strip any <think> tags that leaked into content
            clean_text, reasoning_from_tags = parse_thinking(raw_text)
            reasoning = (thinking_field.strip() or reasoning_from_tags) or None
            result = {"tool_call": None, "tool_calls": [], "text": clean_text}
            if reasoning:
                result["reasoning"] = reasoning
                logger.info(f"💭 Reasoning captured ({len(reasoning)} chars)")
            return result

        except Exception as e:
            error_str = str(e)
            # Detect models that don't support native tool calling (Ollama returns 400)
            if tools and ("400" in error_str or "does not support tools" in error_str
                          or "tool" in error_str.lower()):
                logger.warning(f"Tool calling failed ({e}), switching to text-based tool calling")
                AdaptiveLLM._MODELS_WITHOUT_NATIVE_TOOLS.add(self.current_model)
                try:
                    return await self._invoke_with_text_tool_calling(messages, tools)
                except Exception as e2:
                    logger.error(f"Text-based tool calling failed: {e2}")
            else:
                logger.warning(f"Tool calling failed ({e}), falling back to plain chat")

            # Last resort: plain chat without tools
            try:
                client = ollama.AsyncClient(host=self.base_url)
                plain_msgs = []
                for m in messages:
                    role = m.get("role", "user")
                    plain_msgs.append({"role": role, "content": m.get("content", "")})
                plain_msgs = _inject_no_think(plain_msgs)
                async with _ollama_lock():
                    resp = await client.chat(model=self.current_model, messages=plain_msgs, think=False)
                raw_text = resp.get("message", {}).get("content", "")
                thinking_field = resp.get("message", {}).get("thinking", "") or ""
                clean_text, reasoning_from_tags = parse_thinking(raw_text)
                reasoning = (thinking_field.strip() or reasoning_from_tags) or None
                result = {"tool_call": None, "tool_calls": [], "text": clean_text}
                if reasoning:
                    result["reasoning"] = reasoning
                    logger.info(f"💭 Reasoning captured ({len(reasoning)} chars)")
                return result
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return {"tool_call": None, "tool_calls": [], "text": f"Error: {e}"}

    async def astream(self, messages: List[Dict]) -> AsyncIterator[str]:
        """
        Yield text tokens one-by-one from Ollama streaming API.

        DeepSeek models: <think>...</think> blocks are silently consumed
        and emitted as a single ``[REASONING]`` event at the end.

        Usage:
            async for token in llm.astream(messages):
                print(token, end="", flush=True)
        """
        try:
            client = ollama.AsyncClient(host=self.base_url)
            messages = _inject_no_think(messages)
            # Acquire Ollama lock for the entire streaming duration
            self._stream_lock_cm = _ollama_lock()
            await self._stream_lock_cm.__aenter__()
            try:
                stream = await client.chat(
                    model=self.current_model,
                    messages=messages,
                    stream=True,
                    think=False,
                )
            except Exception:
                await self._stream_lock_cm.__aexit__(None, None, None)
                raise

            # State machine for <think> block detection
            _buf = ""        # accumulates partial tag matches
            _inside = False  # currently inside <think>...</think>
            _reasoning = []  # collected reasoning lines
            _check_tags = "deepseek" in self.current_model.lower()

            async for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if not token:
                    continue

                if not _check_tags:
                    yield token
                    continue

                # Tag-aware streaming
                _buf += token
                while _buf:
                    if _inside:
                        end_idx = _buf.find("</think>")
                        if end_idx != -1:
                            _reasoning.append(_buf[:end_idx])
                            _buf = _buf[end_idx + 8:]  # skip </think>
                            _inside = False
                        else:
                            # Still inside thinking — buffer everything
                            _reasoning.append(_buf)
                            _buf = ""
                    else:
                        start_idx = _buf.find("<think>")
                        if start_idx != -1:
                            # Yield text before the tag
                            if start_idx > 0:
                                yield _buf[:start_idx]
                            _buf = _buf[start_idx + 7:]  # skip <think>
                            _inside = True
                        else:
                            # Check for partial tag at end of buffer
                            safe = True
                            for i in range(1, min(len("<think>"), len(_buf) + 1)):
                                if _buf.endswith("<think>"[:i]):
                                    # Might be start of a tag — hold back
                                    yield _buf[:-i]
                                    _buf = _buf[-i:]
                                    safe = False
                                    break
                            if safe:
                                yield _buf
                                _buf = ""

            # Flush remaining buffer
            if _buf:
                yield _buf

            # Emit reasoning summary if captured
            if _reasoning:
                reasoning_text = "".join(_reasoning).strip()
                if reasoning_text:
                    logger.info(f"💭 DeepSeek reasoning streamed ({len(reasoning_text)} chars)")
                    yield f"\n\n---\n💭 **Reasoning** ({len(reasoning_text)} chars captured)\n"

            # Release Ollama lock after streaming completes
            await self._stream_lock_cm.__aexit__(None, None, None)

        except Exception as e:
            # Release lock on error too
            if hasattr(self, '_stream_lock_cm'):
                try:
                    await self._stream_lock_cm.__aexit__(None, None, None)
                except Exception:
                    pass
            logger.error(f"Streaming failed: {e}")
            yield f"Error: {e}"


def get_llm(config):
    """Get LLM instance based on configuration"""
    try:
        # Auto-select model if enabled
        model_to_use = config.default_model

        if config.auto_select_model:
            from opensable.core.system_detector import auto_configure_system

            auto_config = auto_configure_system()
            recommended = auto_config["recommended_model"]

            # Verify the recommended model is actually available before using it
            try:
                client = ollama.Client(host=config.ollama_base_url)
                models = client.list()
                available = [
                    getattr(m, "model", None) or m.get("name") or m.get("model", "")
                    for m in models.get("models", [])
                ]
                if any(recommended in a or a in recommended for a in available):
                    model_to_use = recommended
                    logger.info(
                        f"Auto-selected model: {model_to_use} (tier: {auto_config['device_tier']})"
                    )
                else:
                    logger.warning(
                        f"Auto-selected model '{recommended}' not available locally. Using default: {model_to_use}"
                    )
            except Exception:
                logger.warning(f"Cannot verify model availability. Using default: {model_to_use}")

        # Return adaptive LLM that can switch models
        adaptive_llm = AdaptiveLLM(config, model_to_use)
        logger.info(f"Using adaptive LLM starting with: {model_to_use}")
        return adaptive_llm

    except Exception as e:
        logger.warning(f"Ollama not available: {e}")

        # Fallback to cloud APIs — try each configured provider in priority order
        _CLOUD_FALLBACK_ORDER = [
            ("openai", "openai_api_key"),
            ("anthropic", "anthropic_api_key"),
            ("gemini", "gemini_api_key"),
            ("deepseek", "deepseek_api_key"),
            ("groq", "groq_api_key"),
            ("mistral", "mistral_api_key"),
            ("together", "together_api_key"),
            ("xai", "xai_api_key"),
            ("cohere", "cohere_api_key"),
            ("kimi", "kimi_api_key"),
            ("qwen", "qwen_api_key"),
            ("openrouter", "openrouter_api_key"),
            ("openwebui", "openwebui_api_key"),
        ]
        for provider, key_attr in _CLOUD_FALLBACK_ORDER:
            if getattr(config, key_attr, None):
                logger.info(f"Falling back to {provider} with tool calling")
                return CloudLLM(provider=provider, config=config)

        raise Exception(
            "No LLM available. Install Ollama or set an API key env var: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, "
            "DEEPSEEK_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, "
            "TOGETHER_API_KEY, XAI_API_KEY, COHERE_API_KEY, "
            "KIMI_API_KEY, QWEN_API_KEY, OPENROUTER_API_KEY, "
            "OPENWEBUI_API_KEY + OPENWEBUI_API_URL"
        )


class CloudLLM:
    """Cloud LLM provider with full tool calling parity.

    Supported providers:
      OpenAI-compatible : openai, deepseek, groq, together, xai, mistral,
                          kimi, qwen, openrouter
      Native SDK        : anthropic, gemini, cohere

    Implements the same interface as AdaptiveLLM so the agent loop can use
    it transparently: invoke_with_tools(), ainvoke(), current_model, etc.
    """

    # Provider → (base_url | None, config key name, default model)
    _PROVIDERS = {
        # OpenAI-compatible providers (reuse openai SDK)
        "openai": (None, "openai_api_key", "gpt-4o-mini"),
        "deepseek": ("https://api.deepseek.com", "deepseek_api_key", "deepseek-chat"),
        "groq": (
            "https://api.groq.com/openai/v1",
            "groq_api_key",
            "llama-3.3-70b-versatile",
        ),
        "together": (
            "https://api.together.xyz/v1",
            "together_api_key",
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        ),
        "xai": ("https://api.x.ai/v1", "xai_api_key", "grok-3-mini-fast"),
        "mistral": (
            "https://api.mistral.ai/v1",
            "mistral_api_key",
            "mistral-small-latest",
        ),
        "kimi": (
            "https://api.moonshot.cn/v1",
            "kimi_api_key",
            "moonshot-v1-8k",
        ),
        "qwen": (
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen_api_key",
            "qwen-plus",
        ),
        "openrouter": (
            "https://openrouter.ai/api/v1",
            "openrouter_api_key",
            "openai/gpt-4o-mini",
        ),
        "openwebui": (
            None,  # user sets OPENWEBUI_API_URL in .env
            "openwebui_api_key",
            "llama3.2:latest",  # user sets OPENWEBUI_MODEL in .env
        ),
        # Native SDK providers
        "anthropic": (None, "anthropic_api_key", "claude-sonnet-4-20250514"),
        "gemini": (None, "gemini_api_key", "gemini-2.5-flash"),
        "cohere": (None, "cohere_api_key", "command-a-03-2025"),
    }

    def __init__(self, provider: str, config):
        if provider not in self._PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider}'. " f"Supported: {', '.join(self._PROVIDERS)}"
            )
        self.provider = provider
        self.config = config
        _, _, default_model = self._PROVIDERS[provider]
        self.current_model = default_model
        self.available_models = [self.current_model]
        self._client = None
        self.token_tracker = TokenTracker()

        # Open WebUI: user configures URL and model via .env
        if provider == "openwebui":
            custom_url = getattr(config, "openwebui_api_url", None)
            if not custom_url:
                raise ValueError(
                    "OPENWEBUI_API_URL is required for Open WebUI provider. "
                    "Set it in .env (e.g. https://your-server.com/api)"
                )
            # Ensure URL ends with OpenAI-compatible path
            self._openwebui_base_url = custom_url.rstrip("/")
            if not self._openwebui_base_url.endswith(("/v1", "/api")):
                self._openwebui_base_url += ""  # keep as-is, user knows their URL
            custom_model = getattr(config, "openwebui_model", None)
            if custom_model:
                self.current_model = custom_model
                self.available_models = [custom_model]

    def _get_api_key(self) -> str:
        """Retrieve the API key for the current provider from config."""
        _, key_attr, _ = self._PROVIDERS[self.provider]
        key = getattr(self.config, key_attr, None)
        if not key:
            raise ValueError(
                f"No API key for {self.provider}. " f"Set {key_attr.upper()} environment variable."
            )
        return key

    # ── OpenAI-compatible providers ──────────────────────────────────────

    async def _openai_invoke(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        """Works for openai, deepseek, groq, together, xai, mistral, openwebui."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("pip install openai  — required for OpenAI-compatible providers")

        base_url, _, _ = self._PROVIDERS[self.provider]
        # Open WebUI: URL comes from config, not hardcoded in _PROVIDERS
        if self.provider == "openwebui":
            base_url = getattr(self, "_openwebui_base_url", base_url)
        client = AsyncOpenAI(api_key=self._get_api_key(), base_url=base_url)

        kwargs: dict = {"model": self.current_model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        # Track token usage
        usage = getattr(resp, "usage", None)
        if usage:
            pt = getattr(usage, "prompt_tokens", 0)
            ct = getattr(usage, "completion_tokens", 0)
            self.token_tracker.record(TokenUsage(
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=pt + ct,
                model=self.current_model,
                provider=self.provider,
                estimated_cost_usd=TokenTracker.estimate_cost(self.current_model, pt, ct),
            ))

        if msg.tool_calls:
            parsed = []
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                parsed.append({"name": tc.function.name, "arguments": args})
            return {
                "tool_call": parsed[0],
                "tool_calls": parsed,
                "text": None,
            }

        # Check for DeepSeek reasoning — API may return reasoning_content or <think> tags
        raw_text = msg.content or ""
        reasoning = None

        # DeepSeek API returns reasoning_content as a separate field
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            reasoning = msg.reasoning_content
        else:
            raw_text, reasoning = parse_thinking(raw_text)

        result = {
            "tool_call": None,
            "tool_calls": [],
            "text": raw_text,
        }
        if reasoning:
            result["reasoning"] = reasoning
            logger.info(f"💭 DeepSeek reasoning captured ({len(reasoning)} chars)")
        return result

    # ── Anthropic ────────────────────────────────────────────────────────

    async def _anthropic_invoke(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("pip install anthropic  — required for Anthropic provider")

        client = AsyncAnthropic(api_key=self._get_api_key())

        # Convert OpenAI-style tool schemas → Anthropic format
        anthropic_tools = []
        for t in tools:
            fn = t.get("function", t)
            anthropic_tools.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )

        # Separate system message from conversation
        system_text = ""
        conv_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            else:
                conv_msgs.append({"role": m["role"], "content": m["content"]})

        kwargs: dict = {
            "model": self.current_model,
            "max_tokens": 4096,
            "messages": conv_msgs or [{"role": "user", "content": "Hello"}],
        }
        if system_text.strip():
            kwargs["system"] = system_text.strip()
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        resp = await client.messages.create(**kwargs)

        text_parts = []
        parsed_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                parsed_calls.append({"name": block.name, "arguments": block.input or {}})

        if parsed_calls:
            return {
                "tool_call": parsed_calls[0],
                "tool_calls": parsed_calls,
                "text": None,
            }
        return {
            "tool_call": None,
            "tool_calls": [],
            "text": "\n".join(text_parts),
        }

    # ── Google Gemini ────────────────────────────────────────────────────

    async def _gemini_invoke(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("pip install google-genai  — required for Gemini provider")

        client = genai.Client(api_key=self._get_api_key())

        # Build Gemini function declarations from OpenAI schemas
        fn_decls = []
        for t in tools:
            fn = t.get("function", t)
            fn_decls.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )

        gemini_tools = [types.Tool(function_declarations=fn_decls)] if fn_decls else []
        config = types.GenerateContentConfig(tools=gemini_tools or None)

        # Build Gemini contents from messages
        system_text = ""
        contents = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            elif m["role"] == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=m["content"])],
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=m["content"])],
                    )
                )

        if system_text.strip():
            config.system_instruction = system_text.strip()

        if not contents:
            contents = [types.Content(role="user", parts=[types.Part(text="Hello")])]

        resp = await client.aio.models.generate_content(
            model=self.current_model,
            contents=contents,
            config=config,
        )

        # Parse function calls
        parsed_calls = []
        text_parts = []
        if resp.candidates:
            for part in resp.candidates[0].content.parts:
                if part.function_call:
                    parsed_calls.append(
                        {
                            "name": part.function_call.name,
                            "arguments": dict(part.function_call.args or {}),
                        }
                    )
                elif part.text:
                    text_parts.append(part.text)

        if parsed_calls:
            return {
                "tool_call": parsed_calls[0],
                "tool_calls": parsed_calls,
                "text": None,
            }
        return {
            "tool_call": None,
            "tool_calls": [],
            "text": "\n".join(text_parts),
        }

    # ── Cohere ───────────────────────────────────────────────────────────

    async def _cohere_invoke(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        try:
            import cohere
        except ImportError:
            raise ImportError("pip install cohere  — required for Cohere provider")

        co = cohere.AsyncClientV2(self._get_api_key())

        # Build Cohere-format tool list (same as OpenAI schema)
        cohere_tools = []
        for t in tools:
            fn = t.get("function", t)
            cohere_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "parameters": fn.get(
                            "parameters",
                            {"type": "object", "properties": {}},
                        ),
                    },
                }
            )

        # Cohere v2 uses the same message format
        cohere_msgs = []
        for m in messages:
            cohere_msgs.append({"role": m["role"], "content": m["content"]})

        kwargs: dict = {
            "model": self.current_model,
            "messages": cohere_msgs,
        }
        if cohere_tools:
            kwargs["tools"] = cohere_tools

        resp = await co.chat(**kwargs)

        parsed_calls = []
        if resp.message.tool_calls:
            for tc in resp.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                parsed_calls.append({"name": tc.function.name, "arguments": args})

        if parsed_calls:
            return {
                "tool_call": parsed_calls[0],
                "tool_calls": parsed_calls,
                "text": None,
            }

        text = ""
        if resp.message.content:
            text = resp.message.content[0].text if resp.message.content else ""
        return {"tool_call": None, "tool_calls": [], "text": text}

    # ── Public interface (same as AdaptiveLLM) ───────────────────────────

    # Map providers to their invoke method
    _OPENAI_COMPAT = {
        "openai",
        "deepseek",
        "groq",
        "together",
        "xai",
        "mistral",
        "kimi",
        "qwen",
        "openrouter",
        "openwebui",
    }

    async def invoke_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
        """Call cloud LLM with native tool calling."""
        try:
            if self.provider in self._OPENAI_COMPAT:
                return await self._openai_invoke(messages, tools)
            elif self.provider == "anthropic":
                return await self._anthropic_invoke(messages, tools)
            elif self.provider == "gemini":
                return await self._gemini_invoke(messages, tools)
            elif self.provider == "cohere":
                return await self._cohere_invoke(messages, tools)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except ImportError:
            raise
        except Exception as e:
            logger.error(f"Cloud LLM ({self.provider}) failed: {e}")
            return {"tool_call": None, "tool_calls": [], "text": f"Error: {e}"}

    async def ainvoke(self, messages):
        """Plain text invoke (LangChain compat)."""
        result = await self.invoke_with_tools(
            [
                {
                    "role": m.type if hasattr(m, "type") else "user",
                    "content": m.content,
                }
                for m in messages
            ],
            [],
        )
        from types import SimpleNamespace

        return SimpleNamespace(content=result.get("text", ""))

    def invoke(self, messages):
        """Sync invoke — uses asyncio.run for simple scripts."""
        import asyncio

        return asyncio.run(self.ainvoke(messages))

    async def auto_switch_model(self, task_type: str) -> bool:
        """Cloud models don't auto-switch (always use the configured one)."""
        return False

    async def astream(self, messages: List[Dict]) -> AsyncIterator[str]:
        """
        Yield text tokens from cloud LLM streaming.

        DeepSeek API: reasoning_content is captured from stream deltas;
        <think> tags in content are also handled as fallback.

        Supports OpenAI-compatible providers and Anthropic.
        """
        try:
            if self.provider in self._OPENAI_COMPAT:
                from openai import AsyncOpenAI
                base_url, _, _ = self._PROVIDERS[self.provider]
                # Open WebUI: URL comes from config
                if self.provider == "openwebui":
                    base_url = getattr(self, "_openwebui_base_url", base_url)
                client = AsyncOpenAI(api_key=self._get_api_key(), base_url=base_url)
                stream = await client.chat.completions.create(
                    model=self.current_model,
                    messages=messages,
                    stream=True,
                )

                _is_deepseek = self.provider == "deepseek" or "deepseek" in self.current_model.lower()
                _reasoning_parts: list[str] = []
                _buf = ""
                _inside_think = False

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    # DeepSeek API: reasoning_content comes as a separate field
                    rc = getattr(delta, "reasoning_content", None)
                    if rc:
                        _reasoning_parts.append(rc)
                        continue

                    if not delta.content:
                        continue

                    if not _is_deepseek:
                        yield delta.content
                        continue

                    # Fallback: parse <think> tags from content stream
                    _buf += delta.content
                    while _buf:
                        if _inside_think:
                            end_idx = _buf.find("</think>")
                            if end_idx != -1:
                                _reasoning_parts.append(_buf[:end_idx])
                                _buf = _buf[end_idx + 8:]
                                _inside_think = False
                            else:
                                _reasoning_parts.append(_buf)
                                _buf = ""
                        else:
                            start_idx = _buf.find("<think>")
                            if start_idx != -1:
                                if start_idx > 0:
                                    yield _buf[:start_idx]
                                _buf = _buf[start_idx + 7:]
                                _inside_think = True
                            else:
                                safe = True
                                for i in range(1, min(len("<think>"), len(_buf) + 1)):
                                    if _buf.endswith("<think>"[:i]):
                                        yield _buf[:-i]
                                        _buf = _buf[-i:]
                                        safe = False
                                        break
                                if safe:
                                    yield _buf
                                    _buf = ""

                # Flush
                if _buf:
                    yield _buf
                if _reasoning_parts:
                    reasoning_text = "".join(_reasoning_parts).strip()
                    if reasoning_text:
                        logger.info(f"💭 DeepSeek reasoning streamed ({len(reasoning_text)} chars)")
                        yield f"\n\n---\n💭 **Reasoning** ({len(reasoning_text)} chars captured)\n"

            elif self.provider == "anthropic":
                from anthropic import AsyncAnthropic
                client = AsyncAnthropic(api_key=self._get_api_key())
                system_text = ""
                conv_msgs = []
                for m in messages:
                    if m["role"] == "system":
                        system_text += m["content"] + "\n"
                    else:
                        conv_msgs.append({"role": m["role"], "content": m["content"]})
                kwargs: dict = {
                    "model": self.current_model,
                    "max_tokens": 4096,
                    "messages": conv_msgs or [{"role": "user", "content": "Hello"}],
                }
                if system_text.strip():
                    kwargs["system"] = system_text.strip()
                async with client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        yield text
            else:
                # Fallback: non-streaming invoke
                result = await self.invoke_with_tools(messages, [])
                yield result.get("text", "")
        except Exception as e:
            logger.error(f"Cloud streaming failed ({self.provider}): {e}")
            yield f"Error: {e}"


async def check_ollama_models(base_url: str = "http://localhost:11434") -> list:
    """Check which models are available in Ollama"""
    try:
        client = ollama.Client(host=base_url)
        models = client.list()
        return [
            getattr(m, "model", None) or m.get("name") or m.get("model", "")
            for m in models.get("models", [])
        ]
    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
        return []


async def pull_ollama_model(model_name: str, base_url: str = "http://localhost:11434"):
    """Pull a model from Ollama"""
    try:
        client = ollama.Client(host=base_url)
        logger.info(f"Pulling model {model_name}...")
        client.pull(model_name)
        logger.info(f"Model {model_name} pulled successfully")
    except Exception as e:
        logger.error(f"Failed to pull model {model_name}: {e}")
        raise
