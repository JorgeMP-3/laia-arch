"""Checkpoint loader: hardened against corrupted / stale files.

The wizard's checkpoint is plain JSON on disk so it can be inspected by
users. That makes it easy to corrupt accidentally — partial writes,
manual edits, version drift after an upgrade. The loader must:

* Never crash the wizard on a broken file.
* Quarantine the bad file (rename with `.corrupt-<ts>` suffix) so the
  user can post-mortem and so subsequent runs see a clean start.
* Surface a human-readable reason via ``consume_load_warning()`` so the
  UI can render a one-time panel explaining what happened.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from laia_cli.install_wizard import state as state_mod
from laia_cli.install_wizard.contract import CONTRACT_VERSION


@pytest.fixture(autouse=True)
def _laia_home_tmp(tmp_path, monkeypatch):
    """All tests here use a sandboxed LAIA_HOME so the real ~/LAIA-ARCH is untouched."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    yield
    # Clear any leftover module-level warning between tests.
    state_mod.consume_load_warning()


def _state_path(tmp_path: Path) -> Path:
    return tmp_path / "wizard-state.json"


def test_load_missing_file_returns_none_and_no_warning(tmp_path):
    """Absence of a checkpoint is normal — not a corruption."""
    assert state_mod.load() is None
    assert state_mod.consume_load_warning() is None


def test_load_truncated_json_quarantines_and_warns(tmp_path):
    path = _state_path(tmp_path)
    path.write_text("{\"contract_version\": \"0.1", encoding="utf-8")  # truncated
    assert state_mod.load() is None
    warning = state_mod.consume_load_warning()
    assert warning is not None and "JSON inválido" in warning
    # Original file is gone…
    assert not path.exists()
    # …but a quarantined copy lives nearby.
    siblings = [p for p in tmp_path.iterdir() if p.name.startswith("wizard-state.json.corrupt-")]
    assert len(siblings) == 1, f"expected exactly 1 quarantined file, got {siblings}"


def test_load_version_mismatch_quarantines(tmp_path):
    path = _state_path(tmp_path)
    data = {
        "contract_version": "0.0.1-ancient",
        "mode": "install",
        "current_screen_id": "admin",
        "values": {"admin_user": "x"},
        "history": [],
        "extra": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert state_mod.load() is None
    warning = state_mod.consume_load_warning()
    assert warning is not None and "versión" in warning
    assert any(p.name.startswith("wizard-state.json.corrupt-") for p in tmp_path.iterdir())


def test_load_non_object_root_quarantines(tmp_path):
    path = _state_path(tmp_path)
    path.write_text('["not", "an", "object"]', encoding="utf-8")
    assert state_mod.load() is None
    warning = state_mod.consume_load_warning()
    assert warning is not None and "objeto" in warning.lower()


def test_load_valid_returns_state_and_no_warning(tmp_path):
    path = _state_path(tmp_path)
    data = {
        "contract_version": CONTRACT_VERSION,
        "mode": "install",
        "current_screen_id": "admin",
        "values": {"admin_user": "carla"},
        "history": ["mode_select", "admin"],
        "extra": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    state = state_mod.load()
    assert state is not None
    assert state.mode == "install"
    assert state.values.get("admin_user") == "carla"
    assert state_mod.consume_load_warning() is None


def test_warning_is_consumed_on_first_call(tmp_path):
    """consume_load_warning() returns the warning once, then None forever."""
    path = _state_path(tmp_path)
    path.write_text("not even json", encoding="utf-8")
    assert state_mod.load() is None
    first = state_mod.consume_load_warning()
    assert first is not None
    assert state_mod.consume_load_warning() is None
    assert state_mod.consume_load_warning() is None


def test_multiple_corrupt_files_dont_collide(tmp_path):
    """Each quarantine gets a unique timestamp suffix."""
    import time
    path = _state_path(tmp_path)
    path.write_text("bad-json-#1", encoding="utf-8")
    state_mod.load()
    time.sleep(1.1)  # ensure ts suffix differs (HMS resolution)
    path.write_text("bad-json-#2", encoding="utf-8")
    state_mod.load()
    quarantined = sorted(p for p in tmp_path.iterdir() if p.name.startswith("wizard-state.json.corrupt-"))
    assert len(quarantined) == 2, f"expected 2 quarantined files, got {quarantined}"
