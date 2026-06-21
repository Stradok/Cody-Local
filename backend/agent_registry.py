import asyncio

_queues: dict[str, asyncio.Queue] = {}


def register_queue(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    return q


def get_queue(session_id: str) -> asyncio.Queue | None:
    return _queues.get(session_id)


def unregister_queue(session_id: str) -> None:
    _queues.pop(session_id, None)
