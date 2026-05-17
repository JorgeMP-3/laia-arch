"""Tests for the cron_* handlers.

systemctl is invoked via subprocess; we monkeypatch _systemctl to capture
calls without actually touching the host's systemd. Validates: name
regex, schedule/command required, idempotent replace, list parsing,
delete cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from laia_executor.tools import cron_tools


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Redirect SYSTEMD_UNIT_DIR to tmp + stub _systemctl."""
    monkeypatch.setattr(cron_tools, "SYSTEMD_UNIT_DIR", tmp_path / "units")
    calls: list[tuple] = []

    def fake_systemctl(*args):
        calls.append(args)
        # Pretend "list-timers" returns nothing — the parsing test reads
        # the unit files directly anyway.
        if args and args[0] == "list-timers":
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(cron_tools, "_systemctl", fake_systemctl)
    yield calls


def _parse(s: str) -> dict:
    return json.loads(s)


def test_create_writes_service_and_timer(_isolated):
    out = _parse(cron_tools.cron_create(
        name="daily-summary",
        schedule="*-*-* 09:00:00",
        command="echo morning",
    ))
    assert out["ok"] is True

    service = cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-daily-summary.service"
    timer = cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-daily-summary.timer"
    assert service.is_file()
    assert timer.is_file()

    timer_content = timer.read_text()
    assert "OnCalendar=*-*-* 09:00:00" in timer_content
    assert "Unit=laia-cron-daily-summary.service" in timer_content

    service_content = service.read_text()
    # ExecStart quotes the command via shlex.quote — accept either single
    # or unquoted simple commands.
    assert "ExecStart=/bin/bash -lc" in service_content
    assert "echo morning" in service_content

    # systemctl was driven through daemon-reload → enable --now (post-write).
    enabled = [c for c in _isolated if c and c[0] == "enable"]
    assert enabled and "--now" in enabled[0]


def test_create_rejects_bad_name():
    out = _parse(cron_tools.cron_create(name="../escape", schedule="hourly", command="x"))
    assert out["ok"] is False
    assert "name" in out["error"]


def test_create_requires_schedule_and_command():
    out = _parse(cron_tools.cron_create(name="x", schedule="", command="echo hi"))
    assert out["ok"] is False
    assert "schedule" in out["error"]

    out = _parse(cron_tools.cron_create(name="x", schedule="hourly", command=""))
    assert out["ok"] is False
    assert "command" in out["error"]


def test_create_replaces_existing(_isolated):
    cron_tools.cron_create(name="rep", schedule="hourly", command="echo v1")
    out = _parse(cron_tools.cron_create(name="rep", schedule="daily", command="echo v2"))
    assert out["ok"] is True
    timer = cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-rep.timer"
    assert "OnCalendar=daily" in timer.read_text()
    service = cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-rep.service"
    assert "echo v2" in service.read_text()


def test_list_returns_created_crons(_isolated):
    cron_tools.cron_create(name="a", schedule="hourly", command="echo a")
    cron_tools.cron_create(name="b", schedule="daily", command="echo b")

    listed = _parse(cron_tools.cron_list())
    assert listed["ok"] is True
    assert listed["count"] == 2
    names = sorted(c["name"] for c in listed["crons"])
    assert names == ["a", "b"]
    schedules = {c["name"]: c["schedule"] for c in listed["crons"]}
    assert schedules["a"] == "hourly"
    assert schedules["b"] == "daily"


def test_delete_removes_units(_isolated):
    cron_tools.cron_create(name="bye", schedule="hourly", command="echo x")
    out = _parse(cron_tools.cron_delete(name="bye"))
    assert out["ok"] is True
    assert not (cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-bye.timer").exists()
    assert not (cron_tools.SYSTEMD_UNIT_DIR / "laia-cron-bye.service").exists()


def test_delete_unknown_returns_error():
    out = _parse(cron_tools.cron_delete(name="ghost"))
    assert out["ok"] is False
    assert "no cron named" in out["error"]
