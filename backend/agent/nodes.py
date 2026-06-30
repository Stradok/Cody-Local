import json
import logging
import os

from agent.state import AgentState
from ollama_client import chat_stream
from tool_executor import TOOL_DEFINITIONS, execute_tool
from agent_registry import get_queue

logger = logging.getLogger(__name__)

# ── Subset tool lists per agent specialty ─────────────────────────────────────

_FS_TOOL_NAMES = {"list_directory", "create_directory", "move_file", "rename_file", "delete_file", "delete_directory"}
_TERMINAL_TOOL_NAMES = {"execute_command"}
_CODING_TOOL_NAMES = {"read_file", "write_file", "list_directory", "create_directory"}
_VALIDATION_TOOL_NAMES = {"read_file", "list_directory", "execute_command"}

def _filter_tools(names: set) -> list[dict]:
    return [t for t in TOOL_DEFINITIONS if t["function"]["name"] in names]

CODING_TOOLS     = _filter_tools(_CODING_TOOL_NAMES)
FILESYSTEM_TOOLS = _filter_tools(_FS_TOOL_NAMES)
TERMINAL_TOOLS   = _filter_tools(_TERMINAL_TOOL_NAMES)
VALIDATION_TOOLS = _filter_tools(_VALIDATION_TOOL_NAMES)


# ── Prompts ───────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """You are a software architect. Create a concrete implementation plan.

PROJECT STRUCTURE:
{tree}

USER REQUEST: {query}

Output ONLY a numbered list of steps. Rules:
- Maximum 10 steps, minimum 1
- Each step must be specific and name exact files/commands
- File creation steps: name the exact path (e.g. "Create src/api/routes.py with...")
- Install steps: name exact packages
- Steps in logical execution order
- No vague steps like "set up the backend" or "implement the feature"

Example format:
1. Create requirements.txt with: fastapi, uvicorn, httpx
2. Create backend/main.py with a FastAPI app and /health endpoint
3. Run: pip install -r requirements.txt"""


CODING_PROMPT = """You are a senior software engineer. Execute this coding task using your tools.

TASK: {next_step}

PLAN (for context):
{plan}

ALREADY DONE:
{completed}

PROJECT STRUCTURE:
{tree}

MANDATORY RULES — follow every one:
1. Call write_file for EVERY file you create or modify. Do NOT output code as text — write it to disk.
2. Write the COMPLETE file content in each write_file call. No "..." truncations. No "# TODO" placeholders. No "# add implementation here". Write the real, working code.
3. Call read_file before modifying any existing file to see its current content.
4. After each write_file call, verify by calling read_file on the same path.
5. If write_file returns a warning about empty content, call write_file again with the full content.
6. Every file must be immediately runnable: include all imports, type hints, and error handling.
7. Use create_directory before writing files in new subdirectories.

Execute the task now. Use tools."""


FILESYSTEM_PROMPT = """You are a filesystem operations agent. Execute this filesystem task.

TASK: {next_step}

WORKSPACE: {workspace}

MANDATORY RULES:
1. Use create_directory to create any new directories.
2. Use move_file(src, dst) to move or relocate files.
3. Use rename_file(path, new_name) to rename a file within its directory.
4. Use delete_file to delete individual files.
5. Use delete_directory to remove directories (recursive=true if not empty).
6. After every operation, call list_directory to verify it succeeded.

Execute now. Use tools."""


TERMINAL_PROMPT = """You are a terminal agent. Execute this shell task.

TASK: {next_step}

WORKSPACE: {workspace}

MANDATORY RULES:
1. Use execute_command for ALL shell operations.
2. The working directory is ALREADY set to the workspace root — NEVER use cd.
3. Use relative paths from the workspace root (e.g. "src/main.py", not "/full/path/src/main.py").
4. Compound commands work: you can use &&, |, ; and shell redirects (>, >>) freely.
5. Read the command output — if there are errors, fix them and retry.
6. After installing packages, verify with: pip show <pkg> or npm list <pkg>.
7. NEVER write file content using echo or cat heredocs — file writing is done by the coding agent.

Execute now. Use tools."""


VALIDATION_PROMPT = """You are a code validation agent. Verify that the following work was completed correctly.

TASK THAT SHOULD BE DONE: {next_step}

FULL PLAN:
{plan}

RULES:
1. Use read_file to check each file that should have been created or modified.
2. Verify the file exists and contains actual, non-empty code (not just comments or empty content).
3. Use list_directory to verify the directory structure is correct.
4. Use execute_command to run syntax checks where applicable (e.g. python -m py_compile file.py).
5. Report clearly: what was found, what's missing, any issues.
6. If everything looks correct, state "VALIDATION PASSED".
7. If issues exist, describe them specifically so they can be fixed.

Validate now. Use tools."""


# ── Step classifier ───────────────────────────────────────────────────────────

import re as _re

# File extensions that signal a coding step
_FILE_EXT_RE = _re.compile(
    r'\b\w[\w.\-]*/?\w*\.(py|js|ts|tsx|jsx|html|css|scss|json|yaml|yml|toml|rs|go|java|kt|swift|cpp|c|h|sh|rb|php|cs|vue|svelte|md)\b'
)

# Keywords that, when combined with a file extension, clearly mean "write code"
_CODING_VERBS = (
    "write ", "implement ", "create ", "add ", "update ", "modify ",
    "refactor ", "replace ", "rewrite ", "build the ", "define ",
)


def classify_step(step: str) -> str:
    """Classify a plan step into an agent type."""
    s = step.lower()
    # Strip leading step number so "1. run ..." works the same as "run ..."
    body = _re.sub(r"^\d+\.\s*", "", s).strip()

    # ── Coding priority ───────────────────────────────────────────────────────
    # If a step mentions a source file AND a coding verb, always go to coding.
    # This prevents "write Python ..." from hitting the terminal classifier.
    has_file = bool(_FILE_EXT_RE.search(s))
    if has_file and any(v in body for v in _CODING_VERBS):
        return "coding"

    # ── Terminal ──────────────────────────────────────────────────────────────
    # Match only when the step is clearly running a shell command.
    terminal_always = [
        "install ", "install:", "npm ", "pip ", "pytest",
        "docker", "git ", "make ", "bundle", "webpack",
    ]
    # Command verbs at the start of the body (after stripping step number)
    _terminal_start = _re.compile(
        r"^(run|execute|start|serve|launch|deploy|restart|compile|transpile)\b"
    )
    # Explicit CLI tool followed by a space (e.g. "python3 hello.py", "node index.js")
    _terminal_tool = _re.compile(
        r"^(python3?|node|npx|cargo|go run|java|mvn|gradle|php|ruby)\s"
    )
    # "run:" prefix anywhere (planner uses this convention)
    _run_prefix = _re.compile(r"\brun:\s")

    if (
        any(kw in s for kw in terminal_always)
        or _terminal_start.match(body)
        or _terminal_tool.match(body)
        or _run_prefix.search(s)
    ):
        return "terminal"

    # ── Filesystem ────────────────────────────────────────────────────────────
    filesystem_kw = [
        "create directory", "mkdir", "move file", "move the file",
        "rename file", "rename the file", "delete file", "delete the file",
        "delete old_", "remove file", "remove the file",
        "delete directory", "remove directory",
        "move backend/", "move frontend/", "move src/", "move app/",
    ]
    if (
        any(kw in s for kw in filesystem_kw)
        or _re.search(r"\bmove\b.+\bto\b.+[./]", s)
        or _re.search(r"\brename\b.+\bto\b", s)
        or (_re.search(r"\bdelete\b\s+(the\s+)?(\w[\w.\-/]*\.\w+)", s) and " from " not in s)
        or (_re.search(r"\bremove\b\s+(the\s+)?(\w[\w.\-/]*\.\w+)", s) and " from " not in s and " in " not in s)
    ):
        return "filesystem"

    # ── Validation ────────────────────────────────────────────────────────────
    validation_kw = [
        "verify", "validate", "check that", "confirm that", "ensure that",
        "test that", "assert ", "review ", "audit ",
    ]
    if any(kw in s for kw in validation_kw):
        return "validation"

    return "coding"


# ── Shared step execution helper ──────────────────────────────────────────────

async def _run_step(
    state: AgentState,
    user_prompt: str,
    tools: list[dict],
    agent_label: str,
) -> AgentState:
    """
    Core execution loop shared by all specialist nodes.
    Handles tool calls, empty-file detection, and SSE event emission.
    """
    queue = get_queue(state.session_id)
    step_idx = state.current_step
    step_desc = state.plan[step_idx]

    logger.info(
        "[%s] session=%s model=%s step=%d/%d: %r",
        agent_label, state.session_id[:8], state.model,
        step_idx + 1, len(state.plan), step_desc[:80],
    )

    if queue:
        await queue.put({
            "type": "step_start",
            "step": step_idx,
            "description": step_desc,
            "agent": agent_label,
        })

    messages = list(state.messages) + [{"role": "user", "content": user_prompt}]
    state.iteration_count += 1
    max_tool_rounds = 20

    for round_num in range(max_tool_rounds):
        got_tool_call = False
        round_content = ""

        try:
            async for chunk in chat_stream(state.model, messages, tools=tools):
                msg = chunk.get("message", {})

                if msg.get("tool_calls"):
                    got_tool_call = True
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        raw_args = fn.get("arguments", "{}")
                        tool_name = fn.get("name", "")

                        try:
                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except json.JSONDecodeError as e:
                            logger.error(
                                "[%s] JSON parse error tool=%r: %s | raw=%r",
                                agent_label, tool_name, e, raw_args[:300],
                            )
                            parsed_args = {}

                        logger.info(
                            "[%s] tool_call=%s args=%s",
                            agent_label, tool_name, list(parsed_args.keys()),
                        )

                        if queue:
                            await queue.put({
                                "type": "tool_call",
                                "name": tool_name,
                                "arguments": json.dumps(parsed_args),
                            })

                        result = await execute_tool(tool_name, parsed_args, state.workspace)
                        logger.info("[%s] tool_result=%s: %r", agent_label, tool_name, result[:150])

                        # Detect empty-file write and inject a correction prompt
                        tool_message = result
                        if tool_name == "write_file":
                            content_arg = parsed_args.get("content", "")
                            path_arg = parsed_args.get("path", "?")
                            if not content_arg:
                                tool_message = (
                                    f"{result}\n\n"
                                    f"CRITICAL ERROR: write_file was called with EMPTY content for '{path_arg}'. "
                                    f"The file was NOT written. You MUST call write_file again immediately "
                                    f"with the complete, real file content."
                                )
                                logger.error(
                                    "[%s] write_file called with EMPTY content for %s",
                                    agent_label, path_arg,
                                )
                            elif "Error" not in result:
                                if queue:
                                    await queue.put({
                                        "type": "file_written",
                                        "path": path_arg,
                                        "workspace": state.workspace,
                                    })

                        messages.append({"role": "tool", "content": tool_message})

                        if queue:
                            await queue.put({
                                "type": "tool_result",
                                "name": tool_name,
                                "result": result,
                            })

                    break  # restart loop with tool results appended

                elif msg.get("content"):
                    round_content += msg["content"]
                    if queue and msg["content"]:
                        await queue.put({"type": "chunk", "content": msg["content"]})

                if chunk.get("done"):
                    break

        except Exception as e:
            logger.error("[%s] chat_stream error round=%d: %s", agent_label, round_num, e, exc_info=True)
            if queue:
                await queue.put({"type": "warning", "message": f"{agent_label} error: {e}"})
            break

        if round_content:
            messages.append({"role": "assistant", "content": round_content})

        if not got_tool_call:
            break  # model finished — no more tool calls

    state.messages = messages
    state.done[state.current_step] = True
    state.current_step += 1

    logger.info(
        "[%s] step done → %d/%d",
        agent_label, state.current_step, len(state.plan),
    )

    if queue:
        await queue.put({
            "type": "step_done",
            "step": step_idx,
            "description": step_desc,
        })

    if state.current_step >= len(state.plan):
        state.finish_reason = "all_steps_completed"

    return state


# ── Planner node ──────────────────────────────────────────────────────────────

async def planner_node(state: AgentState) -> AgentState:
    tree = _get_tree(state.workspace)
    query = state.messages[-1]["content"] if state.messages else ""

    queue = get_queue(state.session_id)

    logger.info(
        "[planner] session=%s model=%s query=%r",
        state.session_id[:8], state.model, query[:80],
    )

    if queue:
        await queue.put({"type": "status", "message": f"Planning with {state.model}…"})

    prompt = PLANNER_PROMPT.format(tree=tree, query=query)

    full_response = ""
    try:
        async for chunk in chat_stream(state.model, [{"role": "user", "content": prompt}], tools=None):
            if "message" in chunk and "content" in chunk["message"]:
                content = chunk["message"]["content"]
                if content:
                    full_response += content
    except Exception as e:
        logger.error("[planner] chat_stream error: %s", e)
        state.error = f"Planner failed: {e}"
        return state

    lines = [line.strip() for line in full_response.strip().split("\n") if line.strip()]
    plan_steps = [
        line for line in lines
        if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*"))
    ]
    if not plan_steps:
        plan_steps = lines if lines else ["Complete the user request directly"]

    # Classify each step into an agent type
    step_types = [classify_step(step) for step in plan_steps]

    state.plan = plan_steps
    state.step_types = step_types
    state.done = [False] * len(plan_steps)
    state.current_step = 0

    logger.info(
        "[planner] %d steps: %s",
        len(plan_steps),
        [(i + 1, t) for i, t in enumerate(step_types)],
    )

    if queue:
        await queue.put({
            "type": "plan",
            "steps": plan_steps,
            "step_types": step_types,
        })

    return state


# ── Specialist nodes ──────────────────────────────────────────────────────────

async def coding_node(state: AgentState) -> AgentState:
    if state.current_step >= len(state.plan):
        state.finish_reason = "all_steps_completed"
        return state
    if state.iteration_count >= state.max_iterations:
        state.finish_reason = "max_iterations_reached"
        return state

    step = state.plan[state.current_step]
    tree = _get_tree(state.workspace)
    completed = [s for i, s in enumerate(state.plan) if state.done[i]]

    prompt = CODING_PROMPT.format(
        next_step=step,
        plan="\n".join(f"{i+1}. {s}" for i, s in enumerate(state.plan)),
        completed="\n".join(f"✓ {s}" for s in completed) if completed else "None yet",
        tree=tree,
    )
    return await _run_step(state, prompt, CODING_TOOLS, "coding")


async def filesystem_node(state: AgentState) -> AgentState:
    if state.current_step >= len(state.plan):
        state.finish_reason = "all_steps_completed"
        return state
    if state.iteration_count >= state.max_iterations:
        state.finish_reason = "max_iterations_reached"
        return state

    step = state.plan[state.current_step]
    prompt = FILESYSTEM_PROMPT.format(
        next_step=step,
        workspace=state.workspace,
    )
    return await _run_step(state, prompt, FILESYSTEM_TOOLS, "filesystem")


async def terminal_node(state: AgentState) -> AgentState:
    if state.current_step >= len(state.plan):
        state.finish_reason = "all_steps_completed"
        return state
    if state.iteration_count >= state.max_iterations:
        state.finish_reason = "max_iterations_reached"
        return state

    step = state.plan[state.current_step]
    prompt = TERMINAL_PROMPT.format(
        next_step=step,
        workspace=state.workspace,
    )
    return await _run_step(state, prompt, TERMINAL_TOOLS, "terminal")


async def validation_node(state: AgentState) -> AgentState:
    if state.current_step >= len(state.plan):
        state.finish_reason = "all_steps_completed"
        return state
    if state.iteration_count >= state.max_iterations:
        state.finish_reason = "max_iterations_reached"
        return state

    step = state.plan[state.current_step]
    prompt = VALIDATION_PROMPT.format(
        next_step=step,
        plan="\n".join(f"{i+1}. {s}" for i, s in enumerate(state.plan)),
    )
    return await _run_step(state, prompt, VALIDATION_TOOLS, "validation")


async def review_node(state: AgentState) -> AgentState:
    """Final node: summarize what was done without an extra LLM call."""
    queue = get_queue(state.session_id)

    completed = [s for i, s in enumerate(state.plan) if i < len(state.done) and state.done[i]]
    skipped = [s for i, s in enumerate(state.plan) if i >= len(state.done) or not state.done[i]]

    logger.info(
        "[review] session=%s completed=%d/%d finish_reason=%s",
        state.session_id[:8], len(completed), len(state.plan), state.finish_reason,
    )

    summary_lines = [f"Completed {len(completed)}/{len(state.plan)} steps."]
    if completed:
        summary_lines.append("Done: " + "; ".join(s.replace("\n", " ")[:60] for s in completed))
    if skipped:
        summary_lines.append("Skipped: " + "; ".join(s.replace("\n", " ")[:60] for s in skipped))
    if state.finish_reason == "max_iterations_reached":
        summary_lines.append("Note: hit max iterations limit.")

    summary = " ".join(summary_lines)

    if queue:
        await queue.put({"type": "chunk", "content": f"\n\n{summary}"})

    return state


# ── Router ────────────────────────────────────────────────────────────────────

def step_router(state: AgentState) -> str:
    """
    Route to the appropriate specialist node based on the current step type,
    or to 'review' when all steps are done.
    """
    if state.error or state.finish_reason:
        return "review"
    if state.current_step >= len(state.plan):
        return "review"
    if state.iteration_count >= state.max_iterations:
        return "review"

    step_type = (
        state.step_types[state.current_step]
        if state.step_types and state.current_step < len(state.step_types)
        else "coding"
    )
    return step_type


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tree(workspace: str) -> str:
    from tools.file_ops import get_directory_tree
    try:
        return get_directory_tree(workspace)
    except Exception as e:
        logger.warning("[nodes] could not read directory tree: %s", e)
        return "(unable to read directory tree)"
