# Cody Local

A fully local AI coding assistant that runs entirely on your machine. No cloud required, no API keys, no usage limits — just your models via [Ollama](https://ollama.com).

Built with a **FastAPI** backend and a **Next.js** frontend, Cody Local supports interactive chat, architectural planning, and an autonomous multi-step coding agent that can read files, write code, run shell commands, and interact with GitHub — all from a clean browser UI.

---

## Features

- **Local-first** — all inference runs through Ollama; your code never leaves your machine
- **Chat mode** — streaming chat with tool-calling (file read/write, shell execution, GitHub)
- **Plan mode** — software architect persona that produces structured implementation plans without writing code
- **Agent mode** — autonomous LangGraph agent that breaks tasks into steps and executes them using specialist sub-agents (planner, coder, filesystem, terminal, validator)
- **Complete file management** — read, write, create, delete, move, rename files and directories
- **Shell execution** — run any command: tests, builds, scripts, package management
- **Full Git workflow** — clone, branch, commit, push, pull, view history and diffs (all 5 new git commands!)
- **GitHub integration** — repos, issues, PRs, clone, commit, push
- **Session memory** — conversation history persisted in a local SQLite database
- **Workspace sandboxing** — file and shell operations are scoped to the open workspace; path traversal is blocked
- **Auto port selection** — if the default ports are taken, the next free port is used automatically
- **Works completely offline** — no internet required, all processing local

---

## What Can It Do?

Cody-Local can **do everything Claude Code does** — completely offline:

✅ **Code Development**
- Write and modify code in any language
- Read existing code and understand it
- Debug errors automatically
- Run tests and verify code works

✅ **File & Project Management**
- Read/write/delete/organize files
- Create project structures
- Manage directories
- Browse code repositories

✅ **Git & GitHub Workflow**
- Clone repositories
- Create and switch branches
- Commit changes with messages
- Push to GitHub
- View commit history and diffs
- Create pull requests and issues

✅ **Autonomous Execution**
- Multi-step task execution
- Automatic error recovery
- Verify work before finishing
- Iterative refinement

**Full details:** See **[CAPABILITIES.md](./CAPABILITIES.md)** for real-world examples and use cases.

---

## Architecture

```
cody-local/
├── backend/                  # FastAPI (Python)
│   ├── main.py               # API routes: chat, agent, workspace, GitHub, sessions
│   ├── ollama_client.py      # Streaming Ollama client
│   ├── tool_executor.py      # Tool dispatch layer
│   ├── memory.py             # SQLite session + workspace history
│   ├── agent_registry.py     # SSE queue registry per session
│   ├── agent/
│   │   ├── graph.py          # LangGraph agent graph definition
│   │   ├── nodes.py          # Specialist nodes: planner, coding, filesystem, terminal, validation, review
│   │   └── state.py          # Typed agent state
│   └── tools/
│       ├── file_ops.py       # Read, write, list, move, rename, delete (sandboxed)
│       ├── shell.py          # execute_command (allowlist-restricted)
│       └── github.py         # GitHub API: repos, issues, PRs, clone, commit
└── frontend/                 # Next.js 14 + Tailwind + Monaco Editor
```

### Agent graph

When the agent mode is used, the request flows through a LangGraph graph:

```
START → planner → [coding | filesystem | terminal | validation]* → review → END
```

The planner produces a numbered step list. Each step is classified by keyword into the appropriate specialist node. Steps iterate until completion, hitting a maximum of 20 tool-call rounds per step before moving on.

---

## Prerequisites

| Dependency | Minimum version |
|---|---|
| [Ollama](https://ollama.com) | Latest |
| Python | 3.11+ |
| Node.js | 18+ |

Ollama must be running and have at least one model pulled before you start Cody Local.

```bash
ollama pull qwen2.5-coder:7b   # recommended for coding tasks
# or any other model you prefer
ollama serve                   # start Ollama if it is not already running
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd cody-local

# 2. Install all dependencies (run once)
make setup

# 3. Start backend + frontend
make run
```

The terminal will print the URLs for both services:

```
Backend:   http://127.0.0.1:8000
Frontend:  http://localhost:3000
API docs:  http://127.0.0.1:8000/docs
```

Open the frontend URL in your browser and select a model to start chatting.

---

## Portable & Offline Setup

For **external drives, USB sticks, or offline environments** (villages, remote areas, no internet):

```bash
# 1. Run portable setup (instead of make setup)
bash portable-setup.sh

# 2. Works from any location — external drive, local machine, etc.
make run
```

**For complete offline mode** (no internet on destination machine):
- See **[PORTABLE.md](./PORTABLE.md)** for detailed offline deployment guide
- Pre-download AI models on a machine with internet
- Transfer everything via external drive
- Alternative: Use Docker (`docker-compose -f docker-compose.portable.yml up`)

**Use cases:**
- 🚗 Traveling with limited connectivity
- 📍 Villages and rural communities with no internet
- 🏢 Corporate air-gapped networks
- 🎓 Workshops and training in offline environments

---

## Configuration

Copy the example environment file and edit as needed:

```bash
cp backend/.env.example backend/.env
```

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `GITHUB_TOKEN` | *(empty)* | Personal access token for GitHub features |
| `ALLOWED_COMMANDS` | `python,python3,node,npm,...` | Comma-separated list of shell commands the agent may run |
| `MAX_TOOL_CALLS` | `25` | Max tool calls per chat turn |

The GitHub token can also be set at runtime from the Settings panel in the UI — no restart required.

---

## Make Commands

| Command | Description |
|---|---|
| `make setup` | Install Python venv + npm dependencies (run once) |
| `make portable` | Complete setup: check Ollama, download models, install deps (recommended!) |
| `make run` | Start both backend and frontend |
| `make run-backend` | Start the FastAPI backend only |
| `make run-frontend` | Start the Next.js frontend only |
| `make health` | Check that backend, frontend, and Ollama are reachable |
| `make logs` | Tail the most recent backend log file |
| `make clean` | Remove Python `__pycache__` files |
| `make clean-all` | Remove venv, `node_modules`, and `.next` |

---

## API Overview

The backend exposes a REST + SSE API at `http://127.0.0.1:8000`. Interactive docs are at `/docs`.

### Main Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/models` | GET | List available Ollama models |
| `/api/models/pull` | POST | Pull a model from Ollama (streaming) |
| `/api/chat` | POST | Streaming chat with optional tool use |
| `/api/agent` | POST | Run the autonomous LangGraph agent |
| `/api/workspace` | POST | Open a workspace directory |
| `/api/sessions` | GET | List chat sessions |
| `/api/github/*` | POST/GET | GitHub integration endpoints |

### Available Tools (Auto-called by Agent)
**File Operations:** `read_file`, `write_file`, `create_directory`, `move_file`, `rename_file`, `delete_file`, `delete_directory`, `list_directory`

**Shell:** `execute_command` (runs any shell command)

**Git Operations:** `git_status`, `git_diff`, `git_branch`, `git_pull`, `git_log`, `clone_repo`, `commit_and_push`

**GitHub API:** `search_repositories`, `get_issue`, `create_issue`, `create_pr`, `list_repos`, `get_user`

Streaming endpoints return `text/event-stream` (SSE) with typed JSON events: `chunk`, `tool_call`, `tool_result`, `plan`, `step_start`, `step_done`, `done`, `error`.

---

## Security Notes

- **File operations** are sandboxed to the currently open workspace. The backend resolves symlinks and rejects any path that escapes the workspace root.
- **Shell commands** are restricted to the `ALLOWED_COMMANDS` allowlist. The default list covers common development tools.
- **CORS** is configured to allow any `localhost` or `127.0.0.1` origin — this is intentional for a local-only tool.
- No data is sent to external services unless you explicitly use the GitHub integration or pull a model through Ollama.

---

## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com) + [Uvicorn](https://www.uvicorn.org)
- [LangGraph](https://github.com/langchain-ai/langgraph) — agent graph orchestration
- [LangChain Ollama](https://github.com/langchain-ai/langchain) — Ollama integration
- [aiosqlite](https://github.com/omnilib/aiosqlite) — async SQLite for session memory
- [httpx](https://www.python-httpx.org) — async HTTP client (GitHub API)

**Frontend**
- [Next.js 14](https://nextjs.org)
- [Tailwind CSS](https://tailwindcss.com)
- [Monaco Editor](https://microsoft.github.io/monaco-editor/) — in-browser code editor
- [Lucide React](https://lucide.dev) — icons

---

## Documentation

- **[CAPABILITIES.md](./CAPABILITIES.md)** — Complete guide: what Cody-Local can do, real examples, use cases
- **[PORTABLE.md](./PORTABLE.md)** — Offline deployment: how to use on USB drives, external drives, no internet
- **[MODELS.md](./MODELS.md)** — AI model selection guide: choosing the right model for your hardware
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** — For contributors: architecture deep-dive, extending with custom tools

---

## License

MIT
