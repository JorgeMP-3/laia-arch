"""Validation logic for Atlas path registry.

Pure functions that operate on a resolved alias→path dict (no I/O except
optional disk existence checks). Used by `laia-path validate`.
"""
from __future__ import annotations

import keyword
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# Reserved alias names. Includes Python keywords (e.g. `class`, `for`) plus a
# small set of pathd-internal names that would shadow internal API.
_RESERVED_NAMES: frozenset[str] = frozenset(keyword.kwlist) | frozenset({
    "path",       # would shadow pathlib.Path conceptually
    "paths",      # collides with the config section name
    "__init__",
    "__name__",
})


@dataclass
class ValidationIssue:
    """One finding from validation. `severity` is 'error' or 'warning'."""
    severity: str          # "error" | "warning"
    code: str              # short machine-readable code
    aliases: tuple[str, ...]
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.issues

    def exit_code(self) -> int:
        """0 if clean, 1 if any errors, 2 if only warnings."""
        if self.errors:
            return 1
        if self.warnings:
            return 2
        return 0


def _normalize(p: str | Path) -> str:
    """Normalize a path string for equality comparison.

    Resolves `..`, strips trailing slashes, and collapses redundant separators.
    Does NOT follow symlinks (we want to detect aliases that point to the
    same logical path, not the same physical inode — symlinks intentionally
    point elsewhere).
    """
    return str(Path(p)).rstrip("/")


def validate_paths(
    paths: dict[str, str],
    *,
    check_existence: bool = True,
) -> ValidationReport:
    """Validate a resolved alias→path dict.

    Checks:
      - Reserved alias names (error)
      - Hard conflict: two aliases resolve to identical normalized path (warning)
      - Soft conflict: one alias is a strict path-prefix of another (info; recorded as warning)
      - Path missing on disk (error; only if check_existence=True)

    Returns a ValidationReport. Pure: no side effects.
    """
    report = ValidationReport()

    # 1. Reserved alias names — error.
    for alias in paths:
        if alias in _RESERVED_NAMES:
            report.issues.append(ValidationIssue(
                severity="error",
                code="reserved-name",
                aliases=(alias,),
                message=f"alias {alias!r} uses a reserved name",
            ))

    # 2. Hard conflicts: identical normalized paths.
    by_path: dict[str, list[str]] = {}
    for alias, raw in paths.items():
        key = _normalize(raw)
        by_path.setdefault(key, []).append(alias)
    for path_str, aliases in by_path.items():
        if len(aliases) > 1:
            sorted_aliases = tuple(sorted(aliases))
            report.issues.append(ValidationIssue(
                severity="warning",
                code="duplicate-target",
                aliases=sorted_aliases,
                message=(
                    f"aliases {', '.join(sorted_aliases)} all resolve to {path_str!r} "
                    "(may be intentional; verify each alias is needed)"
                ),
            ))

    # 3. Missing paths — error if requested.
    if check_existence:
        for alias, raw in sorted(paths.items()):
            if not Path(raw).exists():
                report.issues.append(ValidationIssue(
                    severity="error",
                    code="missing",
                    aliases=(alias,),
                    message=f"path {raw!r} for alias {alias!r} does not exist on disk",
                ))

    return report


def format_report(report: ValidationReport, *, use_color: bool = True) -> str:
    """Render a human-readable validation report."""
    if use_color:
        red = "\033[1;31m"
        yel = "\033[1;33m"
        grn = "\033[1;32m"
        dim = "\033[2m"
        rst = "\033[0m"
    else:
        red = yel = grn = dim = rst = ""

    if report.ok:
        return f"{grn}✓ no validation issues{rst}\n"

    lines: list[str] = []
    for issue in report.issues:
        marker = f"{red}✗{rst}" if issue.severity == "error" else f"{yel}⚠{rst}"
        lines.append(f"  {marker} [{issue.code}] {issue.message}")

    n_err = len(report.errors)
    n_warn = len(report.warnings)
    summary = []
    if n_err:
        summary.append(f"{red}{n_err} error(s){rst}")
    if n_warn:
        summary.append(f"{yel}{n_warn} warning(s){rst}")
    lines.append(f"\n{dim}Summary:{rst} " + ", ".join(summary))
    return "\n".join(lines) + "\n"
