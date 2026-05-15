"""Tests for fetch_llm_secret_from_agora — sync HTTP call to AGORA /secrets."""
from __future__ import annotations

import httpx
import pytest

from laia_agent.agent_wrapper import fetch_llm_secret_from_agora


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _patch_httpx(monkeypatch, handler):
    """Monkeypatch httpx.post to use a MockTransport."""
    real_client = httpx.Client

    def fake_post(url, json=None, timeout=None):
        with httpx.Client(transport=_mock_transport(handler), timeout=timeout) as c:
            return c.post(url, json=json)

    monkeypatch.setattr("laia_agent.agent_wrapper.httpx.post", fake_post)


def test_returns_key_and_provider(monkeypatch):
    def handler(req):
        assert req.url.path == "/api/agents/nombrix/secrets"
        assert b"tk-1234" in req.content
        return httpx.Response(
            200, json={"llm_api_key": "sk-or-xyz", "llm_provider": "openrouter"}
        )

    _patch_httpx(monkeypatch, handler)
    key, provider = fetch_llm_secret_from_agora(
        "nombrix", "tk-1234", agora_url="http://test.local:8088"
    )
    assert key == "sk-or-xyz"
    assert provider == "openrouter"


def test_raises_on_401(monkeypatch):
    def handler(req):
        return httpx.Response(401, json={"detail": "invalid bootstrap token"})

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="401"):
        fetch_llm_secret_from_agora("ghost", "bad-token", agora_url="http://test.local")


def test_raises_on_connection_error(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("no route")

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="failed to reach AGORA"):
        fetch_llm_secret_from_agora("nombrix", "tk", agora_url="http://test.local")


def test_raises_on_empty_key(monkeypatch):
    def handler(req):
        return httpx.Response(200, json={"llm_api_key": "", "llm_provider": "openrouter"})

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="missing llm_api_key"):
        fetch_llm_secret_from_agora("nombrix", "tk", agora_url="http://test.local")


def test_uses_env_var_when_url_not_passed(monkeypatch):
    monkeypatch.setenv("AGORA_BACKEND_URL", "http://agora.from.env:8088")

    seen_url = []

    def handler(req):
        seen_url.append(str(req.url))
        return httpx.Response(
            200, json={"llm_api_key": "k", "llm_provider": "openrouter"}
        )

    _patch_httpx(monkeypatch, handler)
    fetch_llm_secret_from_agora("nombrix", "tk")
    assert "agora.from.env" in seen_url[0]
