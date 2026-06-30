import json
import logging
import httpx
from typing import AsyncGenerator

OLLAMA_BASE = "http://localhost:11434"
logger = logging.getLogger(__name__)


class ModelNotFoundError(Exception):
    """Ollama returned 404 — model not installed."""


class OllamaOfflineError(Exception):
    """Ollama is unreachable."""


async def list_models() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            return resp.json().get("models", [])
    except httpx.ConnectError as e:
        raise OllamaOfflineError(
            f"Cannot connect to Ollama at {OLLAMA_BASE}. Start it with: ollama serve"
        ) from e


async def check_model(model: str) -> bool:
    try:
        models = await list_models()
        names = [m["name"] for m in models]
        base = model.split(":")[0]
        return any(
            n == model or n.startswith(model + ":") or n.split(":")[0] == base
            for n in names
        )
    except Exception:
        return False


async def pull_model_stream(model: str) -> AsyncGenerator[dict, None]:
    """Stream Ollama pull progress events."""
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE}/api/pull",
                json={"name": model, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            pass
    except httpx.ConnectError as e:
        raise OllamaOfflineError(
            f"Cannot connect to Ollama at {OLLAMA_BASE}. Start it with: ollama serve"
        ) from e


async def chat_stream(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    body: dict = {"model": model, "messages": messages, "stream": True}
    if tools:
        body["tools"] = tools

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/chat", json=body) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    if resp.status_code == 404:
                        raise ModelNotFoundError(
                            f'Model "{model}" is not installed.\n'
                            f"Pull it first:\n\n  ollama pull {model}\n\n"
                            f"Or select an installed model from the dropdown."
                        )
                    raise RuntimeError(
                        f"Ollama API error {resp.status_code}: {resp.text[:300]}"
                    )
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError as e:
                            logger.warning("Ollama JSON parse error: %s | line=%r", e, line[:200])

    except httpx.ConnectError as e:
        raise OllamaOfflineError(
            f"Ollama is not running.\n\nStart it with:\n\n  ollama serve"
        ) from e
    except (ModelNotFoundError, OllamaOfflineError):
        raise
