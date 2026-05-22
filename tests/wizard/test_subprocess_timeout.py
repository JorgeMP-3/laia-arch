"""Bounded subprocess execution: timeouts always fire.

The wizard cannot afford to wait forever for a stuck child (apt lock,
network stall, deadlocked rsync). ``stream_command`` accepts both an
absolute and an idle timeout, and is expected to:

* Yield a ``step_error`` event when the absolute deadline passes.
* Yield a ``warning`` event when the child goes silent past the
  idle timeout (without killing it — the child may still finish).
* Kill the child tree (SIGINT → SIGTERM → SIGKILL) when aborting.
"""

from __future__ import annotations

import os
import time

import pytest

from laia_cli.install_wizard.flows._subprocess import stream_command


def test_short_command_runs_and_emits_done():
    events = list(stream_command(
        ["sh", "-c", "echo hello"],
        step_id="echo", label="echo hello",
        timeout_s=10, idle_timeout_s=5,
    ))
    types = [e.type for e in events]
    assert "step_start" in types
    assert "step_done" in types
    assert "step_error" not in types
    # log_line for the actual "hello".
    log_lines = [e.label for e in events if e.type == "log_line"]
    assert any("hello" in line for line in log_lines)


def test_absolute_timeout_aborts_long_sleep():
    """sleep 10 with timeout_s=2 must return in roughly 2 seconds with an error."""
    t0 = time.time()
    events = list(stream_command(
        ["sleep", "10"],
        step_id="timeout", label="sleep 10",
        timeout_s=2, idle_timeout_s=10,
    ))
    elapsed = time.time() - t0
    # Allow some slack for OS scheduling but never anywhere near 10s.
    assert elapsed < 5.0, f"timeout ignored — elapsed {elapsed:.2f}s"
    assert any(
        e.type == "step_error" and "tiempo máximo" in e.label
        for e in events
    ), f"expected absolute-timeout error event, got {[e.type for e in events]}"


def test_idle_timeout_emits_warning_but_lets_child_finish():
    """A child that's silent for >idle_timeout but eventually finishes
    should produce a warning event AND a normal step_done."""
    # sh -c 'sleep 2; echo done' is silent for 2s then prints "done".
    events = list(stream_command(
        ["sh", "-c", "sleep 2 && echo done"],
        step_id="idle", label="silent then done",
        timeout_s=10, idle_timeout_s=1,
    ))
    types = [e.type for e in events]
    assert "step_done" in types
    assert "warning" in types, f"expected an idle-timeout warning, got {types}"


def test_nonzero_exit_yields_step_error():
    events = list(stream_command(
        ["sh", "-c", "exit 7"],
        step_id="rc", label="exit 7",
        timeout_s=5,
    ))
    error_events = [e for e in events if e.type == "step_error"]
    assert error_events, f"expected step_error on rc=7, got {[e.type for e in events]}"
    assert error_events[0].extra.get("returncode") == 7


def test_nonexistent_command_yields_step_error():
    events = list(stream_command(
        ["this-command-cannot-possibly-exist-xyzzy"],
        step_id="missing", label="missing cmd",
        timeout_s=5,
    ))
    types = [e.type for e in events]
    assert "step_error" in types


def test_disabled_timeout_with_negative_value():
    """A negative timeout disables the check (still must complete normally)."""
    events = list(stream_command(
        ["sh", "-c", "echo ok"],
        step_id="notimeout", label="ok",
        timeout_s=-1, idle_timeout_s=-1,
    ))
    assert any(e.type == "step_done" for e in events)
