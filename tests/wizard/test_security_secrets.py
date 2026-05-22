"""Security: secrets never leak to argv or to disk.

Two threat models in scope here:

* On a shared machine, another tenant can list our argv via
  ``ps`` / ``/proc/<pid>/cmdline``. The wizard must never expose
  the admin password (or any other secret) on the command line.
* Even on a single-tenant machine, the checkpoint file is plain JSON
  on disk. Secret fields must be replaced with a non-recoverable
  placeholder before serialization.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from laia_cli.install_wizard import state as state_mod
from laia_cli.install_wizard.flows import install as install_flow
from laia_cli.install_wizard.state import WizardState


def test_secret_to_tempfile_writes_0600_and_unlinks(tmp_path, monkeypatch):
    """Sanity-check the contextmanager that bridges secrets argv→file."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    seen_paths: list[Path] = []
    with install_flow._secret_to_tempfile("hunter2", prefix="laia-test-") as p:
        seen_paths.append(p)
        assert p.exists()
        assert p.read_text() == "hunter2"
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600, f"expected 0600, got {oct(mode)}"
    # contextmanager unlinks on exit even when the body succeeded.
    assert not seen_paths[0].exists()


def test_secret_to_tempfile_unlinks_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    captured: list[Path] = []
    with pytest.raises(RuntimeError):
        with install_flow._secret_to_tempfile("xyzzy", prefix="laia-test-") as p:
            captured.append(p)
            raise RuntimeError("simulated mid-flow failure")
    assert captured, "context body never ran"
    assert not captured[0].exists(), "tempfile must vanish on exception"


def test_install_flow_never_puts_password_in_argv():
    """Read flows/install.py and assert it doesn't construct --admin-pass=<value>."""
    src = Path(install_flow.__file__).read_text(encoding="utf-8")
    # Old, insecure pattern: "--admin-pass", admin_pass,
    bad_pattern = re.compile(r'"--admin-pass"\s*,\s*admin_pass')
    assert not bad_pattern.search(src), (
        "install.py still puts admin_pass into argv — should use "
        "--admin-pass-file via _secret_to_tempfile."
    )
    # Positive: it MUST construct --admin-pass-file with the tempfile path.
    assert "--admin-pass-file" in src, (
        "install.py should pass --admin-pass-file to bin/laia-install."
    )


def test_state_save_strips_known_secret_names(tmp_path, monkeypatch):
    """save() replaces every secret name with '***' in the checkpoint."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    state = WizardState(
        mode="install",
        current_screen_id="confirm",
        values={
            "admin_user": "admin",
            "admin_pass": "S0meR3alP4ss!",
            "llm_api_key": "sk-aaaaaa",
            "ssh_password": "letmein",
            "github_token": "ghp_xxx",
            "telegram_token": "9999:AAAA",
            "init_lxd": True,
        },
    )
    path = state_mod.save(state)
    body = path.read_text(encoding="utf-8")
    # Direct grep for any of the secrets — nothing should appear verbatim.
    for needle in ("S0meR3alP4ss!", "sk-aaaaaa", "letmein", "ghp_xxx", "9999:AAAA"):
        assert needle not in body, f"secret leaked to disk: {needle!r} in {body[:300]}"
    # Non-secret fields and IDs should still be there.
    data = json.loads(body)
    assert data["values"]["admin_user"] == "admin"
    assert data["values"]["init_lxd"] is True
    assert data["mode"] == "install"


def test_state_checkpoint_file_is_mode_0600(tmp_path, monkeypatch):
    """The wizard-state.json file itself must not be world-readable."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    state = WizardState(mode="install", current_screen_id="admin",
                        values={"admin_user": "admin"})
    path = state_mod.save(state)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0600 on {path}, got {oct(mode)}"


def test_no_subprocess_arg_with_admin_pass_literal(monkeypatch):
    """Capture the cmd list flows/install.execute() would pass to subprocess
    and assert no element starts with '--admin-pass' alone (must always be
    '--admin-pass-file')."""
    captured_cmds: list[list[str]] = []

    def fake_stream(cmd, **kw):
        captured_cmds.append(list(cmd))
        return iter([])  # no events

    monkeypatch.setattr(install_flow, "stream_command", fake_stream)

    state = WizardState(
        mode="install",
        values={
            "admin_user": "admin",
            "admin_pass": "TopSecret9!",
            "llm_provider": "unset",
            "init_lxd": False,
        },
    )
    list(install_flow.execute(state))

    assert captured_cmds, "install.execute() never invoked stream_command"
    cmd = captured_cmds[0]
    # Must contain --admin-pass-file but never --admin-pass alone.
    assert "--admin-pass-file" in cmd
    assert "--admin-pass" not in cmd, f"argv leaked --admin-pass: {cmd}"
    # And the literal password must not appear anywhere in the argv.
    for token in cmd:
        assert "TopSecret9!" not in str(token), f"password leaked in {token!r}"
