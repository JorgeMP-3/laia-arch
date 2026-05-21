from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.storage import store


client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}


def _create_user(username: str = "areauser", password: str = "pw1234") -> dict:
    r = client.post(
        "/api/users",
        headers=ADMIN_HEADERS,
        json={
            "username": username,
            "display_name": "Area User",
            "role": "employee",
            "password": password,
        },
    )
    assert r.status_code in (201, 409), r.text
    if r.status_code == 409:
        users = client.get("/api/users", headers=ADMIN_HEADERS).json()["users"]
        return next(u for u in users if u["username"] == username)
    return r.json()["user"]


def _login(username: str = "areauser", password: str = "pw1234") -> dict[str, str]:
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_agent_area_created_on_first_read():
    user = _create_user("areaone")
    headers = _login("areaone")

    r = client.get("/api/me/agent-area", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == user["id"]
    assert body["area"]["agent_display_name"] == "Area User"
    assert body["area"]["soul_md"] == ""
    assert body["plugins"] == []
    assert body["skills"] == []


def test_patch_my_agent_area_updates_agora_owned_profile_and_invalidates_pool(monkeypatch):
    _create_user("areapatch")
    headers = _login("areapatch")
    calls: list[str] = []

    from app.agent_pool import AgentPool
    monkeypatch.setattr(AgentPool, "invalidate_user_static", staticmethod(lambda user_id: calls.append(user_id) or 1))

    r = client.patch(
        "/api/me/agent-area",
        headers=headers,
        json={
            "agent_display_name": "Nombrix",
            "soul_md": "# Soul\nSoy Nombrix.",
            "instructions_md": "Responde en castellano.",
            "memory_preferences": {"private_mode": "executor-private"},
            "behavior_preferences": {"tone": "directo"},
        },
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["area"]["agent_display_name"] == "Nombrix"
    assert body["area"]["soul_md"] == "# Soul\nSoy Nombrix."
    assert calls == [body["user"]["id"]]


def test_agent_profile_compatibility_uses_agent_area():
    _create_user("areaprofile")
    headers = _login("areaprofile")
    r = client.patch(
        "/api/agent/profile",
        headers=headers,
        json={"persona": "persona nueva", "instructions": "hazlo claro", "preferences": {"tone": "calm"}},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["persona"] == "persona nueva"
    assert body["instructions"] == "hazlo claro"
    assert body["preferences"]["tone"] == "calm"

    area = client.get("/api/me/agent-area", headers=headers).json()["area"]
    assert area["soul_md"] == "persona nueva"
    assert area["instructions_md"] == "hazlo claro"


def test_admin_can_patch_user_agent_area():
    user = _create_user("areaadmin")

    r = client.patch(
        f"/api/admin/users/{user['id']}/agent-area",
        headers=ADMIN_HEADERS,
        json={"soul_md": "admin soul"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["area"]["soul_md"] == "admin soul"


def test_soul_md_too_long_is_rejected():
    """A.1 — clients can't push multi-MB markdown into soul_md / instructions_md."""
    _create_user("areabig")
    headers = _login("areabig")
    big = "x" * 60_000

    r = client.patch("/api/me/agent-area", headers=headers, json={"soul_md": big})
    assert r.status_code == 422, r.text

    r = client.patch("/api/me/agent-area", headers=headers, json={"instructions_md": big})
    assert r.status_code == 422, r.text


def test_get_auto_creates_default_area_for_fresh_user():
    """A.2 — a brand new user that hits GET first (never PATCHed) gets a default
    area, not a 404. The seed admin (jorge) is also covered by this path."""
    user = _create_user("areafresh")
    headers = _login("areafresh")

    r = client.get("/api/me/agent-area", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == user["id"]
    # Defaults: display name from the user, empty soul/instructions, empty prefs.
    assert body["area"]["soul_md"] == ""
    assert body["area"]["instructions_md"] == ""
    assert body["area"]["memory_preferences"] == {}
    assert body["area"]["behavior_preferences"] == {}


def test_seed_admin_can_get_agent_area_without_404():
    """A.2 — the seed admin user 'jorge' must be able to read its area on first
    boot. Even though storage seeds the user/agent rows, no agent_area row is
    pre-created — the GET handler auto-creates it via agent_area_for_user(create=True)."""
    r = client.post("/api/login", json={"username": "jorge", "password": "dev-admin"})
    # Login may be disabled if a previous test rotated the password — in that
    # case fall back to the static seed token (also persisted on the user row).
    if r.status_code != 200:
        admin_headers = ADMIN_HEADERS
    else:
        admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get("/api/me/agent-area", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["username"] == "jorge"


def test_user_cannot_patch_other_users_agent_area():
    """A.4 — admin-only endpoint must reject regular employees."""
    user_other = _create_user("areavictim")
    _create_user("areaattacker")
    attacker_h = _login("areaattacker")

    r = client.patch(
        f"/api/admin/users/{user_other['id']}/agent-area",
        headers=attacker_h,
        json={"soul_md": "pwned"},
    )
    assert r.status_code in (401, 403), r.text


def test_malformed_json_in_db_returns_empty_prefs():
    """A.4 — defensive read: a corrupt memory/behavior preferences JSON in DB
    must not crash the GET; the helper coerces to {}."""
    user = _create_user("areacorrupt")
    headers = _login("areacorrupt")

    # Force a corrupt row directly into the DB.
    store.db.conn.execute(
        "INSERT OR REPLACE INTO agent_areas "
        "(user_id, agent_display_name, soul_md, instructions_md, "
        "memory_preferences_json, behavior_preferences_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user["id"], "Corrupt", "", "", "NOT-JSON", "ALSO-NOT-JSON",
         "2026-01-01", "2026-01-01"),
    )
    store.db.conn.commit()

    r = client.get("/api/me/agent-area", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["area"]["memory_preferences"] == {}
    assert body["area"]["behavior_preferences"] == {}


def test_register_agent_uses_agent_prefix_and_reregisters_legacy():
    user = _create_user("areareg")
    legacy = store.agents()[0].model_copy(update={
        "id": "agent_legacy_areareg",
        "user_id": user["id"],
        "container_name": "laia-areareg",
        "container_ip": "10.0.0.2",
        "api_token": "old-token",
    })
    store.save_agent(legacy)
    db_user = store.user_by_id(user["id"])
    db_user.agent_id = legacy.id
    store.save_user(db_user)

    r = client.post(
        "/api/agents/register",
        headers=ADMIN_HEADERS,
        json={
            "slug": "areareg",
            "user_id": user["id"],
            "container_ip": "10.0.0.3",
            "api_token": "new-token",
            "api_port": 9091,
        },
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["updated"] is True
    assert body["agent"]["container_name"] == "agent-areareg"
    assert body["agent"]["api_token"] == "new-token"
