"""Native filesystem tool handlers.

Simple, root-friendly, no sandbox. Designed for use inside per-user LXD
containers where the user owns everything under /home/user.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from pathlib import Path


MAX_READ_CHARS = 1_000_000
MAX_GREP_RESULTS = 500


def _safe_path(path: str) -> Path:
    p = Path(os.path.expanduser(path))
    return p


def read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    """Read a text file. `offset` is 1-indexed line number; `limit` is line count."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    if not p.is_file():
        return f"ERROR: not a regular file: {path}"
    try:
        size = p.stat().st_size
        if size > MAX_READ_CHARS * 4:  # rough byte ceiling
            return f"ERROR: file too large ({size} bytes); refusing to read"
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"ERROR: read failed: {exc}"
    lines = text.splitlines()
    start = max(0, offset - 1)
    end = min(len(lines), start + limit)
    selected = lines[start:end]
    numbered = [f"{i + start + 1}\t{line}" for i, line in enumerate(selected)]
    header = f"# {path} (lines {start + 1}-{end} of {len(lines)})\n"
    return header + "\n".join(numbered)


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with `content`. Parents are created."""
    p = _safe_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"ERROR: write failed: {exc}"
    return f"OK: wrote {len(content)} chars to {path}"


def apply_patch(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace `old_string` with `new_string` in the file. If replace_all is False,
    `old_string` must be unique in the file (we error otherwise)."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    try:
        original = p.read_text(encoding="utf-8")
    except Exception as exc:
        return f"ERROR: read failed: {exc}"
    if old_string not in original:
        return f"ERROR: old_string not found in {path}"
    if not replace_all and original.count(old_string) > 1:
        return f"ERROR: old_string occurs {original.count(old_string)} times; use replace_all=true or add context"
    if replace_all:
        new_content = original.replace(old_string, new_string)
        n = original.count(old_string)
    else:
        new_content = original.replace(old_string, new_string, 1)
        n = 1
    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as exc:
        return f"ERROR: write failed: {exc}"
    return f"OK: replaced {n} occurrence(s) in {path}"


def list_dir(path: str) -> str:
    """List directory contents (one per line, dirs marked with trailing /)."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: path not found: {path}"
    if not p.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = []
    try:
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            name = entry.name + "/" if entry.is_dir() else entry.name
            entries.append(name)
    except Exception as exc:
        return f"ERROR: list failed: {exc}"
    return "\n".join(entries) if entries else "(empty)"


def _truncated_marker(kind: str) -> str:
    """Standardised tail appended when output hits MAX_GREP_RESULTS so the
    LLM knows it has not seen every match and refines its query."""
    return f"... (truncated at {MAX_GREP_RESULTS} {kind} — refine the pattern/path)"


def glob_tool(pattern: str, path: str = ".") -> str:
    """Find files matching `pattern` under `path` (recursive)."""
    root = _safe_path(path)
    if not root.exists():
        return f"ERROR: path not found: {path}"
    matches: list[str] = []
    truncated = False
    try:
        for p in root.rglob("*"):
            if p.is_file() and fnmatch.fnmatch(p.name, pattern):
                matches.append(str(p))
                if len(matches) >= MAX_GREP_RESULTS:
                    truncated = True
                    break
    except Exception as exc:
        return f"ERROR: glob failed: {exc}"
    if not matches:
        return "(no matches)"
    if truncated:
        matches.append(_truncated_marker("matches"))
    return "\n".join(matches)


def grep_tool(pattern: str, path: str = ".", include: str | None = None) -> str:
    """Search file contents for `pattern` (regex). Uses ripgrep if available, falls back to Python."""
    root = _safe_path(path)
    if not root.exists():
        return f"ERROR: path not found: {path}"
    # Try ripgrep first
    rg = shutil.which("rg")
    if rg:
        import subprocess
        cmd = [
            rg, "--no-heading", "--with-filename", "--line-number",
            "--max-count", str(MAX_GREP_RESULTS), "-e", pattern,
        ]
        if include:
            cmd.extend(["--glob", include])
        cmd.append(str(root))
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = res.stdout.strip()
            if not output:
                return "(no matches)"
            lines = output.splitlines()
            if len(lines) >= MAX_GREP_RESULTS:
                lines = lines[:MAX_GREP_RESULTS] + [_truncated_marker("lines")]
            return "\n".join(lines)
        except Exception as exc:
            return f"ERROR: ripgrep failed: {exc}"
    # Python fallback
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"ERROR: invalid regex: {exc}"
    matches: list[str] = []
    inc_glob = include or "*"
    truncated = False
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if not fnmatch.fnmatch(p.name, inc_glob):
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{p}:{i}:{line}")
                    if len(matches) >= MAX_GREP_RESULTS:
                        truncated = True
                        break
        except Exception:
            continue
        if len(matches) >= MAX_GREP_RESULTS:
            truncated = True
            break
    if not matches:
        return "(no matches)"
    if truncated:
        matches.append(_truncated_marker("lines"))
    return "\n".join(matches)


def delete_file(path: str) -> str:
    """Delete a file or empty directory."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: path not found: {path}"
    try:
        if p.is_dir():
            p.rmdir()
        else:
            p.unlink()
    except Exception as exc:
        return f"ERROR: delete failed: {exc}"
    return f"OK: deleted {path}"


def move_file(src: str, dst: str) -> str:
    """Move/rename a file or directory."""
    sp = _safe_path(src)
    dp = _safe_path(dst)
    if not sp.exists():
        return f"ERROR: source not found: {src}"
    try:
        dp.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sp), str(dp))
    except Exception as exc:
        return f"ERROR: move failed: {exc}"
    return f"OK: moved {src} → {dst}"


def make_dir(path: str, parents: bool = True) -> str:
    """Create a directory."""
    p = _safe_path(path)
    try:
        p.mkdir(parents=parents, exist_ok=True)
    except Exception as exc:
        return f"ERROR: mkdir failed: {exc}"
    return f"OK: created {path}"
