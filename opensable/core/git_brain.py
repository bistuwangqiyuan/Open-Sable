"""
Git Brain,  version-controlled agent memory via git.

Uses a local git repository as the agent's episodic memory:
  - Auto-commit after each tick
  - Tools to inspect history, branch, merge, show files
  - Episode files (markdown) written per tick
  - Git diffs as selection pressure for evolution

Academic grounding:
  [1] Wu et al., arXiv:2508.00031,  GCC: +13% SWE-bench with git memory
  [2] Growth Kinetics,  DiffMem: 6mo production git-backed AI memory
  [3] Yegge (2026),  Beads: git-backed memory for coding agents
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Git CLI helpers ──────────────────────────────────────────────────────────


@dataclass
class GitResult:
    """Typed result from a git CLI operation."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def _git(repo_dir: Path, *args: str, timeout: int = 30) -> GitResult:
    """Run git CLI in repo_dir async."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(repo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return GitResult("", f"timeout after {timeout}s", -1)

        return GitResult(
            stdout=(stdout_bytes or b"").decode("utf-8", errors="replace").strip(),
            stderr=(stderr_bytes or b"").decode("utf-8", errors="replace").strip(),
            returncode=proc.returncode or 0,
        )
    except FileNotFoundError:
        return GitResult("", "git not found", -1)


def _git_sync(repo_dir: Path, *args: str, timeout: int = 10) -> GitResult:
    """Run git CLI synchronously (for compile_life which is sync)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return GitResult(
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            returncode=proc.returncode,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return GitResult("", str(e), -1)


async def _ensure_repo(repo_dir: Path) -> GitResult:
    """Initialize git repo if needed. Idempotent."""
    repo_dir.mkdir(parents=True, exist_ok=True)

    check = await _git(repo_dir, "rev-parse", "--git-dir")
    if check.ok:
        return check

    init = await _git(repo_dir, "init")
    if not init.ok:
        return init

    await _git(repo_dir, "config", "user.name", "sable-agent")
    await _git(repo_dir, "config", "user.email", "agent@sable.local")

    gitignore = repo_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "trace.jsonl\n__pycache__/\n*.pyc\n.DS_Store\n"
        )

    return init


# ─── Git Brain ────────────────────────────────────────────────────────────────


class GitBrain:
    """Git-backed agent memory with version-controlled state.

    The agent's memory_dir IS the git repo.  Each tick auto-commits
    all changed files.  Tools let the agent inspect its own history,
    branch for hypotheses, and merge experiments.

    Usage:
        brain = GitBrain(repo_dir=Path("data/brain"))
        await brain.initialize()

        # After each tick:
        await brain.write_episode(tick=5, summary="...", goals=[...])
        await brain.auto_commit(tick=5, summary="completed 2 tasks")

        # Agent tools:
        history = await brain.get_history(limit=10)
        diff = await brain.get_diff(ticks_back=1)
    """

    def __init__(
        self,
        repo_dir: Path,
        auto_commit_enabled: bool = True,
        history_in_context: int = 5,
        episodes_in_context: int = 5,
    ):
        self.repo_dir = Path(repo_dir)
        self.auto_commit_enabled = auto_commit_enabled
        self.history_in_context = history_in_context
        self.episodes_in_context = episodes_in_context
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the git repo."""
        result = await _ensure_repo(self.repo_dir)
        self._initialized = result.ok or result.stdout != ""
        if self._initialized:
            logger.info(f"Git brain initialized at {self.repo_dir}")
        else:
            logger.warning(f"Git brain init failed: {result.stderr}")

    # ── Agent tools (async) ────────────────────────────────────────────────

    async def get_history(
        self, limit: int = 10,
    ) -> Dict[str, Any]:
        """View recent commit history."""
        result = await _git(
            self.repo_dir, "log",
            f"--max-count={limit}",
            "--format=%H|%s|%ai",
        )
        if not result.ok:
            return {"error": result.stderr, "commits": []}

        commits = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0][:8],
                    "message": parts[1],
                    "date": parts[2],
                })
        return {"commits": commits, "count": len(commits)}

    async def get_diff(
        self, ticks_back: int = 1,
    ) -> Dict[str, str]:
        """Show what changed between ticks."""
        ref = f"HEAD~{ticks_back}" if ticks_back > 0 else "HEAD"
        stat = await _git(self.repo_dir, "diff", ref, "--stat")
        if not stat.ok:
            return {"error": stat.stderr, "hint": "Not enough history yet"}
        full = await _git(self.repo_dir, "diff", ref)
        return {
            "summary": stat.stdout[:2000],
            "diff": full.stdout[:5000],
        }

    async def create_branch(
        self, name: str, reason: str = "",
    ) -> Dict[str, Any]:
        """Create a hypothesis branch."""
        result = await _git(self.repo_dir, "checkout", "-b", name)
        if not result.ok:
            return {"error": result.stderr}
        return {"created": True, "branch": name, "reason": reason}

    async def merge_branch(
        self, branch: str,
    ) -> Dict[str, Any]:
        """Merge a branch back to main."""
        switch = await _git(self.repo_dir, "checkout", "main")
        if not switch.ok:
            switch = await _git(self.repo_dir, "checkout", "master")
            if not switch.ok:
                return {"error": f"Cannot switch to main: {switch.stderr}"}

        merge = await _git(self.repo_dir, "merge", branch, "--no-edit")
        if not merge.ok:
            await _git(self.repo_dir, "merge", "--abort")
            return {"error": f"Merge conflict: {merge.stderr}", "merged": False}
        return {"merged": True, "branch": branch}

    async def show_file(
        self, ref: str, path: str,
    ) -> Dict[str, str]:
        """Show a file at a specific point in history."""
        result = await _git(self.repo_dir, "show", f"{ref}:{path}")
        if not result.ok:
            return {"error": result.stderr}
        return {"ref": ref, "path": path, "content": result.stdout[:10000]}

    # ── Episodic memory ────────────────────────────────────────────────────

    async def write_episode(
        self,
        tick: int,
        *,
        summary: str = "",
        goals: Optional[List[Dict[str, Any]]] = None,
        response_text: str = "",
        tools_used: Optional[List[str]] = None,
    ) -> Path:
        """Write a tick episode as a markdown file.

        Creates episodes/tick_NNN.md with: what happened, goals, response.
        """
        episodes_dir = self.repo_dir / "episodes"
        episodes_dir.mkdir(parents=True, exist_ok=True)

        episode_path = episodes_dir / f"tick_{tick:04d}.md"

        parts = [f"# Tick {tick}"]

        if summary:
            parts.append(f"\n## Summary\n{summary}")

        if response_text:
            parts.append(f"\n## Response\n{response_text[:3000]}")

        if goals:
            goal_lines = [
                f"- {g.get('name', 'unknown')}: "
                f"{g.get('progress', 0):.0%} "
                f"(priority {g.get('priority', 0)})"
                for g in goals[:5]
            ]
            parts.append(f"\n## Goals\n" + "\n".join(goal_lines))

        if tools_used:
            parts.append(
                f"\n## Tools Used\n" + ", ".join(tools_used[:20])
            )

        episode_path.write_text("\n".join(parts), encoding="utf-8")
        return episode_path

    def load_recent_episodes(
        self, max_episodes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Load recent episode files as memory items.

        Returns list of dicts with: tick, content, path.
        """
        limit = max_episodes or self.episodes_in_context
        episodes_dir = self.repo_dir / "episodes"
        if not episodes_dir.is_dir():
            return []

        files = sorted(episodes_dir.glob("tick_*.md"), reverse=True)
        files = files[:limit]

        result = []
        for ep_file in files:
            try:
                content = ep_file.read_text(encoding="utf-8")
                stem = ep_file.stem
                tick_part = stem.removeprefix("tick_")
                tick_num = int(tick_part) if tick_part.isdigit() else 0
                result.append({
                    "tick": tick_num,
                    "content": content,
                    "path": str(ep_file),
                })
            except Exception as e:
                logger.debug(f"Failed to read episode {ep_file}: {e}")

        return result

    # ── Auto-commit ────────────────────────────────────────────────────────

    async def auto_commit(
        self,
        tick: int,
        summary: str = "completed",
    ) -> bool:
        """Auto-commit all changes after a tick.

        Returns True if a commit was made.
        """
        if not self.auto_commit_enabled:
            return False

        await _git(self.repo_dir, "add", "-A")

        status = await _git(self.repo_dir, "status", "--porcelain")
        if not status.stdout.strip():
            return False  # Nothing to commit

        message = f"tick {tick}: {summary}"
        result = await _git(self.repo_dir, "commit", "-m", message)
        return result.ok

    # ── Context for LLM ───────────────────────────────────────────────────

    def get_context_prompt(self) -> str:
        """Build a system message with recent git history.

        Runs synchronously so it can be called from sync code.
        """
        parts = [
            "GIT BRAIN active,  your state is version-controlled. "
            "Every tick auto-commits. You can inspect your own past."
        ]

        # Recent commits
        result = _git_sync(
            self.repo_dir, "log",
            f"--max-count={self.history_in_context}",
            "--format=  tick: %s",
        )
        if result.ok and result.stdout.strip():
            parts.append(f"\nRECENT HISTORY (git):\n{result.stdout}")

        # Recent episodes as context
        episodes = self.load_recent_episodes()
        if episodes:
            parts.append(f"\nRECENT EPISODES ({len(episodes)}):")
            for ep in episodes[:3]:
                # First 200 chars of each episode
                snippet = ep["content"][:200].replace("\n", " ")
                parts.append(f"  tick {ep['tick']}: {snippet}")

        return "\n".join(parts)

    def get_evolution_pressure(self) -> List[str]:
        """Get git-based evolution pressure signals.

        Returns list of pressure strings for the evolution pipeline.
        """
        pressures = []

        result = _git_sync(
            self.repo_dir, "log", "--max-count=5", "--format=%H",
        )
        if result.ok and result.stdout.strip():
            commit_count = len(result.stdout.strip().splitlines())
            stat = _git_sync(
                self.repo_dir, "diff", "--shortstat", "HEAD~1", "HEAD",
            )
            stat_text = stat.stdout[:100] if stat.ok else ""
            pressures.append(
                f"git:commits={commit_count},last_change={stat_text}"
            )

        return pressures

    def get_stats(self) -> Dict[str, Any]:
        """Get git brain statistics."""
        stats: Dict[str, Any] = {
            "initialized": self._initialized,
            "repo_dir": str(self.repo_dir),
            "auto_commit": self.auto_commit_enabled,
        }

        result = _git_sync(self.repo_dir, "rev-list", "--count", "HEAD")
        if result.ok:
            stats["total_commits"] = int(result.stdout) if result.stdout.isdigit() else 0

        result = _git_sync(self.repo_dir, "branch", "--list")
        if result.ok:
            stats["branches"] = len(result.stdout.splitlines())

        episodes_dir = self.repo_dir / "episodes"
        if episodes_dir.is_dir():
            stats["episodes"] = len(list(episodes_dir.glob("tick_*.md")))

        return stats
