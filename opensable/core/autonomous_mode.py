"""
Autonomous Agent Mode - Tick-based continuous operation.

Tick-based continuous autonomous operation.  Each tick is a numbered cycle:
  discover → plan → execute → learn → trace → advance

The tick counter persists across restarts.  An append-only JSONL trace
records every phase of every tick for post-hoc observability.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from .agent import SableAgent
from .goal_system import GoalManager

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

        # ── Initialize tick-based modules ───────────────────────────────
        data_dir = Path(getattr(self.config, "data_dir", "./data"))

        try:
            from opensable.core.trace_exporter import TraceExporter
            self.trace_exporter = TraceExporter(directory=data_dir / "traces")
            logger.info("📝 Trace exporter initialized")
        except Exception as e:
            logger.warning(f"Trace exporter unavailable: {e}")

        try:
            from opensable.core.sub_agents import SubAgentManager, DEFAULT_SUB_AGENTS
            self.sub_agent_manager = SubAgentManager(self.agent)
            for spec in DEFAULT_SUB_AGENTS:
                self.sub_agent_manager.register(spec)
            logger.info(f"🤖 Sub-agent manager: {len(DEFAULT_SUB_AGENTS)} agents registered")
        except Exception as e:
            logger.warning(f"Sub-agent manager unavailable: {e}")

        try:
            from opensable.core.skill_fitness import SkillFitnessTracker
            self.skill_fitness = SkillFitnessTracker(directory=data_dir / "fitness")
            logger.info("🏋️ Skill fitness tracker initialized")
        except Exception as e:
            logger.warning(f"Skill fitness tracker unavailable: {e}")

        try:
            from opensable.core.conversation_log import ConversationLogger
            self.conversation_logger = ConversationLogger(directory=data_dir / "conversations")
            logger.info("💬 Conversation logger initialized")
        except Exception as e:
            logger.warning(f"Conversation logger unavailable: {e}")

        try:
            from opensable.core.cognitive_memory import CognitiveMemoryManager
            self.cognitive_memory = CognitiveMemoryManager(directory=data_dir / "cognitive_memory")
            logger.info("🧠 Cognitive memory initialized")
        except Exception as e:
            logger.warning(f"Cognitive memory unavailable: {e}")

        try:
            from opensable.core.self_reflection import ReflectionEngine
            self.self_reflection = ReflectionEngine(directory=data_dir / "reflection")
            logger.info("🪞 Self-reflection engine initialized")
        except Exception as e:
            logger.warning(f"Self-reflection unavailable: {e}")

        try:
            from opensable.core.skill_evolution import SkillEvolutionManager
            self.skill_evolution = SkillEvolutionManager(directory=data_dir / "skill_evolution")
            logger.info("🧬 Skill evolution manager initialized")
        except Exception as e:
            logger.warning(f"Skill evolution unavailable: {e}")

        try:
            from opensable.core.git_brain import GitBrain
            self.git_brain = GitBrain(repo_dir=Path("."))
            await self.git_brain.initialize()
            logger.info("📓 Git brain initialized")
        except Exception as e:
            logger.warning(f"Git brain unavailable: {e}")

        try:
            from opensable.core.inner_life import InnerLifeProcessor
            self.inner_life = InnerLifeProcessor(data_dir=data_dir / "inner_life")
            logger.info("💭 Inner life processor initialized")
        except Exception as e:
            logger.warning(f"Inner life unavailable: {e}")

        try:
            from opensable.core.pattern_learner import PatternLearningManager
            self.pattern_learner = PatternLearningManager(directory=data_dir / "patterns")
            logger.info("🔍 Pattern learner initialized")
        except Exception as e:
            logger.warning(f"Pattern learner unavailable: {e}")

        try:
            from opensable.core.proactive_reasoning import ProactiveReasoningEngine
            think_interval = getattr(self.config, "proactive_think_every_n_ticks", 5)
            max_risk = getattr(self.config, "proactive_max_risk", "medium")
            self.proactive_engine = ProactiveReasoningEngine(
                directory=data_dir / "proactive",
                think_every_n_ticks=think_interval,
                max_risk_level=max_risk,
            )
            logger.info(f"🧠 Proactive reasoning initialized (every {think_interval} ticks)")
        except Exception as e:
            logger.warning(f"Proactive reasoning unavailable: {e}")

        try:
            from opensable.core.react_executor import ReActExecutor
            self.react_executor = ReActExecutor(
                max_steps=getattr(self.config, "react_max_steps", 8),
                timeout_s=getattr(self.config, "react_timeout_s", 180.0),
                log_dir=data_dir / "react_logs",
            )
            logger.info("⚡ ReAct executor initialized")
        except Exception as e:
            logger.warning(f"ReAct executor unavailable: {e}")

        try:
            from opensable.skills.automation.github_skill import GitHubSkill
            self.github_skill = GitHubSkill(self.config)
            gh_ok = await self.github_skill.initialize()
            if gh_ok:
                logger.info("🐙 GitHub skill initialized")
            else:
                self.github_skill = None
        except Exception as e:
            logger.warning(f"GitHub skill unavailable: {e}")

        # Load persisted tick counter
        await self._load_state()

        # Initialize goal manager if Agentic AI is available
        try:
            from opensable.core.agi_integration import AGIAgent

            if hasattr(self.agent, "agi"):
                self.goal_manager = self.agent.agi.goals
                logger.info("Agentic AI goal system available")
        except ImportError:
            logger.warning("Agentic AI not available, using basic autonomous mode")

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

        self.running = True

        # Start main loop
        await self._autonomous_loop()

    async def stop(self):
        """Stop autonomous operation"""
        logger.info("Stopping autonomous mode...")
        self.running = False
        if self.x_autoposter:
            await self.x_autoposter.stop()

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

                # Wait before next tick
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in tick {self.tick}: {e}")
                if self.trace_exporter:
                    self.trace_exporter.record_event(
                        "tick_error",
                        summary=str(e),
                        tick=self.tick,
                    )
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
        """Parse LLM JSON output and inject tasks into the queue."""
        import re as _re

        text = llm_text.strip()

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

        injected = 0
        for item in items[:5]:  # Max 5 tasks per source
            if not isinstance(item, dict):
                continue
            desc = item.get("description", "").strip()
            if not desc or len(desc) < 5:
                continue

            task_id = f"{source}_{self.tick}_{injected}"
            if any(t.get("description") == desc for t in self.task_queue):
                continue  # Dedup

            self.task_queue.append({
                "id": task_id,
                "type": item.get("type", source),
                "description": desc,
                "priority": _parse_priority(item.get("priority", 5)),
                "created_at": datetime.now(),
                "source": source,
            })
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

    async def _check_goals(self):
        """Check for pending goals (Agentic AI mode)"""
        if not self.goal_manager:
            return

        try:
            # Get active goals
            active_goals = [g for g in self.goal_manager.goals.values() if g.status == "active"]

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
        """Prioritize tasks in queue"""
        # Sort by priority (higher first)
        self.task_queue.sort(key=lambda t: t.get("priority", 0), reverse=True)

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
                self.completed_tasks.append(task)

                logger.info(
                    f"✅ Task {task['id']} done ({duration_ms:.0f}ms): "
                    f"{task.get('description', '')[:60]}"
                )

                # Store outcome in cognitive memory for future reasoning
                self._record_outcome(task, success=True, result=result)

            except Exception as e:
                duration_ms = (time.monotonic() - start_time) * 1000

                # ── Failure: record for learning ──
                self.task_queue.remove(task)
                task["completed_at"] = datetime.now()
                task["result"] = str(e)[:500]
                task["status"] = "error"
                task["duration_ms"] = duration_ms
                self.completed_tasks.append(task)

                logger.error(
                    f"❌ Task {task['id']} failed ({duration_ms:.0f}ms): {e}"
                )

                self._record_outcome(task, success=False, result=e)

    def _record_outcome(self, task: Dict, success: bool, result: Any):
        """Record task outcome for learning — feeds cognitive memory + proactive reasoning."""
        description = task.get("description", "")[:200]
        task_type = task.get("type", "unknown")
        duration_ms = task.get("duration_ms", 0)

        # 1. Store in cognitive memory (if available)
        if self.cognitive_memory:
            try:
                importance = 0.7 if success else 0.9  # Failures are more memorable
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
                                self.goal_manager.goals[goal_id].status = "completed"
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
            if self.inner_life and hasattr(self.inner_life, "state"):
                try:
                    cognitive_state["emotion"] = str(self.inner_life.state.emotion.trigger)
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
                        if g.status == "active":
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
                            if g.status == "active":
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
                            if g.status == "active":
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
                        self.inner_life.process_response(content, tick=self.tick)
                        logger.debug(
                            f"Inner life: emotion={self.inner_life.emotion.primary}, "
                            f"valence={self.inner_life.emotion.valence:+.1f}"
                        )
                except Exception as e:
                    logger.debug(f"Inner life tick failed: {e}")

        except Exception as e:
            logger.warning(f"Cognitive tick failed: {e}")

    async def _perform_maintenance(self):
        """Perform system maintenance tasks"""
        try:
            # Memory consolidation
            if hasattr(self.agent, "memory"):
                # This would be handled by the advanced memory system
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
            state_file = Path(getattr(self.config, "data_dir", "./data")) / "autonomous_state.json"
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
            state_file = Path(getattr(self.config, "data_dir", "./data")) / "autonomous_state.json"

            if state_file.exists():
                state = json.loads(state_file.read_text())
                self.tick = state.get("tick", 0)
                self.task_queue = state.get("task_queue", [])
                self.completed_tasks = state.get("completed_tasks", [])
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
