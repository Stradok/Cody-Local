import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


ALLOWED_BASE: Optional[str] = None


def set_allowed_base(path: str) -> None:
    global ALLOWED_BASE
    # Use realpath to resolve symlinks — critical for mounted drives
    ALLOWED_BASE = os.path.realpath(path)


def _resolve_path(path: str) -> Path:
    if ALLOWED_BASE:
        candidate = os.path.realpath(os.path.join(ALLOWED_BASE, path))
        # Also resolve the base for comparison
        base_resolved = os.path.realpath(ALLOWED_BASE)
        if not candidate.startswith(base_resolved + os.sep) and candidate != base_resolved:
            raise PermissionError(f"Access denied: {path} is outside the workspace")
        return Path(candidate)
    else:
        abs_path = os.path.realpath(path)
        return Path(abs_path)


def list_directory(path: str = ".") -> str:
    target = _resolve_path(path)
    if not target.is_dir():
        return f"Error: {path} is not a directory"
    entries = []
    for entry in sorted(target.iterdir()):
        suffix = "/" if entry.is_dir() else ""
        entries.append(f"{entry.name}{suffix}")
    return "\n".join(entries)


def get_directory_tree(path: str = ".", max_depth: int = 4) -> str:
    target = _resolve_path(path)
    if not target.is_dir():
        return f"Error: {path} is not a directory"

    lines = []

    def walk(dir_path: Path, depth: int):
        if depth > max_depth:
            return
        indent = "  " * depth
        for entry in sorted(dir_path.iterdir()):
            if entry.name.startswith(".") and entry.is_dir():
                continue
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                walk(entry, depth + 1)
            else:
                lines.append(f"{indent}{entry.name}")

    lines.append(f"{target.name}/")
    walk(target, 1)
    return "\n".join(lines)


def read_file(path: str) -> str:
    target = _resolve_path(path)
    if not target.is_file():
        return f"Error: file not found — {path}"
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def create_directory(path: str) -> str:
    target = _resolve_path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
        logger.info("create_directory: %s", path)
        return f"Created directory: {path}"
    except PermissionError as e:
        return f"Error creating directory {path}: permission denied — {e}"
    except Exception as e:
        return f"Error creating directory {path}: {e}"


def move_file(src: str, dst: str) -> str:
    src_path = _resolve_path(src)
    dst_path = _resolve_path(dst)
    if not src_path.exists():
        return f"Error: source does not exist — {src}"
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        logger.info("move_file: %s → %s", src, dst)
        return f"Moved {src} → {dst}"
    except Exception as e:
        return f"Error moving {src} → {dst}: {e}"


def rename_file(path: str, new_name: str) -> str:
    src_path = _resolve_path(path)
    if not src_path.exists():
        return f"Error: file does not exist — {path}"
    dst_path = src_path.parent / new_name
    if ALLOWED_BASE:
        base_resolved = os.path.realpath(ALLOWED_BASE)
        if not str(os.path.realpath(dst_path)).startswith(base_resolved):
            return "Error: rename target is outside the workspace"
    try:
        src_path.rename(dst_path)
        logger.info("rename_file: %s → %s", path, new_name)
        return f"Renamed {path} → {new_name}"
    except Exception as e:
        return f"Error renaming {path}: {e}"


def delete_file(path: str) -> str:
    target = _resolve_path(path)
    if not target.exists():
        return f"Error: file does not exist — {path}"
    if target.is_dir():
        return f"Error: {path} is a directory — use delete_directory instead"
    try:
        target.unlink()
        logger.info("delete_file: %s", path)
        return f"Deleted: {path}"
    except Exception as e:
        return f"Error deleting {path}: {e}"


def delete_directory(path: str, recursive: bool = False) -> str:
    target = _resolve_path(path)
    if not target.exists():
        return f"Error: directory does not exist — {path}"
    if not target.is_dir():
        return f"Error: {path} is not a directory"
    try:
        if recursive:
            import shutil
            shutil.rmtree(target)
            logger.info("delete_directory (recursive): %s", path)
            return f"Deleted directory (recursive): {path}"
        else:
            target.rmdir()
            logger.info("delete_directory: %s", path)
            return f"Deleted directory: {path}"
    except OSError as e:
        if "not empty" in str(e).lower():
            return f"Error: directory not empty — use recursive=true to force delete: {path}"
        return f"Error deleting directory {path}: {e}"
    except Exception as e:
        return f"Error deleting directory {path}: {e}"


def write_file(path: str, content: str) -> str:
    if content is None:
        logger.warning("write_file called with None content for %s", path)
        content = ""

    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not content:
        logger.warning("write_file called with empty content for %s — writing empty file", path)

    # Atomic write: write to temp file in same directory, then rename.
    # Same-filesystem rename is atomic on Linux/macOS.
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=".cody_tmp_",
            suffix=target.suffix or ".tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp_path).replace(target)
        tmp_path = None  # successfully renamed — don't delete

        actual_bytes = target.stat().st_size
        logger.info("write_file: %s — %d bytes", path, actual_bytes)

        if actual_bytes == 0 and content:
            return (
                f"Written to {path} but file reports 0 bytes on disk — "
                "possible filesystem issue. Please retry."
            )
        return f"Written {actual_bytes} bytes to {path}"

    except PermissionError as e:
        logger.error("write_file permission error for %s: %s", path, e)
        return f"Error writing {path}: permission denied — {e}"
    except Exception as e:
        logger.error("write_file failed for %s: %s", path, e)
        return f"Error writing {path}: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
