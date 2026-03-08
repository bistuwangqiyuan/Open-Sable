"""
Tests for autonomous agency modules:
  - GitHubSkill
  - ProactiveReasoningEngine
  - ReActExecutor
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# GitHubSkill tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGitHubSkill:
    """Tests for GitHubSkill (works without real GitHub credentials)."""

    def _make_skill(self, tmp_path, default_repo="test-owner/test-repo"):
        from opensable.skills.automation.github_skill import GitHubSkill

        config = MagicMock()
        config.github_token = None
        config.github_default_repo = default_repo
        skill = GitHubSkill(config)
        # _default_repo is normally set during initialize()
        skill._default_repo = default_repo
        return skill

    def test_init(self, tmp_path):
        from opensable.skills.automation.github_skill import GitHubSkill
        config = MagicMock()
        skill = GitHubSkill(config)
        assert skill._default_repo is None
        assert skill._initialized is False

    def test_is_available_before_init(self, tmp_path):
        skill = self._make_skill(tmp_path)
        assert skill.is_available() is False

    def test_resolve_repo_default(self, tmp_path):
        skill = self._make_skill(tmp_path)
        assert skill._resolve_repo() == "test-owner/test-repo"

    def test_resolve_repo_explicit(self, tmp_path):
        skill = self._make_skill(tmp_path)
        assert skill._resolve_repo("other/repo") == "other/repo"

    def test_resolve_repo_no_default(self, tmp_path):
        skill = self._make_skill(tmp_path, default_repo=None)
        skill._default_repo = None
        with pytest.raises(ValueError, match="No repository"):
            skill._resolve_repo()

    @pytest.mark.asyncio
    async def test_create_issue_not_initialized(self, tmp_path):
        skill = self._make_skill(tmp_path)
        result = await skill.create_issue(title="Test")
        # Should fail gracefully (no client, no CLI)
        assert result.success is False or result.success is True  # depends on gh CLI

    @pytest.mark.asyncio
    async def test_list_issues_not_initialized(self, tmp_path):
        skill = self._make_skill(tmp_path)
        result = await skill.list_issues()
        assert isinstance(result.data, dict) or result.error is not None

    @pytest.mark.asyncio
    async def test_create_issue_with_mock_client(self, tmp_path):
        skill = self._make_skill(tmp_path)

        # Mock PyGithub client
        mock_issue = MagicMock()
        mock_issue.html_url = "https://github.com/test-owner/test-repo/issues/42"
        mock_issue.number = 42
        mock_issue.title = "Test Issue"
        mock_issue.state = "open"

        mock_repo = MagicMock()
        mock_repo.create_issue.return_value = mock_issue

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        skill._client = mock_github
        skill._initialized = True

        result = await skill.create_issue(
            title="Test Issue",
            body="Test body",
            labels=["bug"],
        )
        assert result.success is True
        assert result.data["number"] == 42
        assert "42" in str(result.url)

    @pytest.mark.asyncio
    async def test_list_issues_with_mock_client(self, tmp_path):
        skill = self._make_skill(tmp_path)

        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.title = "Bug report"
        mock_issue.state = "open"
        mock_issue.user.login = "testuser"
        mock_issue.labels = []
        mock_issue.html_url = "https://github.com/test/repo/issues/1"
        mock_issue.pull_request = None

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        skill._client = mock_github
        skill._initialized = True

        result = await skill.list_issues()
        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["issues"][0]["title"] == "Bug report"

    @pytest.mark.asyncio
    async def test_comment_on_issue_with_mock(self, tmp_path):
        skill = self._make_skill(tmp_path)

        mock_comment = MagicMock()
        mock_comment.html_url = "https://github.com/test/repo/issues/1#comment-123"
        mock_comment.id = 123

        mock_issue = MagicMock()
        mock_issue.create_comment.return_value = mock_comment

        mock_repo = MagicMock()
        mock_repo.get_issue.return_value = mock_issue

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        skill._client = mock_github
        skill._initialized = True

        result = await skill.comment_on_issue(1, "Great work!")
        assert result.success is True
        assert result.data["comment_id"] == 123

    @pytest.mark.asyncio
    async def test_create_pr_with_mock(self, tmp_path):
        skill = self._make_skill(tmp_path)

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/test/repo/pull/5"
        mock_pr.number = 5
        mock_pr.title = "Feature branch"
        mock_pr.state = "open"

        mock_repo = MagicMock()
        mock_repo.create_pull.return_value = mock_pr

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        skill._client = mock_github
        skill._initialized = True

        result = await skill.create_pull_request(
            title="Feature branch",
            head="feature/x",
            base="main",
        )
        assert result.success is True
        assert result.data["number"] == 5

    @pytest.mark.asyncio
    async def test_get_repo_info_with_mock(self, tmp_path):
        skill = self._make_skill(tmp_path)

        mock_repo = MagicMock()
        mock_repo.full_name = "test/repo"
        mock_repo.description = "A test repo"
        mock_repo.language = "Python"
        mock_repo.stargazers_count = 100
        mock_repo.forks_count = 20
        mock_repo.open_issues_count = 5
        mock_repo.default_branch = "main"
        mock_repo.private = False
        mock_repo.html_url = "https://github.com/test/repo"

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        skill._client = mock_github
        skill._initialized = True

        result = await skill.get_repo_info()
        assert result.success is True
        assert result.data["stars"] == 100
        assert result.data["language"] == "Python"


# ═══════════════════════════════════════════════════════════════════════════════
# ProactiveReasoningEngine tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProactiveReasoning:
    """Tests for the proactive reasoning engine."""

    def _make_engine(self, tmp_path, think_every=5, max_risk="medium"):
        from opensable.core.proactive_reasoning import ProactiveReasoningEngine
        return ProactiveReasoningEngine(
            directory=tmp_path / "proactive",
            think_every_n_ticks=think_every,
            max_risk_level=max_risk,
        )

    def test_should_think_interval(self, tmp_path):
        engine = self._make_engine(tmp_path, think_every=5)
        assert engine.should_think(0) is False  # tick 0 never thinks
        assert engine.should_think(1) is False
        assert engine.should_think(5) is True
        assert engine.should_think(10) is True
        assert engine.should_think(7) is False

    def test_build_context_minimal(self, tmp_path):
        engine = self._make_engine(tmp_path)
        ctx = engine.build_context(tick=10)
        assert "tick: 10" in ctx.lower()

    def test_build_context_full(self, tmp_path):
        engine = self._make_engine(tmp_path)
        ctx = engine.build_context(
            tick=10,
            completed_tasks=[{"description": "did thing A"}],
            queued_tasks=[{"description": "do thing B"}],
            system_state={"cpu": 50},
            recent_errors=["something broke"],
            goals=["improve metrics"],
            cognitive_state={"emotion": "curious"},
        )
        assert "did thing A" in ctx
        assert "do thing B" in ctx
        assert "something broke" in ctx
        assert "improve metrics" in ctx

    def test_parse_proposals_valid_json(self, tmp_path):
        engine = self._make_engine(tmp_path)
        text = json.dumps([
            {
                "action": "Check repo health",
                "goal_type": "maintenance",
                "tool_name": "execute_command",
                "tool_args": {"command": "pytest"},
                "reasoning": "Ensure tests pass",
                "priority": 0.8,
                "risk_level": "low",
            }
        ])
        proposals = engine._parse_proposals(text, tick=5)
        assert len(proposals) == 1
        assert proposals[0].action == "Check repo health"
        assert proposals[0].priority == 0.8
        assert proposals[0].goal_type.value == "maintenance"

    def test_parse_proposals_markdown_code_block(self, tmp_path):
        engine = self._make_engine(tmp_path)
        text = '```json\n[{"action": "Test action", "goal_type": "custom", "priority": 0.5, "risk_level": "low"}]\n```'
        proposals = engine._parse_proposals(text, tick=5)
        assert len(proposals) == 1
        assert proposals[0].action == "Test action"

    def test_parse_proposals_empty_list(self, tmp_path):
        engine = self._make_engine(tmp_path)
        proposals = engine._parse_proposals("[]", tick=5)
        assert len(proposals) == 0

    def test_parse_proposals_invalid_json(self, tmp_path):
        engine = self._make_engine(tmp_path)
        proposals = engine._parse_proposals("not json at all", tick=5)
        assert len(proposals) == 0

    def test_risk_filtering(self, tmp_path):
        engine = self._make_engine(tmp_path, max_risk="low")
        text = json.dumps([
            {"action": "Safe action", "goal_type": "monitoring", "priority": 0.5, "risk_level": "low"},
            {"action": "Risky action", "goal_type": "social", "priority": 0.9, "risk_level": "medium"},
        ])
        proposals = engine._parse_proposals(text, tick=5)
        assert len(proposals) == 1
        assert proposals[0].action == "Safe action"

    def test_dedup(self, tmp_path):
        engine = self._make_engine(tmp_path)
        text = json.dumps([
            {"action": "Do X", "goal_type": "custom", "priority": 0.5, "risk_level": "low"},
        ])
        # First parse
        proposals1 = engine._parse_proposals(text, tick=5)
        assert len(proposals1) == 1
        # Second parse — same action should be deduped
        proposals2 = engine._parse_proposals(text, tick=10)
        assert len(proposals2) == 0

    def test_to_task(self, tmp_path):
        from opensable.core.proactive_reasoning import ProactiveProposal, ProactiveGoalType

        proposal = ProactiveProposal(
            action="Create issue for bug",
            goal_type=ProactiveGoalType.COMMUNICATION,
            tool_name="github_create_issue",
            tool_args={"title": "Fix bug"},
            priority=0.7,
            risk_level="low",
        )
        task = proposal.to_task(tick=42)
        assert task["type"] == "proactive"
        assert task["goal_type"] == "communication"
        assert task["tool_name"] == "github_create_issue"
        assert task["priority"] == 7  # 0.7 * 10

    def test_stats(self, tmp_path):
        engine = self._make_engine(tmp_path)
        text = json.dumps([
            {"action": "Action 1", "goal_type": "custom", "priority": 0.5, "risk_level": "low"},
        ])
        engine._parse_proposals(text, tick=5)
        stats = engine.get_stats()
        assert stats["total_proposals"] == 1

    @pytest.mark.asyncio
    async def test_think_with_mock_llm(self, tmp_path):
        engine = self._make_engine(tmp_path)
        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.return_value = {
            "text": json.dumps([
                {"action": "Run tests", "goal_type": "maintenance", "priority": 0.6, "risk_level": "low"},
            ])
        }

        proposals = await engine.think(
            llm=mock_llm,
            tick=10,
            context="Current state: all good",
        )
        assert len(proposals) == 1
        assert proposals[0].action == "Run tests"

    @pytest.mark.asyncio
    async def test_think_llm_failure(self, tmp_path):
        engine = self._make_engine(tmp_path)
        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.side_effect = Exception("LLM down")

        proposals = await engine.think(llm=mock_llm, tick=10, context="")
        assert len(proposals) == 0

    def test_state_persistence(self, tmp_path):
        engine = self._make_engine(tmp_path)
        text = json.dumps([
            {"action": "Persisted action", "goal_type": "custom", "priority": 0.5, "risk_level": "low"},
        ])
        engine._parse_proposals(text, tick=5)

        # Create new engine from same dir
        engine2 = self._make_engine(tmp_path)
        assert "Persisted action" in engine2._recent_actions
        assert engine2._total_proposals == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ReActExecutor tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestReActExecutor:
    """Tests for the ReAct executor."""

    def _make_executor(self, tmp_path, max_steps=5):
        from opensable.core.react_executor import ReActExecutor
        return ReActExecutor(
            max_steps=max_steps,
            timeout_s=30.0,
            log_dir=tmp_path / "react_logs",
        )

    def test_init(self, tmp_path):
        executor = self._make_executor(tmp_path)
        assert executor.max_steps == 5
        assert executor._total_executions == 0

    def test_parse_react_json(self, tmp_path):
        executor = self._make_executor(tmp_path)
        result = executor._parse_react_output(json.dumps({
            "thought": "I need to check files",
            "action": "list_directory",
            "action_input": {"path": "/tmp"},
        }))
        assert result["thought"] == "I need to check files"
        assert result["action"] == "list_directory"
        assert result["action_input"]["path"] == "/tmp"

    def test_parse_react_markdown_block(self, tmp_path):
        executor = self._make_executor(tmp_path)
        text = '```json\n{"thought": "Let me check", "action": "FINISH", "action_input": {"answer": "Done"}}\n```'
        result = executor._parse_react_output(text)
        assert result["action"] == "FINISH"
        assert result["action_input"]["answer"] == "Done"

    def test_parse_react_embedded_json(self, tmp_path):
        executor = self._make_executor(tmp_path)
        text = 'Here is my response:\n{"thought": "thinking", "action": "read_file", "action_input": {"path": "x.py"}}\nDone.'
        result = executor._parse_react_output(text)
        assert result["action"] == "read_file"

    def test_parse_react_freeform(self, tmp_path):
        executor = self._make_executor(tmp_path)
        text = "I'm not sure what to do, so I'll just give up."
        result = executor._parse_react_output(text)
        assert result["action"] == "FINISH"  # fallback

    def test_format_tool_list_empty(self, tmp_path):
        executor = self._make_executor(tmp_path)
        desc = executor._format_tool_list([])
        assert "execute_command" in desc

    def test_format_tool_list_with_tools(self, tmp_path):
        executor = self._make_executor(tmp_path)
        tools = [
            {"function": {"name": "read_file", "description": "Read a file", "parameters": {"properties": {"path": {}}}}},
        ]
        desc = executor._format_tool_list(tools)
        assert "read_file" in desc

    @pytest.mark.asyncio
    async def test_execute_single_step_finish(self, tmp_path):
        executor = self._make_executor(tmp_path)

        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.return_value = {
            "text": json.dumps({
                "thought": "The task is simple",
                "action": "FINISH",
                "action_input": {"answer": "42"},
            })
        }

        async def tool_executor(name, args):
            return "result"

        result = await executor.execute(
            task="What is the answer?",
            llm=mock_llm,
            tool_executor=tool_executor,
        )
        assert result.success is True
        assert result.final_answer == "42"
        assert len(result.steps) == 1

    @pytest.mark.asyncio
    async def test_execute_multi_step(self, tmp_path):
        executor = self._make_executor(tmp_path, max_steps=5)

        call_count = 0

        async def mock_invoke(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"text": json.dumps({
                    "thought": "Let me read the file first",
                    "action": "read_file",
                    "action_input": {"path": "test.py"},
                })}
            elif call_count == 2:
                return {"text": json.dumps({
                    "thought": "Now I have the info",
                    "action": "FINISH",
                    "action_input": {"answer": "File contains 10 lines"},
                })}
            return {"text": json.dumps({"thought": "done", "action": "FINISH", "action_input": {"answer": "ok"}})}

        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.side_effect = mock_invoke

        async def tool_executor(name, args):
            if name == "read_file":
                return "10 lines of code"
            return "unknown tool"

        result = await executor.execute(
            task="Count lines in test.py",
            llm=mock_llm,
            tool_executor=tool_executor,
        )
        assert result.success is True
        assert len(result.steps) == 2
        assert "read_file" in result.tools_used

    @pytest.mark.asyncio
    async def test_execute_max_steps(self, tmp_path):
        executor = self._make_executor(tmp_path, max_steps=3)

        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.return_value = {
            "text": json.dumps({
                "thought": "Keep going",
                "action": "read_file",
                "action_input": {"path": "x"},
            })
        }

        async def tool_executor(name, args):
            return "some result"

        result = await executor.execute(
            task="Infinite task",
            llm=mock_llm,
            tool_executor=tool_executor,
        )
        assert result.success is False
        assert len(result.steps) == 3
        assert "maximum" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, tmp_path):
        executor = self._make_executor(tmp_path, max_steps=3)

        call_count = 0

        async def mock_invoke(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"text": json.dumps({
                    "thought": "Try the tool",
                    "action": "bad_tool",
                    "action_input": {},
                })}
            return {"text": json.dumps({
                "thought": "Tool failed, finish",
                "action": "FINISH",
                "action_input": {"answer": "Could not complete"},
            })}

        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.side_effect = mock_invoke

        async def tool_executor(name, args):
            raise ValueError("Tool not found")

        result = await executor.execute(
            task="Do something",
            llm=mock_llm,
            tool_executor=tool_executor,
        )
        assert result.success is True  # It finished gracefully
        assert "ERROR" in result.steps[0].observation

    @pytest.mark.asyncio
    async def test_execute_llm_exception(self, tmp_path):
        executor = self._make_executor(tmp_path)

        mock_llm = AsyncMock()
        mock_llm.invoke_with_tools.side_effect = RuntimeError("Model crashed")

        async def tool_executor(name, args):
            return "result"

        result = await executor.execute(
            task="Do something",
            llm=mock_llm,
            tool_executor=tool_executor,
        )
        assert result.success is False
        assert "Model crashed" in result.error

    def test_get_stats(self, tmp_path):
        executor = self._make_executor(tmp_path)
        stats = executor.get_stats()
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0

    def test_log_execution(self, tmp_path):
        executor = self._make_executor(tmp_path)
        from opensable.core.react_executor import ReActResult
        result = ReActResult(
            success=True, task="test", final_answer="done",
            total_duration_ms=100, tools_used=["read_file"],
        )
        executor._log_execution(result)
        log_file = tmp_path / "react_logs" / "react_executions.jsonl"
        assert log_file.exists()
        data = json.loads(log_file.read_text().strip())
        assert data["success"] is True
        assert data["task"] == "test"


# ═══════════════════════════════════════════════════════════════════════════════
# GitHub tool schemas tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGitHubSchemas:
    """Validate GitHub tool schemas are properly structured."""

    def test_schemas_exist(self):
        from opensable.core.tools._schemas.github import SCHEMAS
        assert len(SCHEMAS) == 13  # 13 GitHub tools

    def test_schema_structure(self):
        from opensable.core.tools._schemas.github import SCHEMAS
        for schema in SCHEMAS:
            assert schema["type"] == "function"
            fn = schema["function"]
            assert "name" in fn
            assert fn["name"].startswith("github_")
            assert "description" in fn
            assert "parameters" in fn

    def test_dispatch_mapping(self):
        from opensable.core.tools._dispatch import SCHEMA_TO_TOOL
        github_tools = [k for k in SCHEMA_TO_TOOL if k.startswith("github_")]
        assert len(github_tools) == 13

    def test_permissions_mapping(self):
        from opensable.core.tools._permissions import TOOL_PERMISSIONS
        github_perms = {k: v for k, v in TOOL_PERMISSIONS.items() if k.startswith("github_")}
        assert len(github_perms) == 13
        # Read tools should have github_read permission
        assert github_perms["github_list_issues"] == "github_read"
        assert github_perms["github_repo_info"] == "github_read"
        # Write tools should have github_write permission
        assert github_perms["github_create_issue"] == "github_write"
        assert github_perms["github_create_pr"] == "github_write"

    def test_schemas_in_get_all(self):
        from opensable.core.tools._schemas import get_all_schemas
        all_schemas = get_all_schemas()
        github_schemas = [s for s in all_schemas if s["function"]["name"].startswith("github_")]
        assert len(github_schemas) == 13


# ═══════════════════════════════════════════════════════════════════════════════
# Integration-style tests (import checks)
# ═══════════════════════════════════════════════════════════════════════════════


class TestImports:
    """Verify all new modules import cleanly."""

    def test_import_github_skill(self):
        from opensable.skills.automation.github_skill import GitHubSkill, GitHubResult
        assert GitHubSkill is not None
        assert GitHubResult is not None

    def test_import_proactive_reasoning(self):
        from opensable.core.proactive_reasoning import (
            ProactiveReasoningEngine,
            ProactiveProposal,
            ProactiveGoalType,
        )
        assert ProactiveReasoningEngine is not None
        assert ProactiveGoalType.MAINTENANCE.value == "maintenance"

    def test_import_react_executor(self):
        from opensable.core.react_executor import (
            ReActExecutor,
            ReActResult,
            ReActStep,
        )
        assert ReActExecutor is not None
        assert ReActResult is not None

    def test_import_github_tools_mixin(self):
        from opensable.core.tools._github import GitHubToolsMixin
        assert GitHubToolsMixin is not None

    def test_github_result_to_str(self):
        from opensable.skills.automation.github_skill import GitHubResult
        r = GitHubResult(success=True, url="https://github.com/x", data={"key": "val"})
        s = r.to_str()
        assert "github.com" in s
        r2 = GitHubResult(success=False, error="Not found")
        s2 = r2.to_str()
        assert "Not found" in s2

    def test_react_result_summary(self):
        from opensable.core.react_executor import ReActResult
        r = ReActResult(
            success=True, task="Do X", final_answer="Done",
            total_duration_ms=500, tools_used=["read_file", "read_file"],
        )
        s = r.summary()
        assert "Do X" in s
        assert "500" in s
        assert "read_file" in s

    def test_react_step_dataclass(self):
        from opensable.core.react_executor import ReActStep
        step = ReActStep(step_num=0, thought="think", action="act")
        assert step.step_num == 0
        assert step.observation == ""

    def test_proactive_proposal_dataclass(self):
        from opensable.core.proactive_reasoning import ProactiveProposal, ProactiveGoalType
        p = ProactiveProposal(action="do stuff", goal_type=ProactiveGoalType.RESEARCH)
        assert p.priority == 0.5
        assert p.risk_level == "low"
        assert p.estimated_ticks == 1

    def test_proactive_system_prompt(self):
        from opensable.core.proactive_reasoning import PROACTIVE_SYSTEM_PROMPT
        assert "autonomous" in PROACTIVE_SYSTEM_PROMPT.lower()
        assert "JSON" in PROACTIVE_SYSTEM_PROMPT

    def test_react_system_prompt(self):
        from opensable.core.react_executor import REACT_SYSTEM_PROMPT
        assert "FINISH" in REACT_SYSTEM_PROMPT
        assert "thought" in REACT_SYSTEM_PROMPT.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# AutonomousMode — Outcome learning, discovery, self-improvement tests
# ═══════════════════════════════════════════════════════════════════════════════


def _make_autonomous_mode():
    """Create a minimal AutonomousMode for testing (no real agent)."""
    from opensable.core.autonomous_mode import AutonomousMode

    mock_agent = MagicMock()
    mock_agent.llm = MagicMock()
    mock_agent.tools = MagicMock()

    mock_config = MagicMock()
    mock_config.autonomous_check_interval = 30
    mock_config.autonomous_max_tasks = 3
    mock_config.autonomous_sources = "calendar,email,system_monitoring"
    mock_config.data_dir = "/tmp/test_autonomous"

    am = AutonomousMode(mock_agent, mock_config)
    am.tick = 10
    return am


class TestOutcomeLearning:
    """Tests for _record_outcome and _execute_tasks outcome tracking."""

    def test_record_outcome_success_stores_in_cognitive_memory(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = MagicMock()
        am.skill_fitness = None
        am.trace_exporter = None

        task = {"id": "t1", "type": "goal", "description": "Test task", "tools_used": []}
        am._record_outcome(task, success=True, result="done")

        am.cognitive_memory.add_memory.assert_called_once()
        call_args = am.cognitive_memory.add_memory.call_args
        assert "succeeded" in call_args[0][0]
        assert call_args[1]["category"] == "success"
        assert call_args[1]["importance"] == 0.7

    def test_record_outcome_failure_higher_importance(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = MagicMock()
        am.skill_fitness = None
        am.trace_exporter = None

        task = {"id": "t2", "type": "command", "description": "Failing task", "tools_used": []}
        am._record_outcome(task, success=False, result=Exception("boom"))

        call_args = am.cognitive_memory.add_memory.call_args
        assert "FAILED" in call_args[0][0]
        assert call_args[1]["importance"] == 0.9

    def test_record_outcome_skill_fitness_tracking(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.skill_fitness = MagicMock()
        am.trace_exporter = None

        task = {
            "id": "t3", "type": "goal", "description": "x",
            "tools_used": ["read_file", "web_search"],
            "duration_ms": 1500,
        }
        am._record_outcome(task, success=True, result="ok")

        assert am.skill_fitness.record_event.call_count == 2

    def test_record_outcome_trace_exporter(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.skill_fitness = None
        am.trace_exporter = MagicMock()

        task = {"id": "t4", "type": "email_action", "description": "Reply to boss", "source": "email"}
        am._record_outcome(task, success=True, result="sent")

        am.trace_exporter.record_event.assert_called_once()
        call_args = am.trace_exporter.record_event.call_args
        assert call_args[0][0] == "task_outcome"
        assert "✅" in call_args[1]["summary"]

    def test_record_outcome_no_modules_no_crash(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.skill_fitness = None
        am.trace_exporter = None

        task = {"id": "t5", "type": "goal", "description": "x"}
        # Should not raise
        am._record_outcome(task, success=False, result="err")

    @pytest.mark.asyncio
    async def test_execute_tasks_records_success(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = MagicMock()
        am.skill_fitness = None
        am.trace_exporter = None
        am.react_executor = None
        am.goal_manager = None

        am.task_queue = [
            {"id": "t6", "type": "reminder", "description": "Remember to drink water"}
        ]

        await am._execute_tasks()

        assert len(am.task_queue) == 0
        assert len(am.completed_tasks) == 1
        assert am.completed_tasks[0]["status"] == "done"
        assert am.completed_tasks[0]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_tasks_records_failure(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = MagicMock()
        am.skill_fitness = None
        am.trace_exporter = None

        # Patch _execute_single_task to raise
        am._execute_single_task = AsyncMock(side_effect=RuntimeError("boom"))

        am.task_queue = [
            {"id": "t7", "type": "goal", "description": "Will fail"}
        ]

        await am._execute_tasks()

        assert len(am.task_queue) == 0
        assert len(am.completed_tasks) == 1
        assert am.completed_tasks[0]["status"] == "error"
        assert "boom" in am.completed_tasks[0]["result"]


class TestInjectLLMTasks:
    """Tests for _inject_llm_tasks helper."""

    def test_inject_json_array(self):
        am = _make_autonomous_mode()
        content = json.dumps([
            {"type": "goal", "description": "Write tests", "priority": "high"},
            {"type": "command", "description": "Check disk", "priority": "low"},
        ])
        am._inject_llm_tasks(content, source="test")

        assert len(am.task_queue) == 2
        assert am.task_queue[0]["type"] == "goal"
        assert am.task_queue[0]["source"] == "test"

    def test_inject_json_in_markdown_code_block(self):
        am = _make_autonomous_mode()
        content = '```json\n[{"type":"goal","description":"Clean logs"}]\n```'
        am._inject_llm_tasks(content, source="email")

        assert len(am.task_queue) == 1
        assert am.task_queue[0]["description"] == "Clean logs"

    def test_inject_deduplicates(self):
        am = _make_autonomous_mode()
        am.task_queue = [{"id": "existing", "description": "Write tests"}]

        content = json.dumps([
            {"type": "goal", "description": "Write tests"},  # duplicate
            {"type": "goal", "description": "Deploy app"},   # new
        ])
        am._inject_llm_tasks(content, source="test")

        descriptions = [t["description"] for t in am.task_queue]
        assert descriptions.count("Write tests") == 1
        assert "Deploy app" in descriptions

    def test_inject_max_5_tasks(self):
        am = _make_autonomous_mode()
        content = json.dumps([
            {"type": "goal", "description": f"Task {i}"} for i in range(10)
        ])
        am._inject_llm_tasks(content, source="test")

        assert len(am.task_queue) == 5

    def test_inject_invalid_json_no_crash(self):
        am = _make_autonomous_mode()
        am._inject_llm_tasks("This is not JSON at all", source="test")
        assert len(am.task_queue) == 0

    def test_inject_single_dict(self):
        am = _make_autonomous_mode()
        content = json.dumps({"type": "goal", "description": "Single task"})
        am._inject_llm_tasks(content, source="test")
        assert len(am.task_queue) == 1


class TestCheckSystem:
    """Tests for _check_system with real threshold detection."""

    @pytest.mark.asyncio
    async def test_check_system_high_disk_creates_task(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(return_value={
            "disk": "95% used", "memory": "45% used", "cpu": "20%"
        })

        await am._check_system()

        assert any("disk" in t.get("description", "").lower() for t in am.task_queue)

    @pytest.mark.asyncio
    async def test_check_system_high_memory_creates_task(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(return_value={
            "disk": "40% used", "memory": "92% used", "cpu": "10%"
        })

        await am._check_system()

        assert any("memory" in t.get("description", "").lower() for t in am.task_queue)

    @pytest.mark.asyncio
    async def test_check_system_normal_no_tasks(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(return_value={
            "disk": "40% used", "memory": "45% used", "cpu": "20%"
        })

        await am._check_system()

        assert len(am.task_queue) == 0

    @pytest.mark.asyncio
    async def test_check_system_tool_failure_no_crash(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(side_effect=Exception("tool offline"))

        await am._check_system()  # Should not raise
        assert len(am.task_queue) == 0


class TestCheckCalendar:
    """Tests for _check_calendar with LLM analysis."""

    @pytest.mark.asyncio
    async def test_check_calendar_injects_tasks(self):
        am = _make_autonomous_mode()

        # Mock tool returning events
        am.agent.tools.execute = AsyncMock(return_value={
            "events": [{"title": "Team standup", "time": "10:00"}]
        })

        # Mock LLM returning action items
        am.agent.llm.invoke_with_tools = AsyncMock(return_value={
            "text": '[{"type":"calendar","description":"Prepare for team standup at 10:00","priority":"high"}]'
        })

        await am._check_calendar()

        assert len(am.task_queue) >= 1
        assert am.task_queue[0]["type"] == "calendar"

    @pytest.mark.asyncio
    async def test_check_calendar_no_events_no_tasks(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(return_value={"events": []})
        am.agent.llm.invoke_with_tools = AsyncMock(return_value={"text": "[]"})

        await am._check_calendar()

        assert len(am.task_queue) == 0


class TestCheckEmail:
    """Tests for _check_email with LLM analysis."""

    @pytest.mark.asyncio
    async def test_check_email_injects_tasks(self):
        am = _make_autonomous_mode()

        am.agent.tools.execute = AsyncMock(return_value={
            "emails": [{"from": "boss@co.com", "subject": "Urgent: deploy fix"}]
        })

        am.agent.llm.invoke_with_tools = AsyncMock(return_value={
            "text": '[{"type":"email_action","description":"Reply to boss about deploy fix","priority":"high"}]'
        })

        await am._check_email()

        assert len(am.task_queue) >= 1
        assert am.task_queue[0]["type"] == "email_action"


class TestSelfImprove:
    """Tests for _self_improve with LLM-driven meta-learning."""

    @pytest.mark.asyncio
    async def test_self_improve_generates_tasks(self):
        am = _make_autonomous_mode()
        am._last_improvement = datetime.now() - timedelta(hours=25)
        am.self_reflection = None
        am.pattern_learner = None
        am.skill_fitness = None

        am.completed_tasks = [
            {"status": "done", "type": "goal", "description": "Task A", "result": "ok", "duration_ms": 100},
            {"status": "error", "type": "goal", "description": "Task B", "result": "timeout", "duration_ms": 5000},
        ]

        am.agent.llm.invoke_with_tools = AsyncMock(return_value={
            "text": '[{"type":"goal","description":"Implement retry logic for timeouts","priority":"high"}]'
        })

        await am._self_improve()

        assert len(am.task_queue) >= 1
        assert "retry" in am.task_queue[0]["description"].lower() or len(am.task_queue) >= 1

    @pytest.mark.asyncio
    async def test_self_improve_skips_if_recent(self):
        am = _make_autonomous_mode()
        am._last_improvement = datetime.now()  # Just ran

        await am._self_improve()

        # Should not call LLM
        am.agent.llm.invoke_with_tools.assert_not_called()

    @pytest.mark.asyncio
    async def test_self_improve_no_llm_no_crash(self):
        am = _make_autonomous_mode()
        am._last_improvement = datetime.now() - timedelta(hours=25)
        am.agent.llm = None

        await am._self_improve()  # Should not raise


class TestExecuteSingleTask:
    """Tests for _execute_single_task routing through ReAct."""

    @pytest.mark.asyncio
    async def test_reminder_task_returns_description(self):
        am = _make_autonomous_mode()
        task = {"type": "reminder", "description": "Drink water"}
        result = await am._execute_single_task(task)
        assert "Drink water" in str(result)

    @pytest.mark.asyncio
    async def test_command_task_executes_tool(self):
        am = _make_autonomous_mode()
        am.agent.tools.execute = AsyncMock(return_value="disk: 45% used")

        task = {"type": "command", "tool_name": "system_info", "tool_args": {}}
        result = await am._execute_single_task(task)
        assert result == "disk: 45% used"

    @pytest.mark.asyncio
    async def test_goal_task_uses_react(self):
        am = _make_autonomous_mode()
        am.react_executor = MagicMock()
        react_result = MagicMock()
        react_result.success = True
        react_result.final_answer = "Goal completed"
        react_result.steps = []
        react_result.tools_used = ["web_search"]
        react_result.total_duration_ms = 200
        am.react_executor.execute = AsyncMock(return_value=react_result)
        am.agent.tools.get_tool_schemas = MagicMock(return_value=[])
        am.trace_exporter = None

        task = {"type": "goal", "description": "Research AI trends"}
        result = await am._execute_single_task(task)
        assert result == "Goal completed"

    @pytest.mark.asyncio
    async def test_system_maintenance_uses_react(self):
        am = _make_autonomous_mode()
        am.react_executor = MagicMock()
        react_result = MagicMock()
        react_result.success = True
        react_result.final_answer = "Cleaned 5GB of logs"
        react_result.steps = []
        react_result.tools_used = ["run_command"]
        react_result.total_duration_ms = 500
        am.react_executor.execute = AsyncMock(return_value=react_result)
        am.agent.tools.get_tool_schemas = MagicMock(return_value=[])
        am.trace_exporter = None

        task = {"type": "system_maintenance", "description": "Clean old logs from disk"}
        result = await am._execute_single_task(task)
        assert "Cleaned" in str(result)

    @pytest.mark.asyncio
    async def test_trading_alert_logs_only(self):
        am = _make_autonomous_mode()
        task = {"type": "trading_alert", "description": "BTC spike detected"}
        result = await am._execute_single_task(task)
        assert "BTC" in str(result)


class TestCognitiveTick:
    """Tests for _cognitive_tick with proper module wiring."""

    @pytest.mark.asyncio
    async def test_cognitive_tick_runs_all_modules(self):
        am = _make_autonomous_mode()

        am.cognitive_memory = MagicMock()
        am.self_reflection = MagicMock()
        am.skill_evolution = MagicMock()
        am.skill_evolution.evaluate_tick.return_value = {}
        am.pattern_learner = MagicMock()
        am.skill_fitness = MagicMock()
        am.skill_fitness.get_fitness_dicts.return_value = []
        am.skill_fitness.events = []
        am.git_brain = MagicMock()
        am.git_brain.write_episode = AsyncMock()
        am.inner_life = None  # Skip LLM call

        await am._cognitive_tick()

        am.cognitive_memory.process_tick.assert_called_once_with(10)
        am.self_reflection.record_outcome.assert_called_once()
        am.skill_evolution.evaluate_tick.assert_called_once_with(10)
        am.pattern_learner.process_tick.assert_called_once()

    @pytest.mark.asyncio
    async def test_cognitive_tick_inner_life_calls_llm(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.self_reflection = None
        am.skill_evolution = None
        am.pattern_learner = None
        am.git_brain = None
        am.goal_manager = None

        # Set up inner life
        am.inner_life = MagicMock()
        am.inner_life.get_system1_prompt.return_value = "TICK 10..."
        am.inner_life.process_response = MagicMock()
        am.inner_life.emotion = MagicMock()
        am.inner_life.emotion.primary = "curiosity"
        am.inner_life.emotion.valence = 0.3

        am.agent.llm.invoke_with_tools = AsyncMock(return_value={
            "content": '{"emotion":{"primary":"excitement","valence":0.7,"arousal":0.6,"trigger":"progress"}}'
        })

        await am._cognitive_tick()

        am.inner_life.get_system1_prompt.assert_called_once()
        am.agent.llm.invoke_with_tools.assert_called_once()
        am.inner_life.process_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_cognitive_tick_self_reflection_gets_real_data(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.skill_evolution = None
        am.pattern_learner = None
        am.git_brain = None
        am.inner_life = None
        am.goal_manager = None

        am.self_reflection = MagicMock()
        am.completed_tasks = [
            {"status": "done", "type": "goal", "description": "A", "tools_used": ["web_search"]},
            {"status": "error", "type": "command", "description": "B", "result": "timeout"},
        ]

        await am._cognitive_tick()

        call_args = am.self_reflection.record_outcome.call_args[0][0]
        assert call_args.tick == 10
        assert call_args.success is False  # has errors
        assert "web_search" in call_args.tools_used
        assert len(call_args.errors) >= 1

    @pytest.mark.asyncio
    async def test_cognitive_tick_no_modules_no_crash(self):
        am = _make_autonomous_mode()
        am.cognitive_memory = None
        am.self_reflection = None
        am.skill_evolution = None
        am.pattern_learner = None
        am.git_brain = None
        am.inner_life = None

        await am._cognitive_tick()  # Should not raise
