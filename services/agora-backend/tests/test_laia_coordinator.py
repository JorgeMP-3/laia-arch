"""LAIA coordinator (v0.4 Fase 1).

Covers:
  * seed of ``user_laia`` + AgentArea on backend boot.
  * laia_coordinator toolset isolation (only LAIA gets it).
  * coordinator_messages CRUD + inbox injection into the user prompt.
  * /api/laia/chat admin-only gate.
  * the 8 tool handlers — happy paths and the "not LAIA" refusal.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}


@pytest.fixture(scope="module")
def app_client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def make_user():
    from app.storage import store

    def _make(prefix: str = "u") -> str:
        username = f"{prefix}_{uuid.uuid4().hex[:6]}"
        ts = "2026-01-01T00:00:00+00:00"
        uid = f"user_{username}"
        store.db.conn.execute(
            "INSERT INTO users (id, username, display_name, role, agent_id, token, "
            "password, active, created_at, updated_at) "
            "VALUES (?, ?, ?, 'employee', NULL, ?, NULL, 1, ?, ?)",
            (uid, username, username, f"tok-{username}", ts, ts),
        )
        store.db.conn.commit()
        return uid
    return _make


def _load_laia_plugin():
    """Side-load the laia-coordinator plugin module for unit-level tests."""
    from tests._laia_core import load_plugin_or_skip

    return load_plugin_or_skip(
        "laia-coordinator/__init__.py",
        "laia_coordinator_plugin",
    )


# ── 1. Seed ─────────────────────────────────────────────────────────────────


def test_seed_creates_user_laia_with_agent_area():
    from app.storage import store
    user = store.user_by_id("user_laia")
    assert user is not None
    assert user.username == "laia"
    assert user.role == "agora_admin"
    area = store.agent_area_for_user(user, create=False)
    assert area is not None
    assert area.agent_display_name == "LAIA"
    assert "coordinadora" in area.soul_md.lower()


def test_user_laia_has_no_agent_id_no_container():
    from app.storage import store
    user = store.user_by_id("user_laia")
    assert user is not None
    assert user.agent_id is None
    # The seeded jorge user has an agent record; LAIA must NOT.
    agents = [a for a in store.agents() if a.user_id == "user_laia"]
    assert agents == []


# ── 2. Toolset isolation ────────────────────────────────────────────────────


def test_laia_toolset_split_by_role(monkeypatch):
    """Fase 2 split: regular PA chat gets no laia_coordinator toolsets;
    a LAIA chat for an employee gets only ``_base``; a LAIA chat for an
    admin gets both ``_base`` and ``_admin``.
    """
    from app import agent_pool as ap

    captured: list[dict] = []

    def fake_build(cfg, *, session_metadata, extra_toolsets=None,
                   ephemeral_system_prompt=None):
        captured.append({
            "user_id": session_metadata.get("user_id"),
            "extra_toolsets": list(extra_toolsets or []),
        })
        return ap._PlaceholderAgent(
            llm_config=cfg, session_metadata=session_metadata,
            ephemeral_system_prompt=ephemeral_system_prompt,
        )

    monkeypatch.setattr(ap, "_build_aiagent", fake_build)
    pool = ap.AgentPool()
    cfg = ap.LLMSessionConfig(provider="x", api_key="k", base_url=None,
                              model="m", api_mode=None)
    # 1) Regular PA chat — no laia tools.
    pool.get_or_create("user_jorge", "s-regular", "jorge", cfg)
    # 2) Employee in LAIA chat — only base.
    pool.get_or_create("user_emp", "s-laia-emp", "laia", cfg,
                       mode="laia", actor_role="employee")
    # 3) Admin in LAIA chat — base + admin.
    pool.get_or_create("user_admin", "s-laia-adm", "laia", cfg,
                       mode="laia", actor_role="agora_admin")

    by_user = {c["user_id"]: set(c["extra_toolsets"]) for c in captured}
    assert "laia_coordinator_base" not in by_user["user_jorge"]
    assert "laia_coordinator_admin" not in by_user["user_jorge"]

    assert "laia_coordinator_base" in by_user["user_emp"]
    assert "laia_coordinator_admin" not in by_user["user_emp"]

    assert "laia_coordinator_base" in by_user["user_admin"]
    assert "laia_coordinator_admin" in by_user["user_admin"]


def test_laia_admin_tool_refuses_for_employee_role():
    """An admin-only handler must return ``ok=false`` when the chat
    context is set to an employee role, even if LAIA-chat mode is on.
    """
    mod = _load_laia_plugin()
    mod.set_laia_chat_mode("employee")
    try:
        import json
        out = json.loads(mod._send_message(
            {"user_id": "user_x", "text": "hola"}))
    finally:
        mod.clear_laia_chat_mode()
    assert out["ok"] is False
    assert "admin-only" in out["error"]


def test_laia_base_tool_allowed_for_employee_role(make_user):
    """A base handler must succeed for employee LAIA chat."""
    mod = _load_laia_plugin()
    # Seed a target so list_users has something to return.
    make_user("listed")
    mod.set_laia_chat_mode("employee")
    try:
        import json
        out = json.loads(mod._list_users({}))
    finally:
        mod.clear_laia_chat_mode()
    assert out["ok"] is True
    assert out["count"] >= 1


def test_laia_coordinator_tools_refuse_outside_laia_mode(make_user):
    """No chat mode + non-LAIA user → tools refuse."""
    mod = _load_laia_plugin()
    mod.set_session_context(make_user("nope"))
    try:
        result = mod._list_users({})
    finally:
        mod.clear_session_context()
    import json
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "laia" in parsed["error"].lower()


# ── 3. Inbox + injection ────────────────────────────────────────────────────


def test_send_message_creates_inbox_row(make_user):
    mod = _load_laia_plugin()
    target = make_user("inbox")
    mod.set_session_context("user_laia")
    try:
        import json
        out = json.loads(mod._send_message({"user_id": target, "text": "hola",
                                             "severity": "warn"}))
    finally:
        mod.clear_session_context()
    assert out["ok"] is True
    from app.storage import store
    inbox = store.list_inbox(target, only_unread=True)
    assert len(inbox) == 1
    assert inbox[0].text == "hola"
    assert inbox[0].severity == "warn"


def test_inbox_unread_injected_into_user_prompt(make_user):
    """Build a prompt for a user with unread mail and assert the system
    prompt contains the inbox block. Also assert the messages get marked
    read so the next call doesn't re-inject them."""
    from app.agent_pool import _build_agent_area_prompt
    from app.storage import store

    uid = make_user("inj")
    store.create_coordinator_message(user_id=uid, text="container reiniciado",
                                      severity="warn")
    store.create_coordinator_message(user_id=uid, text="skill X actualizada")
    prompt = _build_agent_area_prompt(uid)
    assert prompt is not None
    assert "Mensajes de LAIA pendientes" in prompt
    assert "container reiniciado" in prompt
    assert store.unread_count_for_user(uid) == 0  # marked read

    # Second call must not re-inject (now empty inbox).
    prompt2 = _build_agent_area_prompt(uid)
    assert prompt2 is None or "Mensajes de LAIA" not in prompt2


# ── 4. Audit / overview / usage handlers ───────────────────────────────────


def test_read_audit_filters_correctly(make_user):
    mod = _load_laia_plugin()
    from app.models import Event, new_id
    from app.storage import store

    uid = make_user("aud")
    for et in ("chat_error", "chat_error", "scheduled_job_run"):
        store.record_event(Event(
            id=new_id("evt"), event_type=et, actor_id=uid, summary="x",
        ))
    mod.set_session_context("user_laia")
    try:
        import json
        out = json.loads(mod._read_audit({"user_id": uid,
                                           "event_type": "chat_error"}))
    finally:
        mod.clear_session_context()
    assert out["ok"] is True
    assert out["count"] == 2
    assert all(e["event_type"] == "chat_error" for e in out["events"])


def test_user_overview_aggregates(make_user):
    mod = _load_laia_plugin()
    from app.storage import store
    uid = make_user("ovr")
    store.create_learning(user_id=uid, kind="insight", title="t",
                          content_md="c", tags=None)
    store.record_usage(user_id=uid, provider="anthropic",
                       model="claude-haiku-4-5",
                       tokens_input=10, tokens_output=5, cost_usd=0.0001)
    mod.set_session_context("user_laia")
    try:
        import json
        out = json.loads(mod._user_overview({"user_id": uid}))
    finally:
        mod.clear_session_context()
    assert out["ok"] is True
    assert out["learnings_count"] >= 1
    assert out["usage_7d"]["calls"] >= 1
    assert out["user"]["id"] == uid


def test_alert_admin_emits_event():
    mod = _load_laia_plugin()
    from app.storage import store
    mod.set_session_context("user_laia")
    try:
        import json
        out = json.loads(mod._alert_admin({"summary": "test alert",
                                            "severity": "warn"}))
    finally:
        mod.clear_session_context()
    assert out["ok"] is True
    # The event should exist.
    row = store.db.conn.execute(
        "SELECT * FROM events WHERE id = ?", (out["event_id"],),
    ).fetchone()
    assert row is not None
    assert row["event_type"] == "laia_alert"


def test_list_users_excludes_laia(make_user):
    mod = _load_laia_plugin()
    make_user("vis")
    mod.set_session_context("user_laia")
    try:
        import json
        out = json.loads(mod._list_users({}))
    finally:
        mod.clear_session_context()
    assert out["ok"] is True
    ids = {u["id"] for u in out["users"]}
    assert "user_laia" not in ids


# ── 5. Endpoint admin-only ──────────────────────────────────────────────────


def test_laia_inbox_count_requires_admin(app_client):
    r = app_client.get("/api/laia/inbox-count")
    assert r.status_code in (401, 403)


def test_laia_inbox_count_admin_ok(app_client, make_user):
    from app.storage import store
    uid = make_user("incnt")
    store.create_coordinator_message(user_id=uid, text="hola")
    r = app_client.get("/api/laia/inbox-count", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert any(row["user_id"] == uid and row["unread"] >= 1
               for row in body["unread_by_user"])


def test_laia_chat_endpoint_employee_uses_base_toolset(app_client, make_user,
                                                       monkeypatch):
    """Fase 2: employees can chat with LAIA and get ONLY base tools.

    We stub ``_build_aiagent`` to capture what toolsets the pool requested,
    so we don't have to spin up a real AIAgent / LLM.
    """
    from app import agent_pool as ap

    captured: list[dict] = []

    def fake_build(cfg, *, session_metadata, extra_toolsets=None,
                   ephemeral_system_prompt=None):
        captured.append({
            "user_id": session_metadata.get("user_id"),
            "extra_toolsets": list(extra_toolsets or []),
        })

        class _Stub:
            stream_delta_callback = None
            tool_start_callback = None
            tool_complete_callback = None
            def run_conversation(self, message):
                return {"response": "ok", "iterations": 0}
        return _Stub()

    monkeypatch.setattr(ap, "_build_aiagent", fake_build)

    uid = make_user("emp")
    from app.storage import store
    user = store.user_by_id(uid)
    assert user is not None
    r = app_client.post(
        "/api/laia/chat",
        headers={"Authorization": f"Bearer {user.token}"},
        json={"message": "hola laia"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert "\"type\": \"done\"" in body
    # The pool was asked to build an AIAgent for THIS employee with only base.
    emp_calls = [c for c in captured if c["user_id"] == uid]
    assert emp_calls, f"expected a build for employee {uid}, got {captured}"
    tools = set(emp_calls[-1]["extra_toolsets"])
    assert "laia_coordinator_base" in tools
    assert "laia_coordinator_admin" not in tools


def test_laia_chat_endpoint_admin_streams(app_client, monkeypatch):
    """Admin actor sigue funcionando contra el camino completo. Mockeamos
    el worker para no construir un AIAgent real ni tocar la red — solo
    verificamos que el endpoint acepta el admin y devuelve un SSE.
    """
    # Stub the AIAgent build so the test doesn't need .laia-core PYTHONPATH.
    from app import agent_pool as ap

    class _Stub:
        stream_delta_callback = None
        tool_start_callback = None
        tool_complete_callback = None
        def run_conversation(self, message):
            # Echo so the response body is deterministic.
            if self.stream_delta_callback:
                self.stream_delta_callback("ok")
            return {"response": "ok", "iterations": 1}

    def fake_build(cfg, *, session_metadata, extra_toolsets=None,
                   ephemeral_system_prompt=None):
        return _Stub()

    monkeypatch.setattr(ap, "_build_aiagent", fake_build)

    r = app_client.post(
        "/api/laia/chat",
        headers=ADMIN_HEADERS,
        json={"message": "status"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert "\"type\": \"token\"" in body
    assert "\"type\": \"done\"" in body
