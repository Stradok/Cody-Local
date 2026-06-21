import os
import subprocess
import httpx
from typing import Optional

GITHUB_API = "https://api.github.com"
_token: Optional[str] = None


def set_token(token: str) -> None:
    global _token
    _token = token


def get_token() -> Optional[str]:
    return _token


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if _token:
        headers["Authorization"] = f"Bearer {_token}"
    return headers


def _require_token():
    if not _token:
        raise ValueError("GitHub token not set. Set it in Settings or via GITHUB_TOKEN env var.")


async def get_user() -> str:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GITHUB_API}/user", headers=_headers())
        resp.raise_for_status()
        u = resp.json()
        return f"{u['login']} ({u.get('name', '')}) — {u.get('public_repos', 0)} public repos"


async def list_repos(per_page: int = 30) -> str:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            params={"per_page": per_page, "sort": "updated", "type": "all"},
            headers=_headers(),
        )
        resp.raise_for_status()
        repos = resp.json()
        if not repos:
            return "No repositories found."
        lines = []
        for r in repos:
            private = "🔒" if r["private"] else "🌍"
            lines.append(f"{private} {r['full_name']} — {r.get('description', '') or 'No description'} ⭐{r['stargazers_count']} 🍴{r['forks_count']}")
        return "\n".join(lines)


async def list_repos_json(per_page: int = 30) -> list[dict]:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            params={"per_page": per_page, "sort": "updated", "type": "all"},
            headers=_headers(),
        )
        resp.raise_for_status()
        repos = resp.json()
        return [{
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r.get("description", ""),
            "private": r["private"],
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "url": r["html_url"],
            "clone_url": r["clone_url"],
            "language": r.get("language", ""),
            "updated_at": r.get("updated_at", ""),
        } for r in repos]


async def list_issues_json(repo: str, state: str = "open", per_page: int = 20) -> list[dict]:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/issues",
            params={"state": state, "per_page": per_page},
            headers=_headers(),
        )
        resp.raise_for_status()
        issues = resp.json()
        return [{
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "user": i["user"]["login"],
            "comments": i["comments"],
            "url": i["html_url"],
            "body": (i.get("body") or "")[:500],
            "created_at": i.get("created_at", ""),
        } for i in issues if "pull_request" not in i]


async def list_pulls_json(repo: str, state: str = "open", per_page: int = 20) -> list[dict]:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            params={"state": state, "per_page": per_page},
            headers=_headers(),
        )
        resp.raise_for_status()
        pulls = resp.json()
        return [{
            "number": p["number"],
            "title": p["title"],
            "state": p["state"],
            "user": p["user"]["login"],
            "url": p["html_url"],
            "body": (p.get("body") or "")[:500],
            "created_at": p.get("created_at", ""),
            "head": p["head"]["label"],
            "base": p["base"]["label"],
        } for p in pulls]


async def search_repositories(query: str, per_page: int = 5) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/search/repositories",
            params={"q": query, "per_page": per_page},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return "No repositories found."
        lines = []
        for repo in items:
            lines.append(f"{repo['full_name']} — {repo.get('description') or 'No description'} ⭐ {repo['stargazers_count']}")
        return "\n".join(lines)


async def get_issue(repo: str, issue_number: int) -> str:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/issues/{issue_number}",
            headers=_headers(),
        )
        resp.raise_for_status()
        issue = resp.json()
        return (
            f"#{issue['number']} {issue['title']} [{issue['state']}]\n"
            f"By: {issue['user']['login']}\n"
            f"---\n{issue.get('body') or 'No description'}"
        )


async def create_issue(repo: str, title: str, body: str = "") -> str:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            json={"title": title, "body": body},
            headers=_headers(),
        )
        resp.raise_for_status()
        issue = resp.json()
        return f"Created #{issue['number']}: {issue['html_url']}"


async def create_pr(repo: str, title: str, head: str, base: str = "main", body: str = "") -> str:
    _require_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
            headers=_headers(),
        )
        resp.raise_for_status()
        pr = resp.json()
        return f"Created PR #{pr['number']}: {pr['html_url']}"


async def clone_repo(url: str, target_dir: str) -> str:
    result = subprocess.run(
        ["git", "clone", url, target_dir],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already exists" in stderr:
            return f"Repository already exists at {target_dir}"
        return f"Error cloning: {stderr}"
    return f"Cloned to {target_dir}"


def commit_and_push(repo_path: str, message: str, branch: str = "main") -> str:
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return f"Error: {repo_path} is not a git repository"
    commands = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", message],
        ["git", "push", "origin", branch],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=30)
        if result.returncode != 0 and "nothing to commit" not in result.stderr and "Everything up-to-date" not in result.stdout:
            return f"Error running {' '.join(cmd)}: {result.stderr.strip() or result.stdout.strip()}"
    return f"Committed and pushed to {branch}"
