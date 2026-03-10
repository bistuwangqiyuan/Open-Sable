"""
Tool schemas for GitHub domain.
"""

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "github_create_issue",
            "description": "Create a new issue on a GitHub repository. Use this to report bugs, request features, or create tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue body (Markdown)"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format (optional if GITHUB_DEFAULT_REPO is set)"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add"},
                    "assignees": {"type": "array", "items": {"type": "string"}, "description": "GitHub usernames to assign"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_issues",
            "description": "List issues on a GitHub repository. Filter by state and labels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue state filter"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Filter by labels"},
                    "limit": {"type": "integer", "description": "Max results (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_comment_issue",
            "description": "Add a comment to an existing GitHub issue or pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer", "description": "Issue or PR number"},
                    "body": {"type": "string", "description": "Comment body (Markdown)"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                },
                "required": ["issue_number", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_close_issue",
            "description": "Close an existing GitHub issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer", "description": "Issue number to close"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "reason": {"type": "string", "enum": ["completed", "not_planned"], "description": "Close reason"},
                },
                "required": ["issue_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_pr",
            "description": "Create a pull request on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description (Markdown)"},
                    "head": {"type": "string", "description": "Branch to merge FROM"},
                    "base": {"type": "string", "description": "Branch to merge INTO (default: main)"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "draft": {"type": "boolean", "description": "Create as draft PR"},
                },
                "required": ["title", "head"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_prs",
            "description": "List pull requests on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "PR state filter"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_merge_pr",
            "description": "Merge an open pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "PR number to merge"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"], "description": "Merge method"},
                },
                "required": ["pr_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_repo_info",
            "description": "Get information about a GitHub repository,  stars, forks, language, description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_repos",
            "description": "List repositories for a user or the authenticated user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "GitHub username (omit for your own repos)"},
                    "limit": {"type": "integer", "description": "Max results"},
                    "sort": {"type": "string", "enum": ["updated", "created", "full_name"], "description": "Sort order"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_branch",
            "description": "Create a new branch on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name": {"type": "string", "description": "Name for the new branch"},
                    "from_branch": {"type": "string", "description": "Source branch (default: repo default branch)"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                },
                "required": ["branch_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search_code",
            "description": "Search for code across GitHub or within a specific repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (code, function names, etc.)"},
                    "repo": {"type": "string", "description": "Limit search to this repo (owner/repo format)"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_file",
            "description": "Read a file from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path within the repository"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "branch": {"type": "string", "description": "Branch to read from (default: repo default)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_release",
            "description": "Create a new release/tag on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Tag name (e.g. v1.0.0)"},
                    "name": {"type": "string", "description": "Release title"},
                    "body": {"type": "string", "description": "Release notes (Markdown)"},
                    "repo": {"type": "string", "description": "Repository in owner/repo format"},
                    "draft": {"type": "boolean", "description": "Create as draft release"},
                    "prerelease": {"type": "boolean", "description": "Mark as pre-release"},
                },
                "required": ["tag"],
            },
        },
    },
]
