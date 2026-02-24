"""
LLM integration for Open-Sable - Ollama with native tool calling
Dynamic model switching based on task requirements.
Supports: Ollama (local), OpenAI, Anthropic, DeepSeek, Groq, Together AI,
          xAI (Grok), Mistral, Google Gemini, Cohere, Kimi (Moonshot),
          Qwen (DashScope), OpenRouter — all with full tool calling.
"""

import logging
import json
from typing import Dict, List, Any, AsyncIterator
import ollama

logger = logging.getLogger(__name__)


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

    def __init__(self, config, initial_model: str):
        self.config = config
        self.current_model = initial_model
        self.base_url = config.ollama_base_url
        self.available_models = []
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
        resp = await client.chat(model=self.current_model, messages=plain_msgs)
        from types import SimpleNamespace
        return SimpleNamespace(content=resp.get("message", {}).get("content", ""))

    def invoke(self, messages):
        """Sync invoke"""
        import asyncio
        return asyncio.run(self.ainvoke(messages))

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
        try:
            client = ollama.AsyncClient(host=self.base_url)
            response = await client.chat(
                model=self.current_model,
                messages=messages,
                tools=tools,
            )
            msg = response.get("message", {})

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
            return {"tool_call": None, "tool_calls": [], "text": msg.get("content", "")}

        except Exception as e:
            logger.warning(f"Tool calling failed ({e}), falling back to plain chat")
            # Fallback: use ollama chat without tools
            try:
                client = ollama.AsyncClient(host=self.base_url)
                plain_msgs = []
                for m in messages:
                    role = m.get("role", "user")
                    plain_msgs.append({"role": role, "content": m.get("content", "")})
                resp = await client.chat(model=self.current_model, messages=plain_msgs)
                return {"tool_call": None, "tool_calls": [], "text": resp.get("message", {}).get("content", "")}
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return {"tool_call": None, "tool_calls": [], "text": f"Error: {e}"}

    async def astream(self, messages: List[Dict]) -> AsyncIterator[str]:
        """
        Yield text tokens one-by-one from Ollama streaming API.

        Usage:
            async for token in llm.astream(messages):
                print(token, end="", flush=True)
        """
        try:
            client = ollama.AsyncClient(host=self.base_url)
            stream = await client.chat(
                model=self.current_model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
        except Exception as e:
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

        return {
            "tool_call": None,
            "tool_calls": [],
            "text": msg.content or "",
        }

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

        Supports OpenAI-compatible providers and Anthropic.
        """
        try:
            if self.provider in self._OPENAI_COMPAT:
                from openai import AsyncOpenAI
                base_url, _, _ = self._PROVIDERS[self.provider]
                client = AsyncOpenAI(api_key=self._get_api_key(), base_url=base_url)
                stream = await client.chat.completions.create(
                    model=self.current_model,
                    messages=messages,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield delta.content
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
