#!/usr/bin/env python3
"""Detect hardcoded local paths that should come from environment variables.

Usage:
    python3 check-hardcoded-paths.py
    python3 check-hardcoded-paths.py --fix

Exit codes:
    0 = no violations
    1 = violations found
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INCLUDE_DIRS = (
    Path("scripts"),
    Path("plugins"),
    Path("workspace_store"),
    Path(".laia-arch/workspace-ui/backend"),
)
EXCLUDE_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
EXCLUDE_FILES = {Path("scripts/check-hardcoded-paths.py")}

CORRECT_HERMES_HOME = 'Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))'

PATH_HOME_HERMES_RE = re.compile(r"(?:pathlib\.)?Path\.home\(\)\s*/\s*['\"]\.hermes['\"]")
TILDE_HERMES_STRING_RE = re.compile(r"['\"][^'\"]*~/\.hermes[^'\"]*['\"]")
EXPANDUSER_HERMES_RE = re.compile(r"os\.path\.expanduser\(\s*['\"]~/\.hermes(?:/[^'\"]*)?['\"]\s*\)")
ABS_LAIA_HOME_STRING_RE = re.compile(r"['\"][^'\"]*/home/laia-arch(?:/[^'\"]*)?['\"]")
DEFAULT_WORKSPACE_NAMES = ("arete", "doyouwin", "pixelcore", "laia_arch", "servidor_jmp", "demo-completo")
WORKSPACE_NAME_RE = re.compile(
    r"['\"](" + "|".join(re.escape(name) for name in DEFAULT_WORKSPACE_NAMES) + r")['\"]"
)
WORKSPACE_NAME_ALLOWED_FILES = {
    Path("plugins/workspace-context/__init__.py"),
    Path("plugins/doyouwin/__init__.py"),
    Path("scripts/workspace-daily-diagnostic.py"),
    Path("scripts/_doc_context_engine.py"),
    Path("scripts/git-manager.py"),
}

# Pattern 4: workspace assigned directly from a string literal (e.g. workspace = "arete")
HARDCODED_WORKSPACE_ASSIGN_RE = re.compile(
    r"""workspace\s*=\s*["'](arete|doyouwin|pixelcore|laia_arch|servidor_jmp)["']"""
)
HARDCODED_WORKSPACE_ASSIGN_EXCLUDE_DIRS = {"workspace_store", "workspaces"}
HARDCODED_WORKSPACE_ASSIGN_EXCLUDE_SUFFIXES = {"workspace.db", "config.yaml", "config.yml"}

SAFE_HERMES_HOME_ASSIGN_RE = re.compile(
    r"^(\s*)HERMES_HOME\s*=\s*Path\.home\(\)\s*/\s*['\"]\.hermes['\"]\s*$",
    re.MULTILINE,
)
SAFE_EXPANDUSER_ASSIGN_RE = re.compile(
    r"^(\s*)HERMES_HOME\s*=\s*Path\(os\.path\.expanduser\(\s*['\"]~/\.hermes['\"]\s*\)\)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line_no: int
    description: str
    fragment: str


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def _is_excluded(path: Path, root: Path) -> bool:
    rel = _relative(path, root)
    if rel in EXCLUDE_FILES:
        return True
    return any(part in EXCLUDE_DIR_NAMES for part in rel.parts)


def collect_files(root: Path, include_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for include in include_dirs:
        base = root / include
        if not base.exists():
            continue
        candidates = [base] if base.is_file() else base.rglob("*.py")
        for path in candidates:
            if not path.is_file() or _is_excluded(path, root):
                continue
            files.append(path)
    return sorted(set(files))


def _safe_hermes_env_fallback(line: str) -> bool:
    return "HERMES_HOME" in line and ("os.environ" in line or "os.getenv" in line)


def _hardcoded_workspace_assign_excluded(path: Path, root: Path) -> bool:
    """Return True if *path* should be skipped for Pattern 4 (workspace= assignment)."""
    rel = _relative(path, root)
    parts = set(rel.parts)
    if parts & HARDCODED_WORKSPACE_ASSIGN_EXCLUDE_DIRS:
        return True
    if path.name in HARDCODED_WORKSPACE_ASSIGN_EXCLUDE_SUFFIXES:
        return True
    return False


def _workspace_name_allowed(path: Path, line: str) -> bool:
    rel = _relative(path, PROJECT_ROOT)
    if rel in WORKSPACE_NAME_ALLOWED_FILES:
        return True
    return rel == Path(".laia-arch/workspace-ui/backend/main.py") and 'plugin.get("workspace"' in line


def scan_file(path: Path) -> list[Violation]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    violations: list[Violation] = []
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "no-hardcoded-path" in line:
            continue

        if PATH_HOME_HERMES_RE.search(line) and not _safe_hermes_env_fallback(line):
            violations.append(
                Violation(path, line_no, 'Path.home() / ".hermes" sin HERMES_HOME', stripped)
            )
            continue
        if EXPANDUSER_HERMES_RE.search(line):
            violations.append(
                Violation(path, line_no, 'os.path.expanduser("~/.hermes") hardcodeado', stripped)
            )
            continue
        if TILDE_HERMES_STRING_RE.search(line):
            violations.append(
                Violation(path, line_no, '"~/.hermes" hardcodeado en string', stripped)
            )
            continue
        if ABS_LAIA_HOME_STRING_RE.search(line):
            violations.append(
                Violation(path, line_no, '"/home/laia-arch" hardcodeado en string', stripped)
            )
            continue
        if WORKSPACE_NAME_RE.search(line) and not _workspace_name_allowed(path, line):
            violations.append(
                Violation(path, line_no, "nombre de workspace hardcodeado en string", stripped)
            )
            continue
        # Pattern 4: workspace variable assigned directly from a known workspace name literal.
        m4 = HARDCODED_WORKSPACE_ASSIGN_RE.search(line)
        if m4 and not _hardcoded_workspace_assign_excluded(path, PROJECT_ROOT):
            violations.append(
                Violation(
                    path,
                    line_no,
                    "workspace= asignado con nombre de workspace hardcodeado (usa config)",
                    m4.group(0),
                )
            )

    return violations


def scan(files: list[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in files:
        violations.extend(scan_file(path))
    return violations


def _ensure_import_os(source: str) -> str:
    if re.search(r"^import os\b", source, re.MULTILINE):
        return source

    lines = source.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if line.startswith("from pathlib import Path"):
            lines.insert(idx, "import os\n")
            return "".join(lines)

    insert_at = 0
    for idx, line in enumerate(lines):
        if line.startswith("from __future__ import "):
            insert_at = idx + 1
    lines.insert(insert_at, "import os\n")
    return "".join(lines)


def apply_fix(files: list[Path]) -> int:
    fixed = 0
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue

        replacement = rf"\1HERMES_HOME = {CORRECT_HERMES_HOME}"
        new_source = SAFE_HERMES_HOME_ASSIGN_RE.sub(replacement, source)
        new_source = SAFE_EXPANDUSER_ASSIGN_RE.sub(replacement, new_source)

        if new_source == source:
            continue

        new_source = _ensure_import_os(new_source)
        path.write_text(new_source, encoding="utf-8")
        fixed += 1
        print(f"FIXED {_relative(path, PROJECT_ROOT)}")

    return fixed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Apply safe automatic replacements")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATH",
        help="Relative file or directory to scan. Defaults to scripts, plugins, workspace_store and Web UI backend.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_dirs = [Path(item) for item in args.include] if args.include else list(DEFAULT_INCLUDE_DIRS)
    files = collect_files(PROJECT_ROOT, include_dirs)

    if args.fix:
        fixed = apply_fix(files)
        print(f"{fixed} file(s) modified.")
        files = collect_files(PROJECT_ROOT, include_dirs)

    violations = scan(files)
    if not violations:
        print("OK: no hardcoded path violations found.")
        return 0

    print(f"{len(violations)} hardcoded path violation(s) found:\n")
    for violation in violations:
        rel = _relative(violation.path, PROJECT_ROOT)
        print(f"{rel}:{violation.line_no}: {violation.description}")
        print(f"  {violation.fragment}")
        if "workspace" in violation.description:
            print("  Suggestion: lee los workspaces desde config.yaml o list_workspaces(HERMES_HOME).\n")
        else:
            print(f"  Suggestion: {CORRECT_HERMES_HOME}\n")

    return 1


if __name__ == "__main__":
    sys.exit(main())
