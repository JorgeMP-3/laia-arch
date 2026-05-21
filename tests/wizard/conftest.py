"""Shared pytest fixtures for the wizard suite.

Adds .laia-core/ to sys.path so the ``laia_cli.install_wizard`` package is
importable without installing the project.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_DIR = _REPO_ROOT / ".laia-core"
sys.path.insert(0, str(_CORE_DIR))


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Point HOME and LAIA_HOME at a tmpdir so checkpoint writes don't escape."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LAIA_HOME", str(tmp_path / "LAIA-ARCH"))
    (tmp_path / "LAIA-ARCH").mkdir(parents=True, exist_ok=True)
    return tmp_path
