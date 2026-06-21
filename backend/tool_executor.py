import os
import json

from tools import (
    list_directory,
    read_file,
    write_file,
    create_directory,
    move_file,
    rename_file,
    delete_file,
    delete_directory,
    execute_command,
    search_repositories,
    get_issue,
    create_issue,
    create_pr,
    clone_repo,
    commit_and_push,
    list_repos,
    get_user,
)
from tools.file_ops import set_allowed_base

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path relative to workspace"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates intermediate directories)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (and any missing parent directories)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create (relative to workspace)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move a file or directory from src to dst",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path (relative to workspace)"},
                    "dst": {"type": "string", "description": "Destination path (relative to workspace)"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename a file within its current directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to rename (relative to workspace)"},
                    "new_name": {"type": "string", "description": "New filename (not a full path — just the name)"},
                },
                "required": ["path", "new_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a single file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to delete (relative to workspace)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Delete a directory (use recursive=true to delete non-empty directories)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to delete (relative to workspace)"},
                    "recursive": {"type": "boolean", "description": "Delete non-empty directory recursively", "default": False},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Run a shell command (e.g., python, npm, git)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_repositories",
            "description": "Search GitHub repositories",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "per_page": {"type": "integer", "description": "Results per page", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue",
            "description": "Get details of a GitHub issue",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "issue_number": {"type": "integer", "description": "Issue number"},
                },
                "required": ["repo", "issue_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_issue",
            "description": "Create a new GitHub issue",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue body"},
                },
                "required": ["repo", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pr",
            "description": "Create a GitHub Pull Request",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "title": {"type": "string", "description": "PR title"},
                    "head": {"type": "string", "description": "Branch with changes"},
                    "base": {"type": "string", "description": "Target branch (default: main)"},
                    "body": {"type": "string", "description": "PR description"},
                },
                "required": ["repo", "title", "head"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clone_repo",
            "description": "Clone a git repository to the workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Git clone URL"},
                    "target_dir": {"type": "string", "description": "Target directory name"},
                },
                "required": ["url", "target_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "commit_and_push",
            "description": "Commit all changes and push to remote",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to local git repository"},
                    "message": {"type": "string", "description": "Commit message"},
                    "branch": {"type": "string", "description": "Branch to push to (default: main)"},
                },
                "required": ["repo_path", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_repos",
            "description": "List your GitHub repositories",
            "parameters": {
                "type": "object",
                "properties": {
                    "per_page": {"type": "integer", "description": "Number of repos to fetch", "default": 30},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user",
            "description": "Get the authenticated GitHub user info",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def execute_tool(tool_name: str, args: dict, workspace: str = ".") -> str:
    set_allowed_base(workspace)
    tool_map = {
        "list_directory": lambda: list_directory(args.get("path", ".")),
        "read_file": lambda: read_file(args["path"]),
        "write_file": lambda: write_file(args["path"], args["content"]),
        "create_directory": lambda: create_directory(args["path"]),
        "move_file": lambda: move_file(args["src"], args["dst"]),
        "rename_file": lambda: rename_file(args["path"], args["new_name"]),
        "delete_file": lambda: delete_file(args["path"]),
        "delete_directory": lambda: delete_directory(args["path"], args.get("recursive", False)),
        "execute_command": lambda: execute_command(args["command"], workspace),
        "search_repositories": lambda: search_repositories(args["query"], args.get("per_page", 5)),
        "get_issue": lambda: get_issue(args["repo"], args["issue_number"]),
        "create_issue": lambda: create_issue(args["repo"], args["title"], args.get("body", "")),
        "create_pr": lambda: create_pr(
            args["repo"], args["title"], args["head"],
            args.get("base", "main"), args.get("body", ""),
        ),
        "clone_repo": lambda: clone_repo(
            args["url"],
            os.path.join(workspace, args.get("target_dir", args["url"].split("/")[-1].replace(".git", ""))),
        ),
        "commit_and_push": lambda: commit_and_push(
            args["repo_path"], args["message"], args.get("branch", "main"),
        ),
        "list_repos": lambda: list_repos(args.get("per_page", 30)),
        "get_user": lambda: get_user(),
    }
    func = tool_map.get(tool_name)
    if not func:
        return f"Error: unknown tool '{tool_name}'"
    try:
        result = func()
        if hasattr(result, "__await__"):
            result = await result
        return str(result)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"
