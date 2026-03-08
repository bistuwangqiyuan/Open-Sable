"""
Autonomous Agent Mode - Tick-based continuous operation.

Tick-based continuous autonomous operation.  Each tick is a numbered cycle:
  discover → plan → execute → learn → trace → advance

The tick counter persists across restarts.  An append-only JSONL trace
records every phase of every tick for post-hoc observability.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from .agent import SableAgent
from .goal_system import GoalManager, GoalStatus

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {"critical": 10, "high": 8, "medium": 5, "low": 3, "minimal": 1}


def _parse_priority(value) -> int:
    """Convert a priority value (int, str, or anything) to int 1-10."""
    if isinstance(value, int):
        return max(1, min(10, value))
    if isinstance(value, str):
        mapped = _PRIORITY_MAP.get(value.strip().lower())
        if mapped is not None:
            return mapped
        try:
            return max(1, min(10, int(value)))
        except ValueError:
            return 5
    return 5


def _init_sub_agents(agent):
    """Create and populate a SubAgentManager."""
    from opensable.core.sub_agents import SubAgentManager, DEFAULT_SUB_AGENTS
    mgr = SubAgentManager(agent)
    for spec in DEFAULT_SUB_AGENTS:
        mgr.register(spec)
    return mgr


async def _init_git_brain():
    """Create and initialise a GitBrain."""
    from opensable.core.git_brain import GitBrain
    gb = GitBrain(repo_dir=Path("."))
    await gb.initialize()
    return gb


class AutonomousMode:
    """
    Tick-based autonomous operation mode.

    Each iteration of the loop is a *tick* — numbered, traced, and
    persisted.  Sub-agents and fitness tracking plug in via the manager
    fields initialized in start().
    """

    def __init__(self, agent: SableAgent, config):
        self.agent = agent
        self.config = config
        self.running = False
        self.task_queue: List[Dict] = []
        self.completed_tasks: List[Dict] = []
        self.goal_manager: Optional[GoalManager] = None
        self.x_autoposter = None
        self.ig_autoposter = None

        # ── Tick state ──────────────────────────────────────────────────
        self.tick: int = 0  # Monotonic tick counter (persisted)
        self.tick_start: float = 0.0

        # Pluggable modules (initialized in start())
        self.trace_exporter = None      # TraceExporter
        self.sub_agent_manager = None   # SubAgentManager
        self.skill_fitness = None       # SkillFitnessTracker
        self.conversation_logger = None # ConversationLogger
        self.cognitive_memory = None    # CognitiveMemoryManager
        self.self_reflection = None     # ReflectionEngine
        self.skill_evolution = None     # SkillEvolutionManager
        self.git_brain = None           # GitBrain
        self.inner_life = None          # InnerLifeProcessor
        self.pattern_learner = None     # PatternLearningManager
        self.proactive_engine = None    # ProactiveReasoningEngine
        self.react_executor = None      # ReActExecutor
        self.github_skill = None        # GitHubSkill

        # Autonomous operation settings
        self.check_interval = getattr(config, "autonomous_check_interval", 60)  # seconds
        self.max_concurrent_tasks = getattr(config, "autonomous_max_tasks", 3)
        _sources = getattr(config, "autonomous_sources", "calendar,email,system_monitoring")
        if isinstance(_sources, str):
            self.enabled_sources = [s.strip() for s in _sources.split(",") if s.strip()]
        else:
            self.enabled_sources = list(_sources)

    async def start(self):
        """Start autonomous operation"""
        logger.info("🤖 Starting autonomous mode...")

        # ── Inherit modules from agent (single source of truth) ───────────
        # Use agent's profile-aware data dir, falling back to _SABLE_DATA_DIR env
        data_dir = Path(
            getattr(self.agent, "_data_dir", None)
            or os.environ.get("_SABLE_DATA_DIR")
            or "./data"
        )

        # Helper: reuse agent's instance when available, else create fresh
        def _inherit(attr_name, factory, label):
            """Reuse self.agent.<attr_name> if available, else call factory()."""
            existing = getattr(self.agent, attr_name, None)
            if existing:
                logger.info(f"♻️  {label} (shared with agent)")
                return existing
            try:
                instance = factory()
                logger.info(f"📦 {label} (new instance)")
                return instance
            except Exception as e:
                logger.warning(f"{label} unavailable: {e}")
                return None

        async def _inherit_async(attr_name, factory, label):
            existing = getattr(self.agent, attr_name, None)
            if existing:
                logger.info(f"♻️  {label} (shared with agent)")
                return existing
            try:
                instance = await factory()
                logger.info(f"📦 {label} (new instance)")
                return instance
            except Exception as e:
                logger.warning(f"{label} unavailable: {e}")
                return None

        self.trace_exporter = _inherit("trace_exporter", lambda: __import__(
            "opensable.core.trace_exporter", fromlist=["TraceExporter"]
        ).TraceExporter(directory=data_dir / "traces"), "Trace exporter")

        self.sub_agent_manager = _inherit("sub_agent_manager", lambda: _init_sub_agents(self.agent), "Sub-agent manager")

        self.skill_fitness = _inherit("skill_fitness", lambda: __import__(
            "opensable.core.skill_fitness", fromlist=["SkillFitnessTracker"]
        ).SkillFitnessTracker(directory=data_dir / "fitness"), "Skill fitness")

        self.conversation_logger = _inherit("conversation_logger", lambda: __import__(
            "opensable.core.conversation_log", fromlist=["ConversationLogger"]
        ).ConversationLogger(directory=data_dir / "conversations"), "Conversation logger")

        self.cognitive_memory = _inherit("cognitive_memory", lambda: __import__(
            "opensable.core.cognitive_memory", fromlist=["CognitiveMemoryManager"]
        ).CognitiveMemoryManager(directory=data_dir / "cognitive_memory"), "Cognitive memory")

        self.self_reflection = _inherit("self_reflection", lambda: __import__(
            "opensable.core.self_reflection", fromlist=["ReflectionEngine"]
        ).ReflectionEngine(directory=data_dir / "reflection"), "Self-reflection")

        self.skill_evolution = _inherit("skill_evolution", lambda: __import__(
            "opensable.core.skill_evolution", fromlist=["SkillEvolutionManager"]
        ).SkillEvolutionManager(directory=data_dir / "skill_evolution"), "Skill evolution")

        self.git_brain = await _inherit_async("git_brain", _init_git_brain, "Git brain")

        self.inner_life = _inherit("inner_life", lambda: __import__(
            "opensable.core.inner_life", fromlist=["InnerLifeProcessor"]
        ).InnerLifeProcessor(data_dir=data_dir / "inner_life"), "Inner life")

        self.pattern_learner = _inherit("pattern_learner", lambda: __import__(
            "opensable.core.pattern_learner", fromlist=["PatternLearningManager"]
        ).PatternLearningManager(directory=data_dir / "patterns"), "Pattern learner")

        think_interval = getattr(self.config, "proactive_think_every_n_ticks", 5)
        max_risk = getattr(self.config, "proactive_max_risk", "medium")
        self.proactive_engine = _inherit("proactive_engine", lambda: __import__(
            "opensable.core.proactive_reasoning", fromlist=["ProactiveReasoningEngine"]
        ).ProactiveReasoningEngine(
            directory=data_dir / "proactive",
            think_every_n_ticks=think_interval,
            max_risk_level=max_risk,
        ), "Proactive reasoning")

        self.react_executor = _inherit("react_executor", lambda: __import__(
            "opensable.core.react_executor", fromlist=["ReActExecutor"]
        ).ReActExecutor(
            max_steps=getattr(self.config, "react_max_steps", 8),
            timeout_s=getattr(self.config, "react_timeout_s", 180.0),
            log_dir=data_dir / "react_logs",
        ), "ReAct executor")

        self.github_skill = _inherit("github_skill", lambda: None, "GitHub skill")
        if not self.github_skill:
            try:
                from opensable.skills.automation.github_skill import GitHubSkill
                skill = GitHubSkill(self.config)
                # GitHub skill needs async init — we'll do it inline
                self.github_skill = skill
            except Exception as e:
                logger.warning(f"GitHub skill unavailable: {e}")

        # Load persisted tick counter
        await self._load_state()

        # Connect goal manager from the agent
        self.goal_manager = getattr(self.agent, "goals", None)
        if self.goal_manager:
            logger.info("Goal system connected")
        else:
            logger.warning("Goal system not available")

        # Initialize X Autoposter if enabled and not already running
        if (
            getattr(self.config, "x_autoposter_enabled", False)
            and getattr(self.config, "x_enabled", False)
            and not getattr(self.agent, "x_autoposter", None)
        ):
            try:
                from .x_autoposter import XAutoposter

                self.x_autoposter = XAutoposter(self.agent, self.config)
                self.agent.x_autoposter = self.x_autoposter  # expose to gateway

                async def _run_ap():
                    try:
                        await self.x_autoposter.start()
                    except Exception as exc:
                        logger.error(f"🐦 X Autoposter crashed: {exc}", exc_info=True)

                asyncio.create_task(_run_ap())
                logger.info("🐦 X Autoposter launched as background task")
            except Exception as e:
                logger.error(f"Failed to start X Autoposter: {e}", exc_info=True)

        # Initialize IG Autoposter if enabled
        if (
            os.getenv("IG_AUTOPOSTER_ENABLED", "false").lower() in ("true", "1", "yes")
            and not getattr(self.agent, "ig_autoposter", None)
        ):
            try:
                from .ig_autoposter import IGAutoposter

                self.ig_autoposter = IGAutoposter(self.agent, self.config)
                self.agent.ig_autoposter = self.ig_autoposter

                async def _run_ig_ap():
                    try:
                        await self.ig_autoposter.start()
                    except Exception as exc:
                        logger.error(f"📸 IG Autoposter crashed: {exc}", exc_info=True)

                asyncio.create_task(_run_ig_ap())
                logger.info("📸 IG Autoposter launched as background task")
            except Exception as e:
                logger.error(f"Failed to start IG Autoposter: {e}", exc_info=True)

        self.running = True

        # Start main loop
        await self._autonomous_loop()

    async def stop(self):
        """Stop autonomous operation"""
        logger.info("Stopping autonomous mode...")
        self.running = False
        if self.x_autoposter:
            await self.x_autoposter.stop()
        if self.ig_autoposter:
            await self.ig_autoposter.stop()

    async def _autonomous_loop(self):
        """Main tick-based autonomous loop.

        Each iteration is a numbered *tick*.  Pipeline per tick:
          1. trace_tick_start
          2. discover tasks
          3. prioritize
          4. execute
          5. collect sub-agent results
          6. self-improve
          7. maintain
          8. trace_tick_end + advance tick counter
        """
        logger.info(
            f"Autonomous loop started — tick {self.tick} "
            f"(interval: {self.check_interval}s)"
        )

        consecutive_errors = 0
        _MAX_CONSECUTIVE_ERRORS = 10
        _BACKOFF_MULTIPLIER = 2  # double interval after many failures

        while self.running:
            self.tick_start = time.monotonic()
            try:
                # ── Phase 0: Trace tick start ───────────────────────────
                if self.trace_exporter:
                    self.trace_exporter.record_tick_start(
                        tick=self.tick,
                    )

                # ── Phase 1: Discover ───────────────────────────────────
                await self._discover_tasks()

                # ── Phase 2: Prioritize ─────────────────────────────────
                await self._prioritize_tasks()

                # ── Phase 3: Execute ────────────────────────────────────
                await self._execute_tasks()

                # ── Phase 4: Collect sub-agent results ──────────────────
                if self.sub_agent_manager and self.sub_agent_manager.pending_count > 0:
                    results = await self.sub_agent_manager.await_all(timeout_s=30.0)
                    for task_id, result in results.items():
                        if self.trace_exporter:
                            self.trace_exporter.record_event(
                                "sub_agent_result",
                                summary=f"{result.agent_name}: {result.status} — {result.task[:60]}",
                                tick=self.tick,
                                data={"task_id": task_id, "duration_ms": result.duration_ms},
                            )
                    self.sub_agent_manager.clear_inbox()

                # ── Phase 5: Self-improvement ───────────────────────────
                if self.goal_manager:
                    await self._self_improve()

                # ── Phase 6: Proactive reasoning ─────────────────────
                await self._proactive_tick()

                # ── Phase 7: Cognitive processing ───────────────────────
                await self._cognitive_tick()

                # ── Phase 8: Maintenance + state save ───────────────────
                await self._perform_maintenance()

                # ── Phase 9: Trace tick end + advance ───────────────────
                tick_duration = (time.monotonic() - self.tick_start) * 1000
                if self.trace_exporter:
                    self.trace_exporter.record_tick_end(
                        tick=self.tick,
                        summary=f"completed {len(self.completed_tasks)} tasks",
                        duration_ms=tick_duration,
                    )

                logger.info(
                    f"✅ Tick {self.tick} complete ({tick_duration:.0f}ms, "
                    f"{len(self.task_queue)} queued, "
                    f"{len(self.completed_tasks)} completed)"
                )
                self.tick += 1
                consecutive_errors = 0  # Reset on success

                # Wait before next tick
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in tick {self.tick}: {e} (consecutive: {consecutive_errors})")
                if self.trace_exporter:
                    self.trace_exporter.record_event(
                        "tick_error",
                        summary=str(e),
                        tick=self.tick,
                    )

                # Circuit breaker: back off when many consecutive failures
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    backoff = self.check_interval * _BACKOFF_MULTIPLIER
                    logger.warning(
                        f"⚠️ Circuit breaker: {consecutive_errors} consecutive failures. "
                        f"Backing off to {backoff}s interval."
                    )
                    await asyncio.sleep(backoff)
                else:
                    await asyncio.sleep(self.check_interval)

    async def _discover_tasks(self):
        """Discover tasks from various sources"""

        # Check calendar for upcoming events
        if "calendar" in self.enabled_sources:
            await self._check_calendar()

        # Check email for action items
        if "email" in self.enabled_sources:
            await self._check_email()

        # Monitor system resources
        if "system_monitoring" in self.enabled_sources:
            await self._check_system()

        # Check for trading opportunities
        if "trading" in self.enabled_sources:
            await self._check_trading()

        # Check world news for situational awareness
        if "news" in self.enabled_sources:
            await self._check_news()

        # Check for scheduled goals (if Agentic AI available)
        if self.goal_manager:
            await self._check_goals()

    async def _check_calendar(self):
        """Check calendar for upcoming events and create actionable tasks."""
        try:
            result = await self.agent.tools.execute(
                "calendar", {"action": "list", "timeframe": "24h"}
            )
            result_text = str(result).strip()

            # Skip empty results
            if not result_text or "no " in result_text.lower() or len(result_text) < 20:
                logger.debug("Calendar: no upcoming events")
                return

            # Use LLM to extract actionable tasks from calendar events
            if self.agent.llm:
                messages = [
                    {"role": "system", "content": (
                        "You are an autonomous agent's calendar analyzer. "
                        "Extract actionable tasks from calendar events. "
                        "Output ONLY valid JSON array. Each item: "
                        '{"description": "what to do", "priority": 1-10, "type": "reminder"}. '
                        "If nothing actionable, return []."
                    )},
                    {"role": "user", "content": f"Calendar events:\n{result_text[:2000]}"},
                ]
                try:
                    response = await self.agent.llm.invoke_with_tools(messages, [])
                    self._inject_llm_tasks(response.get("text", ""), source="calendar")
                except Exception as e:
                    logger.debug(f"Calendar LLM analysis failed: {e}")
            else:
                logger.debug("Checked calendar (no LLM for analysis)")

        except Exception as e:
            logger.debug(f"Calendar check skipped: {e}")

    async def _check_email(self):
        """Check email for action items and create tasks from them."""
        try:
            result = await self.agent.tools.execute(
                "email", {"action": "read", "filter": "unread", "limit": 5}
            )
            result_text = str(result).strip()

            if not result_text or "no " in result_text.lower() or len(result_text) < 20:
                logger.debug("Email: no unread messages")
                return

            # Use LLM to extract action items from emails
            if self.agent.llm:
                messages = [
                    {"role": "system", "content": (
                        "You are an autonomous agent's email analyzer. "
                        "Extract actionable tasks from emails. "
                        "Output ONLY valid JSON array. Each item: "
                        '{"description": "what to do", "priority": 1-10, "type": "email_action"}. '
                        "Ignore spam and newsletters. If nothing actionable, return []."
                    )},
                    {"role": "user", "content": f"Emails:\n{result_text[:3000]}"},
                ]
                try:
                    response = await self.agent.llm.invoke_with_tools(messages, [])
                    self._inject_llm_tasks(response.get("text", ""), source="email")
                except Exception as e:
                    logger.debug(f"Email LLM analysis failed: {e}")
            else:
                logger.debug("Checked email (no LLM for analysis)")

        except Exception as e:
            logger.debug(f"Email check skipped: {e}")

    async def _check_system(self):
        """Monitor system resources and create maintenance tasks if needed."""
        try:
            result = await self.agent.tools.execute("system_info", {})
            result_text = str(result).strip()

            if not result_text or len(result_text) < 10:
                return

            # Parse common system thresholds directly (no LLM needed)
            tasks_created = 0

            # Check for disk space issues
            import re
            disk_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(?:used|full|disk)", result_text, re.IGNORECASE)
            for pct in disk_matches:
                if float(pct) > 90:
                    task_id = f"system_disk_{datetime.now().strftime('%Y%m%d')}"
                    if not any(t.get("id") == task_id for t in self.task_queue):
                        self.task_queue.append({
                            "id": task_id,
                            "type": "system_maintenance",
                            "description": f"Disk usage at {pct}% — clean up temp files, old logs, caches",
                            "priority": 8,
                            "created_at": datetime.now(),
                        })
                        tasks_created += 1
                        logger.warning(f"⚠️ Disk usage {pct}% — created cleanup task")

            # Check for high memory usage
            mem_matches = re.findall(r"(?:memory|ram|mem)[^0-9]*(\d+(?:\.\d+)?)\s*%", result_text, re.IGNORECASE)
            for pct in mem_matches:
                if float(pct) > 90:
                    task_id = f"system_memory_{datetime.now().strftime('%Y%m%d_%H')}"
                    if not any(t.get("id") == task_id for t in self.task_queue):
                        self.task_queue.append({
                            "id": task_id,
                            "type": "system_maintenance",
                            "description": f"Memory usage at {pct}% — identify memory-heavy processes",
                            "priority": 7,
                            "created_at": datetime.now(),
                        })
                        tasks_created += 1
                        logger.warning(f"⚠️ Memory at {pct}%")

            if tasks_created:
                logger.info(f"🖥️ System check: created {tasks_created} maintenance task(s)")
            else:
                logger.debug("System check: all healthy")

        except Exception as e:
            logger.debug(f"System check skipped: {e}")

    def _inject_llm_tasks(self, llm_text: str, source: str = "unknown"):
        """Parse LLM JSON output and inject tasks into the queue.

        Deduplicates against both pending queue AND recently completed tasks
        to prevent the agent from endlessly re-creating already-done work.
        """
        import re as _re

        text = llm_text.strip()

        # Strip <think> blocks (Qwen3 / DeepSeek reasoning)
        text = _re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        # Strip role prefix
        text = _re.sub(r"^(?:system|assistant)\s*\n", "", text).strip()

        # Extract JSON from potential markdown code block
        if "```" in text:
            match = _re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, _re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    items = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    return
            else:
                return

        if isinstance(items, dict):
            items = [items]
        elif not isinstance(items, list):
            return

        # Build dedup set: descriptions from queue + recent completed tasks
        existing_descs = {t.get("description", "").strip().lower() for t in self.task_queue}
        # Check completed tasks (last 50) for similarity
        for ct in self.completed_tasks[-50:]:
            existing_descs.add(ct.get("description", "").strip().lower())

        injected = 0
        for item in items[:5]:  # Max 5 tasks per source
            if not isinstance(item, dict):
                continue
            desc = item.get("description", "").strip()
            if not desc or len(desc) < 5:
                continue

            # Dedup: exact match OR high substring overlap with existing
            desc_lower = desc.lower()
            if desc_lower in existing_descs:
                continue
            # Fuzzy dedup: skip if >80% of words overlap with any existing
            desc_words = set(desc_lower.split())
            skip = False
            for existing in existing_descs:
                if not existing:
                    continue
                existing_words = set(existing.split())
                if desc_words and existing_words:
                    overlap = len(desc_words & existing_words) / max(len(desc_words), 1)
                    if overlap > 0.8:
                        skip = True
                        break
            if skip:
                continue

            task_id = f"{source}_{self.tick}_{injected}"

            self.task_queue.append({
                "id": task_id,
                "type": item.get("type", source),
                "description": desc,
                "priority": _parse_priority(item.get("priority", 5)),
                "created_at": datetime.now(),
                "source": source,
            })
            existing_descs.add(desc_lower)

            # Also register in GoalManager if it's a goal-type task
            if self.goal_manager and item.get("type") in ("goal", "self_improve"):
                try:
                    from .goal_system import GoalPriority
                    priority_map = {"high": GoalPriority.HIGH, "medium": GoalPriority.MEDIUM, "low": GoalPriority.LOW}
                    gp = priority_map.get(str(item.get("priority", "medium")).lower(), GoalPriority.MEDIUM)
                    import asyncio
                    asyncio.ensure_future(self.goal_manager.create_goal(
                        description=desc,
                        success_criteria=[f"Complete: {desc}"],
                        priority=gp,
                    ))
                except Exception as e:
                    logger.debug(f"Goal registration failed: {e}")

            injected += 1

        if injected:
            logger.info(f"📋 Injected {injected} task(s) from {source}")

    async def _check_trading(self):
        """Check for trading opportunities and portfolio health"""
        try:
            trading_skill = getattr(self.agent.tools, "trading_skill", None)
            if not trading_skill or not trading_skill._initialized:
                return

            # 1. Scan watchlist for signals
            signals_result = await trading_skill.get_signals()
            if signals_result and "No signals" not in signals_result:
                task = {
                    "id": f"trading_signals_{datetime.now().strftime('%H%M')}",
                    "type": "trading",
                    "description": f"Trading signals detected:\n{signals_result[:500]}",
                    "priority": 7,  # High priority
                    "created_at": datetime.now(),
                }
                if not any(t.get("type") == "trading" and "signals" in t.get("id", "") for t in self.task_queue):
                    self.task_queue.append(task)
                    logger.info("📊 Added trading signal task to queue")

            # 2. Check portfolio health (risk status)
            risk_result = await trading_skill.get_risk_status()
            if risk_result and "Emergency Halt: 🔴 YES" in risk_result:
                task = {
                    "id": f"trading_risk_alert_{datetime.now().strftime('%H%M')}",
                    "type": "trading_alert",
                    "description": "⚠️ TRADING EMERGENCY HALT ACTIVE — review portfolio immediately",
                    "priority": 10,  # Maximum priority
                    "created_at": datetime.now(),
                }
                if not any(t.get("type") == "trading_alert" for t in self.task_queue):
                    self.task_queue.append(task)
                    logger.warning("🚨 Trading emergency halt detected!")

            logger.debug("Checked trading opportunities")

        except Exception as e:
            logger.error(f"Failed to check trading: {e}")

    async def _check_news(self):
        """Check world news for situational awareness and actionable events."""
        try:
            news_skill = getattr(self.agent.tools, "news_reader_skill", None)
            if not news_skill or not news_skill._ready:
                return

            digest = await news_skill.get_news_digest()
            if not digest or "(no news available)" in digest:
                logger.debug("News: no digest available")
                return

            # Use LLM to extract actionable items from the news digest
            if self.agent.llm:
                messages = [
                    {"role": "system", "content": (
                        "You are an autonomous agent's world-news analyst. "
                        "Review the news digest and extract items that are actionable, "
                        "noteworthy, or worth following up on. Think about: breaking events, "
                        "geopolitical shifts, market-moving news, tech breakthroughs, "
                        "security threats. Output ONLY valid JSON array. Each item: "
                        '{"description": "what happened and why it matters", "priority": 1-10, '
                        '"type": "news_followup"}. If nothing actionable, return [].'
                    )},
                    {"role": "user", "content": f"News digest:\n{digest[:3000]}"},
                ]
                try:
                    response = await self.agent.llm.invoke_with_tools(messages, [])
                    self._inject_llm_tasks(response.get("text", ""), source="news")
                except Exception as e:
                    logger.debug(f"News LLM analysis failed: {e}")
            else:
                logger.debug("Checked news (no LLM for analysis)")

        except Exception as e:
            logger.debug(f"News check skipped: {e}")

    async def _check_goals(self):
        """Check for pending goals (Agentic AI mode)"""
        if not self.goal_manager:
            return

        try:
            # Get active goals
            active_goals = [g for g in self.goal_manager.goals.values() if g.status in (GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS)]

            # Add to task queue if not already there
            for goal in active_goals:
                task = {
                    "id": goal.goal_id,
                    "type": "goal",
                    "description": goal.description,
                    "priority": goal.priority.value,
                    "created_at": datetime.now(),
                }

                if not any(t["id"] == task["id"] for t in self.task_queue):
                    self.task_queue.append(task)
                    logger.info(f"Added goal to queue: {goal.description}")

        except Exception as e:
            logger.error(f"Failed to check goals: {e}")

    async def _prioritize_tasks(self):
        """Prioritize tasks in queue — modulated by inner emotional state.

        Emotion influences:
          • High arousal → urgent/reactive tasks get boosted
          • Negative valence → defensive/maintenance tasks prioritized
          • Frustration → improvement/learning tasks boosted
          • Boredom → creative/proactive tasks boosted
          • Positive valence → ambitious goals get a nudge
        """
        if not self.task_queue:
            return

        # Get emotional modulation factors
        emotion_boost = {}  # type → priority delta
        if self.inner_life:
            try:
                e = self.inner_life.emotion
                arousal = getattr(e, "arousal", 0.3)
                valence = getattr(e, "valence", 0.0)
                primary = getattr(e, "primary", "neutral")

                # High arousal → boost urgent/system tasks
                if arousal > 0.6:
                    emotion_boost["system_maintenance"] = 2
                    emotion_boost["command"] = 1
                    emotion_boost["trading_alert"] = 2

                # Negative valence → boost defensive tasks
                if valence < -0.3:
                    emotion_boost["system_maintenance"] = emotion_boost.get("system_maintenance", 0) + 2
                    emotion_boost["email_action"] = 1

                # Frustration → boost self-improvement
                if primary == "frustration":
                    emotion_boost["goal"] = 2
                    emotion_boost["self_improve"] = 3

                # Boredom → boost creative/proactive
                if primary == "boredom":
                    emotion_boost["proactive"] = 3
                    emotion_boost["creative"] = 2
                    emotion_boost["research"] = 2

                # Positive valence → boost ambitious goals
                if valence > 0.3:
                    emotion_boost["goal"] = emotion_boost.get("goal", 0) + 1
                    emotion_boost["proactive"] = emotion_boost.get("proactive", 0) + 1

                if emotion_boost:
                    logger.debug(
                        f"Emotion modulation: {primary} (v={valence:+.1f}, a={arousal:.1f}) "
                        f"→ boosts: {emotion_boost}"
                    )
            except Exception as e:
                logger.debug(f"Emotion modulation skipped: {e}")

        # Apply emotional modulation to priority scores
        for task in self.task_queue:
            base = task.get("priority", 5)
            boost = emotion_boost.get(task.get("type", ""), 0)
            task["_effective_priority"] = base + boost

        # Sort by effective priority (higher first)
        self.task_queue.sort(key=lambda t: t.get("_effective_priority", t.get("priority", 0)), reverse=True)

    async def _execute_tasks(self):
        """Execute tasks from queue — ONE AT A TIME (sequential).
        
        After each task, record the outcome for learning.
        Concurrent task execution causes multiple simultaneous API calls,
        which gets detected as bot behavior. A real user does one thing at a time.
        """
        tasks_to_execute = self.task_queue[: self.max_concurrent_tasks]

        if not tasks_to_execute:
            return

        logger.info(f"Executing {len(tasks_to_execute)} task(s) sequentially...")

        for task in list(tasks_to_execute):
            start_time = time.monotonic()
            try:
                result = await self._execute_single_task(task)
                duration_ms = (time.monotonic() - start_time) * 1000

                # ── Success: record outcome ──
                self.task_queue.remove(task)
                task["completed_at"] = datetime.now()
                task["result"] = str(result)[:500] if result else ""
                task["status"] = "done"
                task["duration_ms"] = duration_ms
                task["retries"] = task.get("retries", 0)
                self.completed_tasks.append(task)

                logger.info(
                    f"✅ Task {task['id']} done ({duration_ms:.0f}ms): "
                    f"{task.get('description', '')[:60]}"
                )

                # Store outcome in cognitive memory for future reasoning
                self._record_outcome(task, success=True, result=result)

            except Exception as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                retries = task.get("retries", 0)
                max_retries = task.get("max_retries", 2)

                if retries < max_retries:
                    # ── Retry: re-enqueue with incremented retry count ──
                    task["retries"] = retries + 1
                    task["last_error"] = str(e)[:200]
                    # Move to end of queue for later retry
                    self.task_queue.remove(task)
                    self.task_queue.append(task)
                    logger.warning(
                        f"🔄 Task {task['id']} retry {retries + 1}/{max_retries}: {e}"
                    )
                else:
                    # ── Final failure: record for learning ──
                    self.task_queue.remove(task)
                    task["completed_at"] = datetime.now()
                    task["result"] = str(e)[:500]
                    task["status"] = "error"
                    task["duration_ms"] = duration_ms
                    task["retries"] = retries
                    self.completed_tasks.append(task)

                    logger.error(
                        f"❌ Task {task['id']} failed after {retries + 1} attempts ({duration_ms:.0f}ms): {e}"
                    )

                    self._record_outcome(task, success=False, result=e)

    def _record_outcome(self, task: Dict, success: bool, result: Any):
        """Record task outcome for learning — feeds cognitive memory + proactive reasoning."""
        description = task.get("description", "")[:200]
        task_type = task.get("type", "unknown")
        duration_ms = task.get("duration_ms", 0)

        # 1. Store in cognitive memory (if available)
        #    Use emotion modulation: high arousal → memories stored with higher importance
        if self.cognitive_memory:
            try:
                importance = 0.7 if success else 0.9  # Failures are more memorable

                # Apply inner life emotion modulation (amygdala effect)
                if self.inner_life:
                    try:
                        modulation = self.inner_life.get_emotion_modulation()
                        importance = min(1.0, importance * modulation)
                    except Exception:
                        pass

                category = "success" if success else "failure"
                self.cognitive_memory.add_memory(
                    f"Task [{task_type}] {'succeeded' if success else 'FAILED'}: {description}. "
                    f"Result: {str(result)[:200]}",
                    category=category,
                    importance=importance,
                )
            except Exception:
                pass

        # 2. Record in skill fitness tracker
        if self.skill_fitness:
            try:
                # Track tools used in proactive/react tasks
                tools_used = task.get("tools_used", [])
                for tool_name in tools_used:
                    self.skill_fitness.record_event(
                        skill_name=tool_name,
                        tick=self.tick,
                        success=success,
                        duration_ms=duration_ms,
                    )
            except Exception:
                pass

        # 3. Log to trace exporter
        if self.trace_exporter:
            try:
                self.trace_exporter.record_event(
                    "task_outcome",
                    summary=f"{'✅' if success else '❌'} [{task_type}] {description[:60]}",
                    tick=self.tick,
                    data={
                        "task_id": task.get("id"),
                        "type": task_type,
                        "success": success,
                        "duration_ms": duration_ms,
                        "source": task.get("source", ""),
                    },
                )
            except Exception:
                pass

    async def _execute_single_task(self, task: Dict) -> Any:
        """Execute a single task using the best available method."""
        task_type = task.get("type")

        if task_type == "goal":
            # Execute goal — try ReAct first for multi-step reasoning,
            # fall back to GoalManager direct execution
            if self.react_executor and self.agent.llm:
                description = task.get("description", "")
                result = await self._execute_via_react(
                    f"Complete this goal: {description}"
                )
                if result:
                    # Update goal status if GoalManager is available
                    if self.goal_manager:
                        try:
                            goal_id = task["id"]
                            if goal_id in self.goal_manager.goals:
                                self.goal_manager.goals[goal_id].status = GoalStatus.COMPLETED
                        except Exception:
                            pass
                    return result
            # Fallback to direct goal execution
            if self.goal_manager:
                goal_id = task["id"]
                return await self.goal_manager.execute_goal(goal_id)

        elif task_type == "command":
            command = task.get("command")
            return await self.agent.tools.execute("execute_command", {"command": command})

        elif task_type == "reminder":
            message = task.get("message", task.get("description", ""))
            logger.info(f"⏰ Reminder: {message}")
            return message

        elif task_type == "proactive":
            return await self._execute_proactive_task(task)

        elif task_type == "system_maintenance":
            # System maintenance tasks are executed via ReAct
            description = task.get("description", "")
            return await self._execute_via_react(
                f"System maintenance: {description}. "
                "Use execute_command to diagnose and fix the issue. "
                "Be careful and non-destructive."
            )

        elif task_type in ("email_action", "calendar"):
            # LLM-discovered tasks from email/calendar
            description = task.get("description", "")
            return await self._execute_via_react(description)

        elif task_type == "trading":
            # Trading tasks — execute via trading skill
            description = task.get("description", "")
            if self.react_executor and self.agent.llm:
                return await self._execute_via_react(
                    f"Trading task: {description}. Use trading tools to handle this."
                )
            return description

        elif task_type == "trading_alert":
            description = task.get("description", "")
            logger.warning(f"🚨 {description}")
            return description

        else:
            # Unknown type — always try ReAct
            if self.react_executor and self.agent.llm:
                return await self._execute_via_react(task.get("description", str(task)))
            logger.warning(f"Unknown task type: {task_type} (no ReAct available)")
            return None

    async def _self_improve(self):
        """Run LLM-driven meta-learning: analyse past outcomes + inject improvements.

        Runs every 24 hours.  The LLM receives:
          • Recent completed tasks (successes + failures)
          • Skill fitness summary
          • Self-reflection summary
          • Pattern learner rules

        It then proposes concrete improvements as tasks injected into the queue.
        """
        try:
            if not hasattr(self, "_last_improvement"):
                self._last_improvement = datetime.now() - timedelta(hours=25)

            if datetime.now() - self._last_improvement < timedelta(hours=24):
                return

            if not self.agent.llm:
                return

            logger.info("🧬 Running self-improvement analysis...")

            # ── Gather evidence ──
            recent_tasks = self.completed_tasks[-30:]
            successes = [t for t in recent_tasks if t.get("status") == "done"]
            failures = [t for t in recent_tasks if t.get("status") == "error"]

            summaries = []
            summaries.append(f"Tasks completed: {len(successes)}, failed: {len(failures)}")

            for t in failures[-5:]:
                summaries.append(
                    f"FAIL: [{t.get('type','')}] {t.get('description','')[:80]} → {t.get('result','')[:120]}"
                )
            for t in successes[-5:]:
                summaries.append(
                    f"OK: [{t.get('type','')}] {t.get('description','')[:80]} ({t.get('duration_ms',0):.0f}ms)"
                )

            if self.self_reflection:
                try:
                    summaries.append(f"Self-reflection: {self.self_reflection.get_summary()}")
                except Exception:
                    pass

            if self.pattern_learner and hasattr(self.pattern_learner, "rules"):
                try:
                    rules = self.pattern_learner.rules[:5]
                    for r in rules:
                        summaries.append(f"Pattern rule: {r}")
                except Exception:
                    pass

            if self.skill_fitness:
                try:
                    fitness = self.skill_fitness.get_fitness_dicts(self.tick, 200)
                    low_fitness = [f for f in fitness if f.get("fitness", 1.0) < 0.5]
                    for lf in low_fitness[:5]:
                        summaries.append(
                            f"Low-fitness skill: {lf.get('skill','')} fitness={lf.get('fitness',0):.2f}"
                        )
                except Exception:
                    pass

            # Emotion-driven evolution pressure
            if self.inner_life:
                try:
                    pressures = self.inner_life.get_evolution_pressure()
                    for p in pressures:
                        summaries.append(f"Evolution pressure: {p}")
                    if pressures:
                        summaries.append(
                            f"Current emotion: {self.inner_life.emotion.primary} "
                            f"(valence={self.inner_life.emotion.valence:+.1f}, "
                            f"arousal={self.inner_life.emotion.arousal:.1f})"
                        )
                except Exception:
                    pass

            evidence = "\n".join(summaries)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an autonomous agent performing self-improvement analysis.\n"
                        "Given evidence about your recent performance, propose 1-3 concrete "
                        "improvement actions the agent can take RIGHT NOW.\n"
                        "For each action, output JSON:\n"
                        '[{"type":"goal","description":"...","priority":"high|medium|low"}]\n'
                        "Focus on: fixing recurring errors, improving slow tasks, learning new skills, "
                        "automating manual patterns. Be specific and actionable."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Performance evidence (last 24h):\n{evidence}\n\nPropose improvements:",
                },
            ]

            result = await self.agent.llm.invoke_with_tools(messages, [])
            content = result.get("text", "") or result.get("content", "") if isinstance(result, dict) else str(result)

            if content:
                self._inject_llm_tasks(content, source="self_improve")

            self._last_improvement = datetime.now()
            logger.info("🧬 Self-improvement analysis complete")

        except Exception as e:
            logger.error(f"Self-improvement failed: {e}")

    async def _proactive_tick(self):
        """Run proactive reasoning — LLM decides what to do autonomously.

        Only triggers every N ticks (configurable). Generates action proposals
        and injects them into the task queue for execution.
        """
        if not self.proactive_engine:
            return
        if not self.proactive_engine.should_think(self.tick):
            return
        if not self.agent.llm:
            return

        try:
            # Build world context
            system_state = {}
            try:
                system_state = self.get_status()
            except Exception:
                pass

            cognitive_state = {}
            if self.inner_life:
                try:
                    e = self.inner_life.emotion
                    cognitive_state["emotion"] = {
                        "primary": e.primary,
                        "valence": e.valence,
                        "arousal": e.arousal,
                        "trigger": e.trigger,
                    }
                    pressures = self.inner_life.get_evolution_pressure()
                    if pressures:
                        cognitive_state["evolution_pressures"] = pressures
                except Exception:
                    pass
            if self.self_reflection:
                try:
                    cognitive_state["reflection"] = self.self_reflection.get_summary()
                except Exception:
                    pass

            goals = []
            if self.goal_manager:
                try:
                    for g in self.goal_manager.goals.values():
                        if g.status in (GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS):
                            goals.append(g.description)
                except Exception:
                    pass

            recent_errors = []
            for t in self.completed_tasks[-10:]:
                if t.get("status") == "error":
                    recent_errors.append(str(t.get("result", ""))[:100])

            context = self.proactive_engine.build_context(
                tick=self.tick,
                completed_tasks=self.completed_tasks,
                queued_tasks=self.task_queue,
                system_state=system_state,
                recent_errors=recent_errors,
                goals=goals,
                cognitive_state=cognitive_state,
            )

            # Ask LLM to think proactively
            proposals = await self.proactive_engine.think(
                llm=self.agent.llm,
                tick=self.tick,
                context=context,
            )

            # Inject proposals into task queue
            for proposal in proposals:
                task = proposal.to_task(self.tick)
                self.task_queue.append(task)
                self.proactive_engine.record_accepted(proposal)
                logger.info(
                    f"🧠 Proactive: {proposal.action[:60]} "
                    f"(type={proposal.goal_type.value}, pri={proposal.priority:.1f})"
                )

            if self.trace_exporter and proposals:
                self.trace_exporter.record_event(
                    "proactive_proposals",
                    summary=f"{len(proposals)} proposals generated",
                    tick=self.tick,
                    data={"actions": [p.action[:80] for p in proposals]},
                )

        except Exception as e:
            logger.warning(f"Proactive reasoning tick failed: {e}")

    async def _execute_proactive_task(self, task: Dict) -> Any:
        """Execute a proactive task, using ReAct if available."""
        description = task.get("description", "")
        tool_name = task.get("tool_name")
        tool_args = task.get("tool_args", {})

        # If a specific tool was proposed, try direct execution first
        if tool_name and tool_args:
            try:
                result = await self.agent.tools.execute(tool_name, tool_args)
                return result
            except Exception as e:
                logger.debug(f"Direct tool execution failed, falling back to ReAct: {e}")

        # Fall back to ReAct for complex tasks
        return await self._execute_via_react(description)

    async def _execute_via_react(self, task_description: str) -> Any:
        """Execute a task using the ReAct reasoning + acting loop."""
        if not self.react_executor or not self.agent.llm:
            logger.debug(f"ReAct not available for task: {task_description[:60]}")
            return None

        async def tool_executor(tool_name: str, args: Dict[str, Any]) -> str:
            """Bridge between ReAct and the ToolRegistry."""
            try:
                result = await self.agent.tools.execute(tool_name, args)
                return str(result)[:2000]
            except Exception as e:
                return f"Error: {e}"

        # Get available tool schemas for the LLM
        available_tools = []
        try:
            available_tools = self.agent.tools.get_tool_schemas()[:30]
        except Exception:
            pass

        result = await self.react_executor.execute(
            task=task_description,
            llm=self.agent.llm,
            tool_executor=tool_executor,
            available_tools=available_tools,
        )

        if self.trace_exporter:
            self.trace_exporter.record_event(
                "react_execution",
                summary=f"{'✅' if result.success else '❌'} {task_description[:60]}",
                tick=self.tick,
                data={
                    "success": result.success,
                    "steps": len(result.steps),
                    "tools_used": result.tools_used,
                    "duration_ms": result.total_duration_ms,
                },
            )

        if result.success:
            return result.final_answer
        else:
            logger.warning(f"ReAct execution failed: {result.error}")
            return None

    async def _cognitive_tick(self):
        """Run all cognitive modules for the current tick.

        Order:
          1. Cognitive memory — decay + consolidation + attention filter
          2. Self-reflection — pattern detection + stagnation check (with real data)
          3. Skill evolution — natural selection + mutation + niche
          4. Pattern learner — windowed analysis + snapshots + rules
          5. Git brain — write episode + optional auto-commit
          6. Inner life — System 1 LLM pass (emotion, impulse, fantasy, landscape)
        """
        try:
            # ── 1. Cognitive memory ──
            if self.cognitive_memory:
                try:
                    self.cognitive_memory.process_tick(self.tick)
                except Exception as e:
                    logger.debug(f"Cognitive memory tick failed: {e}")

            # ── 2. Self-reflection — feed REAL outcome data ──
            if self.self_reflection:
                try:
                    recent = self.completed_tasks[-10:]
                    success_count = sum(1 for t in recent if t.get("status") == "done")
                    error_count = sum(1 for t in recent if t.get("status") == "error")
                    errors_list = [
                        str(t.get("result", ""))[:100]
                        for t in recent if t.get("status") == "error"
                    ]
                    tools = []
                    for t in recent:
                        if t.get("tools_used"):
                            tools.extend(t["tools_used"])
                    goals = []
                    if self.goal_manager:
                        for g in self.goal_manager.goals.values():
                            if g.status in (GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS):
                                goals.append(g.description[:60])

                    from .self_reflection import TickOutcome
                    outcome = TickOutcome(
                        tick=self.tick,
                        success=error_count == 0,
                        summary=(
                            f"Tick {self.tick}: {success_count} ok, "
                            f"{error_count} errors, {len(self.task_queue)} queued"
                        ),
                        tools_used=tools[:20],
                        errors=errors_list[:5],
                        goals_progressed=goals[:5],
                    )
                    self.self_reflection.record_outcome(outcome)
                except Exception as e:
                    logger.debug(f"Self-reflection tick failed: {e}")

            # ── 3. Skill evolution ──
            if self.skill_evolution:
                try:
                    evolution_result = self.skill_evolution.evaluate_tick(self.tick)
                    if evolution_result.get("condemned"):
                        logger.info(
                            f"🧬 Evolution condemned {len(evolution_result['condemned'])} skills"
                        )
                except Exception as e:
                    logger.debug(f"Skill evolution tick failed: {e}")

            # ── 4. Pattern learner + fitness snapshots ──
            if self.pattern_learner:
                try:
                    fitness_dicts = []
                    if self.skill_fitness:
                        fitness_dicts = self.skill_fitness.get_fitness_dicts(
                            current_tick=self.tick, window_ticks=50,
                        )
                    events = []
                    if self.skill_fitness:
                        events = self.skill_fitness.events
                    self.pattern_learner.process_tick(
                        tick=self.tick,
                        events=events,
                        fitness_records=fitness_dicts,
                    )
                except Exception as e:
                    logger.debug(f"Pattern learner tick failed: {e}")

            # ── 5. Git brain — write episode ──
            if self.git_brain:
                try:
                    recent = self.completed_tasks[-5:]
                    episode_parts = []
                    for t in recent:
                        status = "✅" if t.get("status") == "done" else "❌"
                        episode_parts.append(
                            f"{status} [{t.get('type','')}] {t.get('description','')[:60]}"
                        )
                    summary = "; ".join(episode_parts) if episode_parts else "idle tick"
                    await self.git_brain.write_episode(self.tick, summary=summary)
                except Exception as e:
                    logger.debug(f"Git brain tick failed: {e}")

            # ── 6. Inner life — System 1 LLM pass ──
            if self.inner_life and self.agent.llm:
                try:
                    # Build context from recent activity
                    recent_ctx_parts = []
                    for t in self.completed_tasks[-3:]:
                        status = "ok" if t.get("status") == "done" else "fail"
                        recent_ctx_parts.append(
                            f"{status}: {t.get('description','')[:60]}"
                        )
                    recent_context = "; ".join(recent_ctx_parts) if recent_ctx_parts else "idle"

                    active_goal = ""
                    if self.goal_manager:
                        for g in self.goal_manager.goals.values():
                            if g.status in (GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS):
                                active_goal = g.description[:100]
                                break

                    # Generate System 1 prompt and send to LLM
                    from .inner_life import SYSTEM1_SYSTEM_PROMPT
                    user_prompt = self.inner_life.get_system1_prompt(
                        active_goal=active_goal,
                        context=recent_context,
                    )
                    messages = [
                        {"role": "system", "content": SYSTEM1_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ]
                    result = await self.agent.llm.invoke_with_tools(messages, [])
                    content = result.get("text", "") or result.get("content", "") if isinstance(result, dict) else str(result)

                    if content:
                        old_emotion = self.inner_life.emotion.primary
                        self.inner_life.process_response(content, tick=self.tick)
                        new_emotion = self.inner_life.emotion
                        if new_emotion.primary != old_emotion:
                            logger.info(
                                f"🧠 Inner life: {old_emotion} → {new_emotion.primary} "
                                f"(v={new_emotion.valence:+.1f}, a={new_emotion.arousal:.1f})"
                            )
                        else:
                            logger.debug(
                                f"Inner life: {new_emotion.primary} "
                                f"(v={new_emotion.valence:+.1f}, a={new_emotion.arousal:.1f})"
                            )
                except Exception as e:
                    logger.warning(f"Inner life tick failed: {e}")

        except Exception as e:
            logger.warning(f"Cognitive tick failed: {e}")

    async def _perform_maintenance(self):
        """Perform system maintenance tasks"""
        try:
            # Memory consolidation
            if self.cognitive_memory and hasattr(self.cognitive_memory, "consolidate"):
                try:
                    self.cognitive_memory.consolidate()
                except Exception:
                    pass

            # Clean up old completed tasks (keep last 100)
            if len(self.completed_tasks) > 100:
                self.completed_tasks = self.completed_tasks[-100:]

            # Save state
            await self._save_state()

        except Exception as e:
            logger.error(f"Maintenance failed: {e}")

    async def _save_state(self):
        """Save autonomous agent state including tick counter"""
        try:
            state_file = Path(
                getattr(self.agent, "_data_dir", None)
                or os.environ.get("_SABLE_DATA_DIR")
                or "./data"
            ) / "autonomous_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "tick": self.tick,
                "task_queue": self.task_queue,
                "completed_tasks": self.completed_tasks[-50:],  # Keep last 50
                "last_update": datetime.now().isoformat(),
            }

            state_file.write_text(json.dumps(state, indent=2, default=str))

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def _load_state(self):
        """Load autonomous agent state including tick counter"""
        try:
            state_file = Path(
                getattr(self.agent, "_data_dir", None)
                or os.environ.get("_SABLE_DATA_DIR")
                or "./data"
            ) / "autonomous_state.json"

            if state_file.exists():
                state = json.loads(state_file.read_text())
                self.tick = state.get("tick", 0)
                self.task_queue = state.get("task_queue", [])
                self.completed_tasks = state.get("completed_tasks", [])

                # Restore datetime objects from ISO strings
                for task_list in (self.task_queue, self.completed_tasks):
                    for task in task_list:
                        for dt_key in ("created_at", "completed_at"):
                            val = task.get(dt_key)
                            if isinstance(val, str):
                                try:
                                    task[dt_key] = datetime.fromisoformat(val)
                                except (ValueError, TypeError):
                                    task[dt_key] = datetime.now()

                logger.info(f"Loaded autonomous state — resuming at tick {self.tick}")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current autonomous agent status"""
        status = {
            "running": self.running,
            "tick": self.tick,
            "tasks_queued": len(self.task_queue),
            "tasks_completed": len(self.completed_tasks),
            "enabled_sources": self.enabled_sources,
            "check_interval": self.check_interval,
            "current_tasks": self.task_queue[:5],  # Show next 5 tasks
        }
        if self.sub_agent_manager:
            status["sub_agents"] = self.sub_agent_manager.get_status()
        if self.skill_fitness:
            status["skill_fitness"] = {
                "tracked_events": self.skill_fitness.event_count,
            }
        if self.proactive_engine:
            status["proactive"] = self.proactive_engine.get_stats()
        if self.react_executor:
            status["react"] = self.react_executor.get_stats()
        if self.github_skill and self.github_skill.is_available():
            status["github"] = True
        return status

    def add_task(self, task: Dict):
        """Manually add a task to the queue"""
        if "id" not in task:
            task["id"] = f"manual_{datetime.now().timestamp()}"
        if "created_at" not in task:
            task["created_at"] = datetime.now()

        self.task_queue.append(task)
        logger.info(f"Manually added task: {task.get('description', task['id'])}")
