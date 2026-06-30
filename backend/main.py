import asyncio
import logging
import os
import json
from contextlib import asynccontextmanager
from uuid import uuid4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ollama_client import list_models, chat_stream, pull_model_stream, ModelNotFoundError, OllamaOfflineError
from tool_executor import TOOL_DEFINITIONS, execute_tool
from tools import get_directory_tree
from tools.file_ops import set_allowed_base
from tools.shell import set_allowed_commands
from tools.github import set_token as set_github_token
from tools import list_repos_json, list_issues_json, list_pulls_json, get_user, set_token, get_token
import memory
import agent_registry


# ── Pydantic request models ───────────────────────────────────────────────────

PLANNING_SYSTEM_PROMPT = """You are an expert software architect and principal engineer operating in PLANNING MODE.

Your role:
- Analyze requirements and ask clarifying questions when anything is ambiguous
- Identify constraints, risks, and architectural tradeoffs
- Decompose complex tasks into numbered implementation plans
- Review proposed designs and suggest improvements
- Reason about technology choices with specific pros/cons

IMPORTANT: In planning mode, do NOT write code or create files. Produce specifications, plans, and analysis.
When producing an implementation plan, format each step as:
  Step N: [Action] — [File/Component] — [Specific details]

Think step by step. Be thorough."""

LEARN_SYSTEM_PROMPT = """You are a knowledgeable teacher and field guide with access to a curated offline library.

Your role:
- Answer questions thoroughly using the provided library context when available
- Always cite which source/book you are drawing from when using specific information
- If the context does not fully cover the question, supplement with general knowledge and say so clearly
- Break complex topics down step by step
- Use practical language — this app may be used in remote areas where clear guidance matters
- Be accurate above all else

This is a general knowledge mode. Do NOT write code unless explicitly asked."""


class ChatRequest(BaseModel):
    model: str
    messages: list[dict]
    workspace: str = "."
    session_id: str = ""
    mode: str = "chat"  # "plan", "chat", or "learn"
    embed_model: str = "nomic-embed-text"


class AgentRequest(BaseModel):
    model: str
    messages: list[dict]
    workspace: str = "."
    session_id: str = ""
    mode: str = "build"  # "build" is the only agent mode currently


class ToolCallRequest(BaseModel):
    tool: str
    args: dict
    workspace: str = "."


class WorkspaceRequest(BaseModel):
    path: str


class FileReadRequest(BaseModel):
    path: str


class TokenRequest(BaseModel):
    token: str


class GitHubRepoRequest(BaseModel):
    per_page: int = 30


class GitHubIssuesRequest(BaseModel):
    repo: str
    state: str = "open"
    per_page: int = 20


class GitHubPullsRequest(BaseModel):
    repo: str
    state: str = "open"
    per_page: int = 20


class GitHubCloneRequest(BaseModel):
    url: str
    target_dir: str
    workspace: str = "."


class GitHubCommitRequest(BaseModel):
    repo_path: str
    message: str
    branch: str = "main"


class FileSearchRequest(BaseModel):
    workspace: str
    query: str
    max_results: int = 10


class LibraryIngestRequest(BaseModel):
    path: str
    title: str = ""
    category: str = "general"
    embed_model: str = "nomic-embed-text"


class LibrarySearchRequest(BaseModel):
    query: str
    n_results: int = 5
    category: str = ""
    embed_model: str = "nomic-embed-text"


class MemoryProcessRequest(BaseModel):
    session_id: str
    model: str
    embed_model: str = "nomic-embed-text"


class SemanticMemoryRequest(BaseModel):
    key: str
    value: str


class SessionMessagesRequest(BaseModel):
    session_id: str
    workspace: str = ""
    model: str = ""


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    allowed = os.environ.get(
        "ALLOWED_COMMANDS",
        "python,python3,node,npm,npx,pip,pip3,git,ls,cat,echo,mkdir,cp,rmdir,rm",
    )
    set_allowed_commands([c.strip() for c in allowed.split(",")])
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        set_token(token)
    await memory.init_db()
    yield


app = FastAPI(title="Cody Local", lifespan=lifespan)

# CORS: use regex to match any localhost/127.0.0.1 origin on any port.
# This is a local dev tool — strict origin validation hurts UX here.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health / Models ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/models")
async def get_models():
    try:
        models = await list_models()
        return {"models": [{"name": m["name"], "size": m.get("size", 0)} for m in models]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama: {e}")


class ModelPullRequest(BaseModel):
    model: str


@app.post("/api/models/pull")
async def pull_model_endpoint(req: ModelPullRequest):
    async def stream():
        try:
            async for chunk in pull_model_stream(req.model):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'status': 'success', 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Chat (direct, streaming) ──────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.workspace:
        set_allowed_base(req.workspace)

    session_id = req.session_id or str(uuid4())

    logger.info(
        "[chat] model=%s workspace=%s mode=%s session=%s",
        req.model, req.workspace or ".", req.mode, session_id[:8],
    )

    async def event_stream():
        # Persist user message
        user_msgs = [m for m in req.messages if m["role"] == "user"]
        if user_msgs:
            await memory.upsert_session(session_id, req.workspace, req.model)
            await memory.save_message(session_id, "user", user_msgs[-1]["content"])

        assistant_content = ""

        # Inject relevant memory context (episodes + semantic facts)
        memory_system = await _build_memory_context(
            query=next((m["content"] for m in reversed(req.messages) if m["role"] == "user"), ""),
            embed_model=req.embed_model,
        )

        # Build message list based on mode
        if req.mode == "plan":
            system_parts = [PLANNING_SYSTEM_PROMPT]
            if memory_system:
                system_parts.insert(0, memory_system)
            send_messages = [{"role": "system", "content": "\n\n".join(system_parts)}] + list(req.messages)
            send_tools = None
        elif req.mode == "learn":
            last_user = next(
                (m["content"] for m in reversed(req.messages) if m["role"] == "user"), ""
            )
            library_results: list[dict] = []
            if last_user:
                try:
                    from library.store import embed_texts, search_library
                    embeds = await embed_texts([last_user], model=req.embed_model)
                    library_results = search_library(embeds[0], n_results=5)
                except Exception as e:
                    logger.warning("[chat/learn] library search failed: %s", e)
            if library_results:
                yield f"data: {json.dumps({'type': 'sources', 'results': library_results})}\n\n"
                context_block = "\n\n---\n\n".join(
                    f'Source: "{r["title"]}" ({r["category"]})\n{r["text"]}'
                    for r in library_results
                )
                system_content = (
                    LEARN_SYSTEM_PROMPT
                    + "\n\nCONTEXT FROM YOUR LIBRARY:\n\n"
                    + context_block
                    + "\n\nUse the above context to answer the question and cite your sources."
                )
            else:
                system_content = (
                    LEARN_SYSTEM_PROMPT
                    + "\n\nNote: No relevant library content was found. Answering from general knowledge."
                )
            if memory_system:
                system_content = memory_system + "\n\n" + system_content
            send_messages = [{"role": "system", "content": system_content}] + list(req.messages)
            send_tools = None
        else:
            if memory_system:
                send_messages = [{"role": "system", "content": memory_system}] + list(req.messages)
            else:
                send_messages = req.messages
            send_tools = TOOL_DEFINITIONS

        try:
            async for chunk in chat_stream(req.model, send_messages, tools=send_tools):
                msg = chunk.get("message", {})

                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        raw_args = fn.get("arguments", "{}")
                        try:
                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except json.JSONDecodeError as e:
                            logger.error("[chat] JSON parse error tool=%r: %s", fn.get("name"), e)
                            parsed_args = {}

                        yield f"data: {json.dumps({'type': 'tool_call', 'name': fn.get('name', ''), 'arguments': json.dumps(parsed_args)})}\n\n"

                        result = await execute_tool(fn["name"], parsed_args, req.workspace)
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': fn['name'], 'result': result})}\n\n"
                        send_messages.append({"role": "tool", "content": result})

                        async for follow_up in chat_stream(req.model, send_messages, tools=send_tools):
                            fu_content = follow_up.get("message", {}).get("content", "")
                            if fu_content:
                                assistant_content += fu_content
                                yield f"data: {json.dumps({'type': 'chunk', 'content': fu_content})}\n\n"
                            if follow_up.get("done"):
                                break

                elif msg.get("content"):
                    assistant_content += msg["content"]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': msg['content']})}\n\n"

                if chunk.get("done"):
                    yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
                    break

        except ModelNotFoundError as e:
            logger.error("Model not found: %s — %s", req.model, e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except OllamaOfflineError as e:
            logger.error("Ollama offline: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        if assistant_content:
            await memory.save_message(session_id, "assistant", assistant_content)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Agent (LangGraph, streaming) ──────────────────────────────────────────────

@app.post("/api/agent")
async def run_agent(req: AgentRequest):
    from agent.graph import build_agent
    from agent.state import AgentState

    if req.workspace:
        set_allowed_base(req.workspace)

    session_id = req.session_id or str(uuid4())

    logger.info(
        "[agent] model=%s workspace=%s session=%s",
        req.model, req.workspace or ".", session_id[:8],
    )

    queue = agent_registry.register_queue(session_id)

    # Persist session + user message so memory/process can load them later
    await memory.upsert_session(session_id, req.workspace, req.model)
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    if user_messages:
        await memory.save_message(session_id, "user", user_messages[-1].get("content", ""))

    state = AgentState(
        messages=req.messages,
        workspace=req.workspace,
        model=req.model,
        session_id=session_id,
        mode=req.mode,
    )

    agent = build_agent()

    async def run_graph():
        try:
            await agent.ainvoke(state.model_dump())
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put({"type": "done", "session_id": session_id})
            agent_registry.unregister_queue(session_id)

    asyncio.create_task(run_graph())

    async def event_stream():
        assistant_chunks: list[str] = []
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Agent timed out'})}\n\n"
                break
            if event.get("type") == "chunk":
                assistant_chunks.append(event.get("content", ""))
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                final_content = "".join(assistant_chunks).strip()
                if final_content:
                    await memory.save_message(session_id, "assistant", final_content)
                break
            if event.get("type") == "error":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Tool execution ────────────────────────────────────────────────────────────

@app.post("/api/tool")
async def call_tool(req: ToolCallRequest):
    result = await execute_tool(req.tool, req.args, req.workspace)
    return {"result": result}


# ── Workspace ─────────────────────────────────────────────────────────────────

def _validate_workspace_path(raw: str) -> str:
    """Expand, resolve symlinks, and validate a workspace path.
    
    Returns the resolved absolute path or raises HTTPException."""
    path = os.path.expanduser(raw.strip())
    if not path:
        raise HTTPException(status_code=400, detail="Path is empty")
    # Resolve symlinks so mounted drives & symlinked dirs work correctly
    resolved = os.path.realpath(path)
    if not os.path.exists(resolved):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {resolved}")
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail=f"Not a directory: {resolved}")
    if not os.access(resolved, os.R_OK):
        raise HTTPException(status_code=400, detail=f"Directory is not readable: {resolved}")
    if not os.access(resolved, os.X_OK):
        raise HTTPException(status_code=400, detail=f"Directory is not accessible: {resolved}")
    return resolved


@app.post("/api/workspace")
async def set_workspace(req: WorkspaceRequest):
    path = _validate_workspace_path(req.path)
    set_allowed_base(path)
    tree = get_directory_tree(path)
    await memory.add_recent_workspace(path)
    return {"path": path, "tree": tree}


@app.post("/api/workspace/validate")
async def validate_workspace(req: WorkspaceRequest):
    """Pre-flight check before actually opening a workspace.
    
    Returns the resolved path + any warnings (symlinks, mount points, etc)."""
    try:
        path = _validate_workspace_path(req.path)
        resolved = os.path.realpath(path)
        info = {
            "valid": True,
            "path": path,
            "resolved": resolved,
            "warnings": [],
        }
        if resolved != os.path.abspath(path):
            info["warnings"].append("Path contains symlinks — resolved to " + resolved)
        # Check if it's on a mounted filesystem
        if os.path.ismount(resolved):
            info["warnings"].append("Path is a mount point")
        parent = os.path.dirname(resolved)
        if parent and not os.access(parent, os.R_OK | os.X_OK):
            info["warnings"].append("Parent directory may not be accessible")
    except HTTPException as e:
        return {"valid": False, "error": e.detail}
    return info


@app.get("/api/workspace/recent")
async def list_recent_workspaces():
    workspaces = await memory.list_recent_workspaces()
    return {"workspaces": workspaces}


@app.post("/api/workspace/recent/remove")
async def remove_recent_workspace(req: WorkspaceRequest):
    await memory.remove_recent_workspace(req.path)
    return {"status": "removed"}


@app.get("/api/workspace/browse-roots")
async def browse_roots():
    """List top-level directories suitable as workspace starting points."""
    candidates = ["/", os.path.expanduser("~")]
    for mp in ["/mnt", "/media", "/run/media", "/Volumes"]:
        if os.path.isdir(mp):
            candidates.append(mp)
    seen = set()
    roots = []
    for c in candidates:
        try:
            rp = os.path.realpath(c)
            if rp in seen:
                continue
            seen.add(rp)
            roots.append({"path": rp, "label": c, "type": "directory"})
        except Exception:
            pass
    return {"roots": roots}


@app.get("/api/workspace/tree")
async def workspace_tree(path: str = "."):
    base = os.path.abspath(path)
    if not os.path.isdir(base):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    return {"path": base, "tree": get_directory_tree(base)}


@app.post("/api/workspace/explore")
async def explore_workspace(req: WorkspaceRequest):
    path = os.path.expanduser(req.path.strip())
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {path}")
    set_allowed_base(path)
    entries = []
    for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
        if entry.name.startswith("."):
            continue
        entries.append({
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "path": entry.path,
        })
    return {"path": path, "entries": entries}


@app.post("/api/workspace/search")
async def search_files(req: FileSearchRequest):
    root = os.path.expanduser(req.workspace.strip())
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="Workspace directory does not exist")
    query = req.query.lower()
    results = []
    skip_dirs = {"venv", "node_modules", "__pycache__", ".git", "dist", ".next", "build"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in skip_dirs]
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root)
            if query in f.lower() or query in rel.lower():
                results.append({"name": f, "path": full, "relative": rel})
                if len(results) >= req.max_results:
                    return {"results": results}
    return {"results": results}


@app.post("/api/workspace/read")
async def read_workspace_file(req: FileReadRequest):
    path = os.path.expanduser(req.path.strip())
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"File does not exist: {path}")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def get_sessions(workspace: str = ""):
    sessions = await memory.list_sessions(workspace)
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    messages = await memory.load_session(session_id)
    return {"messages": messages}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    await memory.delete_session(session_id)
    return {"status": "deleted"}


# ── GitHub ────────────────────────────────────────────────────────────────────

@app.post("/api/github/token")
async def github_set_token(req: TokenRequest):
    set_github_token(req.token)
    return {"status": "ok"}


@app.get("/api/github/user")
async def github_user():
    try:
        user = await get_user()
        return {"user": user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/github/repos")
async def github_repos(req: GitHubRepoRequest):
    try:
        repos = await list_repos_json(req.per_page)
        return {"repos": repos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/github/issues")
async def github_issues(req: GitHubIssuesRequest):
    try:
        issues = await list_issues_json(req.repo, req.state, req.per_page)
        return {"issues": issues}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/github/pulls")
async def github_pulls(req: GitHubPullsRequest):
    try:
        pulls = await list_pulls_json(req.repo, req.state, req.per_page)
        return {"pulls": pulls}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/github/clone")
async def github_clone(req: GitHubCloneRequest):
    from tools.github import clone_repo
    base = os.path.expanduser(req.workspace.strip())
    target = os.path.join(base, req.target_dir)
    result = await clone_repo(req.url, target)
    return {"result": result, "path": target}


@app.post("/api/github/commit")
async def github_commit(req: GitHubCommitRequest):
    from tools.github import commit_and_push
    try:
        result = commit_and_push(req.repo_path, req.message, req.branch)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Library ───────────────────────────────────────────────────────────────────

@app.get("/api/library/status")
async def library_status():
    try:
        from library.store import collection_count, CHROMA_PATH
        count = collection_count()
        books = await memory.list_books()
        return {
            "available": True,
            "chunk_count": count,
            "book_count": len(books),
            "chroma_path": CHROMA_PATH,
        }
    except ImportError as e:
        return {"available": False, "error": f"chromadb not installed: {e}"}
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/api/library/books")
async def library_list_books():
    books = await memory.list_books()
    return {"books": books}


@app.post("/api/library/ingest")
async def library_ingest(req: LibraryIngestRequest):
    from library.ingest import ingest_file

    path = os.path.expanduser(req.path.strip())
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"File not found: {path}")

    title = req.title.strip() or os.path.splitext(os.path.basename(path))[0]

    logger.info("[library] ingesting %s as %r category=%s model=%s", path, title, req.category, req.embed_model)

    try:
        book_id, chunk_count = await ingest_file(
            path=path,
            title=title,
            category=req.category,
            embed_model=req.embed_model,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("[library] ingest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    await memory.add_book(
        book_id=book_id,
        title=title,
        category=req.category,
        source_path=path,
        chunk_count=chunk_count,
    )

    logger.info("[library] indexed %r — %d chunks (book_id=%s)", title, chunk_count, book_id[:8])
    return {"book_id": book_id, "title": title, "chunk_count": chunk_count}


@app.delete("/api/library/books/{book_id}")
async def library_delete_book(book_id: str):
    from library.store import delete_book_chunks
    try:
        delete_book_chunks(book_id)
    except Exception as e:
        logger.warning("[library] delete chunks error: %s", e)
    await memory.delete_book(book_id)
    return {"status": "deleted", "book_id": book_id}


async def _build_memory_context(query: str, embed_model: str) -> str:
    """Search episodic + semantic memory and return a formatted context block, or '' if empty."""
    if not query:
        return ""
    try:
        from library.store import embed_texts, search_episodes, search_semantic
        embeds = await embed_texts([query], model=embed_model)
        emb = embeds[0]
        episodes = search_episodes(emb, n_results=3)
        semantic = search_semantic(emb, n_results=6)
        if not episodes and not semantic:
            return ""
        parts: list[str] = ["[MEMORY CONTEXT — from past sessions]"]
        if semantic:
            parts.append("Known facts about you and your work:")
            for s in semantic:
                parts.append(f"  • {s['key']}: {s['value']}")
        if episodes:
            parts.append("Relevant past sessions:")
            for ep in episodes:
                date = ep.get("created_at", "")[:10]
                parts.append(f"  [{date}] {ep['summary']}")
        parts.append("[END MEMORY]")
        return "\n".join(parts)
    except Exception as e:
        logger.debug("[memory] context build skipped: %s", e)
        return ""


@app.post("/api/library/search")
async def library_search(req: LibrarySearchRequest):
    from library.store import embed_texts, search_library

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        embeds = await embed_texts([req.query], model=req.embed_model)
        results = search_library(
            embeds[0],
            n_results=req.n_results,
            category=req.category or None,
        )
    except Exception as e:
        logger.error("[library] search error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    return {"results": results, "query": req.query}


# ── Memory ────────────────────────────────────────────────────────────────────

@app.post("/api/memory/process")
async def memory_process(req: MemoryProcessRequest):
    """Summarise a session, extract semantic facts, embed + store both."""
    from memory_agent import process_session
    from library.store import embed_texts, add_episode_embedding, add_semantic_embedding

    messages = await memory.load_session(req.session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found or empty")

    result = await process_session(req.session_id, messages, req.model)

    saved_episode_id = None
    if result["summary"]:
        sessions = await memory.list_sessions()
        meta = next((s for s in sessions if s["session_id"] == req.session_id), {})
        episode_id = await memory.save_episode(
            session_id=req.session_id,
            workspace=meta.get("workspace", ""),
            model=meta.get("model", req.model),
            summary=result["summary"],
        )
        saved_episode_id = episode_id
        try:
            embeds = await embed_texts([result["summary"]], model=req.embed_model)
            episodes_list = await memory.list_episodes(limit=1)
            if episodes_list:
                add_episode_embedding(
                    episode_id=episode_id,
                    summary=result["summary"],
                    embedding=embeds[0],
                    session_id=req.session_id,
                    workspace=meta.get("workspace", ""),
                    created_at=episodes_list[0].get("created_at", ""),
                )
        except Exception as e:
            logger.warning("[memory] episode embed failed: %s", e)

    saved_facts: list[str] = []
    for fact in result["facts"]:
        key = fact.get("key", "").strip()
        value = fact.get("value", "").strip()
        if not key or not value:
            continue
        await memory.upsert_semantic(key, value, source=req.session_id)
        saved_facts.append(key)
        try:
            embeds = await embed_texts([f"{key}: {value}"], model=req.embed_model)
            semantics = await memory.list_semantics()
            sem = next((s for s in semantics if s["key"] == key), None)
            if sem:
                add_semantic_embedding(
                    semantic_id=sem["id"],
                    key=key,
                    value=value,
                    embedding=embeds[0],
                    source=req.session_id,
                )
        except Exception as e:
            logger.warning("[memory] semantic embed failed for %s: %s", key, e)

    log_path = await memory.write_session_log(req.session_id)

    logger.info(
        "[memory] processed session %s — summary=%s facts=%d log=%s",
        req.session_id[:8], bool(result["summary"]), len(saved_facts), log_path,
    )
    return {
        "summary": result["summary"],
        "facts_saved": saved_facts,
        "episode_id": saved_episode_id,
        "log_path": log_path,
    }


@app.get("/api/memory/episodes")
async def memory_list_episodes():
    episodes = await memory.list_episodes()
    return {"episodes": episodes}


@app.delete("/api/memory/episodes/{episode_id}")
async def memory_delete_episode(episode_id: int):
    from library.store import delete_episode_embedding
    delete_episode_embedding(episode_id)
    await memory.delete_episode(episode_id)
    return {"status": "deleted"}


@app.get("/api/memory/semantic")
async def memory_list_semantic():
    facts = await memory.list_semantics()
    return {"facts": facts}


@app.post("/api/memory/semantic")
async def memory_add_semantic(req: SemanticMemoryRequest):
    await memory.upsert_semantic(req.key.strip(), req.value.strip())
    facts = await memory.list_semantics()
    sem = next((s for s in facts if s["key"] == req.key.strip()), None)
    return {"status": "saved", "fact": sem}


@app.delete("/api/memory/semantic/{semantic_id}")
async def memory_delete_semantic(semantic_id: int):
    from library.store import delete_semantic_embedding
    delete_semantic_embedding(semantic_id)
    await memory.delete_semantic(semantic_id)
    return {"status": "deleted"}


@app.get("/api/memory/session-logs")
async def memory_list_session_logs():
    from memory import SESSION_LOGS_DIR
    os.makedirs(SESSION_LOGS_DIR, exist_ok=True)
    files = sorted(
        [f for f in os.listdir(SESSION_LOGS_DIR) if f.endswith(".md")],
        reverse=True,
    )
    return {
        "logs_dir": SESSION_LOGS_DIR,
        "logs": [{"filename": f, "path": os.path.join(SESSION_LOGS_DIR, f)} for f in files],
    }
