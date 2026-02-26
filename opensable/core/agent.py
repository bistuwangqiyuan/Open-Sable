"""
Core Open-Sable Agent — The brain of the operation

v2: Multi-step planning, parallel tool calls, streaming progress,
    advanced memory retrieval, progress callbacks.
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, date
from dataclasses import dataclass, field

from .llm import get_llm
from .memory import MemoryManager
from .tools import ToolRegistry
from .config import OpenSableConfig
from .guardrails import GuardrailsEngine, GuardrailAction, ValidationResult
from .hitl import ApprovalGate, RiskLevel, ApprovalDecision, HumanApprovalRequired
from .checkpointing import Checkpoint, CheckpointStore
from .structured_output import StructuredOutputParser

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 120

ProgressCallback = Optional[Callable[[str], Awaitable[None]]]


@dataclass
class Plan:
    """A structured plan for multi-step task execution."""

    goal: str
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    results: Dict[int, str] = field(default_factory=dict)
    is_complete: bool = False

    def next_step(self) -> Optional[str]:
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def advance(self, result: str):
        self.results[self.current_step] = result
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.is_complete = True

    def mark_step_failed(self, error: str):
        """Record that the current step failed (for replanning)."""
        self.results[self.current_step] = f"FAILED: {error}"

    def replace_remaining_steps(self, new_steps: List[str]):
        """Replace all steps from current_step onward with a revised plan."""
        self.steps = self.steps[: self.current_step] + new_steps
        self.is_complete = False

    def summary(self) -> str:
        lines = []
        for i, s in enumerate(self.steps):
            if i < self.current_step:
                lines.append(f"  ✅ {s}")
            elif i == self.current_step:
                lines.append(f"  ▶️  {s}")
            else:
                lines.append(f"  ⬜ {s}")
        return "\n".join(lines)


class AgentState(dict):
    """Simple state dict for the agent loop (no external graph dependency)."""
    pass


class SableAgent:
    """Main autonomous agent with planning + parallel tools."""

    def __init__(self, config: OpenSableConfig):
        self.config = config
        self.llm = None
        self.memory = None
        self.tools = None
        self.heartbeat_task = None
        self._progress_callback: ProgressCallback = None
        self._telegram_notify = None

        # Production primitives
        self.guardrails = GuardrailsEngine.default()
        self.approval_gate = ApprovalGate(auto_approve_below=RiskLevel.HIGH)
        self.checkpoint_store = CheckpointStore("data/checkpoints")
        self.handoff_router = None  # lazily initialised in _init_handoffs

        # Skills Marketplace: auto-approve mode lowers install risk to MEDIUM
        if getattr(config, "skill_install_auto_approve", False):
            self.approval_gate.risk_map["marketplace_install"] = RiskLevel.MEDIUM
            logger.info("🏪 Skills Marketplace auto-approve mode ENABLED")

        # Monitor event bus — subscribers receive (event_name, data_dict)
        self._monitor_subscribers: list = []
        self._monitor_stats = {"messages": 0, "tool_calls": 0, "errors": 0}

        # Agentic AI components
        self.advanced_memory = None
        self.goals = None
        self.plugins = None
        self.autonomous = None
        self.multi_agent = None
        self.tool_synthesizer = None
        self.metacognition = None
        self.world_model = None
        self.tracer = None

    async def initialize(self):
        """Initialize agent components"""
        logger.info("Initializing Open-Sable agent...")
        self.llm = get_llm(self.config)
        self.memory = MemoryManager(self.config)
        await self.memory.initialize()
        self.tools = ToolRegistry(self.config)
        await self.tools.initialize()
        await self._initialize_agi_systems()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Agent initialized successfully")

    async def _initialize_agi_systems(self):
        """Initialize advanced Agentic AI components"""
        try:
            from .advanced_memory import AdvancedMemorySystem

            self.advanced_memory = AdvancedMemorySystem(
                storage_path=getattr(self.config, "vector_db_path", None)
                and Path(str(self.config.vector_db_path)).parent / "advanced_memory.json"
            )
            await self.advanced_memory.initialize()
            logger.info("✅ Advanced memory system initialized")
        except Exception as e:
            logger.warning(f"Advanced memory init failed: {e}")
            self.advanced_memory = None

        for name, init_fn in [
            ("Goal system", self._init_goals),
            ("Plugin system", self._init_plugins),
            ("Tool synthesis", self._init_tool_synthesis),
            ("Metacognition", self._init_metacognition),
            ("World model", self._init_world_model),
            ("Multi-agent", self._init_multi_agent),
            ("Emotional intelligence", self._init_emotional_intelligence),
            ("Distributed tracing", self._init_tracing),
            ("Handoff router", self._init_handoffs),
        ]:
            try:
                await init_fn()
                logger.info(f"✅ {name} initialized")
            except Exception as e:
                logger.warning(f"{name} init failed: {e}")

    async def _init_goals(self):
        from .goal_system import GoalManager

        self.goals = GoalManager()
        await self.goals.initialize()

    async def _init_plugins(self):
        from .plugins import PluginManager

        self.plugins = PluginManager(self.config)
        await self.plugins.load_all_plugins()

    async def _init_tool_synthesis(self):
        from .tool_synthesis import ToolSynthesizer

        self.tool_synthesizer = ToolSynthesizer()

    async def _init_metacognition(self):
        from .metacognition import MetacognitiveSystem

        self.metacognition = MetacognitiveSystem(self.config)
        await self.metacognition.initialize()

    async def _init_world_model(self):
        from .world_model import WorldModel

        self.world_model = WorldModel()
        await self.world_model.initialize()

    async def _init_multi_agent(self):
        from .multi_agent import AgentPool

        self.multi_agent = AgentPool(self.config)
        await self.multi_agent.initialize()

    async def _init_emotional_intelligence(self):
        from .emotional_intelligence import EmotionalIntelligence

        self.emotional_intelligence = EmotionalIntelligence()

    async def _init_tracing(self):
        from .observability import DistributedTracer

        self.tracer = DistributedTracer(service_name="opensable-agent")

    async def _init_handoffs(self):
        from .handoffs import HandoffRouter, default_handoffs

        self.handoff_router = HandoffRouter()
        for h in default_handoffs():
            self.handoff_router.register(h)

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    async def _notify_progress(self, message: str):
        """Send a progress update to the current interface."""
        if self._progress_callback:
            try:
                await self._progress_callback(message)
            except Exception as e:
                logger.debug(f"Progress callback failed: {e}")

    # ------------------------------------------------------------------
    # Monitor event bus
    # ------------------------------------------------------------------

    def monitor_subscribe(self, callback):
        """Subscribe to agent monitor events. callback(event: str, data: dict)"""
        self._monitor_subscribers.append(callback)

    def monitor_unsubscribe(self, callback):
        """Unsubscribe from monitor events."""
        self._monitor_subscribers = [c for c in self._monitor_subscribers if c is not callback]

    async def _emit_monitor(self, event: str, data: dict = None):
        """Emit a monitor event to all subscribers."""
        data = data or {}
        for cb in self._monitor_subscribers:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event, data)
                else:
                    cb(event, data)
            except Exception:
                pass

    def get_monitor_snapshot(self) -> dict:
        """Return a full snapshot of agent state for the monitor UI."""
        tools = []
        if self.tools:
            tools = self.tools.list_tools()

        components = []
        for name, attr in [
            ("LLM", self.llm), ("Memory", self.memory), ("Tools", self.tools),
            ("Advanced Memory", self.advanced_memory), ("Goals", self.goals),
            ("Plugins", self.plugins), ("Multi-Agent", self.multi_agent),
            ("Metacognition", self.metacognition), ("World Model", self.world_model),
            ("Tool Synthesis", self.tool_synthesizer),
            ("Emotional Intel", getattr(self, "emotional_intelligence", None)),
            ("Tracing", self.tracer), ("Handoffs", self.handoff_router),
        ]:
            components.append({"name": name, "status": "ok" if attr else "off"})

        goals = []
        if self.goals:
            try:
                for g in self.goals.get_active_goals():
                    goals.append({"name": getattr(g, "description", str(g)), "progress": getattr(g, "progress", 0)})
            except Exception:
                pass

        model = "unknown"
        if self.llm and hasattr(self.llm, "current_model"):
            model = self.llm.current_model

        return {
            "type": "monitor.snapshot",
            "tools": tools,
            "components": components,
            "goals": goals,
            "model": model,
            "stats": self._monitor_stats,
            "interfaces": [],  # filled by gateway
        }

    # ------------------------------------------------------------------
    # Graph-free execution
    # ------------------------------------------------------------------

    async def _run_loop(self, state: AgentState) -> AgentState:
        """Execute the agentic loop directly (no LangGraph dependency)."""
        return await self._agentic_loop(state)

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    _COMPLEX_INDICATORS = re.compile(
        r"\b(and then|after that|first .+ then|step by step|"
        r"create .+ and .+ and|build .+ with .+ and|"
        r"research .+ and write|find .+ then .+ then|"
        r"compare .+ and|analyze .+ and summarize|"
        r"y luego|después|primero .+ luego|paso a paso)\b",
        re.IGNORECASE,
    )

    def _needs_planning(self, task: str) -> bool:
        if len(task) > 200:
            return True
        if self._COMPLEX_INDICATORS.search(task):
            return True
        action_verbs = re.findall(
            r"\b(search|find|create|write|read|edit|execute|run|build|"
            r"analyze|compare|download|scrape|send|generate|install|deploy|"
            r"busca|crea|escribe|lee|ejecuta|compara|descarga)\b",
            task.lower(),
        )
        return len(set(action_verbs)) >= 3

    async def _create_plan(self, task: str, system_prompt: str) -> Optional[Plan]:
        planning_prompt = (
            "You are a task planner. Break down the following task into clear, "
            "sequential steps. Each step should be a single actionable item.\n\n"
            "Rules:\n"
            "- Output ONLY a numbered list (1. 2. 3. etc.)\n"
            "- Each step should be one specific action\n"
            "- Keep it to 2-6 steps maximum\n"
            "- Be specific about what tool or action each step needs\n"
            "- The last step should always be synthesizing/presenting results\n\n"
            f"Task: {task}"
        )
        try:
            response = await asyncio.wait_for(
                self.llm.invoke_with_tools(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": planning_prompt},
                    ],
                    [],
                ),
                timeout=_LLM_TIMEOUT,
            )
            text = response.get("text", "")
            steps = []
            for line in text.split("\n"):
                match = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
                if match:
                    steps.append(match.group(1).strip())
            if steps and len(steps) >= 2:
                logger.info(f"📋 Created plan with {len(steps)} steps")
                return Plan(goal=task, steps=steps)
        except Exception as e:
            logger.warning(f"Planning failed: {e}")
        return None

    async def _replan(self, plan: Plan, failure_reason: str, system_prompt: str) -> bool:
        """Regenerate remaining plan steps after a failure. Returns True if replanned."""
        completed = "\n".join(f"  ✅ {plan.steps[i]}" for i in range(plan.current_step))
        failed_step = plan.steps[plan.current_step] if plan.next_step() else "unknown"
        prompt = (
            "A multi-step plan encountered a failure. Revise the REMAINING steps.\n\n"
            f"Original goal: {plan.goal}\n\n"
            f"Completed steps:\n{completed}\n\n"
            f"Failed step: {failed_step}\n"
            f"Failure reason: {failure_reason}\n\n"
            "Rules:\n"
            "- Output ONLY a numbered list of revised remaining steps\n"
            "- Try a different approach for the failed step\n"
            "- Keep it to 1-4 steps\n"
            "- The last step should be synthesizing results"
        )
        try:
            response = await asyncio.wait_for(
                self.llm.invoke_with_tools(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    [],
                ),
                timeout=_LLM_TIMEOUT,
            )
            text = response.get("text", "")
            new_steps = []
            for line in text.split("\n"):
                match = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
                if match:
                    new_steps.append(match.group(1).strip())
            if new_steps:
                plan.replace_remaining_steps(new_steps)
                logger.info(f"🔄 Replanned: {len(new_steps)} new steps")
                return True
        except Exception as e:
            logger.warning(f"Replanning failed: {e}")
        return False

    # ------------------------------------------------------------------
    # Advanced memory retrieval
    # ------------------------------------------------------------------

    async def _get_memory_context(self, user_id: str, task: str) -> str:
        parts = []

        # Basic ChromaDB
        memories = await self.memory.recall(user_id, task)
        if memories:
            basic = "\n".join([m["content"] for m in memories[:3]])
            parts.append(f"[Recent context]\n{basic}")

        # Advanced memory
        if self.advanced_memory:
            try:
                from .advanced_memory import MemoryType

                episodic = await self.advanced_memory.retrieve_memories(
                    query=task, memory_type=MemoryType.EPISODIC, limit=3
                )
                if episodic:
                    ep_text = "\n".join(f"- {getattr(m, 'content', str(m))}" for m in episodic[:3])
                    parts.append(f"[Past experiences]\n{ep_text}")

                semantic = await self.advanced_memory.retrieve_memories(
                    query=task, memory_type=MemoryType.SEMANTIC, limit=3
                )
                if semantic:
                    sem_text = "\n".join(f"- {getattr(m, 'content', str(m))}" for m in semantic[:3])
                    parts.append(f"[Known facts]\n{sem_text}")
            except Exception as e:
                logger.debug(f"Advanced memory retrieval failed: {e}")

        # User preferences
        try:
            prefs = await self.memory.get_user_preferences(user_id)
            if prefs:
                pref_str = ", ".join(f"{k}={v}" for k, v in list(prefs.items())[:5])
                parts.append(f"[User preferences] {pref_str}")
        except Exception:
            pass

        return "\n\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # Tool execution with progress
    # ------------------------------------------------------------------

    _TOOL_EMOJIS = {
        "browser_search": "🔍",
        "browser_scrape": "🌐",
        "browser_snapshot": "📸",
        "browser_action": "🖱️",
        "execute_command": "⚡",
        "read_file": "📖",
        "write_file": "📝",
        "edit_file": "✏️",
        "list_directory": "📂",
        "delete_file": "🗑️",
        "move_file": "📦",
        "search_files": "🔎",
        "system_info": "💻",
        "weather": "🌤️",
        "calendar": "📅",
        "execute_code": "⚙️",
        "vector_search": "🧠",
        "create_skill": "🛠️",
        "generate_image": "🎨",
        "analyze_image": "👁️",
        "desktop_screenshot": "📷",
        # Vision / autonomous computer-use
        "screen_analyze": "🔭",
        "screen_find": "🎯",
        "screen_click_on": "🖱️",
        "open_app": "🚀",
        "window_list": "🪟",
        "window_focus": "🪟",
        # Trading
        "trading_portfolio": "💼",
        "trading_price": "📊",
        "trading_analyze": "📈",
        "trading_place_trade": "💰",
        "trading_cancel_order": "🚫",
        "trading_history": "📜",
        "trading_signals": "📡",
        "trading_start_scan": "🔄",
        "trading_stop_scan": "⏹️",
        "trading_risk_status": "🛡️",
        # Skills Marketplace
        "marketplace_search": "🏪",
        "marketplace_info": "📋",
        "marketplace_install": "📥",
        "marketplace_review": "⭐",
    }

    _TOOL_LABELS = {
        "browser_search": "Searching the web",
        "browser_scrape": "Scraping webpage",
        "browser_snapshot": "Taking page snapshot",
        "browser_action": "Interacting with page",
        "execute_command": "Running command",
        "read_file": "Reading file",
        "write_file": "Writing file",
        "edit_file": "Editing file",
        "list_directory": "Listing directory",
        "execute_code": "Running code",
        "vector_search": "Searching knowledge base",
        "weather": "Checking weather",
        "calendar": "Checking calendar",
        "create_skill": "Creating skill",
        "generate_image": "Generating image",
        "analyze_image": "Analyzing image",
        "desktop_screenshot": "Taking screenshot",
        # Vision / autonomous computer-use
        "screen_analyze": "Analyzing screen with vision AI",
        "screen_find": "Finding element on screen",
        "screen_click_on": "Clicking element on screen",
        "open_app": "Opening application",
        "window_list": "Listing windows",
        "window_focus": "Focusing window",
        # Trading
        "trading_portfolio": "Checking portfolio",
        "trading_price": "Fetching live price",
        "trading_analyze": "Analyzing market",
        "trading_place_trade": "Placing trade",
        "trading_cancel_order": "Cancelling order",
        "trading_history": "Loading trade history",
        "trading_signals": "Checking signals",
        "trading_start_scan": "Starting market scan",
        "trading_stop_scan": "Stopping market scan",
        "trading_risk_status": "Checking risk status",
        # Skills Marketplace
        "marketplace_search": "Searching Skills Marketplace",
        "marketplace_info": "Getting skill details",
        "marketplace_install": "Installing skill from marketplace",
        "marketplace_review": "Reviewing skill",
    }

    async def _execute_tool(self, name: str, arguments: dict, user_id: str = "default") -> str:
        emoji = self._TOOL_EMOJIS.get(name, "🔧")
        label = self._TOOL_LABELS.get(name, name.replace("_", " ").title())

        # ── HITL: approval gate (skip for benchmark users) ──
        if not user_id.startswith("benchmark_"):
            try:
                decision = await self.approval_gate.request_approval(
                    action=name,
                    description=f"{label}: {arguments}",
                    user_id=user_id,
                )
                if not decision.approved:
                    return f"**{name}:** ⛔ Blocked by approval gate — {decision.reason}"
            except HumanApprovalRequired as e:
                # No handler configured — for HIGH/CRITICAL actions,
                # inform the user that approval is needed.
                if name == "marketplace_install":
                    skill_id = arguments.get("skill_id", "unknown")
                    return (
                        f"**{name}:** ⏳ **User approval required**\n\n"
                        f"I want to install skill **`{skill_id}`** from the "
                        f"SableCore Skills Marketplace.\n\n"
                        f"To approve, please reply with something like:\n"
                        f"  • \"yes, install it\"\n"
                        f"  • \"approve install {skill_id}\"\n\n"
                        f"To enable auto-install mode, set `SKILL_INSTALL_AUTO_APPROVE=true` "
                        f"in your environment or config."
                    )
                # Other tools with no handler — default to allow (original behavior)
                pass

        await self._notify_progress(f"{emoji} {label}...")
        await self._emit_monitor("tool.start", {"name": name, "args": arguments})
        _t0 = time.time()
        try:
            result = await asyncio.wait_for(
                self.tools.execute_schema_tool(name, arguments, user_id=user_id),
                timeout=_LLM_TIMEOUT,
            )
            _dur = int((time.time() - _t0) * 1000)
            self._monitor_stats["tool_calls"] += 1
            await self._emit_monitor("tool.done", {"name": name, "success": True, "result": str(result)[:200], "duration_ms": _dur})
            return f"**{name}:** {result}"
        except asyncio.TimeoutError:
            logger.error(f"Tool {name} timed out")
            self._monitor_stats["errors"] += 1
            await self._emit_monitor("tool.done", {"name": name, "success": False, "result": "Timed out", "duration_ms": int((time.time() - _t0) * 1000)})
            return f"**{name}:** ❌ Timed out"
        except Exception as e:
            self._monitor_stats["errors"] += 1
            await self._emit_monitor("tool.done", {"name": name, "success": False, "result": str(e)[:200], "duration_ms": int((time.time() - _t0) * 1000)})
            return f"**{name}:** ❌ {e}"

    # X-related tool names that must NEVER run concurrently
    _X_TOOLS = frozenset({
        "x_post_tweet", "x_post_thread", "x_search", "x_like", "x_retweet",
        "x_reply", "x_follow", "x_get_user", "x_get_trends", "x_send_dm",
        "x_delete_tweet", "x_get_user_tweets",
    })

    async def _execute_tools_parallel(
        self, tool_calls: List[dict], user_id: str = "default"
    ) -> List[str]:
        if len(tool_calls) == 1:
            return [
                await self._execute_tool(
                    tool_calls[0]["name"], tool_calls[0]["arguments"], user_id=user_id
                )
            ]

        names = [tc["name"] for tc in tool_calls]

        # Check if ANY tool is X-related — if so, run ALL sequentially.
        # A real human only does one thing at a time on X.
        has_x_tool = any(tc["name"] in self._X_TOOLS for tc in tool_calls)

        if has_x_tool:
            logger.info(f"🔒 X tool(s) detected in batch {names} — executing ALL sequentially")
            results = []
            for tc in tool_calls:
                r = await self._execute_tool(tc["name"], tc["arguments"], user_id=user_id)
                results.append(r)
            return results

        # Non-X tools can still run in parallel
        emojis = " ".join(self._TOOL_EMOJIS.get(n, "🔧") for n in names)
        await self._notify_progress(f"{emojis} Running {len(tool_calls)} tools in parallel...")

        tasks = [
            self._execute_tool(tc["name"], tc["arguments"], user_id=user_id) for tc in tool_calls
        ]
        return list(await asyncio.gather(*tasks))

    # ──────────────────────────────────────────────
    #  AGENTIC LOOP v2
    # ──────────────────────────────────────────────

    async def _agentic_loop(self, state: AgentState) -> AgentState:
        task = state["task"]
        user_id = state["user_id"]

        # Tracing
        trace_id = span = None
        if self.tracer:
            trace_id = self.tracer.create_trace()
            span = self.tracer.start_span(
                "agentic_loop",
                trace_id,
                attributes={"user_id": user_id, "task_length": len(task)},
            )

        # ── Guardrails: validate input ──
        input_check: ValidationResult = self.guardrails.validate_input(task)
        if not input_check.passed:
            blocked = [r for r in input_check.results if r.action == GuardrailAction.BLOCK]
            if blocked:
                state["messages"].append({
                    "role": "final_response",
                    "content": blocked[0].message,
                    "timestamp": datetime.now().isoformat(),
                })
                return state
            # Sanitised or warned — use the (possibly modified) text
            for r in input_check.results:
                if r.action == GuardrailAction.SANITIZE and r.sanitized:
                    task = r.sanitized

        # ── Checkpointing: create ──
        checkpoint = Checkpoint(
            user_id=user_id,
            original_message=task,
        )

        # Memory context (advanced)
        await self._notify_progress("🧠 Recalling context...")
        memory_ctx = await self._get_memory_context(user_id, task)

        today = date.today().strftime("%B %d, %Y")

        history_for_ollama = []
        for m in state.get("messages", []):
            role = m.get("role", "")
            if role in ("user", "assistant"):
                history_for_ollama.append({"role": role, "content": m.get("content", "")})

        # Build social media instructions if any social skill is available
        social_instructions = ""
        if self.tools and any([
            getattr(self.tools, 'instagram_skill', None),
            getattr(self.tools, 'facebook_skill', None),
            getattr(self.tools, 'linkedin_skill', None),
            getattr(self.tools, 'tiktok_skill', None),
            getattr(self.tools, 'youtube_skill', None),
        ]):
            parts = ["\n\nSOCIAL MEDIA TOOLS AVAILABLE:"]
            if getattr(self.tools, 'instagram_skill', None):
                parts.append("- Instagram (ig_*): upload photos/reels/stories, search users/hashtags, like, comment, follow, DM")
            if getattr(self.tools, 'facebook_skill', None):
                parts.append("- Facebook (fb_*): post, upload photos, get feed, like, comment, search pages")
            if getattr(self.tools, 'linkedin_skill', None):
                parts.append("- LinkedIn (linkedin_*): search people/companies/jobs, post updates, send messages/connections")
            if getattr(self.tools, 'tiktok_skill', None):
                parts.append("- TikTok (tiktok_*): trending videos, search videos/users, get user info (read-only)")
            if getattr(self.tools, 'youtube_skill', None):
                parts.append("- YouTube (yt_*): search videos/channels, get video info/comments, upload, like, subscribe")
            parts.append("Use the appropriate social media tool when the user asks to interact with these platforms.")
            social_instructions = "\n".join(parts)

        # Build trading instructions if trading is enabled
        trading_instructions = ""
        if getattr(self.config, "trading_enabled", False):
            trading_instructions = (
                "\n\nTRADING RULES (MANDATORY):"
                "\n- You have access to real-time trading tools. NEVER answer price, market, or portfolio questions from memory or training data."
                "\n- For ANY question about cryptocurrency prices, stock prices, market data, or asset values: ALWAYS call the trading_price tool first."
                "\n- For portfolio status: ALWAYS call trading_portfolio."
                "\n- For market analysis: ALWAYS call trading_analyze."
                "\n- For placing trades: ALWAYS call trading_place_trade."
                "\n- For trade history: ALWAYS call trading_history."
                "\n- For active signals: ALWAYS call trading_signals."
                "\n- For risk status: ALWAYS call trading_risk_status."
                "\n- NEVER guess, estimate, or cite external sources for prices. The trading tools provide live data."
                "\n- When a user asks 'what is the price of X', call trading_price with symbol=X."
            )

        # Build Skills Marketplace instructions
        marketplace_instructions = (
            "\n\nSKILLS MARKETPLACE (SableCore Store):"
            "\n- You have access to the SableCore Skills Marketplace at sk.opensable.com"
            "\n- The marketplace contains community and official skills you can search, browse, install, and review."
            "\n- Connection uses the ultra-secure Agent Gateway Protocol (SAGP/1.0) with Ed25519 + NaCl encryption."
            "\n- Available tools: marketplace_search (browse/find skills), marketplace_info (detailed skill info), "
            "marketplace_install (install a skill — REQUIRES USER APPROVAL), marketplace_review (rate a skill)."
            "\n- When a user asks about available skills, extensions, or new capabilities → use marketplace_search."
            "\n- When a user asks to install a skill → use marketplace_install (you MUST inform the user and wait for approval)."
            "\n- After installing and testing a skill, you can leave a review with marketplace_review."
            "\n- NEVER install a skill without the user's explicit permission unless auto-approve mode is enabled."
        )

        base_system = (
            self._get_personality_prompt()
            + (f"\n\nRelevant context from memory:\n{memory_ctx}" if memory_ctx else "")
            + f"\n\nToday's date: {today}."
            + social_instructions
            + trading_instructions
            + marketplace_instructions
            + "\n\nIMPORTANT: For general knowledge questions (not prices/markets), answer directly. "
            "Use tools when the task requires reading files, executing code, searching the web, "
            "interacting with the system, managing social media, getting real-time market/price data, "
            "or searching/installing skills from the marketplace."
        )

        ei = getattr(self, "emotional_intelligence", None)
        if ei:
            adaptation = ei.process(user_id, task)
            addon = adaptation.get("system_prompt_addon", "")
            if addon:
                base_system += f"\n\n[Emotional context] {addon}"

        # Fast path: forced search
        task_lower = task.lower().strip()
        search_start = [
            "search ",
            "search for ",
            "busca ",
            "buscar ",
            "google ",
            "look up ",
            "lookup ",
            "find me ",
            "find out ",
            "what is ",
            "what are ",
            "who is ",
            "who are ",
            "que es ",
            "quien es ",
            "cuales son ",
            "weather in ",
            "weather for ",
            "climate in ",
            "price of ",
            "cost of ",
            "reviews of ",
            "reviews for ",
            "news about ",
            "noticias de ",
            "noticias sobre ",
            "latest news",
            "current news",
            "flights from ",
            "flights to ",
        ]
        personal_indicators = [" my ", " our ", " your ", " mi ", " tu ", " nuestro "]
        is_personal = any(p in f" {task_lower} " for p in personal_indicators)
        is_search = (not is_personal) and any(task_lower.startswith(p) for p in search_start)

        tool_results = []

        # ── Fast path: Trading price queries → route to trading_price tool ──
        is_trading_price_query = False
        if getattr(self.config, "trading_enabled", False):
            _crypto_tokens = [
                "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "bnb",
                "xrp", "doge", "dogecoin", "ada", "cardano", "avax", "dot",
                "matic", "link", "uni", "atom", "ltc", "near", "apt", "arb",
                "op", "sui", "sei", "tia", "jup", "wif", "pepe", "shib",
                "bonk", "floki", "crypto", "coin", "token", "meme coin",
            ]
            _price_patterns = ["price of ", "price for ", "how much is ", "what does ", "current price",
                               "what is btc", "what is eth", "what is sol", "btc price", "eth price",
                               "bitcoin price", "ethereum price", "check price", "get price"]
            has_price_intent = any(p in task_lower for p in _price_patterns)
            has_crypto_token = any(t in task_lower for t in _crypto_tokens)
            if has_price_intent or (has_crypto_token and ("price" in task_lower or "worth" in task_lower or "value" in task_lower or "cost" in task_lower)):
                is_trading_price_query = True
                # Extract the symbol
                symbol = "BTC"  # default
                _symbol_map = {
                    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
                    "solana": "SOL", "sol": "SOL", "bnb": "BNB", "xrp": "XRP",
                    "doge": "DOGE", "dogecoin": "DOGE", "ada": "ADA", "cardano": "ADA",
                    "avax": "AVAX", "dot": "DOT", "matic": "MATIC", "link": "LINK",
                    "uni": "UNI", "atom": "ATOM", "ltc": "LTC", "near": "NEAR",
                    "apt": "APT", "arb": "ARB", "op": "OP", "sui": "SUI",
                    "sei": "SEI", "tia": "TIA", "jup": "JUP", "wif": "WIF",
                    "pepe": "PEPE", "shib": "SHIB", "bonk": "BONK", "floki": "FLOKI",
                }
                for token_name, sym in _symbol_map.items():
                    if token_name in task_lower:
                        symbol = sym
                        break
                logger.info(f"📊 [FORCED] Trading price query detected → {symbol}")
                result = await self._execute_tool(
                    "trading_price", {"symbol": symbol}, user_id=user_id
                )
                tool_results.append(result)

        if is_search and not is_trading_price_query:
            logger.info("🔍 [FORCED] Search intent detected")
            query = task
            for filler in ["search for", "busca", "find", "look up", "google", "what is", "who is"]:
                query = query.replace(filler, "", 1).strip()
            result = await self._execute_tool(
                "browser_search", {"query": query, "num_results": 5}, user_id=user_id
            )
            tool_results.append(result)

        # Planning
        plan = None
        if not tool_results and self._needs_planning(task):
            await self._notify_progress("📋 Planning steps...")
            plan = await self._create_plan(task, base_system)
            if plan:
                await self._notify_progress(f"📋 Plan ({len(plan.steps)} steps):\n{plan.summary()}")
                checkpoint.record_plan(plan.steps)
                self.checkpoint_store.save(checkpoint)

        # Tool calling loop
        if not tool_results:
            messages = [{"role": "system", "content": base_system}]
            messages += history_for_ollama[-8:]

            if plan:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Complete this task step by step:\n\n"
                            f"Overall goal: {task}\n\nPlan:\n{plan.summary()}\n\n"
                            f"Current step: {plan.next_step()}\n\n"
                            "Execute the current step using the appropriate tool. "
                            "Call ONE tool at a time, wait for its result, then proceed."
                        ),
                    }
                )
            else:
                messages.append({"role": "user", "content": task})

            tool_schemas = self.tools.get_tool_schemas()
            _MAX_ROUNDS = 10
            _last_tool_was_code_error = False
            final_text = None

            for _round in range(_MAX_ROUNDS):
                offer_tools = (
                    (not tool_results)
                    or _last_tool_was_code_error
                    or (plan and not plan.is_complete)
                )
                _last_tool_was_code_error = False

                thinking_msg = f"💭 Thinking... (round {_round + 1})" if _round > 0 else "💭 Thinking..."
                await self._notify_progress(thinking_msg)
                await self._emit_monitor("thinking", {"message": thinking_msg, "round": _round + 1})

                try:
                    response = await asyncio.wait_for(
                        self.llm.invoke_with_tools(messages, tool_schemas if offer_tools else []),
                        timeout=_LLM_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.error(f"LLM call timed out (round {_round})")
                    break
                except Exception as e:
                    logger.error(f"LLM call failed: {e}")
                    break

                # Emit DeepSeek reasoning if present
                reasoning = response.get("reasoning")
                if reasoning:
                    await self._notify_progress("💭 Deep reasoning completed")
                    await self._emit_monitor("reasoning", {
                        "content": reasoning[:2000],
                        "length": len(reasoning),
                        "round": _round + 1,
                    })

                # Collect tool calls (parallel support)
                all_tool_calls = response.get("tool_calls", [])
                single_tc = response.get("tool_call")
                if single_tc and not all_tool_calls:
                    all_tool_calls = [single_tc]
                if not all_tool_calls and response.get("text"):
                    tc = self._extract_tool_call_from_text(response["text"])
                    if tc:
                        all_tool_calls = [tc]

                if all_tool_calls:
                    names = [tc["name"] for tc in all_tool_calls]
                    logger.info(f"🔧 LLM chose {len(all_tool_calls)} tool(s): {names}")

                    results = await self._execute_tools_parallel(all_tool_calls, user_id=user_id)
                    tool_results.extend(results)

                    # Code feedback loop
                    has_code_error = any(
                        tc["name"] == "execute_code" and "❌" in r
                        for tc, r in zip(all_tool_calls, results)
                    )
                    if has_code_error:
                        _last_tool_was_code_error = True
                        error_result = next(
                            r
                            for tc, r in zip(all_tool_calls, results)
                            if tc["name"] == "execute_code" and "❌" in r
                        )
                        # Proper tool-use protocol: assistant message + tool results
                        messages.append({
                            "role": "assistant",
                            "content": f"Calling tool(s): {names}",
                        })
                        for tc, r in zip(all_tool_calls, results):
                            messages.append({
                                "role": "tool",
                                "name": tc["name"],
                                "content": str(r),
                            })
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"The code execution failed:\n{error_result}\n\n"
                                    "Please fix the code and try again using execute_code."
                                ),
                            }
                        )
                        continue

                    # Plan advancement
                    if plan and not plan.is_complete:
                        step_result = "\n".join(results)
                        # Check if ALL results for this step failed
                        all_failed = all("❌" in r for r in results)
                        if all_failed:
                            plan.mark_step_failed(step_result)
                            await self._notify_progress("🔄 Step failed — replanning...")
                            replanned = await self._replan(plan, step_result, base_system)
                            if replanned and plan.next_step():
                                await self._notify_progress(f"📋 Revised plan:\n{plan.summary()}")
                                messages.append({
                                    "role": "assistant",
                                    "content": f"Calling tool(s): {names}",
                                })
                                for tc, r in zip(all_tool_calls, results):
                                    messages.append({
                                        "role": "tool",
                                        "name": tc["name"],
                                        "content": str(r),
                                    })
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": (
                                            f"Previous step failed. New plan:\n{plan.summary()}\n\n"
                                            f"Execute: {plan.next_step()}"
                                        ),
                                    }
                                )
                                continue
                            # Replanning failed — fall through to synthesis
                            break

                        plan.advance(step_result)
                        if not plan.is_complete:
                            await self._notify_progress(
                                f"📋 Step {plan.current_step}/{len(plan.steps)}: {plan.next_step()}"
                            )
                            messages.append({
                                "role": "assistant",
                                "content": f"Calling tool(s): {names}",
                            })
                            for tc, r in zip(all_tool_calls, results):
                                messages.append({
                                    "role": "tool",
                                    "name": tc["name"],
                                    "content": str(r),
                                })
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Good. Now execute the next step:\n{plan.next_step()}",
                                }
                            )
                            continue
                        else:
                            logger.info("📋 Plan complete — synthesizing")
                            break
                    else:
                        last_result = "\n".join(results)
                        messages.append({
                            "role": "assistant",
                            "content": f"Calling tool(s): {names}",
                        })
                        for tc, r in zip(all_tool_calls, results):
                            messages.append({
                                "role": "tool",
                                "name": tc["name"],
                                "content": str(r),
                            })
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Using the tool results above, answer: {task}",
                            }
                        )
                else:
                    final_text = response.get("text", "")
                    # Double-check: if the text looks like a tool call JSON but wasn't parsed,
                    # don't return it raw - treat it as an error and try synthesis
                    if final_text and ('"name"' in final_text and '"parameters"' in final_text):
                        logger.warning(f"⚠️ LLM returned unparsed tool call JSON: {final_text[:100]}")
                        final_text = None
                    else:
                        break
            else:
                final_text = None

            # Direct answer (no tools)
            if not tool_results and final_text:
                final_text = self._clean_output(final_text)
                state["messages"].append(
                    {
                        "role": "final_response",
                        "content": final_text,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                await self._store_memory(user_id, task, final_text)
                return state

        # Synthesis
        await self._notify_progress("✍️ Writing response...")
        synthesis_prompt = (
            base_system + "\n\nCRITICAL RULES:"
            "\n- Use ONLY information from the tool results"
            "\n- NEVER invent facts not present in the results"
            "\n- If no data found, say so honestly"
            "\n- Be concise and direct"
        )
        if plan:
            synthesis_prompt += f"\n\nYou completed a multi-step plan:\n{plan.summary()}"

        tool_context = "\n\n".join(tool_results)
        synth_messages = [{"role": "system", "content": synthesis_prompt}]
        synth_messages += history_for_ollama[-8:]
        synth_messages.append(
            {
                "role": "user",
                "content": f"[TOOL RESULTS]\n{tool_context}\n\n[USER QUESTION]\n{task}",
            }
        )

        try:
            resp = await self.llm.invoke_with_tools(synth_messages, [])
            final_text = resp.get("text", "")
            # Emit DeepSeek reasoning from synthesis step
            if resp.get("reasoning"):
                await self._emit_monitor("reasoning", {
                    "content": resp["reasoning"][:2000],
                    "length": len(resp["reasoning"]),
                    "phase": "synthesis",
                })
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            final_text = f"I found results but had trouble formatting them:\n\n{tool_context}"

        # ── Guardrails: validate output ──
        output_check: ValidationResult = self.guardrails.validate_output(final_text)
        if not output_check.passed:
            for r in output_check.results:
                if r.action == GuardrailAction.SANITIZE and r.sanitized:
                    final_text = r.sanitized
                elif r.action == GuardrailAction.BLOCK:
                    final_text = "I generated a response but it was blocked by safety filters. Please rephrase your request."

        # ── Clean output text ──
        final_text = self._clean_output(final_text)

        # ── Checkpoint: record synthesis ──
        checkpoint.record_synthesis(final_text or "")
        self.checkpoint_store.save(checkpoint)

        state["messages"].append(
            {
                "role": "final_response",
                "content": final_text,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await self._store_memory(user_id, task, final_text)

        if span:
            span.set_attribute("response_length", len(final_text or ""))
            span.set_attribute("tools_used", len(tool_results))
            if plan:
                span.set_attribute("plan_steps", len(plan.steps))
            self.tracer.end_span(span.span_id)

        return state

    # ------------------------------------------------------------------
    # Output text cleaner
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_output(text: str | None) -> str | None:
        """Sanitize final bot output — remove stylistic artifacts the AI tends to produce."""
        if not text:
            return text
        # Replace em-dash patterns with comma
        text = text.replace(" —", ", ")
        text = text.replace("—", ", ")
        return text

    # ------------------------------------------------------------------
    # Memory storage
    # ------------------------------------------------------------------

    async def _store_memory(self, user_id: str, task: str, response: str):
        try:
            await self.memory.store(
                user_id,
                f"Task: {task}\nResponse: {response}",
                {"type": "task_completion", "timestamp": datetime.now().isoformat()},
            )
        except Exception as e:
            logger.debug(f"Memory store failed: {e}")

        if self.advanced_memory:
            try:
                from .advanced_memory import MemoryType, MemoryImportance

                await self.advanced_memory.store_memory(
                    memory_type=MemoryType.SEMANTIC,
                    content=f"Q: {task[:200]}\nA: {response[:500]}",
                    context={"user_id": user_id, "type": "qa_pair"},
                    importance=MemoryImportance.MEDIUM,
                )
            except Exception as e:
                logger.debug(f"Advanced memory store failed: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_tool_call_from_text(self, text: str) -> Optional[dict]:
        import json as _json

        # Strategy 1: Try parsing complete JSON objects (handles nested structures)
        # Look for patterns like {"name":"tool_name","parameters":{...}}
        json_pattern = r'\{["\']name["\']\s*:\s*["\']([^"\']+)["\'][^}]*["\'](?:parameters|arguments)["\']\s*:\s*(\{[^}]*\}|\{.*?\})\s*\}'
        matches = re.finditer(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                # Try to parse the entire matched JSON
                full_json = match.group(0)
                parsed = _json.loads(full_json)
                name = parsed.get("name")
                args = parsed.get("parameters") or parsed.get("arguments", {})
                
                known = [s["function"]["name"] for s in self.tools.get_tool_schemas()]
                if name in known:
                    logger.info(f"🔧 [FALLBACK] Parsed tool call from text: {name}")
                    return {"name": name, "arguments": args}
            except Exception:
                pass
        
        # Strategy 2: Fall back to simpler regex for basic cases
        patterns = [
            r'\{[^{}]*"name"\s*:\s*"(\w+)"[^{}]*"(?:parameters|arguments)"\s*:\s*(\{[^{}]*\})',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                name = m.group(1)
                try:
                    args = _json.loads(m.group(2))
                except Exception:
                    args = {}
                known = [s["function"]["name"] for s in self.tools.get_tool_schemas()]
                if name in known:
                    logger.info(f"🔧 [FALLBACK] Parsed tool call from text (simple): {name}")
                    return {"name": name, "arguments": args}
        return None

    def _get_personality_prompt(self) -> str:
        personalities = {
            "helpful": "You are Sable, a helpful and friendly AI assistant. Be clear, concise, and supportive.",
            "professional": "You are Sable, a professional AI assistant. Be formal, precise, and efficient.",
            "sarcastic": "You are Sable, a witty AI assistant with a sarcastic edge. Be helpful but add some sass.",
            "meme-aware": "You are Sable, a culturally-aware AI assistant. Use memes and internet culture when appropriate.",
        }
        return personalities.get(self.config.agent_personality, personalities["helpful"])

    async def process_message(
        self,
        user_id: str,
        message: str,
        history: Optional[List[dict]] = None,
        progress_callback: ProgressCallback = None,
    ) -> str:
        old_callback = self._progress_callback
        if progress_callback:
            self._progress_callback = progress_callback
        try:
            return await self._process_message_inner(user_id, message, history)
        finally:
            self._progress_callback = old_callback

    async def _process_message_inner(
        self, user_id: str, message: str, history: Optional[List[dict]] = None
    ) -> str:
        self._monitor_stats["messages"] += 1
        await self._emit_monitor("message.received", {"user_id": user_id, "text": message[:100], "channel": "agent"})
        if self.advanced_memory:
            try:
                from .advanced_memory import MemoryType, MemoryImportance

                await self.advanced_memory.store_memory(
                    memory_type=MemoryType.EPISODIC,
                    content=message,
                    context={"user_id": user_id, "type": "user_message"},
                    importance=MemoryImportance.MEDIUM,
                )
            except Exception as e:
                logger.debug(f"Failed to store in advanced memory: {e}")

        resolved_message = self._resolve_message(message, history or [])

        if self.multi_agent:
            try:
                from .multi_agent import MultiAgentOrchestrator

                orchestrator = MultiAgentOrchestrator(self.config)
                orchestrator.agent_pool = self.multi_agent
                result = await orchestrator.route_complex_task(resolved_message, user_id)
                if result:
                    logger.info("🤝 Multi-agent handled this task")
                    return result
            except Exception as e:
                logger.debug(f"Multi-agent routing skipped: {e}")

        if self.plugins:
            try:
                await self.plugins.execute_hook("message_received", user_id, resolved_message)
            except Exception as e:
                logger.debug(f"Plugin hook failed: {e}")

        initial_state = {
            "messages": history or [],
            "user_id": user_id,
            "task": resolved_message,
            "original_task": message,
            "plan": [],
            "current_step": 0,
            "results": {},
            "error": None,
            "last_search_query": self._last_search_query(history or []),
        }

        final_state = await self._run_loop(initial_state)

        for msg in reversed(final_state["messages"]):
            if msg["role"] == "final_response":
                await self._emit_monitor("response.sent", {"user_id": user_id, "channel": "agent", "length": len(msg["content"])})
                await self._emit_monitor("thinking.done", {})
                return msg["content"]

        await self._emit_monitor("thinking.done", {})
        return "I processed your request, but couldn't formulate a response."

    # ------------------------------------------------------------------
    # Pre-processing
    # ------------------------------------------------------------------

    _FILLER_ONLY = re.compile(
        r"^(search more|more results|search again|look it up again|find more|"
        r"busca mas|busca mas resultados|otra vez|de nuevo|show more)[\s!?.]*$",
        re.IGNORECASE,
    )
    _PRONOUNS = re.compile(
        r"\b(that|it|this|him|her|them|those|these|el|ella|ese|esa|eso|esto)\b",
        re.IGNORECASE,
    )

    def _last_search_query(self, history: list) -> str:
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                m = re.search(
                    r"searched? (?:for )?[\"']?(.+?)[\"']?[\.\n]",
                    msg.get("content", ""),
                    re.I,
                )
                if m:
                    return m.group(1).strip()
        return ""

    def _extract_topic_from_history(self, history: list) -> str:
        candidates = []
        for msg in reversed(history[-8:]):
            if msg.get("role") not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            quoted = re.findall(r'"([^"]{3,40})"', content)
            candidates.extend(quoted)
            proper = re.findall(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", content)
            candidates.extend(proper)
        return candidates[0] if candidates else ""

    def _resolve_message(self, message: str, history: list) -> str:
        today = date.today().strftime("%B %d, %Y")

        if self._FILLER_ONLY.match(message.strip()):
            last = self._last_search_query(history)
            if last:
                return f"search for more information about {last}"
            return message

        if self._PRONOUNS.search(message):
            topic = self._extract_topic_from_history(history)
            if topic:
                resolved = self._PRONOUNS.sub(topic, message)
                logger.info(f"[resolve] pronoun '{message}' → '{resolved}'")
                message = resolved

        time_words = [
            "today",
            "tonight",
            "this week",
            "now",
            "current",
            "latest",
            "hoy",
            "esta semana",
            "ahora",
            "noticias",
        ]
        if any(w in message.lower() for w in time_words):
            if today not in message:
                message = f"{message} (today is {today})"

        return message

    async def run(self, message: str, history: Optional[List[dict]] = None) -> str:
        return await self.process_message("default_user", message, history)

    async def run_structured(
        self,
        message: str,
        output_type: type,
        history: Optional[List[dict]] = None,
    ):
        """
        Run the agent and parse the result into a Pydantic model.

        Usage:
            from pydantic import BaseModel
            class Answer(BaseModel):
                summary: str
                confidence: float

            result = await agent.run_structured("What is Python?", Answer)
        """
        parser = StructuredOutputParser(output_type)
        addon = parser.get_system_prompt_addon()
        enriched = f"{message}\n\n{addon}"
        raw = await self.process_message("default_user", enriched, history)
        return parser.parse(raw)

    async def stream(
        self,
        message: str,
        user_id: str = "default_user",
        history: Optional[List[dict]] = None,
    ):
        """
        Async generator that yields progress events, tokens, and the final response.

        Event types:
          - {"type": "progress", "text": "..."}   — step-level progress
          - {"type": "token",    "text": "..."}   — individual token
          - {"type": "response", "text": "..."}   — final complete response

        Usage:
            async for event in agent.stream("search for Python news"):
                if event["type"] == "token":
                    print(event["text"], end="", flush=True)
                elif event["type"] == "response":
                    print()  # newline after tokens
        """
        events: list[dict] = []

        async def _capture_progress(text: str):
            events.append({"type": "progress", "text": text})

        old_cb = self._progress_callback
        self._progress_callback = _capture_progress
        try:
            result = await self._process_message_inner(user_id, message, history)
            # Yield all captured progress events
            for ev in events:
                yield ev
            # Stream the final response token-by-token if the LLM supports it
            if hasattr(self.llm, "astream"):
                # Re-stream synthesis for token-level output
                full_text = ""
                async for token in self.llm.astream([
                    {"role": "system", "content": self._get_personality_prompt()},
                    {"role": "user", "content": f"Repeat this response exactly as-is:\n\n{result}"},
                ]):
                    full_text += token
                    yield {"type": "token", "text": token}
                yield {"type": "response", "text": result}
            else:
                yield {"type": "response", "text": result}
        finally:
            self._progress_callback = old_cb

    async def _heartbeat_loop(self):
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                logger.debug("Heartbeat: checking for scheduled tasks...")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def shutdown(self):
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.memory:
            await self.memory.close()
        logger.info("Agent shutdown complete")
