"""Tests for the python_exec handler."""

from __future__ import annotations

import json

from laia_executor.tools.python_exec import python_exec, PYTHON_EXEC_CWD


def _parse(s: str) -> dict:
    return json.loads(s)


def test_python_exec_runs_simple_snippet():
    out = _parse(python_exec(code="print(2 + 3)"))
    assert out["ok"] is True
    assert out["exit_code"] == 0
    assert out["stdout"].strip() == "5"


def test_python_exec_captures_stderr():
    out = _parse(python_exec(code="import sys; print('warn', file=sys.stderr); print('ok')"))
    assert out["ok"] is True
    assert "warn" in out["stderr"]
    assert "ok" in out["stdout"]


def test_python_exec_nonzero_exit_on_exception():
    out = _parse(python_exec(code="raise ValueError('boom')"))
    assert out["ok"] is False
    assert out["exit_code"] != 0
    assert "ValueError" in out["stderr"]
    assert "boom" in out["stderr"]


def test_python_exec_rejects_empty_code():
    out = _parse(python_exec(code=""))
    assert out["ok"] is False
    assert "required" in out["error"]


def test_python_exec_cwd_is_writable_or_tmp_fallback(tmp_path, monkeypatch):
    """If /home/user doesn't exist, the handler falls back to /tmp.
    Either way ``cwd`` in the response points to a real directory."""
    out = _parse(python_exec(code="import os; print(os.getcwd())"))
    assert out["ok"] is True
    cwd = out["stdout"].strip()
    assert cwd in (PYTHON_EXEC_CWD, "/tmp")


def test_python_exec_timeout_truncates():
    out = _parse(python_exec(code="import time; time.sleep(5)", timeout=1))
    assert out["ok"] is False
    assert "timed out" in out["error"]


def test_python_exec_returns_truncated_flag_on_huge_output():
    code = "print('x' * 200_000)"
    out = _parse(python_exec(code=code))
    assert out["ok"] is True
    assert out["truncated"] is True
    assert "truncated" in out["stdout"]
