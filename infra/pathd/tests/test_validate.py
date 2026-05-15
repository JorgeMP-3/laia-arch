"""Tests for the Atlas path validator (`laia-path validate`)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pathd.validate import (
    ValidationReport,
    format_report,
    validate_paths,
)


@pytest.fixture
def existing(tmp_path: Path) -> dict[str, str]:
    """Two real directories on disk that we can reference safely."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    return {"a": str(a), "b": str(b)}


def test_clean_config_has_no_issues(existing):
    report = validate_paths(existing)
    assert report.ok
    assert report.exit_code() == 0


def test_reserved_name_raises_error(existing):
    paths = dict(existing)
    paths["class"] = str(Path(existing["a"]))
    report = validate_paths(paths)
    assert any(i.code == "reserved-name" and "class" in i.aliases for i in report.errors)
    assert report.exit_code() == 1


def test_duplicate_target_raises_warning(existing):
    a = existing["a"]
    paths = {"first": a, "second": a, "b": existing["b"]}
    report = validate_paths(paths)
    dup = [i for i in report.warnings if i.code == "duplicate-target"]
    assert len(dup) == 1
    assert dup[0].aliases == ("first", "second")
    # Only warnings → exit code 2
    assert report.exit_code() == 2


def test_missing_path_raises_error(existing, tmp_path):
    paths = dict(existing)
    paths["ghost"] = str(tmp_path / "does-not-exist")
    report = validate_paths(paths)
    assert any(i.code == "missing" and "ghost" in i.aliases for i in report.errors)
    assert report.exit_code() == 1


def test_no_existence_check_skips_missing(existing, tmp_path):
    paths = dict(existing)
    paths["ghost"] = str(tmp_path / "does-not-exist")
    report = validate_paths(paths, check_existence=False)
    # No "missing" errors; clean otherwise.
    assert not any(i.code == "missing" for i in report.issues)
    assert report.ok


def test_normalization_handles_trailing_slashes(tmp_path):
    d = tmp_path / "shared"
    d.mkdir()
    paths = {"a": str(d), "b": str(d) + "/"}
    report = validate_paths(paths)
    dup = [i for i in report.issues if i.code == "duplicate-target"]
    assert len(dup) == 1, "trailing slash should not hide a duplicate"


def test_errors_dominate_warnings_in_exit_code(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    paths = {
        "first": str(a),
        "second": str(a),                         # warning
        "ghost": str(tmp_path / "nope"),          # error
    }
    report = validate_paths(paths)
    assert report.errors and report.warnings
    assert report.exit_code() == 1, "error must dominate"


def test_format_report_includes_codes(existing, tmp_path):
    paths = dict(existing)
    paths["ghost"] = str(tmp_path / "missing-here")
    paths["first"] = existing["a"]
    paths["second"] = existing["a"]
    report = validate_paths(paths)
    text = format_report(report, use_color=False)
    assert "[missing]" in text
    assert "[duplicate-target]" in text
    assert "error" in text.lower()


def test_format_clean_report(existing):
    report = validate_paths(existing)
    text = format_report(report, use_color=False)
    assert "no validation issues" in text
