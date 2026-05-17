"""Tests for the DB-locked retry helper in private_workspace."""

from __future__ import annotations

import sqlite3
import time

import pytest

from laia_executor.tools import private_workspace as pw


def test_retry_recovers_from_transient_lock():
    """Two `database is locked` errors then success → returns the success value."""
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    out = pw._retry_on_db_locked(flaky, base_delay=0.001)
    assert out == "ok"
    assert calls["n"] == 3


def test_retry_propagates_non_lock_errors():
    """A different OperationalError (not "locked") must NOT be retried."""
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise sqlite3.OperationalError("no such table")

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        pw._retry_on_db_locked(boom, base_delay=0.001)
    assert calls["n"] == 1


def test_retry_gives_up_after_max_attempts():
    """If every attempt fails with `locked`, the final attempt's exception bubbles up."""
    calls = {"n": 0}

    def always_locked():
        calls["n"] += 1
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        pw._retry_on_db_locked(always_locked, max_attempts=3, base_delay=0.001)
    assert calls["n"] == 3


def test_retry_passes_args_and_kwargs():
    """The wrapper must forward positional + keyword args verbatim."""
    def add(a, b, c=0):
        return a + b + c

    assert pw._retry_on_db_locked(add, 1, 2, c=3) == 6
