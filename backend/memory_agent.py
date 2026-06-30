import json
import logging

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """You are a memory extraction assistant. Read this conversation and output ONLY valid JSON — no preamble, no markdown fences.

Conversation:
{transcript}

Output this exact JSON structure:
{{
  "summary": "3-5 sentence summary of what was discussed and accomplished",
  "facts": [
    {{"key": "short_snake_case_key", "value": "specific fact value"}}
  ]
}}

Rules:
- summary: concise, past tense, what the user did/asked/decided
- facts: 0-8 entries, only specific useful things to remember (user name, project name, preferences, tools chosen, decisions made, problems solved)
- Do not include trivial or obvious facts
- Keys must be short snake_case (e.g. "preferred_model", "project_name", "os")"""


async def process_session(
    session_id: str,
    messages: list[dict],
    model: str,
) -> dict:
    """
    Summarise a session and extract semantic facts using the LLM.
    Returns {"summary": str, "facts": [{"key": str, "value": str}]}
    """
    from ollama_client import chat_stream

    chat_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
    if len(chat_messages) < 2:
        return {"summary": "", "facts": []}

    lines: list[str] = []
    for m in chat_messages[:40]:
        role = "User" if m["role"] == "user" else "Assistant"
        content = (m.get("content") or "")[:600].strip()
        if content:
            lines.append(f"{role}: {content}")

    transcript = "\n\n".join(lines)
    prompt = _EXTRACT_PROMPT.format(transcript=transcript)

    full_response = ""
    try:
        async for chunk in chat_stream(model, [{"role": "user", "content": prompt}], tools=None):
            content = chunk.get("message", {}).get("content", "")
            if content:
                full_response += content
            if chunk.get("done"):
                break
    except Exception as e:
        logger.error("[memory_agent] chat_stream error: %s", e)
        return {"summary": "", "facts": []}

    try:
        start = full_response.find("{")
        end = full_response.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("no JSON found")
        data = json.loads(full_response[start:end])
        return {
            "summary": str(data.get("summary", "")).strip(),
            "facts": [
                {"key": str(f["key"]).strip(), "value": str(f["value"]).strip()}
                for f in data.get("facts", [])
                if f.get("key") and f.get("value")
            ],
        }
    except Exception as e:
        logger.warning("[memory_agent] JSON parse failed: %s — raw: %r", e, full_response[:300])
        return {"summary": full_response[:400].strip() if full_response else "", "facts": []}
