"""Tests for observability (Fase 5): health, metrics, logging middleware."""

from fastapi.testclient import TestClient

from app.main import app

ADMIN_TOKEN = "dev-admin-token"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

client = TestClient(app)


def test_health_complete():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["service"] == "agora-backend"
    assert "version" in data
    assert data["db"] == "sqlite"
    assert isinstance(data["coordinator"], bool)
    assert "lxd_available" in data
    assert "laiactl_available" in data


def test_metrics_requires_admin():
    r = client.get("/api/metrics")
    assert r.status_code == 401


def test_metrics_ok():
    r = client.get("/api/metrics", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "uptime_seconds" in data
    assert "requests_total" in data
    assert "avg_duration_ms" in data
    assert isinstance(data["requests_total"], int)


def test_request_id_header():
    r = client.get("/api/health", headers={"X-Request-ID": "my-test-id"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "my-test-id"


def test_request_id_generated():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
