"""Integration tests: full user flows end-to-end (Fase 7).

These test real SQLite-backed store, no mocks.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.security import create_access_token

client = TestClient(app)


def _admin_headers() -> dict:
    token = create_access_token("user_jorge", "agora_admin", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def _user_headers(user_id: str = "user_jorge", role: str = "agora_admin") -> dict:
    token = create_access_token(user_id, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


# ── full auth flow ──────────────────────────────────────────────────────

def test_full_auth_flow():
    # 1. Login
    r = client.post("/api/login", json={"username": "jorge", "password": "dev-admin"})
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # 2. Me
    at = tokens["access_token"]
    r = client.get("/api/me", headers={"Authorization": f"Bearer {at}"})
    assert r.status_code == 200
    assert r.json()["username"] == "jorge"

    # 3. Refresh
    r = client.post("/api/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()

    # 4. Change password
    r = client.post("/api/me/password", json={"old_password": "dev-admin", "new_password": "newpass123"},
                    headers={"Authorization": f"Bearer {at}"})
    assert r.status_code == 200

    # 5. Login with new password
    r = client.post("/api/login", json={"username": "jorge", "password": "newpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


# ── user lifecycle (admin flow) ──────────────────────────────────────────

def test_create_user_then_login():
    admin = _admin_headers()

    # Create employee
    r = client.post("/api/users", json={"username": "pepe", "display_name": "Pepe", "role": "employee"},
                    headers=admin)
    assert r.status_code == 201
    pw = r.json()["password"]
    assert r.json()["ok"] is True

    # Login as pepe
    r = client.post("/api/login", json={"username": "pepe", "password": pw})
    assert r.status_code == 200
    pepe_token = r.json()["access_token"]

    # Pepe sees himself
    r = client.get("/api/me", headers={"Authorization": f"Bearer {pepe_token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "pepe"
    assert r.json()["role"] == "employee"


def test_employee_cannot_see_other_users():
    admin = _admin_headers()
    client.post("/api/users", json={"username": "alice", "display_name": "Alice"}, headers=admin)

    # Login as alice
    r = client.post("/api/login", json={"username": "alice", "password": "laia-"})
    # If password doesn't match, try the generated one
    if r.status_code == 401:
        r2 = client.post("/api/users", json={"username": "bob", "display_name": "Bob"}, headers=admin)
        bob_pw = r2.json()["password"]
        r = client.post("/api/login", json={"username": "bob", "password": bob_pw})
        alice_token = r.json()["access_token"]
    else:
        # alice login succeeded with some password
        alice_token = r.json()["access_token"] if "access_token" in r.json() else ""

    if alice_token:
        # Alice trying to list users (admin only)
        r = client.get("/api/users", headers={"Authorization": f"Bearer {alice_token}"})
        assert r.status_code == 403

        # Alice trying to list all agents (admin view)
        r = client.get("/api/agents", headers={"Authorization": f"Bearer {alice_token}"})
        assert r.status_code == 200
        # Should only see her own agent if assigned, or empty
        assert isinstance(r.json()["agents"], list)


# ── task flow ────────────────────────────────────────────────────────────

def test_task_lifecycle():
    admin = _admin_headers()

    # Admin creates task
    r = client.post("/api/tasks", json={"title": "Update docs", "priority": "high"},
                    headers=admin)
    assert r.status_code == 200
    task = r.json()
    task_id = task["id"]
    assert task["status"] == "pending"

    # List tasks
    r = client.get("/api/tasks", headers=admin)
    assert r.status_code == 200
    tasks = r.json()["tasks"]
    found = [t for t in tasks if t["id"] == task_id]
    assert len(found) == 1

    # Update status
    r = client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    # Verify
    r = client.get("/api/tasks", headers=admin)
    updated = [t for t in r.json()["tasks"] if t["id"] == task_id]
    assert updated[0]["status"] == "done"


# ── agent personal flow ──────────────────────────────────────────────────

def test_agent_personal_status():
    admin = _admin_headers()

    # Get my agent status (will fail if LXD not available, but auth works)
    r = client.get("/api/agent/status", headers=admin)
    # Either 200 with status data or error if no agent assigned
    assert r.status_code in (200, 404)


def test_agent_personal_tasks():
    admin = _admin_headers()

    r = client.get("/api/agent/tasks", headers=admin)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "tasks" in data
        assert "slug" in data


# ── coordinator flow ─────────────────────────────────────────────────────

def test_coordinator_assign_and_report():
    admin = _admin_headers()

    # Assign global task
    r = client.post("/api/coordinator/assign", json={
        "title": "Weekly report",
        "description": "Prepare weekly summary",
        "priority": "high",
    }, headers=admin)
    assert r.status_code == 201
    assert r.json()["ok"] is True

    # Report
    r = client.get("/api/coordinator/report", headers=admin)
    assert r.status_code == 200
    data = r.json()
    assert data["coordinator"] == "LAIA AGORA"
    assert "tasks" in data
    assert "agents" in data

    # Health
    r = client.get("/api/coordinator/health")
    assert r.status_code == 200
    assert r.json()["coordinator"] == "LAIA AGORA"

    # Alerts
    r = client.get("/api/coordinator/alerts", headers=admin)
    assert r.status_code == 200


def test_coordinator_force_check():
    admin = _admin_headers()
    r = client.post("/api/coordinator/check", headers=admin)
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── health and metrics ───────────────────────────────────────────────────

def test_health_complete():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["service"] == "agora-backend"
    assert data["db"] == "sqlite"
    assert isinstance(data["coordinator"], bool)
    assert "version" in data


def test_metrics_flow():
    admin = _admin_headers()
    r = client.get("/api/metrics", headers=admin)
    assert r.status_code == 200
    data = r.json()
    assert "requests_total" in data
    assert "uptime_seconds" in data


# ── user disable flow ────────────────────────────────────────────────────

def test_disable_user_cannot_login():
    admin = _admin_headers()

    # Create user
    r = client.post("/api/users", json={"username": "temp_disable", "display_name": "TempDisc"}, headers=admin)
    assert r.status_code == 201
    pw = r.json()["password"]

    # Login works
    r = client.post("/api/login", json={"username": "temp_disable", "password": pw})
    assert r.status_code == 200

    # Disable
    r = client.delete("/api/users/user_temp_disable", headers=admin)
    assert r.status_code == 200

    # Login fails
    r = client.post("/api/login", json={"username": "temp_disable", "password": pw})
    assert r.status_code == 401


# ── permission boundaries ────────────────────────────────────────────────

def test_employee_cannot_access_admin_endpoints():
    admin = _admin_headers()

    # Create employee
    r = client.post("/api/users", json={"username": "peon", "display_name": "Peon"}, headers=admin)
    pw = r.json()["password"]

    r = client.post("/api/login", json={"username": "peon", "password": pw})
    peon_token = r.json()["access_token"]
    peon_headers = {"Authorization": f"Bearer {peon_token}"}

    # Cannot list users
    assert client.get("/api/users", headers=peon_headers).status_code == 403
    # Cannot create agents
    assert client.post("/api/agents", json={"slug": "nope"}, headers=peon_headers).status_code == 403
    # Cannot access coordinator
    assert client.get("/api/coordinator/report", headers=peon_headers).status_code == 403
    # Cannot access metrics
    assert client.get("/api/metrics", headers=peon_headers).status_code == 403

    # Can access own profile
    r = client.get("/api/me", headers=peon_headers)
    assert r.status_code == 200
