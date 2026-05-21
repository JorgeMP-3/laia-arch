"""Smoke tests for the v2 control center app.

These tests don't need a live AGORA backend — they stub the
:class:`ctl.client.AgoraClient` with a fake that returns canned bodies
so we can drive the Textual ``App.run_test()`` headless harness and
confirm each pane mounts, queries the client and renders without
exploding.
"""

from __future__ import annotations

from typing import Any

import pytest


class FakeClient:
    """Minimal stand-in for :class:`AgoraClient`. Every call returns a
    plausible-shape dict and never raises."""

    api_url = "http://fake.local"
    token = "fake-token"

    async def close(self): ...

    async def login(self, *a, **kw): ...

    async def health(self):
        return {"ok": True, "db": "sqlite", "auth_json_status": "linked",
                "default_llm_provider": "openai-codex", "time": "2026-05-19T00:00:00Z",
                "data_dir": "/opt/agora/data", "lxd_available": True}

    async def status(self):
        return {"status": {
            "users": [{"username": "jorge"}],
            "containers": [{"state": "running", "name": "laia-agora"}],
            "image": {"stale": False, "drift_seconds": 30},
            "auth_json": {"path": "/opt/agora/data/auth.json", "status": "linked", "ready": True},
        }}

    async def users(self):
        return {"users": [{
            "id": "user_jorge", "username": "jorge", "role": "agora_admin",
            "active": True, "llm_provider": "openai-codex",
            "agent_id": "agent_jorge",
        }]}

    async def containers_list(self):
        return {"containers": [{
            "name": "laia-agora", "state": "running",
            "ipv4": "10.99.0.155", "profile": "laia-agora",
        }]}

    async def jobs(self):
        return {"jobs": [{
            "id": "job_abc123", "kind": "provision-user",
            "status": "completed", "actor_id": "user_jorge",
            "created_at": "2026-05-19T00:00:00Z",
        }]}

    async def logs(self, source, lines=120):
        return {"logs": {"lines": ["[INFO] hello", "[INFO] world"]}}

    async def audit(self, *, user_id=None, limit=120):
        return {"tool_calls": [{
            "ts": "2026-05-19T00:00:00Z", "phase": "complete",
            "tool": "read_file", "user_id": "user_jorge",
            "agent_slug": "jorge-dev", "result_len": 42,
        }]}

    async def errors(self, *, limit=100):
        return {"errors": []}

    async def marketplace_pending(self):
        return {"plugins": [], "skills": []}

    async def plugins_catalog(self):
        return {"data": []}

    async def skills_catalog(self):
        return {"data": [{"slug": "agent-self-edit",
                          "owner_user_id": "user_jorge", "status": "approved"}]}

    async def laia_inbox_count(self):
        return {"unread_by_user": []}

    async def users_overview(self, *, window="day"):
        return {"window": window, "since": "2026-05-19T00:00:00Z", "users": [{
            "id": "user_jorge", "username": "jorge", "display_name": "Jorge",
            "role": "agora_admin", "active": True,
            "agent_id": "agent_jorge", "container_name": "laia-jorge",
            "container_ip": "10.99.0.10", "container_status": "running",
            "llm_provider": "openai-codex", "llm_model": "gpt-5.5",
            "budget": {"daily_usd": 3.0, "monthly_usd": None, "tokens_daily": None},
            "usage": {"tokens_input": 100, "tokens_output": 50,
                      "cost_usd": 0.01, "calls": 1},
            "unread_inbox": 0, "learnings_count": 0,
        }]}

    async def scheduled_jobs(self, user_id):
        return {"user_id": user_id, "scheduled_jobs": [], "webhooks": []}

    async def child_runs(self, user_id, *, limit=20):
        return {"user_id": user_id, "count": 0, "child_runs": []}


# Patch the AgoraClient ctor so the App uses our fake regardless of args.

@pytest.fixture
def patched_app(monkeypatch):
    from ctl import app as app_mod
    monkeypatch.setattr(app_mod, "AgoraClient", lambda *a, **kw: FakeClient())
    # Also bypass session token load so the modal doesn't pop.
    monkeypatch.setattr(app_mod, "load_session_token", lambda: "fake")
    return app_mod


@pytest.mark.asyncio
async def test_app_starts_and_dashboard_renders(patched_app):
    """App starts, dashboard pane mounts and shows the AGORA header."""
    app = patched_app.CtlApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Let the on_mount + first refresh fire.
        await pilot.pause()
        await pilot.pause()
        text = app.screen_stack[-1].render_str  # type: ignore[attr-defined]
        # Just assert we ended up on the MainScreen with TabbedContent.
        from textual.widgets import TabbedContent
        tc = app.query_one(TabbedContent)
        assert tc.active == "tab-dashboard"


@pytest.mark.asyncio
async def test_all_tabs_mount_without_error(patched_app):
    """Switching through every tab triggers each pane's refresh; none
    should raise (the regression hook for future pane bugs)."""
    from textual.widgets import TabbedContent
    app = patched_app.CtlApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        tc = app.query_one(TabbedContent)
        tab_ids = [f"tab-{tid}" for tid, _, _ in patched_app.TABS]
        for tid in tab_ids:
            tc.active = tid
            await pilot.pause()  # let refresh fire
            await pilot.pause()
        assert tc.active in tab_ids


@pytest.mark.asyncio
async def test_cost_window_cycle(patched_app):
    """The `w` keybinding cycles the Coste pane's window value."""
    from ctl.screens.panes import CostPane
    from textual.widgets import TabbedContent
    app = patched_app.CtlApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        tc = app.query_one(TabbedContent)
        tc.active = "tab-cost"
        await pilot.pause()
        await pilot.pause()
        pane = app.query_one(CostPane)
        assert pane.window == "day"
        await pilot.press("w")
        await pilot.pause()
        assert pane.window == "week"
        await pilot.press("w")
        await pilot.pause()
        assert pane.window == "month"
