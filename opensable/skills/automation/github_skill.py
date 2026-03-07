"""
GitHub Skill — Full GitHub API integration for autonomous agent operations.

Create issues, pull requests, manage repositories, post comments, create branches,
read files, search code — everything an autonomous agent needs to operate on GitHub.

Uses PyGithub for the REST API and falls back to the `gh` CLI when available.

Setup:
    Set in .env:
        GITHUB_TOKEN=ghp_your_personal_access_token
        GITHUB_DEFAULT_REPO=owner/repo  (optional)

    Or authenticate via `gh auth login`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from github import Github, GithubException, Auth
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False
    logger.info("PyGithub not installed. Install with: pip install PyGithub")


@dataclass
class GitHubResult:
    """Standardized result from a GitHub operation."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    url: Optional[str] = None

    def to_str(self) -> str:
        if self.success:
            parts = []
            if self.url:
                parts.append(f"🔗 {self.url}")
            for k, v in self.data.items():
                parts.append(f"  {k}: {v}")
            return "\n".join(parts) if parts else "✅ Success"
        return f"❌ {self.error or 'Unknown error'}"


class GitHubSkill:
    """
    Full GitHub API integration — issues, PRs, repos, branches, comments, code search.

    Works with PyGithub (REST API) or falls back to `gh` CLI.
    """

    def __init__(self, config):
        self.config = config
        self._client: Optional[Any] = None
        self._initialized = False
        self._default_repo: Optional[str] = None

    async def initialize(self) -> bool:
        """Initialize GitHub client with token or CLI auth."""
        token = (
            getattr(self.config, "github_token", None)
            or os.getenv("GITHUB_TOKEN")
        )
        self._default_repo = (
            getattr(self.config, "github_default_repo", None)
            or os.getenv("GITHUB_DEFAULT_REPO")
        )

        if PYGITHUB_AVAILABLE and token:
            try:
                auth = Auth.Token(token)
                self._client = Github(auth=auth)
                # Verify authentication
                user = self._client.get_user()
                logger.info(f"✅ GitHub authenticated as: {user.login}")
                self._initialized = True
                return True
            except Exception as e:
                logger.warning(f"GitHub auth failed: {e}")

        # Fallback: try gh CLI
        if await self._check_gh_cli():
            self._initialized = True
            logger.info("✅ GitHub: using gh CLI fallback")
            return True

        logger.warning("GitHub skill not available — set GITHUB_TOKEN or install gh CLI")
        return False

    def is_available(self) -> bool:
        return self._initialized

    async def _check_gh_cli(self) -> bool:
        """Check if gh CLI is available and authenticated."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh", "auth", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def _gh_cli(self, *args: str) -> str:
        """Run a gh CLI command and return stdout."""
        proc = await asyncio.create_subprocess_exec(
            "gh", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())
        return stdout.decode().strip()

    def _resolve_repo(self, repo: Optional[str] = None) -> str:
        """Resolve repo name — explicit > default > error."""
        r = repo or self._default_repo
        if not r:
            raise ValueError(
                "No repository specified. Pass repo='owner/repo' or set GITHUB_DEFAULT_REPO"
            )
        return r

    # ── Issues ────────────────────────────────────────────────────────────────

    async def create_issue(
        self,
        title: str,
        body: str = "",
        repo: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> GitHubResult:
        """Create a new issue on a repository."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                issue = r.create_issue(
                    title=title,
                    body=body,
                    labels=labels or [],
                    assignees=assignees or [],
                )
                return GitHubResult(
                    success=True,
                    url=issue.html_url,
                    data={
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                    },
                )
            else:
                # gh CLI fallback
                cmd = ["issue", "create", "-R", repo_name, "-t", title, "-b", body]
                if labels:
                    for lbl in labels:
                        cmd.extend(["-l", lbl])
                if assignees:
                    for a in assignees:
                        cmd.extend(["-a", a])
                url = await self._gh_cli(*cmd)
                return GitHubResult(success=True, url=url, data={"title": title})

        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def list_issues(
        self,
        repo: Optional[str] = None,
        state: str = "open",
        labels: Optional[List[str]] = None,
        limit: int = 10,
    ) -> GitHubResult:
        """List issues on a repository."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                kwargs: Dict[str, Any] = {"state": state}
                if labels:
                    kwargs["labels"] = [r.get_label(l) for l in labels]
                issues = list(r.get_issues(**kwargs)[:limit])
                items = []
                for i in issues:
                    if not i.pull_request:  # Exclude PRs
                        items.append({
                            "number": i.number,
                            "title": i.title,
                            "state": i.state,
                            "author": i.user.login if i.user else "unknown",
                            "labels": [l.name for l in i.labels],
                            "url": i.html_url,
                        })
                return GitHubResult(success=True, data={"issues": items, "count": len(items)})
            else:
                output = await self._gh_cli(
                    "issue", "list", "-R", repo_name, "-s", state,
                    "-L", str(limit), "--json", "number,title,state,author,labels,url",
                )
                items = json.loads(output)
                return GitHubResult(success=True, data={"issues": items, "count": len(items)})

        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def comment_on_issue(
        self,
        issue_number: int,
        body: str,
        repo: Optional[str] = None,
    ) -> GitHubResult:
        """Add a comment to an issue or PR."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                issue = r.get_issue(issue_number)
                comment = issue.create_comment(body)
                return GitHubResult(
                    success=True,
                    url=comment.html_url,
                    data={"issue": issue_number, "comment_id": comment.id},
                )
            else:
                url = await self._gh_cli(
                    "issue", "comment", str(issue_number),
                    "-R", repo_name, "-b", body,
                )
                return GitHubResult(success=True, url=url, data={"issue": issue_number})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def close_issue(
        self, issue_number: int, repo: Optional[str] = None, reason: str = "completed",
    ) -> GitHubResult:
        """Close an issue."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                issue = r.get_issue(issue_number)
                issue.edit(state="closed", state_reason=reason)
                return GitHubResult(success=True, data={"issue": issue_number, "state": "closed"})
            else:
                await self._gh_cli("issue", "close", str(issue_number), "-R", repo_name)
                return GitHubResult(success=True, data={"issue": issue_number, "state": "closed"})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Pull Requests ─────────────────────────────────────────────────────────

    async def create_pull_request(
        self,
        title: str,
        body: str = "",
        head: str = "",
        base: str = "main",
        repo: Optional[str] = None,
        draft: bool = False,
    ) -> GitHubResult:
        """Create a pull request."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                pr = r.create_pull(
                    title=title,
                    body=body,
                    head=head,
                    base=base,
                    draft=draft,
                )
                return GitHubResult(
                    success=True,
                    url=pr.html_url,
                    data={
                        "number": pr.number,
                        "title": pr.title,
                        "state": pr.state,
                        "head": head,
                        "base": base,
                    },
                )
            else:
                cmd = [
                    "pr", "create", "-R", repo_name,
                    "-t", title, "-b", body,
                    "-H", head, "-B", base,
                ]
                if draft:
                    cmd.append("--draft")
                url = await self._gh_cli(*cmd)
                return GitHubResult(success=True, url=url, data={"title": title})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def list_pull_requests(
        self,
        repo: Optional[str] = None,
        state: str = "open",
        limit: int = 10,
    ) -> GitHubResult:
        """List pull requests on a repository."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                prs = list(r.get_pulls(state=state)[:limit])
                items = []
                for pr in prs:
                    items.append({
                        "number": pr.number,
                        "title": pr.title,
                        "state": pr.state,
                        "author": pr.user.login if pr.user else "unknown",
                        "head": pr.head.ref,
                        "base": pr.base.ref,
                        "url": pr.html_url,
                    })
                return GitHubResult(success=True, data={"prs": items, "count": len(items)})
            else:
                output = await self._gh_cli(
                    "pr", "list", "-R", repo_name, "-s", state,
                    "-L", str(limit), "--json", "number,title,state,author,headRefName,baseRefName,url",
                )
                items = json.loads(output)
                return GitHubResult(success=True, data={"prs": items, "count": len(items)})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def merge_pull_request(
        self,
        pr_number: int,
        repo: Optional[str] = None,
        merge_method: str = "merge",
    ) -> GitHubResult:
        """Merge a pull request."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                pr = r.get_pull(pr_number)
                pr.merge(merge_method=merge_method)
                return GitHubResult(
                    success=True,
                    data={"pr": pr_number, "merged": True, "method": merge_method},
                )
            else:
                await self._gh_cli(
                    "pr", "merge", str(pr_number), "-R", repo_name,
                    f"--{merge_method}",
                )
                return GitHubResult(success=True, data={"pr": pr_number, "merged": True})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Repositories ──────────────────────────────────────────────────────────

    async def get_repo_info(self, repo: Optional[str] = None) -> GitHubResult:
        """Get repository information."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                return GitHubResult(
                    success=True,
                    url=r.html_url,
                    data={
                        "name": r.full_name,
                        "description": r.description or "",
                        "language": r.language or "unknown",
                        "stars": r.stargazers_count,
                        "forks": r.forks_count,
                        "open_issues": r.open_issues_count,
                        "default_branch": r.default_branch,
                        "private": r.private,
                    },
                )
            else:
                output = await self._gh_cli(
                    "repo", "view", repo_name, "--json",
                    "name,description,primaryLanguage,stargazerCount,forkCount,isPrivate,defaultBranchRef",
                )
                data = json.loads(output)
                return GitHubResult(success=True, data=data)
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def list_repos(
        self,
        user: Optional[str] = None,
        limit: int = 10,
        sort: str = "updated",
    ) -> GitHubResult:
        """List repositories for a user (or authenticated user)."""
        try:
            if self._client:
                if user:
                    gh_user = self._client.get_user(user)
                    repos = list(gh_user.get_repos(sort=sort)[:limit])
                else:
                    repos = list(self._client.get_user().get_repos(sort=sort)[:limit])
                items = []
                for r in repos:
                    items.append({
                        "name": r.full_name,
                        "description": r.description or "",
                        "language": r.language or "unknown",
                        "stars": r.stargazers_count,
                        "url": r.html_url,
                    })
                return GitHubResult(success=True, data={"repos": items, "count": len(items)})
            else:
                cmd = ["repo", "list"]
                if user:
                    cmd.append(user)
                cmd.extend(["-L", str(limit), "--json", "name,description,primaryLanguage,stargazerCount,url"])
                output = await self._gh_cli(*cmd)
                items = json.loads(output)
                return GitHubResult(success=True, data={"repos": items, "count": len(items)})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Branches ──────────────────────────────────────────────────────────────

    async def create_branch(
        self,
        branch_name: str,
        from_branch: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> GitHubResult:
        """Create a new branch from an existing branch."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                source = from_branch or r.default_branch
                sb = r.get_branch(source)
                r.create_git_ref(
                    ref=f"refs/heads/{branch_name}",
                    sha=sb.commit.sha,
                )
                return GitHubResult(
                    success=True,
                    data={"branch": branch_name, "from": source, "sha": sb.commit.sha[:8]},
                )
            else:
                # Use git directly
                proc = await asyncio.create_subprocess_exec(
                    "git", "checkout", "-b", branch_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return GitHubResult(success=True, data={"branch": branch_name})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def list_branches(
        self, repo: Optional[str] = None, limit: int = 20,
    ) -> GitHubResult:
        """List branches of a repository."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                branches = list(r.get_branches()[:limit])
                items = [{"name": b.name, "protected": b.protected} for b in branches]
                return GitHubResult(success=True, data={"branches": items, "count": len(items)})
            else:
                output = await self._gh_cli(
                    "api", f"/repos/{repo_name}/branches",
                    "--jq", ".[].name",
                )
                names = output.strip().split("\n") if output.strip() else []
                items = [{"name": n} for n in names[:limit]]
                return GitHubResult(success=True, data={"branches": items, "count": len(items)})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Files / Code ──────────────────────────────────────────────────────────

    async def get_file_content(
        self,
        path: str,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> GitHubResult:
        """Read a file from a repository."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                kwargs: Dict[str, Any] = {}
                if branch:
                    kwargs["ref"] = branch
                content = r.get_contents(path, **kwargs)
                if isinstance(content, list):
                    # It's a directory
                    items = [{"name": c.name, "type": c.type, "path": c.path} for c in content]
                    return GitHubResult(success=True, data={"type": "directory", "items": items})
                return GitHubResult(
                    success=True,
                    data={
                        "type": "file",
                        "path": content.path,
                        "size": content.size,
                        "content": content.decoded_content.decode("utf-8", errors="replace"),
                    },
                )
            else:
                output = await self._gh_cli(
                    "api", f"/repos/{repo_name}/contents/{path}",
                    "--jq", ".content",
                )
                import base64
                decoded = base64.b64decode(output).decode("utf-8", errors="replace")
                return GitHubResult(success=True, data={"type": "file", "path": path, "content": decoded})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def search_code(
        self,
        query: str,
        repo: Optional[str] = None,
        limit: int = 10,
    ) -> GitHubResult:
        """Search code across GitHub (or within a specific repo)."""
        try:
            if self._client:
                q = query
                if repo:
                    q = f"{query} repo:{repo}"
                results = list(self._client.search_code(q)[:limit])
                items = []
                for r in results:
                    items.append({
                        "name": r.name,
                        "path": r.path,
                        "repo": r.repository.full_name,
                        "url": r.html_url,
                    })
                return GitHubResult(success=True, data={"results": items, "count": len(items)})
            else:
                q = query
                if repo:
                    q = f"{query} repo:{repo}"
                output = await self._gh_cli(
                    "search", "code", q,
                    "-L", str(limit), "--json", "path,repository,url",
                )
                items = json.loads(output)
                return GitHubResult(success=True, data={"results": items, "count": len(items)})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Releases ──────────────────────────────────────────────────────────────

    async def create_release(
        self,
        tag: str,
        name: str = "",
        body: str = "",
        repo: Optional[str] = None,
        draft: bool = False,
        prerelease: bool = False,
    ) -> GitHubResult:
        """Create a new release / tag."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                release = r.create_git_release(
                    tag=tag,
                    name=name or tag,
                    message=body,
                    draft=draft,
                    prerelease=prerelease,
                )
                return GitHubResult(
                    success=True,
                    url=release.html_url,
                    data={"tag": tag, "name": release.title},
                )
            else:
                cmd = ["release", "create", tag, "-R", repo_name, "-t", name or tag]
                if body:
                    cmd.extend(["-n", body])
                if draft:
                    cmd.append("--draft")
                if prerelease:
                    cmd.append("--prerelease")
                url = await self._gh_cli(*cmd)
                return GitHubResult(success=True, url=url, data={"tag": tag})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    # ── Workflows ─────────────────────────────────────────────────────────────

    async def list_workflows(
        self, repo: Optional[str] = None, limit: int = 10,
    ) -> GitHubResult:
        """List GitHub Actions workflows."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                workflows = list(r.get_workflows()[:limit])
                items = [{"name": w.name, "state": w.state, "path": w.path} for w in workflows]
                return GitHubResult(success=True, data={"workflows": items, "count": len(items)})
            else:
                output = await self._gh_cli(
                    "workflow", "list", "-R", repo_name,
                    "--json", "name,state,path",
                )
                items = json.loads(output)
                return GitHubResult(success=True, data={"workflows": items, "count": len(items)})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))

    async def trigger_workflow(
        self,
        workflow_id: str,
        repo: Optional[str] = None,
        ref: str = "main",
        inputs: Optional[Dict[str, str]] = None,
    ) -> GitHubResult:
        """Trigger a GitHub Actions workflow dispatch."""
        repo_name = self._resolve_repo(repo)
        try:
            if self._client:
                r = self._client.get_repo(repo_name)
                wf = r.get_workflow(workflow_id)
                wf.create_dispatch(ref=ref, inputs=inputs or {})
                return GitHubResult(
                    success=True,
                    data={"workflow": workflow_id, "ref": ref, "triggered": True},
                )
            else:
                cmd = [
                    "workflow", "run", workflow_id,
                    "-R", repo_name, "--ref", ref,
                ]
                await self._gh_cli(*cmd)
                return GitHubResult(success=True, data={"workflow": workflow_id, "triggered": True})
        except Exception as e:
            return GitHubResult(success=False, error=str(e))
