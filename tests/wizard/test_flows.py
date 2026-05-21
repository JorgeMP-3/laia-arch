"""Flow modules — verify each one exports the protocol and computes screens."""

from __future__ import annotations

import importlib

import pytest

FLOW_NAMES = ["install", "clone", "diagnose", "reset", "connectivity"]


@pytest.fixture(params=FLOW_NAMES)
def flow(request):
    return importlib.import_module(f"laia_cli.install_wizard.flows.{request.param}")


def test_flow_exports_protocol(flow):
    assert isinstance(flow.flow_id, str)
    assert flow.flow_id
    assert isinstance(flow.first_screen_id, str)
    assert flow.first_screen_id in flow.screens
    assert callable(flow.next_screen_id)
    assert callable(flow.execute)


def test_first_screen_resolves(flow):
    """For static screens, just access; for callable ones, call with empty state."""
    from laia_cli.install_wizard.state import WizardState
    entry = flow.screens[flow.first_screen_id]
    if callable(entry):
        screen = entry(WizardState())
    else:
        screen = entry
    assert screen.id == flow.first_screen_id


def test_install_flow_order():
    from laia_cli.install_wizard.flows import install
    from laia_cli.install_wizard.state import WizardState
    state = WizardState()
    assert install.next_screen_id("admin", state) == "llm"
    assert install.next_screen_id("llm", state) == "lxd"
    assert install.next_screen_id("lxd", state) == "confirm"
    assert install.next_screen_id("confirm", state) is None


def test_clone_flow_order():
    from laia_cli.install_wizard.flows import clone
    from laia_cli.install_wizard.state import WizardState
    state = WizardState()
    assert clone.next_screen_id("source_kind", state) == "source_host"
    assert clone.next_screen_id("source_host", state) == "ssh_auth"
    assert clone.next_screen_id("ssh_auth", state) == "options"
    assert clone.next_screen_id("options", state) == "confirm"
    assert clone.next_screen_id("confirm", state) is None


def test_reset_flow_bounces_when_no_intent():
    from laia_cli.install_wizard.flows import reset
    from laia_cli.install_wizard.state import WizardState
    state = WizardState(values={"confirm_intent": False})
    assert reset.next_screen_id("warning", state) == "warning"
    state.values["confirm_intent"] = True
    assert reset.next_screen_id("warning", state) == "typed_confirm"


def test_install_autogen_password_format():
    from laia_cli.install_wizard.flows.install import _autogen_password
    pw = _autogen_password()
    assert len(pw) == 20
    assert pw.isalnum()


def test_install_materialize_auth_unset_returns_none():
    from laia_cli.install_wizard.flows.install import _materialize_auth_file
    assert _materialize_auth_file("unset", None) is None
    assert _materialize_auth_file("", None) is None


def test_install_materialize_auth_writes_600():
    """The function writes to /tmp; we just verify what it produced."""
    import json
    import os
    from laia_cli.install_wizard.flows.install import _materialize_auth_file
    p = _materialize_auth_file("openai", "sk-test")
    assert p is not None
    try:
        mode = os.stat(p).st_mode & 0o777
        assert mode == 0o600, oct(mode)
        payload = json.loads(p.read_text())
        assert payload["provider"] == "openai"
        assert payload["api_key"] == "sk-test"
    finally:
        p.unlink(missing_ok=True)


def test_diagnose_classify_emoji_lines():
    from laia_cli.install_wizard.flows.diagnose import _classify
    assert _classify("✓ laia-agora RUNNING").type == "step_done"
    assert _classify("⚠ pm2 restart loop").type == "warning"
    assert _classify("✗ /api/health no responde").type == "step_error"
    assert _classify("=== Section ===").type == "step_progress"
    assert _classify("random log line") is None


def test_reset_targets_includes_canonical_paths(monkeypatch, tmp_path):
    from laia_cli.install_wizard.flows.reset import _targets
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = [str(p) for p in _targets()]
    # Must include all four canonical wipe targets.
    assert "/opt/laia" in paths
    assert "/srv/laia" in paths
    assert any(p.endswith("/.laia") for p in paths)
    assert any(p.endswith("/LAIA-ARCH") for p in paths)
