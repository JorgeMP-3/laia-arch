"""End-to-end chat flow — forwarder plugin ↔ real laia-executor over HTTP.

This is the integration test the redesign plan asks for in Fase 10. It does
NOT exercise the LLM (that requires real credentials and a real provider).
What it DOES exercise:

- The :mod:`agora-executor-forwarder` plugin (loaded from disk, no stubs)
  invoking ``httpx.post`` against the real :mod:`laia_executor` FastAPI app.
- The executor's tool registry actually dispatching ``read_file``,
  ``write_file``, ``bash`` and ``private_workspace_*`` like it would in
  production.
- The full ``pre_tool_call`` directive contract — ``{"action": "replace",
  "message": <str>}`` — so the AIAgent loop would feed the result back into
  the LLM unchanged.

Everything is in-process: we patch the plugin's ``httpx.post`` to a sync
client backed by ``httpx.ASGITransport`` so requests skip the network and
land directly on the executor ASGI app. AgentPool is built and used with a
placeholder AIAgent — that path was already covered in test_agent_pool.py,
here we only show that the surrounding lifecycle (configure_session +
clear_session + LLM config plumbing) wires up cleanly.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import httpx
import pytest


# ---------------------------------------------------------------------------
# Path hacks — the executor and the forwarder live outside the agora-backend
# package, so we add their roots before importing.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXECUTOR_SRC = _REPO_ROOT / "services" / "laia-executor" / "src"
_FORWARDER_DIR = _REPO_ROOT / ".laia-core" / "plugins" / "agora-executor-forwarder"
_WORKSPACE_STORE_ROOT = _REPO_ROOT

for path in (str(_EXECUTOR_SRC), str(_REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load_forwarder():
    """Import the forwarder plugin by file path — no install required."""
    if "agora_executor_forwarder" in sys.modules:
        return sys.modules["agora_executor_forwarder"]
    spec = importlib.util.spec_from_file_location(
        "agora_executor_forwarder", _FORWARDER_DIR / "__init__.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["agora_executor_forwarder"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def executor_app(tmp_path, monkeypatch):
    """A live laia-executor ASGI app pointed at an isolated workspace root."""
    monkeypatch.setenv("LAIA_EXECUTOR_TOKEN", "e2e-token")
    monkeypatch.setenv("LAIA_EXECUTOR_SLUG", "e2e-jorge")
    monkeypatch.setenv("LAIA_EXECUTOR_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("LAIA_WORKSPACE_STORE_PATH", str(_WORKSPACE_STORE_ROOT))

    from laia_executor.api import build_app
    from laia_executor.config import ExecutorConfig
    from laia_executor.tools.registry import default_registry
    from laia_executor.tools import private_workspace

    # Force the private_workspace cache to forget any previous tmp dir.
    private_workspace._reset_cache_for_tests()

    cfg = ExecutorConfig.load()
    return build_app(cfg, default_registry), cfg


@pytest.fixture
def patched_forwarder_httpx(executor_app, monkeypatch):
    """Make the forwarder's ``httpx.post`` route into the executor ASGI app.

    The plugin code calls ``httpx.post(url, json=..., headers=..., timeout=
    ...)`` — synchronous. ``httpx.ASGITransport`` only supports the async
    client, so we route through Starlette's :class:`TestClient` instead
    (sync wrapper over the same ASGI app, accepts the same kwargs).
    """
    from fastapi.testclient import TestClient

    app, cfg = executor_app
    plug = _load_forwarder()

    client = TestClient(app)

    def _fake_post(url, json=None, headers=None, timeout=None):
        from urllib.parse import urlparse
        path = urlparse(url).path or "/"
        # TestClient.post forwards kwargs to httpx; timeout is accepted.
        return client.post(path, json=json, headers=headers, timeout=timeout)

    monkeypatch.setattr(plug.httpx, "post", _fake_post)
    yield plug, cfg


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_write_file_flows_to_real_executor(patched_forwarder_httpx, tmp_path):
    plug, cfg = patched_forwarder_httpx

    target = tmp_path / "hello.py"
    plug.configure_session(
        agent_slug="jorge",
        container_ip="10.0.0.5",
        api_token=cfg.token,
        port=9091,
        timeout_seconds=5.0,
    )
    try:
        directive = plug._on_pre_tool_call(
            "write_file",
            {"path": str(target), "content": "print('hola')"},
            tool_call_id="e2e-1",
        )
    finally:
        plug.clear_session()

    assert directive is not None
    assert directive["action"] == "replace"
    # The executor's write_file returns "OK: wrote N chars to <path>"
    assert "OK" in directive["message"]
    assert target.read_text() == "print('hola')"


def test_read_then_write_round_trip(patched_forwarder_httpx, tmp_path):
    plug, cfg = patched_forwarder_httpx
    target = tmp_path / "rw.txt"
    target.write_text("inicial")

    plug.configure_session(
        agent_slug="jorge",
        container_ip="10.0.0.5",
        api_token=cfg.token,
    )
    try:
        read_directive = plug._on_pre_tool_call(
            "read_file", {"path": str(target)}, tool_call_id="r1",
        )
        write_directive = plug._on_pre_tool_call(
            "write_file", {"path": str(target), "content": "actualizado"},
            tool_call_id="w1",
        )
    finally:
        plug.clear_session()

    assert "inicial" in read_directive["message"]
    assert "OK" in write_directive["message"]
    assert target.read_text() == "actualizado"


def test_bash_command_executes_remotely(patched_forwarder_httpx, tmp_path):
    plug, cfg = patched_forwarder_httpx

    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5", api_token=cfg.token,
    )
    try:
        directive = plug._on_pre_tool_call(
            "bash", {"command": "echo hola-mundo"}, tool_call_id="b1",
        )
    finally:
        plug.clear_session()

    assert "hola-mundo" in directive["message"]


def test_private_workspace_search_flows_to_executor(patched_forwarder_httpx):
    """Add a private node via the executor, then search for it through the forwarder."""
    plug, cfg = patched_forwarder_httpx

    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5", api_token=cfg.token,
    )
    try:
        add = plug._on_pre_tool_call(
            "private_workspace_add_node",
            {
                "slug": "e2e-note",
                "title": "Nota E2E",
                "kind": "doc",
                "body": "contenido del test e2e con palabras clave únicas",
            },
            tool_call_id="pw-add",
        )
        search = plug._on_pre_tool_call(
            "private_workspace_search",
            {"query": "únicas", "limit": 5},
            tool_call_id="pw-search",
        )
    finally:
        plug.clear_session()

    add_body = json.loads(add["message"])
    assert add_body["ok"] is True
    assert add_body["node"]["slug"] == "e2e-note"

    search_body = json.loads(search["message"])
    assert search_body["ok"] is True
    slugs = [n["slug"] for n in search_body["results"]]
    assert "e2e-note" in slugs


def test_invalid_token_returns_replace_with_error(patched_forwarder_httpx):
    """Wrong bearer token surfaces as an ``ok: false`` replace directive."""
    plug, cfg = patched_forwarder_httpx

    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5", api_token="wrong-token",
    )
    try:
        directive = plug._on_pre_tool_call(
            "read_file", {"path": "/tmp/anything"}, tool_call_id="bad",
        )
    finally:
        plug.clear_session()

    # The executor returns 403 → forwarder wraps as {"ok": false, "error": "executor returned 403: ..."}
    body = json.loads(directive["message"])
    assert body["ok"] is False
    assert "403" in body["error"]


def test_no_session_context_falls_back_to_local(patched_forwarder_httpx):
    """If AGORA forgets to call configure_session, the hook is inert (returns None)."""
    plug, _cfg = patched_forwarder_httpx
    plug.clear_session()
    assert plug._on_pre_tool_call("read_file", {"path": "/tmp/x"}) is None


# ---------------------------------------------------------------------------
# AgentPool + LLM config plumbing
# ---------------------------------------------------------------------------


def test_agent_pool_threads_user_llm_config_to_aiagent(monkeypatch):
    """End-to-end: pool stores per-user LLM config; reused on lookup.

    When ``.laia-core`` is on PYTHONPATH the real AIAgent constructor
    inspects the user's environment for ``DEEPSEEK_API_KEY``; without it
    set, construction raises (correct behavior). The pool's contract is to
    *store* and *return* the cached AgentSession with the LLM config —
    that's what we check here. We patch out the AIAgent build so the test
    runs in both modes (with or without .laia-core deps).
    """
    from app.agent_pool import AgentPool, LLMSessionConfig
    import app.agent_pool as _pool_mod

    sentinel = object()
    monkeypatch.setattr(_pool_mod, "_build_aiagent", lambda cfg, **kwargs: sentinel)

    pool = AgentPool()
    cfg = LLMSessionConfig(
        provider="deepseek",
        api_key="sk-test-12345",
        base_url=None,
        model="deepseek-chat",
        api_mode=None,
    )
    s = pool.get_or_create("u-e2e", "session-e2e", "jorge", cfg)
    assert s.llm_config.provider == "deepseek"
    assert s.llm_config.api_key == "sk-test-12345"
    assert s.aiagent is sentinel
    # Second call returns the same session (cached AIAgent).
    s2 = pool.get_or_create("u-e2e", "session-e2e", "jorge", cfg)
    assert s2 is s
