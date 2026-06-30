import json
import os
import aiosqlite
from datetime import datetime, timezone

DB_PATH = os.environ.get("CODY_DB_PATH", os.path.join(os.path.expanduser("~"), ".cody-local", "sessions.db"))
SESSION_LOGS_DIR = os.environ.get(
    "CODY_SESSION_LOGS_DIR",
    os.path.join(os.path.expanduser("~"), ".cody-local", "session-logs"),
)


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                workspace  TEXT NOT NULL DEFAULT '',
                model      TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                extra      TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                workspace   TEXT NOT NULL DEFAULT '',
                model       TEXT NOT NULL DEFAULT '',
                summary     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS semantic_memories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key        TEXT NOT NULL UNIQUE,
                value      TEXT NOT NULL,
                source     TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                book_id     TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                source_path TEXT NOT NULL DEFAULT '',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                added_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def upsert_session(session_id: str, workspace: str, model: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO sessions(session_id, workspace, model)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                workspace = excluded.workspace,
                model = excluded.model,
                updated_at = datetime('now')
        """, (session_id, workspace, model))
        await db.commit()


async def save_message(session_id: str, role: str, content: str, extra: dict | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages(session_id, role, content, extra) VALUES (?, ?, ?, ?)",
            (session_id, role, content, json.dumps(extra or {})),
        )
        await db.execute(
            "UPDATE sessions SET updated_at = datetime('now') WHERE session_id = ?",
            (session_id,),
        )
        await db.commit()


async def load_session(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content, extra FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {"role": row[0], "content": row[1], **json.loads(row[2])}
        for row in rows
    ]


async def list_sessions(workspace: str = "") -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace:
            query = "SELECT session_id, workspace, model, updated_at FROM sessions WHERE workspace = ? ORDER BY updated_at DESC LIMIT 50"
            params = (workspace,)
        else:
            query = "SELECT session_id, workspace, model, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 50"
            params = ()
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [
        {"session_id": row[0], "workspace": row[1], "model": row[2], "updated_at": row[3]}
        for row in rows
    ]


async def delete_session(session_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()


# ── Recent Workspaces ─────────────────────────────────────────────────────────


async def add_recent_workspace(path: str) -> None:
    resolved = os.path.realpath(os.path.expanduser(path.strip()))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recent_workspaces (
                path       TEXT PRIMARY KEY,
                resolved   TEXT NOT NULL,
                label      TEXT NOT NULL DEFAULT '',
                last_opened TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        label = os.path.basename(resolved)
        await db.execute("""
            INSERT INTO recent_workspaces(path, resolved, label, last_opened)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(path) DO UPDATE SET
                resolved = excluded.resolved,
                label = excluded.label,
                last_opened = datetime('now')
        """, (path, resolved, label))
        await db.commit()


async def list_recent_workspaces(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT path, resolved, label, last_opened FROM recent_workspaces ORDER BY last_opened DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        except Exception:
            return []
    return [
        {"path": row[0], "resolved": row[1], "label": row[2], "last_opened": row[3]}
        for row in rows
    ]


async def remove_recent_workspace(path: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM recent_workspaces WHERE path = ?", (path,))
        await db.commit()


# ── Library Books ─────────────────────────────────────────────────────────────


async def add_book(
    book_id: str,
    title: str,
    category: str,
    source_path: str,
    chunk_count: int,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO books(book_id, title, category, source_path, chunk_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                source_path = excluded.source_path,
                chunk_count = excluded.chunk_count
            """,
            (book_id, title, category, source_path, chunk_count),
        )
        await db.commit()


async def list_books() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT book_id, title, category, source_path, chunk_count, added_at FROM books ORDER BY added_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        except Exception:
            return []
    return [
        {
            "book_id": row[0],
            "title": row[1],
            "category": row[2],
            "source_path": row[3],
            "chunk_count": row[4],
            "added_at": row[5],
        }
        for row in rows
    ]


async def delete_book(book_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
        await db.commit()


# ── Episodic Memory ───────────────────────────────────────────────────────────


async def save_episode(
    session_id: str,
    workspace: str,
    model: str,
    summary: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO episodes(session_id, workspace, model, summary) VALUES (?, ?, ?, ?)",
            (session_id, workspace, model, summary),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def list_episodes(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT id, session_id, workspace, model, summary, created_at FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        except Exception:
            return []
    return [
        {
            "id": row[0],
            "session_id": row[1],
            "workspace": row[2],
            "model": row[3],
            "summary": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


async def delete_episode(episode_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        await db.commit()


# ── Semantic Memory ───────────────────────────────────────────────────────────


async def upsert_semantic(key: str, value: str, source: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO semantic_memories(key, value, source)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                source = excluded.source,
                updated_at = datetime('now')
            """,
            (key, value, source),
        )
        await db.commit()


async def list_semantics() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT id, key, value, source, updated_at FROM semantic_memories ORDER BY updated_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        except Exception:
            return []
    return [
        {"id": row[0], "key": row[1], "value": row[2], "source": row[3], "updated_at": row[4]}
        for row in rows
    ]


async def delete_semantic(semantic_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM semantic_memories WHERE id = ?", (semantic_id,))
        await db.commit()


# ── Session Log Files ─────────────────────────────────────────────────────────


async def write_session_log(session_id: str) -> str:
    """
    Write the full session conversation to a markdown file.
    Returns the path of the written file.
    """
    messages = await load_session(session_id)
    if not messages:
        return ""

    sessions = await list_sessions()
    meta = next((s for s in sessions if s["session_id"] == session_id), {})
    workspace = meta.get("workspace", "")
    model = meta.get("model", "")
    updated_at = meta.get("updated_at", "")

    os.makedirs(SESSION_LOGS_DIR, exist_ok=True)
    date_str = (updated_at or datetime.now(timezone.utc).isoformat())[:10]
    filename = f"{date_str}-{session_id[:8]}.md"
    filepath = os.path.join(SESSION_LOGS_DIR, filename)

    lines = [
        f"# Chat Session — {date_str}",
        f"",
        f"**Session ID:** `{session_id}`  ",
        f"**Model:** {model}  ",
        f"**Workspace:** {workspace or '(none)'}  ",
        f"**Last updated:** {updated_at}  ",
        f"",
        f"---",
        f"",
    ]

    for msg in messages:
        role = msg.get("role", "")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"**You:** {content}")
        elif role == "assistant":
            lines.append(f"**Cody:** {content}")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath
