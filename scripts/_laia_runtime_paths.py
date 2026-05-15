"""Shared path helpers for LAIA scripts.

Runtime data lives under LAIA_HOME, while source modules live under LAIA_ROOT.
Use the Atlas Path Registry when available, with conservative local fallbacks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_path_registry_importable() -> None:
    core = Path(os.environ.get("LAIA_CORE") or (_repo_root() / ".laia-core"))
    if core.is_dir() and str(core) not in sys.path:
        sys.path.insert(0, str(core))


def _get_path(alias: str, default: Path) -> Path:
    _ensure_path_registry_importable()
    try:
        from laia_paths import get_path

        return get_path(alias, default)
    except Exception:
        return default


def laia_home() -> Path:
    return Path(os.environ.get("LAIA_HOME") or (Path.home() / ".laia"))


def laia_root() -> Path:
    return _get_path("laia_root", Path(os.environ.get("LAIA_ROOT") or (Path.home() / "LAIA")))


def workspaces_dir() -> Path:
    return _get_path("workspaces", laia_home() / "workspaces")


def workspace_store_parent() -> Path:
    return _get_path("store", laia_root() / "workspace_store").parent


def add_workspace_store_to_path() -> None:
    root = workspace_store_parent()
    if (root / "workspace_store").is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))
