"""Connectivity flow: Tailscale install no longer pipes curl to sh, and
ssh-copy-id no longer auto-accepts unknown host keys.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from laia_cli.install_wizard import state as state_mod
from laia_cli.install_wizard.flows import connectivity as connectivity_flow


def test_tailscale_install_never_pipes_curl_to_sh():
    """The actual subprocess invocation must not pipe curl to sh.

    We check for the literal pattern bash -c "curl ... | sh" inside a
    stream_command call — string mentions in description fields are
    fine (they're shown to the user, not executed).
    """
    src = Path(connectivity_flow.__file__).read_text(encoding="utf-8")
    # Old, dangerous pattern: ``["bash", "-c", "curl …| sh"]`` argv.
    invocation_pattern = re.compile(
        r'\[\s*"bash"\s*,\s*"-c"\s*,\s*"curl[^"]*\|\s*sh',
        re.IGNORECASE,
    )
    assert not invocation_pattern.search(src), (
        "connectivity.py still has a bash -c 'curl …| sh' invocation; "
        "should download to tempfile and exec via bash <path> after "
        "sanity checks."
    )
    # Positive: must use --proto =https --tlsv1.2 for the download.
    assert "--proto" in src and "=https" in src
    assert "--tlsv1.2" in src
    # And must download to a tempfile (we look for the tempfile usage marker).
    assert "NamedTemporaryFile" in src or "mkstemp" in src


def test_ssh_copy_id_uses_strict_host_key_checking():
    """ssh-copy-id must use StrictHostKeyChecking=ask (not accept-new)."""
    src = Path(connectivity_flow.__file__).read_text(encoding="utf-8")
    assert "StrictHostKeyChecking=ask" in src, (
        "ssh-copy-id should use StrictHostKeyChecking=ask, not accept-new"
    )
    # Negative assertion — the old, weak setting must be gone.
    assert "StrictHostKeyChecking=accept-new" not in src


def test_ssh_keyscan_runs_before_copy_id():
    """ssh-keyscan should run before ssh-copy-id inside execute().

    The screen choices may mention ssh-copy-id in their descriptions, so
    we look specifically at the execute() function body to enforce the
    ordering of the actual subprocess invocations.
    """
    src = Path(connectivity_flow.__file__).read_text(encoding="utf-8")
    # Slice out the body of execute(): from `def execute(state)` onwards.
    exec_idx = src.index("def execute(state)")
    body = src[exec_idx:]
    keyscan_idx = body.find('"ssh-keyscan"')
    copyid_idx = body.find('"ssh-copy-id"')
    assert keyscan_idx > 0, "ssh-keyscan call missing from execute()"
    assert copyid_idx > 0, "ssh-copy-id call missing from execute()"
    assert keyscan_idx < copyid_idx, (
        "Inside execute(), ssh-keyscan must run before ssh-copy-id so the "
        "user sees the fingerprint before trust is established."
    )


def test_existing_ssh_keys_enumeration_returns_only_keypairs(tmp_path, monkeypatch):
    """Sanity check: helper only returns keys that have a matching .pub."""
    fake_ssh = tmp_path / ".ssh"
    fake_ssh.mkdir()
    # Key with pub: should be picked up.
    (fake_ssh / "id_ed25519").write_text("PRIVATE")
    (fake_ssh / "id_ed25519.pub").write_text("ssh-ed25519 AAA")
    # Orphan private key (no .pub): should be skipped.
    (fake_ssh / "id_rsa").write_text("PRIVATE")
    # Some other unrelated file: should be skipped.
    (fake_ssh / "config").write_text("Host *")

    monkeypatch.setenv("HOME", str(tmp_path))
    keys = connectivity_flow._existing_ssh_keys()
    names = [k.name for k in keys]
    assert "id_ed25519" in names
    assert "id_rsa" not in names
    assert "config" not in names
