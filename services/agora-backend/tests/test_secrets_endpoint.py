"""Tests for POST /api/agents/{slug}/secrets — bootstrap token → LLM API key."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import store

ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}
client = TestClient(app)


def _create_user_and_register_agent(slug: str, ip: str, token: str) -> str:
    """Create an employee + register an agent. Returns the user_id."""
    r = client.post(
        "/api/users",
        json={"username": slug, "display_name": slug.title(), "role": "employee", "password": "test1234"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code in (200, 201), r.text
    uid = r.json()["user"]["id"]

    r = client.post(
        "/api/agents/register",
        json={"slug": slug, "user_id": uid, "container_ip": ip, "api_token": token},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201, r.text
    return uid


# ── happy path ───────────────────────────────────────────────────────────────


def test_secrets_returns_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-12345")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _create_user_and_register_agent("secretsor", "10.0.0.10", "boot-token-or-12345")
    r = client.post(
        "/api/agents/secretsor/secrets",
        json={"bootstrap_token": "boot-token-or-12345"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_api_key"] == "sk-or-12345"
    assert body["llm_provider"] == "openrouter"


def test_secrets_falls_back_to_anthropic_when_openrouter_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fallback")
    _create_user_and_register_agent("secretsant", "10.0.0.11", "boot-token-ant-12345")
    r = client.post(
        "/api/agents/secretsant/secrets",
        json={"bootstrap_token": "boot-token-ant-12345"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["llm_provider"] == "anthropic"


# ── auth failures ────────────────────────────────────────────────────────────


def test_secrets_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    _create_user_and_register_agent("secretsbad", "10.0.0.12", "real-token-xyz-12345")
    r = client.post(
        "/api/agents/secretsbad/secrets",
        json={"bootstrap_token": "wrong-token-12345"},
    )
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


def test_secrets_rejects_unknown_agent(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    r = client.post(
        "/api/agents/ghostxyz/secrets",
        json={"bootstrap_token": "any-token-here-12345"},
    )
    # Same response as bad token (don't leak existence)
    assert r.status_code == 401


def test_secrets_400_on_invalid_slug():
    r = client.post(
        "/api/agents/INVALID-SLUG/secrets",
        json={"bootstrap_token": "tk-tk-tk-tk-12345"},
    )
    assert r.status_code == 400


# ── no key configured ────────────────────────────────────────────────────────


def test_secrets_503_when_no_llm_key_on_host(monkeypatch):
    for env_var in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    _create_user_and_register_agent("secretsnokey", "10.0.0.13", "boot-nokey-12345")
    r = client.post(
        "/api/agents/secretsnokey/secrets",
        json={"bootstrap_token": "boot-nokey-12345"},
    )
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


# ── audit ─────────────────────────────────────────────────────────────────────


def test_secrets_logs_audit_event(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-audit")
    _create_user_and_register_agent("secretsaudit", "10.0.0.14", "boot-audit-12345")
    before = len(store.events())
    client.post(
        "/api/agents/secretsaudit/secrets",
        json={"bootstrap_token": "boot-audit-12345"},
    )
    after = store.events()
    assert len(after) > before
    audit = [e for e in after if e.event_type == "agent_secret_fetched"]
    assert audit, "must emit agent_secret_fetched event"
    assert audit[-1].summary == "secretsaudit"
