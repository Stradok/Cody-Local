import json
import os
import aiosqlite

DB_PATH = os.environ.get("CODY_DB_PATH", os.path.join(os.path.expanduser("~"), ".cody-local", "sessions.db"))


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
