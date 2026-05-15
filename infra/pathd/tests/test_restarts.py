"""Tests for restarts.py — unit dep parsing + pending-restart queue + apply."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from pathd.restarts import (
    PendingRestart,
    PendingRestartStore,
    apply_restart,
    parse_unit_deps,
    queue_restarts_for_change,
    scan_units,
)


class TestParseUnitDeps:
    def test_no_directive(self, tmp_path):
        p = tmp_path / "u.service"
        p.write_text("[Unit]\nDescription=X\n[Service]\nExecStart=/bin/true\n")
        assert parse_unit_deps(p) == []

    def test_single_alias(self, tmp_path):
        p = tmp_path / "u.service"
        p.write_text(
            "[Unit]\nDescription=X\nX-LaiaPathDeps=agora\n"
            "[Service]\nExecStart=/bin/true\n"
        )
        assert parse_unit_deps(p) == ["agora"]

    def test_comma_separated(self, tmp_path):
        p = tmp_path / "u.service"
        p.write_text(
            "[Unit]\nX-LaiaPathDeps=agora,ui_server,laia_core\n"
            "[Service]\nExecStart=/bin/true\n"
        )
        assert parse_unit_deps(p) == ["agora", "ui_server", "laia_core"]

    def test_space_separated(self, tmp_path):
        p = tmp_path / "u.service"
        p.write_text(
            "[Unit]\nX-LaiaPathDeps=a b c\n"
            "[Service]\nExecStart=/bin/true\n"
        )
        assert parse_unit_deps(p) == ["a", "b", "c"]

    def test_directive_outside_unit_section_ignored(self, tmp_path):
        p = tmp_path / "u.service"
        p.write_text(
            "[Unit]\n[Service]\nX-LaiaPathDeps=agora\nExecStart=/bin/true\n"
        )
        assert parse_unit_deps(p) == []

    def test_missing_file_returns_empty(self, tmp_path):
        assert parse_unit_deps(tmp_path / "nope.service") == []


class TestScanUnits:
    def test_finds_units_with_deps(self, tmp_path):
        (tmp_path / "with-deps.service").write_text(
            "[Unit]\nX-LaiaPathDeps=agora\n[Service]\nExecStart=/bin/true\n"
        )
        (tmp_path / "without-deps.service").write_text(
            "[Unit]\nDescription=X\n[Service]\nExecStart=/bin/true\n"
        )
        idx = scan_units([tmp_path])
        assert "with-deps.service" in idx
        assert "without-deps.service" not in idx
        assert idx["with-deps.service"] == ["agora"]

    def test_first_path_wins_on_duplicate_names(self, tmp_path):
        d1 = tmp_path / "first"
        d2 = tmp_path / "second"
        d1.mkdir(); d2.mkdir()
        (d1 / "u.service").write_text(
            "[Unit]\nX-LaiaPathDeps=alpha\n[Service]\nExecStart=/bin/true\n"
        )
        (d2 / "u.service").write_text(
            "[Unit]\nX-LaiaPathDeps=beta\n[Service]\nExecStart=/bin/true\n"
        )
        idx = scan_units([d1, d2])
        assert idx["u.service"] == ["alpha"]


class TestPendingStore:
    def test_empty_load(self, tmp_path):
        store = PendingRestartStore(tmp_path / "p.json")
        assert store.load() == []

    def test_queue_and_load(self, tmp_path):
        store = PendingRestartStore(tmp_path / "p.json")
        store.queue(PendingRestart(unit="u", alias="a", old_path="/o", new_path="/n"))
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].unit == "u"
        assert loaded[0].new_path == "/n"

    def test_queue_replaces_duplicate(self, tmp_path):
        store = PendingRestartStore(tmp_path / "p.json")
        store.queue(PendingRestart(unit="u", alias="a", old_path="/v1", new_path="/v2"))
        store.queue(PendingRestart(unit="u", alias="a", old_path="/v2", new_path="/v3"))
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].old_path == "/v2"
        assert loaded[0].new_path == "/v3"

    def test_clear(self, tmp_path):
        store = PendingRestartStore(tmp_path / "p.json")
        store.queue(PendingRestart(unit="u", alias="a", old_path="/o", new_path="/n"))
        store.clear()
        assert store.load() == []


class TestQueueRestartsForChange:
    def test_queues_only_matching_units(self, tmp_path):
        idx = {"a.service": ["foo"], "b.service": ["bar"], "c.service": ["foo", "baz"]}
        store = PendingRestartStore(tmp_path / "p.json")
        queued = queue_restarts_for_change(
            store, alias="foo", old_path="/o", new_path="/n",
            units_index=idx,
        )
        assert sorted(queued) == ["a.service", "c.service"]
        loaded = store.load()
        assert {e.unit for e in loaded} == {"a.service", "c.service"}

    def test_no_units_means_no_queue(self, tmp_path):
        store = PendingRestartStore(tmp_path / "p.json")
        queued = queue_restarts_for_change(
            store, alias="nobody", old_path="/o", new_path="/n",
            units_index={"a.service": ["other"]},
        )
        assert queued == []
        assert store.load() == []


class TestApplyRestart:
    """End-to-end test for apply_restart — verifies the actual systemctl call."""

    def test_invokes_systemctl_reload_or_restart(self):
        fake = MagicMock(returncode=0, stdout="", stderr="")
        with patch("pathd.restarts.subprocess.run", return_value=fake) as run:
            ok, msg = apply_restart("laia-gateway.service")
        assert ok is True
        run.assert_called_once()
        cmd = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        assert cmd == ["systemctl", "reload-or-restart", "laia-gateway.service"]
        assert kwargs.get("timeout") == 30
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True

    def test_user_flag_inserts_user(self):
        fake = MagicMock(returncode=0, stdout="", stderr="")
        with patch("pathd.restarts.subprocess.run", return_value=fake) as run:
            apply_restart("foo.service", user=True)
        cmd = run.call_args.args[0]
        assert cmd == ["systemctl", "--user", "reload-or-restart", "foo.service"]

    def test_nonzero_returncode_signals_failure(self):
        fake = MagicMock(returncode=5, stdout="", stderr="Failed: unit not found")
        with patch("pathd.restarts.subprocess.run", return_value=fake):
            ok, msg = apply_restart("ghost.service")
        assert ok is False
        assert "unit not found" in msg.lower() or "fail" in msg.lower()

    def test_systemctl_missing_returns_failure(self):
        with patch("pathd.restarts.subprocess.run", side_effect=FileNotFoundError):
            ok, msg = apply_restart("foo.service")
        assert ok is False
        assert "systemctl not available" in msg

    def test_timeout_returns_failure(self):
        with patch("pathd.restarts.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=30)):
            ok, msg = apply_restart("slow.service")
        assert ok is False
        assert "timeout" in msg.lower()
