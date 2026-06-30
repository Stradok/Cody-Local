import subprocess
import shlex
import os
import re
from typing import Optional

ALLOWED_COMMANDS: list[str] = []

# Shell metacharacters that require running through bash
_SHELL_META = re.compile(r"[&|;<>$`]|\bcd\b")


def set_allowed_commands(commands: list[str]) -> None:
    global ALLOWED_COMMANDS
    ALLOWED_COMMANDS = commands


def execute_command(command: str, workdir: Optional[str] = None) -> str:
    command = command.strip()
    if not command:
        return "Error: empty command"

    cwd = workdir or os.getcwd()
    is_compound = bool(_SHELL_META.search(command))

    try:
        if is_compound:
            # Compound commands (&&, |, ;, redirects, cd) need a real shell.
            # The workspace is already the cwd so strip any leading "cd <dir> &&".
            cleaned = re.sub(r"^\s*cd\s+\S+\s*&&\s*", "", command).strip()
            result = subprocess.run(
                ["bash", "-c", cleaned],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
            )
        else:
            parts = shlex.split(command)
            if not parts:
                return "Error: empty command"
            cmd_name = parts[0]
            if ALLOWED_COMMANDS and cmd_name not in ALLOWED_COMMANDS:
                return (
                    f"Error: command '{cmd_name}' is not allowed.\n"
                    f"Allowed: {', '.join(ALLOWED_COMMANDS)}\n"
                    f"Tip: the workspace is already your working directory — no need to cd."
                )
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
            )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output = f"Exit code {result.returncode}\n{output}"
        return output.strip() or "(no output)"

    except subprocess.TimeoutExpired:
        return "Error: command timed out (120s)"
    except FileNotFoundError as e:
        return f"Error: command not found — {e}"
    except Exception as e:
        return f"Error: {e}"
