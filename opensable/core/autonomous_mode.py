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
        """Check calendar for upcoming events requiring action"""
        try:
            # Get upcoming events in next 24 hours
            result = await self.agent.tools.execute(
                "calendar", {"action": "list", "timeframe": "24h"}
            )

            # Parse events and create tasks
            # (This would parse the actual calendar data)
            logger.debug("Checked calendar for tasks")

        except Exception as e:
            logger.error(f"Failed to check calendar: {e}")

    async def _check_email(self):
        """Check email for action items"""
        try:
            # Check for unread emails with high priority
            result = await self.agent.tools.execute(
                "email", {"action": "read", "filter": "unread", "limit": 10}
            )

            # Analyze emails for tasks (using LLM)
            # Example: "Meeting at 3pm tomorrow" -> Create reminder task
            logger.debug("Checked email for tasks")

        except Exception as e:
            logger.error(f"Failed to check email: {e}")

    async def _check_system(self):
        """Monitor system resources and create maintenance tasks"""
        try:
            # Get system info
            result = await self.agent.tools.execute("system_info", {})

            # Check if action needed (e.g., disk space low, high CPU)
            # This would parse the system info and create tasks if needed
            logger.debug("Checked system resources")

        except Exception as e:
            logger.error(f"Failed to check system: {e}")

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
        
        Concurrent task execution causes multiple simultaneous API calls,
        which gets detected as bot behavior. A real user does one thing at a time.
        """
        # Get tasks to execute (up to max_concurrent)
        tasks_to_execute = self.task_queue[: self.max_concurrent_tasks]

        if not tasks_to_execute:
            return

        logger.info(f"Executing {len(tasks_to_execute)} task(s) sequentially...")

        # Execute tasks SEQUENTIALLY — never concurrent
        results = []
        for task in tasks_to_execute:
            try:
                result = await self._execute_single_task(task)
                results.append(result)
            except Exception as e:
                results.append(e)

        # Process results
        for task, result in zip(tasks_to_execute, results):
            if isinstance(result, Exception):
                logger.error(f"Task {task['id']} failed: {result}")
            else:
                logger.info(f"Task {task['id']} completed successfully")

                # Move to completed
                self.task_queue.remove(task)
                task["completed_at"] = datetime.now()
                task["result"] = result
                self.completed_tasks.append(task)

    async def _execute_single_task(self, task: Dict) -> Any:
        """Execute a single task"""
        task_type = task.get("type")

        if task_type == "goal":
            # Execute goal using Agentic AI
            if self.goal_manager:
                goal_id = task["id"]
                return await self.goal_manager.execute_goal(goal_id)

        elif task_type == "command":
            # Execute command
            command = task.get("command")
            return await self.agent.tools.execute("execute_command", {"command": command})

        elif task_type == "reminder":
            # Send reminder
            message = task.get("message")
            logger.info(f"Reminder: {message}")
            return message

        elif task_type == "proactive":
            # Execute proactive task via ReAct loop
            return await self._execute_proactive_task(task)

        else:
            # Unknown type — try ReAct if available
            if self.react_executor and self.agent.llm:
                return await self._execute_via_react(task.get("description", str(task)))
            logger.warning(f"Unknown task type: {task_type}")
            return None

    async def _self_improve(self):
        """Run self-improvement (Agentic AI meta-learning)"""
        if not self.goal_manager:
            return

        try:
            # Run self-improvement every 24 hours
            if not hasattr(self, "_last_improvement"):
                self._last_improvement = datetime.now() - timedelta(hours=25)

            if datetime.now() - self._last_improvement >= timedelta(hours=24):
                logger.info("Running self-improvement...")

                # Use Agentic AI meta-learning
                if hasattr(self.agent, "agi"):
                    improvement = await self.agent.agi.self_improve()
                    logger.info(f"Self-improvement complete: {improvement}")

                self._last_improvement = datetime.now()

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
          2. Self-reflection — pattern detection + stagnation check
          3. Skill evolution — natural selection + mutation + niche
          4. Pattern learner — windowed analysis + snapshots + rules
          5. Git brain — write episode + optional auto-commit
          6. Inner life — System 1 update
        """
        try:
            # 1. Cognitive memory
            if self.cognitive_memory:
                try:
                    self.cognitive_memory.process_tick(self.tick)
                except Exception as e:
                    logger.debug(f"Cognitive memory tick failed: {e}")

            # 2. Self-reflection
            if self.self_reflection:
                try:
                    completed_count = len(self.completed_tasks)
                    errors_count = sum(
                        1 for t in self.completed_tasks
                        if t.get("status") == "error"
                    )
                    from .self_reflection import TickOutcome
                    outcome = TickOutcome(
                        tick=self.tick,
                        success=errors_count == 0,
                        summary=f"Tick {self.tick}: {completed_count} tasks",
                        tools_used=[],
                        errors=[],
                        goals_progressed=[],
                    )
                    self.self_reflection.record_outcome(outcome)
                except Exception as e:
                    logger.debug(f"Self-reflection tick failed: {e}")

            # 3. Skill evolution
            if self.skill_evolution:
                try:
                    evolution_result = self.skill_evolution.evaluate_tick(self.tick)
                    if evolution_result.get("condemned"):
                        logger.info(
                            f"🧬 Evolution condemned {len(evolution_result['condemned'])} skills"
                        )
                except Exception as e:
                    logger.debug(f"Skill evolution tick failed: {e}")

            # 4. Pattern learner + fitness snapshots
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

            # 5. Git brain — write episode
            if self.git_brain:
                try:
                    await self.git_brain.write_episode(
                        self.tick,
                        summary=f"{len(self.completed_tasks)} tasks completed",
                    )
                except Exception as e:
                    logger.debug(f"Git brain tick failed: {e}")

            # 6. Inner life — update emotional state
            if self.inner_life:
                try:
                    self.inner_life.state.emotion.trigger = (
                        f"tick_{self.tick}"
                    )
                    # Save state using the module-level function
                    from opensable.core.inner_life import save_inner_state
                    save_inner_state(self.inner_life.state, self.inner_life.data_dir)
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
