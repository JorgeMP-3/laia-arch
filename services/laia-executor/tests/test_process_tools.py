"""Tests for the process_* handlers — exercises start, list, status, kill."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from laia_executor.tools import process_tools


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Redirect the log dir to a temp tree + wipe registry between tests."""
    monkeypatch.setattr(process_tools, "PROCESS_LOG_DIR", tmp_path / "logs")
    process_tools._reset_for_tests()
    yield
    process_tools._reset_for_tests()


def _parse(s: str) -> dict:
    return json.loads(s)


def test_start_and_list():
    out = _parse(process_tools.process_start(command="sleep 5", name="napper"))
    assert out["ok"] is True
    assert out["process"]["name"] == "napper"
    assert out["process"]["alive"] is True

    listed = _parse(process_tools.process_list())
    assert listed["count"] == 1
    assert listed["processes"][0]["name"] == "napper"


def test_status_returns_log_tail():
    out = _parse(process_tools.process_start(
        command="for i in 1 2 3; do echo line$i; sleep 0.05; done; echo finished",
        name="chatty",
    ))
    assert out["ok"] is True
    # Wait for the child to finish.
    for _ in range(40):
        st = _parse(process_tools.process_status(name_or_pid="chatty"))
        if not st["process"]["alive"]:
            break
        time.sleep(0.1)
    assert st["ok"] is True
    assert st["process"]["alive"] is False
    assert "finished" in st["log_tail"]


def test_kill_running_process():
    out = _parse(process_tools.process_start(command="sleep 30", name="kill-me"))
    pid = out["process"]["pid"]
    killed = _parse(process_tools.process_kill(name_or_pid="kill-me"))
    assert killed["ok"] is True
    assert killed["killed"] is True
    # Confirm via status.
    st = _parse(process_tools.process_status(name_or_pid=pid))
    assert st["process"]["alive"] is False


def test_kill_unknown_returns_error():
    out = _parse(process_tools.process_kill(name_or_pid="ghost"))
    assert out["ok"] is False
    assert "no process matched" in out["error"]


def test_start_rejects_double_named():
    _parse(process_tools.process_start(command="sleep 10", name="dup"))
    out = _parse(process_tools.process_start(command="sleep 10", name="dup"))
    assert out["ok"] is False
    assert "already running" in out["error"]


def test_start_rejects_empty_command():
    out = _parse(process_tools.process_start(command=""))
    assert out["ok"] is False
    assert "required" in out["error"]


def test_status_lookup_by_pid():
    out = _parse(process_tools.process_start(command="sleep 5", name="byname"))
    pid = out["process"]["pid"]
    st = _parse(process_tools.process_status(name_or_pid=str(pid)))
    assert st["ok"] is True
    assert st["process"]["pid"] == pid
