"""Headless wizard: --config drives the engine end-to-end.

Walks every screen of the install flow without any TTY involvement and
asserts the engine reaches the confirm screen with all values populated.
This is the contract a CI pipeline depends on: deterministic install
from a checked-in YAML.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from laia_cli.install_wizard import _headless_ui, state as state_mod
from laia_cli.install_wizard._headless_ui import HeadlessMissingField, HeadlessUI, load_config
from laia_cli.install_wizard.engine import WizardEngine


def _drive(ui: HeadlessUI, engine: WizardEngine, max_steps: int = 20) -> str | None:
    """Run the engine loop until done or ready_action; return action id."""
    for _ in range(max_steps):
        if engine.is_done():
            return None
        screen = engine.next_screen()
        user_input = ui.render(screen)
        result = engine.submit(user_input)
        if not result.ok:
            raise AssertionError(f"engine refused submit: {result.errors}")
        if result.ready_action:
            return result.ready_action
    raise AssertionError("engine never reached ready_action — possible loop")


def test_install_flow_reaches_confirm_with_minimal_config(tmp_path, monkeypatch):
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    ui = HeadlessUI({
        "admin_user": "admin",
        "admin_pass": "S3cr3tPa55!",
        "llm_provider": "unset",  # API key is hidden by depends_on
        "init_lxd": True,
    })
    engine = WizardEngine(state=state_mod.WizardState(mode="install"), autosave=False)
    action = _drive(ui, engine)
    assert action == "confirm"
    # Engine collected every value.
    assert engine.state.values["admin_user"] == "admin"
    assert engine.state.values["llm_provider"] == "unset"
    assert engine.state.values["init_lxd"] is True


def test_install_flow_with_real_provider_requires_api_key(tmp_path, monkeypatch):
    """When provider is a real one, llm_api_key becomes required."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    ui = HeadlessUI({
        "admin_user": "admin",
        "admin_pass": "x",
        "llm_provider": "deepseek",
        # llm_api_key intentionally missing.
        "init_lxd": False,
    })
    engine = WizardEngine(state=state_mod.WizardState(mode="install"), autosave=False)
    with pytest.raises(HeadlessMissingField) as exc:
        _drive(ui, engine)
    assert "llm_api_key" in str(exc.value)


def test_install_flow_with_real_provider_and_key_proceeds(tmp_path, monkeypatch):
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    ui = HeadlessUI({
        "admin_user": "admin",
        "admin_pass": "x",
        "llm_provider": "deepseek",
        "llm_api_key": "sk-fake",
        "init_lxd": False,
    })
    engine = WizardEngine(state=state_mod.WizardState(mode="install"), autosave=False)
    action = _drive(ui, engine)
    assert action == "confirm"


def test_load_config_json(tmp_path):
    p = tmp_path / "install.json"
    p.write_text(json.dumps({
        "mode": "install",
        "values": {"admin_user": "u", "init_lxd": True},
    }))
    data = load_config(p)
    assert data["mode"] == "install"
    assert data["values"]["admin_user"] == "u"


def test_load_config_yaml(tmp_path):
    """YAML loading is optional; skip if pyyaml not installed."""
    yaml = pytest.importorskip("yaml")
    p = tmp_path / "install.yaml"
    p.write_text("mode: install\nvalues:\n  admin_user: u\n  init_lxd: true\n")
    data = load_config(p)
    assert data["mode"] == "install"
    assert data["values"]["admin_user"] == "u"


def test_load_config_rejects_array_root(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        load_config(p)


def test_clone_flow_with_ssh_setup_mode_aborts(tmp_path, monkeypatch):
    """ssh_auth_mode=='setup' must emit a clear step_error (no silent stub)."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    ui = HeadlessUI({
        "source_kind": "lan",
        "source_host": "u@10.0.0.5",
        "ssh_auth_mode": "setup",
        "bwlimit": "50M",
        "keep_session": False,
        "resume": False,
    })
    engine = WizardEngine(state=state_mod.WizardState(mode="clone"), autosave=False)
    action = _drive(ui, engine)
    assert action == "confirm"

    # Now call execute() — should yield a step_error before invoking laia-clone.
    events = list(engine.execute())
    types = [e.type for e in events]
    error_msgs = [e.label for e in events if e.type == "step_error"]
    assert "step_error" in types, f"expected step_error from ssh setup mode, got {types}"
    joined = " ".join(error_msgs)
    assert "connectivity" in joined.lower() or "clave SSH" in joined or "SSH" in joined
