"""Tests for user CRUD endpoints (Fase 3)."""

from fastapi.testclient import TestClient

from app.main import app

ADMIN_TOKEN = "dev-admin-token"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

client = TestClient(app)


# ── list users ─────────────────────────────────────────────────────────────

def test_list_users_ok():
    r = client.get("/api/users", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["users"], list)
    assert len(data["users"]) >= 1


def test_list_users_requires_admin():
    r = client.get("/api/users")
    assert r.status_code == 401


# ── create user ────────────────────────────────────────────────────────────

def test_create_user_ok():
    r = client.post("/api/users", headers=HEADERS, json={
        "username": "maria",
        "display_name": "Maria",
        "role": "employee",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["ok"] is True
    assert data["user"]["username"] == "maria"
    assert data["user"]["role"] == "employee"
    assert data["user"]["active"] is True
    assert data["password"] is not None  # auto-generated


def test_create_user_with_password():
    r = client.post("/api/users", headers=HEADERS, json={
        "username": "carlos",
        "display_name": "Carlos",
        "password": "carlos1234",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["user"]["username"] == "carlos"
    assert data["password"] is None  # not returned if set manually


def test_create_user_duplicate():
    client.post("/api/users", headers=HEADERS, json={
        "username": "maria", "display_name": "Maria",
    })
    r = client.post("/api/users", headers=HEADERS, json={
        "username": "maria", "display_name": "Maria Otra",
    })
    assert r.status_code == 409


def test_create_user_invalid_username():
    r = client.post("/api/users", headers=HEADERS, json={
        "username": "UPPER CASE!",
        "display_name": "Bad",
    })
    assert r.status_code == 422


def test_create_user_hyphen_username_accepted():
    """john-doe / chat-redesign-test / user_with-mix are all valid Linux-style usernames."""
    for name in ("john-doe", "chat-redesign-test", "user_with-mix"):
        r = client.post("/api/users", headers=HEADERS, json={
            "username": name,
            "display_name": name.title(),
        })
        assert r.status_code == 201, f"{name}: {r.text}"


def test_create_user_username_edge_cases_rejected():
    """Hyphens at the boundaries or stand-alone are not accepted."""
    for name in ("-bad", "bad-", "-", "a-"):
        r = client.post("/api/users", headers=HEADERS, json={
            "username": name,
            "display_name": "x",
        })
        assert r.status_code == 422, f"{name} should have failed but got {r.status_code}"


def test_create_user_with_agent():
    r = client.post("/api/users", headers=HEADERS, json={
        "username": "ana",
        "display_name": "Ana",
        "create_agent": True,
    })
    assert r.status_code == 201
    assert r.json()["user"]["agent_id"] == "agent_ana"


# ── get user ───────────────────────────────────────────────────────────────

def test_get_user_ok():
    r = client.get("/api/users/user_jorge", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "jorge"


def test_get_user_not_found():
    r = client.get("/api/users/user_noexiste", headers=HEADERS)
    assert r.status_code == 404


# ── update user ────────────────────────────────────────────────────────────

def test_update_user_display_name():
    r = client.patch("/api/users/user_jorge", headers=HEADERS, json={
        "display_name": "Jorge Admin",
    })
    assert r.status_code == 200
    assert r.json()["display_name"] == "Jorge Admin"


def test_update_user_empty():
    r = client.patch("/api/users/user_jorge", headers=HEADERS, json={})
    assert r.status_code == 200


# ── delete (disable) user ──────────────────────────────────────────────────

def test_disable_user():
    r = client.delete("/api/users/user_jorge", headers=HEADERS)
    assert r.status_code == 400  # cannot delete yourself


def test_disable_other_user():
    client.post("/api/users", headers=HEADERS, json={
        "username": "temp_user", "display_name": "Temp",
    })
    r = client.delete("/api/users/user_temp_user", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── reset password ─────────────────────────────────────────────────────────

def test_reset_password():
    r = client.post("/api/users/user_jorge/reset-password", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["new_password"].startswith("laia-")


# ── auth guard ─────────────────────────────────────────────────────────────

def test_user_endpoints_require_admin():
    for method, path, body in [
        ("post", "/api/users", {"username": "x", "display_name": "x"}),
        ("get", "/api/users/user_jorge", None),
        ("patch", "/api/users/user_jorge", {}),
        ("delete", "/api/users/user_jorge", None),
        ("post", "/api/users/user_jorge/reset-password", None),
    ]:
        fn = getattr(client, method)
        kwargs = {"json": body} if body is not None else {}
        r = fn(path, **kwargs)
        assert r.status_code == 401, f"{method.upper()} {path} should require auth"
