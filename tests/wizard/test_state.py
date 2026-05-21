"""Checkpoint save/load semantics."""

from __future__ import annotations

import json
from pathlib import Path

from laia_cli.install_wizard import state as state_mod
from laia_cli.install_wizard.contract import CONTRACT_VERSION


def test_load_missing_returns_none(tmp_path):
    path = tmp_path / "wizard-state.json"
    assert state_mod.load(path) is None


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "wizard-state.json"
    s = state_mod.WizardState(
        mode="clone",
        current_screen_id="source_host",
        values={"source_host": "laia@1.2.3.4"},
        history=["mode_select", "source_kind", "source_host"],
    )
    state_mod.save(s, path)
    loaded = state_mod.load(path)
    assert loaded is not None
    assert loaded.mode == "clone"
    assert loaded.current_screen_id == "source_host"
    assert loaded.values["source_host"] == "laia@1.2.3.4"
    assert loaded.history[-1] == "source_host"


def test_save_strips_secrets(tmp_path):
    path = tmp_path / "wizard-state.json"
    s = state_mod.WizardState(
        mode="install",
        values={
            "admin_user": "admin",
            "admin_pass": "supersecret",      # in SECRET_FIELD_NAMES
            "llm_api_key": "sk-shouldnotpersist",
        },
    )
    state_mod.save(s, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["values"]["admin_user"] == "admin"
    assert raw["values"]["admin_pass"] == "***"
    assert raw["values"]["llm_api_key"] == "***"


def test_save_writes_mode_600(tmp_path):
    path = tmp_path / "wizard-state.json"
    s = state_mod.WizardState(mode="install")
    state_mod.save(s, path)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_stale_contract_version_returns_none(tmp_path):
    path = tmp_path / "wizard-state.json"
    path.write_text(json.dumps({
        "contract_version": "0.0.0-old",
        "mode": "clone",
        "current_screen_id": "x",
        "values": {},
        "history": [],
        "extra": {},
    }))
    assert state_mod.load(path) is None  # version mismatch → ignored


def test_history_remember_pop_back():
    s = state_mod.WizardState()
    s.remember("a")
    s.remember("b")
    s.remember("c")
    s.remember("c")  # idempotent dedupe of last
    assert s.history == ["a", "b", "c"]
    prev = s.pop_back()
    assert prev == "b"
    assert s.history == ["a", "b"]


def test_clear_is_idempotent(tmp_path):
    path = tmp_path / "wizard-state.json"
    state_mod.clear(path)  # no error on missing
    state_mod.save(state_mod.WizardState(mode="x"), path)
    state_mod.clear(path)
    assert not path.exists()
