"""Clone flow: validated inputs + clear error paths.

Two security/UX guarantees:

1. ``ssh_auth_mode == 'setup'`` no longer silently advances and lets
   ``laia-clone``'s SSH probe fail with an opaque error — it emits a
   ``step_error`` event before invoking the binary, telling the user
   to run the connectivity flow first.

2. ``--bwlimit`` is regex-validated on the wizard side AND on the
   binary side. The bash test ``test_bwlimit_validation.sh`` covers
   the binary; here we cover the wizard.
"""

from __future__ import annotations

import pytest

from laia_cli.install_wizard import state as state_mod, validators as validators_mod
from laia_cli.install_wizard.flows import clone as clone_flow


@pytest.mark.parametrize("good", ["", "50M", "1G", "200K", "100"])
def test_rsync_bwlimit_validator_accepts_legitimate(good):
    ok, err = validators_mod.run("rsync_bwlimit", good)
    assert ok, f"unexpected reject of {good!r}: {err}"


@pytest.mark.parametrize("bad", [
    "50MB", "abc", "50M; rm /tmp/x", "$(rm)", "50M|cmd",
    "50M&", "50M`whoami`", "50 M",
])
def test_rsync_bwlimit_validator_rejects_injection(bad):
    ok, err = validators_mod.run("rsync_bwlimit", bad)
    assert not ok, f"validator accepted hostile value {bad!r}"


@pytest.mark.parametrize("good", [
    "u@host", "user@10.0.0.5", "laia-hermes@old.example.com",
])
def test_ssh_target_validator_accepts_legitimate(good):
    ok, _ = validators_mod.run("ssh_target", good)
    assert ok


@pytest.mark.parametrize("bad", [
    "user@host; rm /tmp/x", "user@host$(rm)", "user@host|cmd",
    "noatsign", "@nohost", "user@",
])
def test_ssh_target_validator_rejects_injection(bad):
    ok, _ = validators_mod.run("ssh_target", bad)
    assert not ok, f"validator accepted hostile value {bad!r}"


def test_clone_execute_aborts_on_ssh_setup_mode(tmp_path, monkeypatch):
    """ssh_auth_mode='setup' must yield step_error before any subprocess."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))

    # Make sure we never accidentally run laia-clone.
    invoked: list = []
    monkeypatch.setattr(
        clone_flow, "stream_command",
        lambda *a, **kw: invoked.append(("stream", a, kw)) or iter([]),
    )

    state = state_mod.WizardState(values={
        "source_host": "u@10.0.0.5",
        "ssh_auth_mode": "setup",
        "bwlimit": "50M",
    })
    events = list(clone_flow.execute(state))

    assert not invoked, f"laia-clone was invoked despite ssh_auth_mode=setup: {invoked}"
    assert any(e.type == "step_error" for e in events)
    # The error should mention the connectivity flow or SSH key setup.
    error_text = " ".join(e.label for e in events if e.type == "step_error")
    assert "connectivity" in error_text.lower() or "SSH" in error_text or "clave" in error_text.lower()


def test_clone_execute_with_valid_input_constructs_safe_cmd(monkeypatch, tmp_path):
    """When values are valid, the constructed argv must include --json-progress
    and the validated --bwlimit, and must NOT contain any shell metacharacters."""
    captured: list = []
    monkeypatch.setattr(
        clone_flow, "stream_command",
        lambda cmd, **kw: captured.append(list(cmd)) or iter([]),
    )

    state = state_mod.WizardState(values={
        "source_host": "u@10.0.0.5",
        "ssh_auth_mode": "existing",
        "bwlimit": "50M",
        "keep_session": False,
        "resume": False,
    })
    list(clone_flow.execute(state))

    assert captured, "stream_command was never called"
    cmd = captured[0]
    assert "--json-progress" in cmd
    assert any("--bwlimit=50M" in c for c in cmd)
    # No shell-metacharacters should appear in the constructed argv.
    for tok in cmd:
        assert not any(meta in str(tok) for meta in (";", "|", "$(")) , (
            f"shell metacharacter leaked into clone argv: {tok!r}"
        )
