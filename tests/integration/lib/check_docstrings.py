#!/usr/bin/env python3
"""English-docstring gate for LAIA production code (Track T · T-DOC).

This linter enforces the documentation policy decided on 2026-06-01: every
*public* module, function, class and method in the production code must carry
an English docstring. It is deliberately dependency-free (standard-library
``ast`` only) so it runs in CI without installing ruff/pydocstyle.

Two failure modes are reported per symbol:

* ``missing``     -- a public symbol has no docstring at all.
* ``non-english`` -- a docstring exists but looks Spanish (heuristic).

The gate is *incremental*: a baseline file records the violations that already
exist, and the gate only fails on violations that are **not** in the baseline.
Run with ``--write-baseline`` once to capture the current debt, then shrink the
baseline over time. This is the standard ratchet pattern -- it lets the gate go
green immediately while preventing new undocumented public APIs from landing.

Exit codes:

* ``0`` -- no new violations (clean, or every violation is in the baseline).
* ``1`` -- at least one violation is not covered by the baseline.
* ``2`` -- usage/configuration error.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# Production source roots covered by the gate. Kept intentionally narrow: the
# agent engine (.laia-core, gitignored), archived snapshots, tests and bundled
# product skills are out of scope. Paths are relative to the repository root.
DEFAULT_ROOTS = (
    "services/agora-backend/app",
    "services/laia-executor",
    "infra/orchestrator",
    "infra/pathd",
)

# Spanish-only characters. Their presence in a docstring is a strong signal the
# text is not English.
SPANISH_CHARS = set("áéíóúñ¿¡ Á É Í Ó Ú Ñ".replace(" ", ""))

# Common Spanish function words. We only flag a docstring as non-English when a
# few of these appear as whole words, to avoid false positives on English text
# that happens to contain, e.g., "a" or "no".
SPANISH_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "que",
    "con", "para", "por", "como", "pero", "porque", "cuando", "donde", "esto",
    "esta", "este", "estos", "estas", "usuario", "contenedor", "fichero",
    "archivo", "ruta", "secreto", "secretos", "datos", "cada", "sobre", "según",
    "también", "sólo", "solo", "más", "está", "están", "ser", "hace", "hacer",
    "devuelve", "retorna", "función", "módulo", "cadena", "número",
}


@dataclass(frozen=True)
class Violation:
    """A single documentation gap discovered by the gate."""

    path: str
    line: int
    kind: str  # module | function | class | method
    qualname: str
    reason: str  # missing | non-english

    def key(self) -> str:
        """Return a line-independent identity used for baseline matching.

        Line numbers are excluded on purpose so that unrelated edits above a
        symbol do not invalidate its baseline entry.
        """
        return f"{self.path}::{self.kind}::{self.qualname}::{self.reason}"


def looks_non_english(text: str) -> bool:
    """Heuristically decide whether a docstring is written in Spanish.

    Returns ``True`` when the text contains Spanish-only characters, or when at
    least two distinct Spanish function words appear. The check is conservative:
    it favours false negatives (letting a borderline docstring pass) over false
    positives (flagging legitimate English).
    """
    if any(ch in SPANISH_CHARS for ch in text):
        return True
    words = {w.strip(".,;:()[]\"'`").lower() for w in text.split()}
    hits = words & SPANISH_WORDS
    return len(hits) >= 2


def _is_public(name: str) -> bool:
    """Return ``True`` for names that are part of a module's public surface."""
    return not name.startswith("_")


def _docstring_problem(node: ast.AST, kind: str, qualname: str, path: str) -> Violation | None:
    """Return a :class:`Violation` if ``node`` lacks a valid English docstring."""
    doc = ast.get_docstring(node, clean=True)
    line = getattr(node, "lineno", 1)
    if doc is None or not doc.strip():
        return Violation(path, line, kind, qualname, "missing")
    if looks_non_english(doc):
        return Violation(path, line, kind, qualname, "non-english")
    return None


def _module_has_public_surface(tree: ast.Module) -> bool:
    """Return ``True`` if the module defines any public function or class.

    A pure ``__main__`` shim or a module of only private helpers does not need
    a module docstring, so we skip the module-level check for those.
    """
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if _is_public(node.name):
                return True
    return False


def check_file(path: Path, repo_root: Path) -> list[Violation]:
    """Scan a single Python file and return its documentation violations."""
    rel = str(path.relative_to(repo_root))
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        return [Violation(rel, 1, "module", rel, f"unreadable:{exc.__class__.__name__}")]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        # Syntax is the linters' job, not ours; do not double-report.
        return []

    violations: list[Violation] = []

    if _module_has_public_surface(tree):
        problem = _docstring_problem(tree, "module", rel, rel)
        if problem:
            violations.append(problem)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_public(node.name):
                problem = _docstring_problem(node, "function", node.name, rel)
                if problem:
                    violations.append(problem)
        elif isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            problem = _docstring_problem(node, "class", node.name, rel)
            if problem:
                violations.append(problem)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(sub.name):
                    qual = f"{node.name}.{sub.name}"
                    problem = _docstring_problem(sub, "method", qual, rel)
                    if problem:
                        violations.append(problem)

    return violations


def _is_excluded(path: Path) -> bool:
    """Return ``True`` for files outside the public production surface.

    Caches and test code are skipped: the policy targets the public API of
    production modules, and test helpers are not part of that surface.
    """
    if "__pycache__" in path.parts:
        return True
    if "tests" in path.parts or "test" in path.parts:
        return True
    if path.name.startswith("test_") or path.name == "conftest.py":
        return True
    return False


def iter_python_files(roots: Iterable[Path]) -> list[Path]:
    """Yield every public ``*.py`` file under ``roots`` (caches/tests excluded)."""
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if _is_excluded(path):
                continue
            files.append(path)
    return files


def load_baseline(path: Path | None) -> set[str]:
    """Read a baseline file into a set of violation keys (empty if absent)."""
    if path is None or not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.add(line)
    return keys


def collect(roots: list[Path], repo_root: Path) -> list[Violation]:
    """Collect all violations under ``roots`` sorted for stable output."""
    violations: list[Violation] = []
    for path in iter_python_files(roots):
        violations.extend(check_file(path, repo_root))
    return sorted(violations, key=lambda v: (v.path, v.line, v.qualname, v.reason))


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    parser = argparse.ArgumentParser(description="English-docstring gate for LAIA production code")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="source root to scan (repeatable); defaults to the production roots",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="repository root used to resolve relative paths",
    )
    parser.add_argument("--baseline", help="baseline file of accepted (pre-existing) violations")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="rewrite the baseline file with the current violations and exit 0",
    )
    parser.add_argument("--json", help="write a JSON report to this path, or '-' for stdout")
    return parser


def main(argv: list[str]) -> int:
    """Entry point: scan, compare against the baseline and report."""
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    root_names = args.root or list(DEFAULT_ROOTS)
    roots = [(repo_root / r).resolve() for r in root_names]

    violations = collect(roots, repo_root)
    baseline_path = Path(args.baseline).resolve() if args.baseline else None

    if args.write_baseline:
        if baseline_path is None:
            print("--write-baseline requires --baseline", file=sys.stderr)
            return 2
        header = (
            "# T-DOC baseline -- accepted pre-existing docstring gaps.\n"
            "# Regenerate with: check_docstrings.py --baseline <this> --write-baseline\n"
            "# Shrink over time; never add new entries by hand.\n"
        )
        body = "\n".join(v.key() for v in violations)
        baseline_path.write_text(header + body + ("\n" if body else ""), encoding="utf-8")
        print(f"wrote {len(violations)} baseline entries to {baseline_path}", file=sys.stderr)
        return 0

    baseline = load_baseline(baseline_path)
    new_violations = [v for v in violations if v.key() not in baseline]
    stale = sorted(baseline - {v.key() for v in violations})

    if args.json:
        report = {
            "roots": root_names,
            "total_violations": len(violations),
            "baseline_size": len(baseline),
            "new_violations": [v.__dict__ for v in new_violations],
            "stale_baseline_entries": stale,
        }
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.json == "-":
            print(text)
        else:
            Path(args.json).write_text(text + "\n", encoding="utf-8")

    if new_violations:
        print(
            f"T-DOC: {len(new_violations)} new docstring violation(s) "
            f"(baseline covers {len(baseline)}):",
            file=sys.stderr,
        )
        for v in new_violations:
            print(f"  {v.reason:11} {v.path}:{v.line} {v.kind} {v.qualname}", file=sys.stderr)
        print(
            "\nAdd an English docstring, or (only for legacy debt) regenerate the "
            "baseline with --write-baseline.",
            file=sys.stderr,
        )
        return 1

    if stale:
        # Stale entries are informational: the debt shrank, so trim the baseline.
        print(
            f"T-DOC: clean. {len(stale)} baseline entry(ies) now obsolete "
            "(consider --write-baseline to trim).",
            file=sys.stderr,
        )
    else:
        print("T-DOC: clean (no new docstring violations).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
