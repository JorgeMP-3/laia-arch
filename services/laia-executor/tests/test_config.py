"""Tests for ExecutorConfig token loading."""

from __future__ import annotations

import pytest

from laia_executor.config import _read_token


def test_read_token_strips_whitespace(tmp_path):
    f = tmp_path / "tok"
    f.write_text("  abc-xyz-123  \n", encoding="utf-8")
    assert _read_token(str(f)) == "abc-xyz-123"


def test_read_token_empty_file_raises(tmp_path):
    """An empty token file would silently disable auth — must fail loudly."""
    f = tmp_path / "tok"
    f.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        _read_token(str(f))


def test_read_token_whitespace_only_file_raises(tmp_path):
    f = tmp_path / "tok"
    f.write_text("   \n\t  \n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        _read_token(str(f))


def test_read_token_missing_file_falls_back_to_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LAIA_EXECUTOR_TOKEN", "env-token-value")
    assert _read_token(str(tmp_path / "nope")) == "env-token-value"


def test_read_token_missing_file_and_empty_env_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("LAIA_EXECUTOR_TOKEN", "")
    with pytest.raises(RuntimeError, match="missing"):
        _read_token(str(tmp_path / "nope"))
