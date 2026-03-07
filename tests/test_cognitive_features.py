"""
Tests for cognitive autonomy features:
  1. TraceExporter (JSONL append-only trace)
  2. SkillFitnessTracker (event-sourced fitness scoring)
  3. ConversationLogger (cross-session persistence)
  4. SubAgentManager (actor-model delegation)
  5. AutonomousMode tick-based loop
"""

import asyncio
import json
import time
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TraceExporter
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceExporter:
    """Tests for JSONL append-only trace exporter."""

    def test_record_event_creates_file(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        exporter.record_event(
            "test", summary="hello world", user_id="test_agent"
        )

        # Should have created a JSONL file
        files = list((tmp_path / "traces").glob("*.jsonl"))
        assert len(files) == 1

        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["event_type"] == "test"
        assert event["summary"] == "hello world"
        assert "ts" in event

    def test_multiple_events_append(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        for i in range(5):
            exporter.record_event(
                "step", summary=f"step {i}", user_id="test"
            )

        files = list((tmp_path / "traces").glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 5

    def test_record_tool_call(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        exporter.record_tool_call(
            tool_name="browser_search",
            args={"query": "python asyncio"},
            user_id="test",
        )

        events = exporter.read_events()
        assert len(events) == 1
        assert events[0].event_type == "tool_call"
        assert events[0].tool == "browser_search"

    def test_record_tool_result(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        exporter.record_tool_result(
            tool_name="browser_search",
            result="Found 10 results",
            success=True,
            duration_ms=150,
            user_id="test",
        )

        events = exporter.read_events()
        assert len(events) == 1
        assert events[0].event_type == "tool_result"
        assert events[0].outcome == "success"

    def test_tick_start_end(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        exporter.record_tick_start(tick=0)
        exporter.record_tick_end(tick=0, summary="done")

        events = exporter.read_events()
        assert len(events) == 2
        # read_events returns most recent first
        types = {e.event_type for e in events}
        assert "tick_start" in types
        assert "tick_end" in types

    def test_session_stats(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        session = "sess-123"
        exporter.record_event(
            "tool_call", summary="t1", run_id=session
        )
        exporter.record_event(
            "tool_result", summary="t2", run_id=session
        )
        exporter.record_event(
            "synthesis", summary="done", run_id=session
        )

        stats = exporter.session_stats(session)
        assert stats["total_steps"] == 3

    def test_read_events_with_filter(self, tmp_path):
        from opensable.core.trace_exporter import TraceExporter

        exporter = TraceExporter(directory=tmp_path / "traces")
        exporter.record_event("plan", summary="p1", user_id="a")
        exporter.record_event("tool_call", summary="tc", user_id="a")
        exporter.record_event("plan", summary="p2", user_id="a")

        plans = exporter.read_events(event_type="plan")
        assert len(plans) == 2
        assert all(e.event_type == "plan" for e in plans)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SkillFitnessTracker
# ═══════════════════════════════════════════════════════════════════════════════


class TestSkillFitnessTracker:
    """Tests for event-sourced fitness scoring."""

    def test_record_created(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker = SkillFitnessTracker(directory=tmp_path / "fitness")
        tracker.record_created("weather_alerts")

        fitness = tracker.get_fitness("weather_alerts")
        assert fitness is not None
        assert fitness.name == "weather_alerts"
        assert fitness.usage_count == 0
        assert fitness.error_count == 0

    def test_fitness_increases_with_use(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker = SkillFitnessTracker(directory=tmp_path / "fitness")
        tracker.record_created("skill_a")
        f1 = tracker.get_fitness("skill_a")

        tracker.record_used("skill_a")
        tracker.record_used("skill_a")
        tracker.record_used("skill_a")
        f2 = tracker.get_fitness("skill_a")

        assert f2.fitness_score >= f1.fitness_score
        assert f2.usage_count == 3

    def test_fitness_decreases_with_errors(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker = SkillFitnessTracker(directory=tmp_path / "fitness")
        # Use tick numbers to give the skill a non-zero ticks_alive
        tracker.record_created("buggy")
        tracker.record_used("buggy", tick=1)
        tracker.record_used("buggy", tick=2)
        tracker.record_used("buggy", tick=3)
        f_good = tracker.get_fitness("buggy")

        tracker.record_error("buggy", error="TypeError: bad arg", tick=4)
        tracker.record_error("buggy", error="ConnectionError", tick=5)
        f_bad = tracker.get_fitness("buggy")

        # Errors reduce quality factor
        assert f_bad.error_count == 2
        assert f_bad.usage_count == 5  # 3 used + 2 errors counted as uses
        assert f_bad.fitness_score <= f_good.fitness_score

    def test_evolution_recorded(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker = SkillFitnessTracker(directory=tmp_path / "fitness")
        tracker.record_created("v1_skill")
        tracker.record_evolved("v1_skill", details="improved performance")

        f = tracker.get_fitness("v1_skill")
        assert f.times_evolved > 0

    def test_rankings_summary(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker = SkillFitnessTracker(directory=tmp_path / "fitness")
        tracker.record_created("a")
        tracker.record_created("b")
        tracker.record_created("c")
        tracker.record_used("b")
        tracker.record_used("b")
        tracker.record_used("c")

        rankings = tracker.get_rankings_summary()
        assert isinstance(rankings, str)
        assert "SKILL FITNESS RANKINGS" in rankings
        assert "b" in rankings

    def test_persistence_across_instances(self, tmp_path):
        from opensable.core.skill_fitness import SkillFitnessTracker

        tracker1 = SkillFitnessTracker(directory=tmp_path / "fitness")
        tracker1.record_created("persistent_skill")
        tracker1.record_used("persistent_skill")

        # New instance reads from same directory
        tracker2 = SkillFitnessTracker(directory=tmp_path / "fitness")
        f = tracker2.get_fitness("persistent_skill")
        assert f is not None
        assert f.usage_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ConversationLogger
# ═══════════════════════════════════════════════════════════════════════════════


class TestConversationLogger:
    """Tests for cross-session conversation persistence."""

    def test_save_and_load(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        logger.save_conversation(
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            user_id="alice",
            run_id="r1",
        )

        turns = logger.load_recent(user_id="alice", last_n=10)
        assert len(turns) == 1
        assert turns[0].user_message == "Hello"
        assert turns[0].agent_response == "Hi there!"

    def test_multi_turn_conversation(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        for i in range(5):
            logger.save_conversation(
                messages=[
                    {"role": "user", "content": f"msg {i}"},
                    {"role": "assistant", "content": f"reply {i}"},
                ],
                user_id="bob",
                run_id=f"r{i}",
            )

        turns = logger.load_recent(user_id="bob", last_n=3)
        assert len(turns) == 3
        # Most recent last (chronological order from file)
        assert turns[-1].user_message == "msg 4"

    def test_build_context_prompt(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        logger.save_conversation(
            messages=[
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "A programming language."},
            ],
            user_id="eve",
            run_id="r1",
        )

        ctx = logger.build_context_prompt(user_id="eve", last_n=5)
        assert "What is Python?" in ctx
        assert "programming language" in ctx

    def test_per_user_isolation(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        logger.save_conversation(
            messages=[
                {"role": "user", "content": "Alice's msg"},
                {"role": "assistant", "content": "For Alice"},
            ],
            user_id="alice",
            run_id="r1",
        )
        logger.save_conversation(
            messages=[
                {"role": "user", "content": "Bob's msg"},
                {"role": "assistant", "content": "For Bob"},
            ],
            user_id="bob",
            run_id="r2",
        )

        alice_turns = logger.load_recent(user_id="alice", last_n=10)
        bob_turns = logger.load_recent(user_id="bob", last_n=10)
        assert len(alice_turns) == 1
        assert len(bob_turns) == 1
        assert alice_turns[0].user_message == "Alice's msg"
        assert bob_turns[0].user_message == "Bob's msg"

    def test_trim_history(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        for i in range(20):
            logger.save_conversation(
                messages=[
                    {"role": "user", "content": f"msg {i}"},
                    {"role": "assistant", "content": f"reply {i}"},
                ],
                user_id="trimtest",
                run_id=f"r{i}",
            )

        trimmed = logger.trim_history(user_id="trimtest", keep_last=5)
        assert trimmed >= 15

        remaining = logger.load_recent(user_id="trimtest", last_n=100)
        assert len(remaining) == 5

    def test_get_stats(self, tmp_path):
        from opensable.core.conversation_log import ConversationLogger

        logger = ConversationLogger(directory=tmp_path / "conv")
        logger.save_conversation(
            messages=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            user_id="stats_user",
            run_id="r1",
        )

        stats = logger.get_stats(user_id="stats_user")
        assert stats["total_turns"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SubAgentManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubAgentManager:
    """Tests for actor-model sub-agent delegation."""

    def test_register_and_list(self):
        from opensable.core.sub_agents import SubAgentManager, SubAgentSpec

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        mgr.register(SubAgentSpec(
            name="test_agent",
            description="A test agent",
        ))

        assert "test_agent" in mgr.registered_agents
        assert mgr.pending_count == 0
        assert mgr.completed_count == 0

    def test_unregister(self):
        from opensable.core.sub_agents import SubAgentManager, SubAgentSpec

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        mgr.register(SubAgentSpec(name="a", description="A"))
        assert mgr.unregister("a")
        assert "a" not in mgr.registered_agents
        assert not mgr.unregister("nonexistent")

    def test_get_status(self):
        from opensable.core.sub_agents import SubAgentManager, SubAgentSpec

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        mgr.register(SubAgentSpec(name="researcher", description="Research"))

        status = mgr.get_status()
        assert "researcher" in status["registered_agents"]
        assert len(status["pending_tasks"]) == 0
        assert "researcher" in status["specs"]

    def test_default_sub_agents_registered(self):
        from opensable.core.sub_agents import SubAgentManager, DEFAULT_SUB_AGENTS

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        for spec in DEFAULT_SUB_AGENTS:
            mgr.register(spec)

        assert "researcher" in mgr.registered_agents
        assert "coder" in mgr.registered_agents
        assert "analyst" in mgr.registered_agents
        assert "communicator" in mgr.registered_agents

    @pytest.mark.asyncio
    async def test_delegate_unknown_agent_raises(self):
        from opensable.core.sub_agents import SubAgentManager

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        with pytest.raises(ValueError, match="Unknown sub-agent"):
            await mgr.delegate("nonexistent", "do something")

    def test_clear_inbox(self):
        from opensable.core.sub_agents import SubAgentManager, SubAgentResult

        class FakeAgent:
            pass

        mgr = SubAgentManager(FakeAgent())
        # Manually add a result to test clear
        mgr._results["fake_0"] = SubAgentResult(
            task_id="fake_0",
            agent_name="fake",
            task="test task",
            result="done",
            status="completed",
            duration_ms=100,
        )

        assert mgr.completed_count == 1
        cleared = mgr.clear_inbox()
        assert cleared == 1
        assert mgr.completed_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AutonomousMode tick-based loop
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutonomousModeTick:
    """Tests for tick-based autonomous loop."""

    def _make_mode(self, tmp_path):
        """Create an AutonomousMode with minimal mock agent."""

        class MockConfig:
            autonomous_check_interval = 1
            autonomous_max_tasks = 3
            autonomous_sources = []
            data_dir = str(tmp_path / "data")

        class MockTools:
            async def execute(self, *a, **k):
                return ""
            def get_tool_schemas(self):
                return []

        class MockLLM:
            pass

        class MockAgent:
            tools = MockTools()
            llm = MockLLM()
            agi = None

        from opensable.core.autonomous_mode import AutonomousMode
        return AutonomousMode(MockAgent(), MockConfig())

    def test_init_tick_state(self, tmp_path):
        mode = self._make_mode(tmp_path)
        assert mode.tick == 0
        assert mode.trace_exporter is None
        assert mode.sub_agent_manager is None

    @pytest.mark.asyncio
    async def test_save_and_load_tick(self, tmp_path):
        mode = self._make_mode(tmp_path)
        mode.tick = 42
        mode.task_queue = [{"id": "t1", "type": "test", "priority": 5}]
        await mode._save_state()

        mode2 = self._make_mode(tmp_path)
        await mode2._load_state()
        assert mode2.tick == 42
        assert len(mode2.task_queue) == 1

    def test_get_status_includes_tick(self, tmp_path):
        mode = self._make_mode(tmp_path)
        mode.tick = 7
        status = mode.get_status()
        assert status["tick"] == 7
        assert "tasks_queued" in status


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Integration: checkpoint_to_trace_events
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckpointTraceIntegration:
    """Test converting checkpoints to trace events."""

    def test_checkpoint_to_trace_events(self):
        from opensable.core.checkpointing import Checkpoint
        from opensable.core.trace_exporter import checkpoint_to_trace_events

        cp = Checkpoint(run_id="test-run", user_id="alice", original_message="hello")
        cp.record_plan(["step 1", "step 2"])
        cp.record_tool_call("browser_search", {"query": "test"})
        cp.record_tool_result("browser_search", "results", success=True)
        cp.record_synthesis("Final answer")

        events = checkpoint_to_trace_events(cp.to_dict())
        assert len(events) == 4
        assert events[0].event_type == "plan"
        assert events[1].event_type == "tool_call"
        assert events[2].event_type == "tool_result"
        assert events[3].event_type == "synthesis"
        assert all(e.run_id == "test-run" for e in events)
        assert all(e.session_id == "alice" for e in events)
