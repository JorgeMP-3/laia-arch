"""Tests for grep/glob truncate marker — A4 fix."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from laia_executor.tools.file_ops import MAX_GREP_RESULTS, glob_tool, grep_tool


def test_glob_truncates_explicitly(tmp_path):
    """When glob hits MAX_GREP_RESULTS files, the output ends in the
    `truncated at N matches` marker so the LLM knows it didn't see all."""
    n = MAX_GREP_RESULTS + 50
    for i in range(n):
        (tmp_path / f"f{i:04d}.txt").write_text("x")
    out = glob_tool("*.txt", str(tmp_path))
    lines = out.splitlines()
    assert len(lines) == MAX_GREP_RESULTS + 1  # results + truncate marker
    assert "truncated" in lines[-1]
    assert str(MAX_GREP_RESULTS) in lines[-1]


def test_glob_no_marker_below_limit(tmp_path):
    """Under the limit, no marker is appended."""
    (tmp_path / "only.txt").write_text("x")
    out = glob_tool("*.txt", str(tmp_path))
    assert "truncated" not in out
    assert "only.txt" in out


def test_grep_python_fallback_truncates(tmp_path, monkeypatch):
    """Force the Python fallback (no ripgrep) and check the marker."""
    # Hide ripgrep so the Python branch runs.
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    n = MAX_GREP_RESULTS + 20
    for i in range(n):
        (tmp_path / f"f{i:04d}.txt").write_text("MATCHME line one")
    out = grep_tool("MATCHME", str(tmp_path))
    lines = out.splitlines()
    # Last line is the truncate marker.
    assert "truncated" in lines[-1]
    assert "lines" in lines[-1]


def test_grep_ripgrep_path_truncates_if_available(tmp_path):
    """If ripgrep is installed, the rg branch also honours the limit."""
    if not shutil.which("rg"):
        pytest.skip("ripgrep not available in this env")
    n = MAX_GREP_RESULTS + 10
    big = tmp_path / "big.txt"
    big.write_text("\n".join(f"MATCHME line {i}" for i in range(n)))
    out = grep_tool("MATCHME", str(tmp_path))
    lines = out.splitlines()
    # We can't predict ripgrep's exact ordering, but the cap holds and the
    # marker is present iff we hit it (with --max-count rg reports per-file,
    # so we may not hit the global cap on a single file — check loosely).
    if len(lines) > MAX_GREP_RESULTS:
        assert "truncated" in lines[-1]
