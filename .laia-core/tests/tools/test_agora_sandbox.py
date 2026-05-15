"""Tests for tools/agora_sandbox.py — path + command sandboxing under LAIA_PROFILE=agora-agent."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import agora_sandbox


@pytest.fixture
def sandbox_active(monkeypatch):
    monkeypatch.setenv(agora_sandbox.SANDBOX_ENV_VAR, agora_sandbox.SANDBOX_ACTIVE_VALUE)


@pytest.fixture
def sandbox_off(monkeypatch):
    monkeypatch.delenv(agora_sandbox.SANDBOX_ENV_VAR, raising=False)


# ── path sandbox ─────────────────────────────────────────────────────────────


def test_path_allowed_inside_data(sandbox_active, tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "file.txt").write_text("ok")
    monkeypatch.setattr(agora_sandbox, "DEFAULT_WHITELISTED_ROOTS", (str(data),))
    assert agora_sandbox.enforce_path_sandbox(data / "file.txt") is None


def test_path_blocked_when_outside_whitelist(sandbox_active, tmp_path, monkeypatch):
    monkeypatch.setattr(
        agora_sandbox, "DEFAULT_WHITELISTED_ROOTS", (str(tmp_path / "allowed"),)
    )
    err = agora_sandbox.enforce_path_sandbox("/etc/passwd")
    assert err is not None
    assert "allowed" in err or "rejected" in err.lower()


def test_path_blocked_for_laia_core_substring(sandbox_active):
    err = agora_sandbox.enforce_path_sandbox("/opt/laia/agent/.laia-core/run_agent.py")
    assert err is not None
    assert "agent code" in err or "protected" in err.lower()


def test_path_blocked_for_agent_tree_even_outside_laia_core(sandbox_active):
    err = agora_sandbox.enforce_path_sandbox("/opt/laia/agent/src/anywhere.py")
    assert err is not None


def test_path_unrestricted_when_sandbox_off(sandbox_off):
    # Without LAIA_PROFILE=agora-agent, anything goes — LAIA ARCH stays unrestricted.
    assert agora_sandbox.enforce_path_sandbox("/etc/passwd") is None
    assert agora_sandbox.enforce_path_sandbox("/opt/laia/agent/.laia-core/run_agent.py") is None


def test_path_symlink_escape_blocked(sandbox_active, tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()
    (forbidden / "secret.txt").write_text("nope")
    (allowed / "trap").symlink_to(forbidden / "secret.txt")

    monkeypatch.setattr(agora_sandbox, "DEFAULT_WHITELISTED_ROOTS", (str(allowed),))
    err = agora_sandbox.enforce_path_sandbox(allowed / "trap")
    assert err is not None, "symlink escape must be detected via resolve()"


# ── command sandbox ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("cmd", [
    "lxc list",
    "systemctl status laia-agent",
    "sudo apt install foo",
    "apt-get update",
    "docker ps",
    "mount /dev/sda1 /mnt",
    "chown root:root /opt",
])
def test_command_blacklist_blocks(sandbox_active, cmd):
    err = agora_sandbox.enforce_command_sandbox(cmd)
    assert err is not None
    assert "rejected" in err.lower() or "not available" in err.lower()


@pytest.mark.parametrize("cmd", [
    "echo hello",
    "python3 script.py",
    "ls /opt/laia/data",
    "grep TODO file.txt",
    "curl https://example.com",
    "",
])
def test_command_blacklist_allows_safe(sandbox_active, cmd):
    assert agora_sandbox.enforce_command_sandbox(cmd) is None


def test_command_blacklist_blocks_in_pipe(sandbox_active):
    err = agora_sandbox.enforce_command_sandbox("echo hi | sudo tee /tmp/x")
    assert err is not None
    assert "sudo" in err


def test_command_blacklist_blocks_in_compound(sandbox_active):
    err = agora_sandbox.enforce_command_sandbox("cd /tmp && systemctl status foo")
    assert err is not None
    assert "systemctl" in err


def test_command_blacklist_strips_full_path(sandbox_active):
    err = agora_sandbox.enforce_command_sandbox("/usr/bin/sudo whoami")
    assert err is not None and "sudo" in err


def test_command_blacklist_skips_env_prefix(sandbox_active):
    """ENV=VALUE prefixes should not be mistaken for the command name."""
    # FOO=1 echo bar  → first real command is "echo", which is allowed.
    assert agora_sandbox.enforce_command_sandbox("FOO=1 echo bar") is None
    # FOO=1 sudo …    → still blocked because we eventually see "sudo".
    err = agora_sandbox.enforce_command_sandbox("FOO=1 sudo whoami")
    assert err is not None and "sudo" in err


def test_command_unrestricted_when_sandbox_off(sandbox_off):
    assert agora_sandbox.enforce_command_sandbox("lxc list") is None
    assert agora_sandbox.enforce_command_sandbox("sudo rm -rf /") is None


# ── is_sandbox_active ────────────────────────────────────────────────────────


def test_is_sandbox_active_true(monkeypatch):
    monkeypatch.setenv(agora_sandbox.SANDBOX_ENV_VAR, agora_sandbox.SANDBOX_ACTIVE_VALUE)
    assert agora_sandbox.is_sandbox_active() is True


def test_is_sandbox_active_false_when_unset(monkeypatch):
    monkeypatch.delenv(agora_sandbox.SANDBOX_ENV_VAR, raising=False)
    assert agora_sandbox.is_sandbox_active() is False


def test_is_sandbox_active_false_when_different_profile(monkeypatch):
    monkeypatch.setenv(agora_sandbox.SANDBOX_ENV_VAR, "research")
    assert agora_sandbox.is_sandbox_active() is False
