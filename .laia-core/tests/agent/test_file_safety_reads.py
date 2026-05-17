"""Tests for the extended read denylist in agent.file_safety (A4)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent.file_safety import (
    build_read_denied_paths,
    build_read_denied_prefixes,
    get_read_block_error,
)


def test_read_denied_includes_os_credentials():
    home = os.path.realpath(os.path.expanduser("~"))
    paths = build_read_denied_paths(home)
    assert any("shadow" in p for p in paths)
    assert any("sudoers" in p for p in paths)


def test_read_denied_includes_user_secrets():
    home = os.path.realpath(os.path.expanduser("~"))
    paths = build_read_denied_paths(home)
    assert any(".aws/credentials" in p for p in paths)
    assert any(".kube/config" in p for p in paths)
    assert any(".netrc" in p for p in paths)
    assert any(".ssh/id_rsa" in p for p in paths)


def test_read_denied_includes_laia_secrets():
    home = os.path.realpath(os.path.expanduser("~"))
    paths = build_read_denied_paths(home)
    assert any(p.endswith(".env") for p in paths)
    assert any(p.endswith("auth.json") for p in paths)


def test_get_read_block_error_blocks_etc_shadow():
    err = get_read_block_error("/etc/shadow")
    assert err is not None
    assert "denied" in err.lower()


def test_get_read_block_error_blocks_ssh_private_key():
    fake_home = os.path.realpath(os.path.expanduser("~"))
    err = get_read_block_error(os.path.join(fake_home, ".ssh", "id_ed25519"))
    assert err is not None
    assert "denied" in err.lower()


def test_get_read_block_error_allows_ssh_public_key():
    fake_home = os.path.realpath(os.path.expanduser("~"))
    err = get_read_block_error(os.path.join(fake_home, ".ssh", "id_ed25519.pub"))
    assert err is None, f"expected pub key readable, got: {err}"


def test_get_read_block_error_blocks_aws_creds_dir():
    fake_home = os.path.realpath(os.path.expanduser("~"))
    err = get_read_block_error(os.path.join(fake_home, ".aws", "some-profile"))
    assert err is not None


def test_get_read_block_error_blocks_proc_environ():
    err = get_read_block_error("/proc/12345/environ")
    assert err is not None
    assert "environment" in err.lower()


def test_get_read_block_error_permits_normal_files(tmp_path):
    target = tmp_path / "normal.txt"
    target.write_text("safe content")
    assert get_read_block_error(str(target)) is None


def test_get_read_block_error_still_blocks_laia_hub_cache(tmp_path, monkeypatch):
    """Original protection (prompt injection via skills cache) must
    keep working alongside the new credentials denylist."""
    fake_home = tmp_path / ".laia"
    (fake_home / "skills" / ".hub" / "index-cache").mkdir(parents=True)
    monkeypatch.setenv("LAIA_HOME", str(fake_home))

    target = fake_home / "skills" / ".hub" / "index-cache" / "x.json"
    target.write_text("{}")

    err = get_read_block_error(str(target))
    assert err is not None
    assert "internal LAIA cache" in err
