import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

CHROMA_PATH = os.environ.get(
    "CODY_CHROMA_PATH",
    os.path.join(os.path.expanduser("~"), ".cody-local", "library"),
)
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL_DEFAULT = "nomic-embed-text"
COLLECTION_NAME = "library"
EPISODES_COLLECTION = "episodes"
SEMANTIC_COLLECTION = "semantic"

_client = None
_collection = None
_episodes_col = None
_semantic_col = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_episodes_col():
    global _episodes_col
    if _episodes_col is None:
        _episodes_col = _get_client().get_or_create_collection(
            name=EPISODES_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _episodes_col


def _get_semantic_col():
    global _semantic_col
    if _semantic_col is None:
        _semantic_col = _get_client().get_or_create_collection(
            name=SEMANTIC_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _semantic_col


async def embed_texts(texts: list[str], model: str = EMBED_MODEL_DEFAULT) -> list[list[float]]:
    """Embed a list of texts via Ollama's /api/embed endpoint, 20 at a time concurrently."""

    async def _one(client: httpx.AsyncClient, text: str) -> list[float]:
        resp = await client.post(
            f"{OLLAMA_BASE}/api/embed",
            json={"model": model, "input": text},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    results: list[list[float]] = []
    async with httpx.AsyncClient() as client:
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await asyncio.gather(*[_one(client, t) for t in batch])
            results.extend(embeddings)
            logger.info("[store] embedded %d/%d chunks", i + len(batch), len(texts))
    return results


def add_chunks(
    book_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    title: str,
    category: str,
    source_path: str,
) -> None:
    collection = _get_collection()
    ids = [f"{book_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "book_id": book_id,
            "title": title,
            "category": category,
            "source_path": source_path,
            "chunk_idx": i,
        }
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    logger.info("[store] stored %d chunks for book %s", len(chunks), book_id[:8])


def delete_book_chunks(book_id: str) -> None:
    collection = _get_collection()
    collection.delete(where={"book_id": book_id})
    logger.info("[store] deleted chunks for book %s", book_id[:8])


def search_library(
    query_embedding: list[float],
    n_results: int = 5,
    category: str | None = None,
) -> list[dict]:
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": actual_n,
        "include": ["documents", "metadatas", "distances"],
    }
    if category:
        kwargs["where"] = {"category": category}

    results = collection.query(**kwargs)
    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append(
            {
                "text": doc,
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "book_id": meta.get("book_id", ""),
                "chunk_idx": int(meta.get("chunk_idx", 0)),
                "score": round(1.0 - float(dist), 4),
            }
        )
    return out


def collection_count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


# ── Episode memory ─────────────────────────────────────────────────────────────


def add_episode(episode_id: int, summary: str, session_id: str, workspace: str, created_at: str) -> None:
    col = _get_episodes_col()
    doc_id = f"ep_{episode_id}"
    existing = col.get(ids=[doc_id])
    if existing["ids"]:
        col.delete(ids=[doc_id])
    embedding = None  # caller embeds separately if needed; stored by chroma without embedding for now
    col.add(
        ids=[doc_id],
        documents=[summary],
        metadatas=[{"session_id": session_id, "workspace": workspace, "created_at": created_at}],
    )


def add_episode_embedding(episode_id: int, summary: str, embedding: list[float], session_id: str, workspace: str, created_at: str) -> None:
    col = _get_episodes_col()
    doc_id = f"ep_{episode_id}"
    try:
        col.delete(ids=[doc_id])
    except Exception:
        pass
    col.add(
        ids=[doc_id],
        documents=[summary],
        embeddings=[embedding],
        metadatas=[{"session_id": session_id, "workspace": workspace, "created_at": created_at}],
    )


def search_episodes(query_embedding: list[float], n_results: int = 3) -> list[dict]:
    col = _get_episodes_col()
    count = col.count()
    if count == 0:
        return []
    actual_n = min(n_results, count)
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=actual_n,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        out.append({
            "summary": doc,
            "session_id": meta.get("session_id", ""),
            "workspace": meta.get("workspace", ""),
            "created_at": meta.get("created_at", ""),
            "score": round(1.0 - float(dist), 4),
        })
    return out


def delete_episode_embedding(episode_id: int) -> None:
    try:
        _get_episodes_col().delete(ids=[f"ep_{episode_id}"])
    except Exception:
        pass


# ── Semantic memory ────────────────────────────────────────────────────────────


def add_semantic_embedding(semantic_id: int, key: str, value: str, embedding: list[float], source: str = "") -> None:
    col = _get_semantic_col()
    doc_id = f"sem_{semantic_id}"
    try:
        col.delete(ids=[doc_id])
    except Exception:
        pass
    col.add(
        ids=[doc_id],
        documents=[f"{key}: {value}"],
        embeddings=[embedding],
        metadatas=[{"key": key, "value": value, "source": source}],
    )


def search_semantic(query_embedding: list[float], n_results: int = 5) -> list[dict]:
    col = _get_semantic_col()
    count = col.count()
    if count == 0:
        return []
    actual_n = min(n_results, count)
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=actual_n,
        include=["metadatas", "distances"],
    )
    out = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        out.append({
            "key": meta.get("key", ""),
            "value": meta.get("value", ""),
            "score": round(1.0 - float(dist), 4),
        })
    return out


def delete_semantic_embedding(semantic_id: int) -> None:
    try:
        _get_semantic_col().delete(ids=[f"sem_{semantic_id}"])
    except Exception:
        pass
