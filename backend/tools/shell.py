import subprocess
import shlex
import os
from typing import Optional

ALLOWED_COMMANDS: list[str] = []


def set_allowed_commands(commands: list[str]) -> None:
    global ALLOWED_COMMANDS
    ALLOWED_COMMANDS = commands


def execute_command(command: str, workdir: Optional[str] = None) -> str:
    parts = shlex.split(command)
    if not parts:
        return "Error: empty command"

    cmd_name = parts[0]
    if ALLOWED_COMMANDS and cmd_name not in ALLOWED_COMMANDS:
        return f"Error: command '{cmd_name}' is not allowed. Allowed: {', '.join(ALLOWED_COMMANDS)}"

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=workdir or os.getcwd(),
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
        return "Error: command timed out (60s)"
    except FileNotFoundError:
        return f"Error: command not found — {cmd_name}"
    except Exception as e:
        return f"Error: {e}"
