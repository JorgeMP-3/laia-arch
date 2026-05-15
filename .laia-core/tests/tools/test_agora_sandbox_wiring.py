"""Integration tests: agora_sandbox wired into file_tools.py and terminal_tool.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import agora_sandbox
from tools.file_tools import patch_tool, read_file_tool, write_file_tool
from tools.terminal_tool import terminal_tool


@pytest.fixture
def sandbox_active(monkeypatch):
    monkeypatch.setenv(agora_sandbox.SANDBOX_ENV_VAR, agora_sandbox.SANDBOX_ACTIVE_VALUE)


@pytest.fixture
def sandbox_off(monkeypatch):
    monkeypatch.delenv(agora_sandbox.SANDBOX_ENV_VAR, raising=False)


@pytest.fixture
def whitelist_tmp(sandbox_active, tmp_path, monkeypatch):
    """Point the sandbox whitelist at a tmpdir for safe testing."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(agora_sandbox, "DEFAULT_WHITELISTED_ROOTS", (str(allowed),))
    return allowed


# ── read_file_tool ───────────────────────────────────────────────────────────


def test_read_file_rejects_laia_core_when_sandbox_active(sandbox_active):
    result = read_file_tool("/opt/laia/agent/.laia-core/run_agent.py")
    payload = json.loads(result)
    assert "error" in payload
    assert "agent code" in payload["error"] or "rejected" in payload["error"].lower()


def test_read_file_allows_whitelisted_path_when_sandbox_active(whitelist_tmp):
    f = whitelist_tmp / "hello.txt"
    f.write_text("hello world\n")
    result = read_file_tool(str(f))
    payload = json.loads(result)
    # If read_file returns content, no error key; or the result is a string with the content.
    assert "error" not in payload or "Path rejected" not in payload.get("error", "")


def test_read_file_unrestricted_when_sandbox_off(sandbox_off, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("ok\n")
    result = read_file_tool(str(f))
    payload = json.loads(result)
    # LAIA ARCH stays unrestricted; the sandbox does not interfere.
    assert "Path rejected" not in payload.get("error", "")


# ── write_file_tool ──────────────────────────────────────────────────────────


def test_write_file_rejects_laia_core_when_sandbox_active(sandbox_active):
    result = write_file_tool("/opt/laia/agent/.laia-core/evil.py", "boom")
    # tool_error returns a JSON string with "error" key
    assert "rejected" in result.lower() or "agent code" in result.lower()


def test_write_file_allows_whitelisted_path_when_sandbox_active(whitelist_tmp):
    target = whitelist_tmp / "out.txt"
    result = write_file_tool(str(target), "content")
    # No path-rejection error
    assert "Path rejected" not in result


# ── patch_tool ───────────────────────────────────────────────────────────────


def test_patch_tool_rejects_laia_core_when_sandbox_active(sandbox_active):
    result = patch_tool(
        mode="replace",
        path="/opt/laia/agent/.laia-core/run_agent.py",
        old_string="x",
        new_string="y",
    )
    assert "rejected" in result.lower() or "agent code" in result.lower()


# ── terminal_tool ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cmd", [
    "lxc list",
    "sudo apt update",
    "systemctl status laia-agent",
    "docker ps",
])
def test_terminal_blocks_blacklisted_commands(sandbox_active, cmd):
    result = terminal_tool(command=cmd)
    payload = json.loads(result)
    assert payload["status"] == "rejected"
    assert "not available" in payload["error"]


def test_terminal_blocks_blacklisted_in_pipe(sandbox_active):
    result = terminal_tool(command="echo hi | sudo tee /tmp/x")
    payload = json.loads(result)
    assert payload["status"] == "rejected"


def test_terminal_unrestricted_when_sandbox_off(sandbox_off):
    """When LAIA_PROFILE is unset, the sandbox layer is a no-op.

    We don't actually execute the command (env may not have lxc); we only
    verify that the sandbox didn't pre-reject it with `status=rejected`.
    """
    result = terminal_tool(command="lxc list")
    payload = json.loads(result)
    assert payload.get("status") != "rejected", (
        "sandbox must not block commands when LAIA_PROFILE is unset"
    )
