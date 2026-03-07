"""
GitHub tools — Issues, PRs, repos, branches, code search, releases.

Provides tool handlers for the GitHub skill, following the same mixin
pattern as _social.py, _trading.py, etc.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class GitHubToolsMixin:
    """Mixin providing GitHub tool implementations for ToolRegistry."""

    async def _github_create_issue_tool(self, params: Dict) -> str:
        """Create a GitHub issue."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.create_issue(
            title=params.get("title", ""),
            body=params.get("body", ""),
            repo=params.get("repo"),
            labels=params.get("labels"),
            assignees=params.get("assignees"),
        )
        if result.success:
            return f"✅ Issue created: #{result.data.get('number', '?')} — {result.data.get('title', '')}\n🔗 {result.url}"
        return f"❌ {result.error}"

    async def _github_list_issues_tool(self, params: Dict) -> str:
        """List GitHub issues."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.list_issues(
            repo=params.get("repo"),
            state=params.get("state", "open"),
            labels=params.get("labels"),
            limit=params.get("limit", 10),
        )
        if result.success:
            issues = result.data.get("issues", [])
            if not issues:
                return "No issues found."
            lines = [f"📋 {result.data.get('count', 0)} issues:"]
            for i in issues:
                labels = ", ".join(i.get("labels", []))
                labels_str = f" [{labels}]" if labels else ""
                lines.append(f"  #{i.get('number', '?')} {i.get('title', '')}{labels_str}")
            return "\n".join(lines)
        return f"❌ {result.error}"

    async def _github_comment_issue_tool(self, params: Dict) -> str:
        """Comment on a GitHub issue."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.comment_on_issue(
            issue_number=params.get("issue_number", 0),
            body=params.get("body", ""),
            repo=params.get("repo"),
        )
        if result.success:
            return f"✅ Comment added to issue #{params.get('issue_number')}\n🔗 {result.url}"
        return f"❌ {result.error}"

    async def _github_close_issue_tool(self, params: Dict) -> str:
        """Close a GitHub issue."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.close_issue(
            issue_number=params.get("issue_number", 0),
            repo=params.get("repo"),
            reason=params.get("reason", "completed"),
        )
        if result.success:
            return f"✅ Issue #{params.get('issue_number')} closed"
        return f"❌ {result.error}"

    async def _github_create_pr_tool(self, params: Dict) -> str:
        """Create a GitHub pull request."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.create_pull_request(
            title=params.get("title", ""),
            body=params.get("body", ""),
            head=params.get("head", ""),
            base=params.get("base", "main"),
            repo=params.get("repo"),
            draft=params.get("draft", False),
        )
        if result.success:
            return f"✅ PR created: #{result.data.get('number', '?')} — {result.data.get('title', '')}\n🔗 {result.url}"
        return f"❌ {result.error}"

    async def _github_list_prs_tool(self, params: Dict) -> str:
        """List GitHub pull requests."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.list_pull_requests(
            repo=params.get("repo"),
            state=params.get("state", "open"),
            limit=params.get("limit", 10),
        )
        if result.success:
            prs = result.data.get("prs", [])
            if not prs:
                return "No pull requests found."
            lines = [f"📋 {result.data.get('count', 0)} PRs:"]
            for pr in prs:
                lines.append(f"  #{pr.get('number', '?')} {pr.get('title', '')} ({pr.get('head', '')} → {pr.get('base', '')})")
            return "\n".join(lines)
        return f"❌ {result.error}"

    async def _github_merge_pr_tool(self, params: Dict) -> str:
        """Merge a GitHub pull request."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.merge_pull_request(
            pr_number=params.get("pr_number", 0),
            repo=params.get("repo"),
            merge_method=params.get("merge_method", "merge"),
        )
        if result.success:
            return f"✅ PR #{params.get('pr_number')} merged"
        return f"❌ {result.error}"

    async def _github_repo_info_tool(self, params: Dict) -> str:
        """Get GitHub repository info."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.get_repo_info(repo=params.get("repo"))
        if result.success:
            d = result.data
            return (
                f"📦 {d.get('name', '?')}\n"
                f"  {d.get('description', 'No description')}\n"
                f"  ⭐ {d.get('stars', 0)} | 🍴 {d.get('forks', 0)} | 📝 {d.get('open_issues', 0)} open issues\n"
                f"  Language: {d.get('language', '?')} | Branch: {d.get('default_branch', '?')}\n"
                f"  🔗 {result.url}"
            )
        return f"❌ {result.error}"

    async def _github_list_repos_tool(self, params: Dict) -> str:
        """List GitHub repositories."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.list_repos(
            user=params.get("user"),
            limit=params.get("limit", 10),
            sort=params.get("sort", "updated"),
        )
        if result.success:
            repos = result.data.get("repos", [])
            if not repos:
                return "No repositories found."
            lines = [f"📦 {result.data.get('count', 0)} repos:"]
            for r in repos:
                lines.append(f"  {r.get('name', '?')} ⭐{r.get('stars', 0)} — {r.get('description', '')[:60]}")
            return "\n".join(lines)
        return f"❌ {result.error}"

    async def _github_create_branch_tool(self, params: Dict) -> str:
        """Create a GitHub branch."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.create_branch(
            branch_name=params.get("branch_name", ""),
            from_branch=params.get("from_branch"),
            repo=params.get("repo"),
        )
        if result.success:
            return f"✅ Branch '{result.data.get('branch', '')}' created from '{result.data.get('from', 'default')}'"
        return f"❌ {result.error}"

    async def _github_search_code_tool(self, params: Dict) -> str:
        """Search code on GitHub."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.search_code(
            query=params.get("query", ""),
            repo=params.get("repo"),
            limit=params.get("limit", 10),
        )
        if result.success:
            results = result.data.get("results", [])
            if not results:
                return "No code matches found."
            lines = [f"🔍 {result.data.get('count', 0)} results:"]
            for r in results:
                lines.append(f"  {r.get('repo', '')}/{r.get('path', '')} — {r.get('name', '')}")
            return "\n".join(lines)
        return f"❌ {result.error}"

    async def _github_get_file_tool(self, params: Dict) -> str:
        """Read a file from GitHub."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.get_file_content(
            path=params.get("path", ""),
            repo=params.get("repo"),
            branch=params.get("branch"),
        )
        if result.success:
            d = result.data
            if d.get("type") == "directory":
                items = d.get("items", [])
                lines = [f"📁 Directory: {params.get('path', '.')}"]
                for item in items:
                    icon = "📁" if item.get("type") == "dir" else "📄"
                    lines.append(f"  {icon} {item.get('name', '?')}")
                return "\n".join(lines)
            content = d.get("content", "")
            return f"📄 {d.get('path', '?')} ({d.get('size', 0)} bytes):\n\n{content[:3000]}"
        return f"❌ {result.error}"

    async def _github_create_release_tool(self, params: Dict) -> str:
        """Create a GitHub release."""
        if not self.github_skill or not self.github_skill.is_available():
            return "❌ GitHub not configured. Set GITHUB_TOKEN in .env"
        result = await self.github_skill.create_release(
            tag=params.get("tag", ""),
            name=params.get("name", ""),
            body=params.get("body", ""),
            repo=params.get("repo"),
            draft=params.get("draft", False),
            prerelease=params.get("prerelease", False),
        )
        if result.success:
            return f"✅ Release {result.data.get('tag', '?')} created\n🔗 {result.url}"
        return f"❌ {result.error}"
