#!/usr/bin/env python3
"""Audit hardcoded paths across the LAIA project.

Finds absolute path references that ought to live in the registry
(~/.laia/config.yaml `paths:` block) and ranks them by number of distinct
files that reference them. Highlights paths that already have an alias and
proposes new aliases for unregistered candidates with >= MIN_REFS references.

Patterns searched (in order):
    /home/<user>/LAIA/...        absolute, real-user path
    /home/<user>/.laia/...       absolute, real-user home
    /srv/laia/...                production data root
    /opt/laia/...                in-container path (flagged but skipped by default)
    ~/LAIA/...                   tilde-expansion
    $HOME/LAIA/...               env-var expansion
    ${HOME}/LAIA/...             braced env-var expansion

Usage:
    audit-hardcoded-paths.py [--min-refs N] [--json] [--include-container]
    audit-hardcoded-paths.py --check  # exit 1 if new candidates exist
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROOTS_TO_SCAN = [
    Path("/home/laia-hermes/LAIA"),
    Path("/home/laia-hermes/bin"),
    Path("/home/laia-hermes/.bashrc"),
    Path("/home/laia-hermes/.zshrc"),
    Path("/home/laia-hermes/.profile"),
    Path("/etc/systemd/system"),  # readable for *.service files we own
]

# Directories whose contents we skip wholesale (cheap-but-exhaustive).
EXCLUDE_DIR_NAMES = {
    "venv", ".venv", "node_modules", "__pycache__", ".git",
    "archived", ".pytest_cache", "dist", "build", ".next",
    "web_dist", ".mypy_cache", ".ruff_cache",
}
# Substring match: any path containing this is skipped.
EXCLUDE_PATH_SUBSTRINGS = ("egg-info",)

# Files we read for path references.
INCLUDE_EXTENSIONS = (
    ".py", ".sh", ".bash", ".zsh", ".service", ".socket", ".timer",
    ".yaml", ".yml", ".toml", ".json", ".md", ".cfg", ".ini", ".env",
    ".conf",
)
# Bin-scripts often have no extension — these dir names trigger ext-less inclusion.
INCLUDE_DIRS_WITHOUT_EXT = {"bin", "scripts"}
# Special files included regardless of extension.
INCLUDE_BASENAMES = {"Makefile", ".bashrc", ".zshrc", ".profile"}

# Patterns. The captured group should be the full hardcoded path.
PATH_PATTERNS = [
    # Real-user absolute paths
    (re.compile(r'/home/[a-zA-Z0-9_-]+/LAIA(?:/[A-Za-z0-9_./-]+)?'), "absolute-home"),
    (re.compile(r'/home/[a-zA-Z0-9_-]+/\.laia(?:/[A-Za-z0-9_./-]+)?'), "absolute-dotlaia"),
    # Production data root
    (re.compile(r'/srv/laia(?:/[A-Za-z0-9_./-]+)?'), "srv-laia"),
    # In-container (flagged but skipped from "to-add" suggestions)
    (re.compile(r'/opt/laia(?:/[A-Za-z0-9_./-]+)?'), "opt-laia"),
    # Tilde and env-var expansions
    (re.compile(r'~/LAIA(?:/[A-Za-z0-9_./-]+)?'), "tilde-laia"),
    (re.compile(r'~/\.laia(?:/[A-Za-z0-9_./-]+)?'), "tilde-dotlaia"),
    (re.compile(r'\$HOME/LAIA(?:/[A-Za-z0-9_./-]+)?'), "home-var-laia"),
    (re.compile(r'\$\{HOME\}/LAIA(?:/[A-Za-z0-9_./-]+)?'), "home-braced-laia"),
]

# Trailing junk that may bleed into a capture (closing brackets, commas, quotes).
TRAILING_TRIM = '.,;:\'"})]>/'  # strip trailing slash too so a/b/ == a/b

# Paths generated/maintained by Atlas itself — never propose them as candidates.
SELF_GENERATED = {
    "~/.laia/.env.paths",
    "~/.laia/pathd.sock",
    "~/.laia/atlas",
    "~/.laia/dns",  # legacy name
    "~/.laia/state/path-cache.json",
    "~/.laia/state/pending-restarts.json",
    "~/.laia/state",
    "~/.laia/config.yaml",  # the registry file itself
}

# Strip the user-specific prefix so we group across machines/users.
def normalize(p: str) -> str:
    p = p.rstrip(TRAILING_TRIM)
    # /home/<anything>/LAIA -> ~/LAIA
    p = re.sub(r"^/home/[^/]+/LAIA", "~/LAIA", p)
    p = re.sub(r"^/home/[^/]+/\.laia", "~/.laia", p)
    # $HOME/.. -> ~/..
    p = p.replace("$HOME/", "~/").replace("${HOME}/", "~/")
    return p


# Group a normalized path into a "registry-grouping" depth, so that
# ~/LAIA/services/agora-backend/data/agora.db groups under
# ~/LAIA/services/agora-backend (depth 4) and ~/LAIA/services (depth 3).
def grouping_keys(normalized: str) -> list[str]:
    parts = normalized.split("/")
    keys = []
    # We want groupings of depth 3, 4, 5 — i.e. up to 3 path segments after `~`.
    for depth in (3, 4, 5):
        if len(parts) >= depth:
            keys.append("/".join(parts[:depth]))
    return keys


# --------------------------------------------------------------------------
# Registry lookup
# --------------------------------------------------------------------------

def load_registry_aliases() -> dict[str, str]:
    """Return {normalized_resolved_path: alias} using the real laia_paths resolver."""
    # Make .laia-core importable
    core = Path(__file__).resolve().parents[2] / ".laia-core"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    try:
        from laia_paths import load_config, resolve  # type: ignore
    except ImportError:
        return {}
    cfg_path = Path(os.environ.get("LAIA_HOME", Path.home() / ".laia")) / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        resolved = resolve(load_config(cfg_path))
    except Exception:
        return {}
    return {normalize(v): k for k, v in resolved.items()}


# --------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------

def iter_files(roots):
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root in seen:
                continue
            seen.add(root)
            yield root
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in EXCLUDE_DIR_NAMES for part in p.parts):
                continue
            if any(s in str(p) for s in EXCLUDE_PATH_SUBSTRINGS):
                continue
            if p.suffix in INCLUDE_EXTENSIONS:
                pass
            elif p.parent.name in INCLUDE_DIRS_WITHOUT_EXT:
                pass
            elif p.name in INCLUDE_BASENAMES:
                pass
            else:
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


def scan(roots, include_container: bool):
    counts_by_group: dict[str, set[str]] = defaultdict(set)  # group_key -> {file}
    raw_counts: dict[str, set[str]] = defaultdict(set)       # normalized -> {file}
    pattern_kinds: dict[str, set[str]] = defaultdict(set)    # group_key -> kinds

    for f in iter_files(roots):
        try:
            text = f.read_text(errors="ignore")
        except (OSError, PermissionError):
            continue
        for regex, kind in PATH_PATTERNS:
            if kind == "opt-laia" and not include_container:
                continue
            for m in regex.findall(text):
                norm = normalize(m)
                raw_counts[norm].add(str(f))
                for key in grouping_keys(norm):
                    counts_by_group[key].add(str(f))
                    pattern_kinds[key].add(kind)
    return counts_by_group, raw_counts, pattern_kinds


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def expand_user_path(p: str) -> str:
    return p.replace("~", str(Path.home()), 1) if p.startswith("~") else p


def build_report(counts_by_group, registry_index, *, min_refs: int):
    """Return list of dicts: one per candidate path (grouping_key)."""
    rows = []
    for group_key, files in counts_by_group.items():
        if group_key in SELF_GENERATED:
            continue
        n = len(files)
        if n < min_refs:
            continue
        existing_alias = registry_index.get(group_key)
        full_path = expand_user_path(group_key)
        on_disk = Path(full_path).exists()
        # Skip paths pointing to individual files (the registry is for dirs +
        # the occasional canonical file like agora.db; per-file references are
        # usually too granular).
        is_file_ref = on_disk and Path(full_path).is_file()
        rows.append({
            "path": group_key,
            "resolved": full_path,
            "refs": n,
            "registered_as": existing_alias,
            "exists_on_disk": on_disk,
            "is_file": is_file_ref,
            "files": sorted(files),
        })
    rows.sort(key=lambda r: (-r["refs"], r["path"]))
    return rows


def render_text(report, *, show_files: bool):
    new_dirs = [r for r in report if r["registered_as"] is None and not r["is_file"]]
    new_files = [r for r in report if r["registered_as"] is None and r["is_file"]]
    known = [r for r in report if r["registered_as"] is not None]

    print(f"\n=== Already in registry ({len(known)}) — for awareness ===")
    print(f"{'refs':>4}  {'alias':<24}  path")
    print("-" * 80)
    for r in known:
        print(f"{r['refs']:>4}  {r['registered_as']:<24}  {r['path']}")

    print(f"\n=== Candidate DIRECTORIES not in registry ({len(new_dirs)}) ===")
    print(f"{'refs':>4}  {'on disk':<8}  path")
    print("-" * 80)
    for r in new_dirs:
        disk = "yes" if r["exists_on_disk"] else "NO"
        print(f"{r['refs']:>4}  {disk:<8}  {r['path']}")
        if show_files:
            for f in r["files"]:
                print(f"        - {f}")

    if new_files:
        print(f"\n=== Individual files referenced (info; usually too granular for registry) ({len(new_files)}) ===")
        for r in new_files:
            print(f"  {r['refs']:>3}  {r['path']}")

    if new_dirs:
        print(f"\nSuggestion: review the candidate directories above.")
        print(f"Add ones with stable identity to ~/.laia/config.yaml `paths:` block.")
    else:
        print("\nNothing to add — every >=N-ref directory is already aliased.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-refs", type=int, default=2,
                   help="Minimum distinct files referencing a path to surface it (default: 2)")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON instead of human-readable text")
    p.add_argument("--include-container", action="store_true",
                   help="Also flag /opt/laia/ paths (in-LXD-container)")
    p.add_argument("--files", action="store_true",
                   help="Show the list of referring files for each candidate")
    p.add_argument("--check", action="store_true",
                   help="Exit 1 if any new candidates exist (CI-friendly)")
    p.add_argument("--root", action="append", type=Path,
                   help="Override scan roots (can be passed multiple times)")
    args = p.parse_args()

    roots = args.root if args.root else ROOTS_TO_SCAN
    counts, _, _ = scan(roots, include_container=args.include_container)
    registry_index = load_registry_aliases()
    report = build_report(counts, registry_index, min_refs=args.min_refs)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        render_text(report, show_files=args.files)

    if args.check:
        new = [r for r in report
               if r["registered_as"] is None and not r["is_file"]]
        return 1 if new else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
