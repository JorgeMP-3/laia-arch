"""Unit tests for the AGORA executor forwarder plugin."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PLUGIN_PARENT = PLUGIN_DIR.parent


def _load_plugin():
    """Import the plugin module by file path (no package install required)."""
    plugin_init = PLUGIN_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location("agora_executor_forwarder", plugin_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules["agora_executor_forwarder"] = module
    spec.loader.exec_module(module)
    return module


def test_passthrough_when_no_session_context():
    """Without configure_session, the hook returns None — local execution."""
    plug = _load_plugin()
    plug.clear_session()
    result = plug._on_pre_tool_call("read_file", {"path": "/tmp/x"}, task_id="t1")
    assert result is None


def test_passthrough_for_non_executor_tool():
    """web_search isn't in EXECUTOR_TOOLS → run locally even with context set."""
    plug = _load_plugin()
    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5",
        api_token="tok", port=9091, timeout_seconds=1.0,
    )
    try:
        result = plug._on_pre_tool_call("web_search", {"q": "x"})
        assert result is None
    finally:
        plug.clear_session()


def test_forward_executor_tool(monkeypatch):
    """A configured session forwards executor tools via HTTPX."""
    plug = _load_plugin()

    captured: dict = {}

    class _FakeResponse:
        status_code = 200
        text = "fine"
        def json(self):
            return {"ok": True, "result": "wrote 12 bytes", "request_id": "r1"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    # Patch httpx.post inside the loaded plugin module.
    monkeypatch.setattr(plug.httpx, "post", fake_post)

    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5",
        api_token="bearer-tok-abc", port=9091, timeout_seconds=10.0,
    )
    try:
        result = plug._on_pre_tool_call(
            "write_file",
            {"path": "/home/user/hello.py", "content": "print(1)"},
            tool_call_id="call-1",
        )
    finally:
        plug.clear_session()

    assert result is not None
    assert result["action"] == "replace"
    assert result["message"] == "wrote 12 bytes"
    assert captured["url"] == "http://10.0.0.5:9091/exec"
    assert captured["headers"]["Authorization"] == "Bearer bearer-tok-abc"
    assert captured["json"]["tool"] == "write_file"
    assert captured["json"]["request_id"] == "call-1"


def test_forward_executor_error(monkeypatch):
    """When the executor returns ok=False, the forwarder surfaces the error."""
    plug = _load_plugin()

    class _FakeResponse:
        status_code = 200
        text = "fine"
        def json(self):
            return {"ok": False, "error": "tool raised: permission denied"}

    monkeypatch.setattr(plug.httpx, "post",
                        lambda *a, **k: _FakeResponse())
    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5", api_token="tok",
    )
    try:
        result = plug._on_pre_tool_call("bash", {"command": "rm /"})
    finally:
        plug.clear_session()

    assert result["action"] == "replace"
    body = json.loads(result["message"])
    assert body["ok"] is False
    assert "permission denied" in body["error"]


def test_forward_network_failure(monkeypatch):
    """If httpx raises, the forwarder returns a structured error string."""
    plug = _load_plugin()

    def bad_post(*a, **k):
        raise plug.httpx.ConnectError("connection refused")

    monkeypatch.setattr(plug.httpx, "post", bad_post)
    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5", api_token="tok",
    )
    try:
        result = plug._on_pre_tool_call("read_file", {"path": "/x"})
    finally:
        plug.clear_session()

    assert result["action"] == "replace"
    body = json.loads(result["message"])
    assert body["ok"] is False
    assert "executor request failed" in body["error"]


def test_private_workspace_tools_in_executor_set():
    """The forwarder always routes private_workspace_* tools to the executor."""
    plug = _load_plugin()
    for name in (
        "private_workspace_search",
        "private_workspace_read_node",
        "private_workspace_add_node",
        "private_workspace_find_related",
    ):
        assert name in plug.EXECUTOR_TOOLS, f"{name!r} missing from EXECUTOR_TOOLS"


def test_private_workspace_schemas_shape():
    """Every private_workspace_* schema declares name + parameters."""
    plug = _load_plugin()
    schemas = {s["name"]: s for s in plug.PRIVATE_WORKSPACE_TOOL_SCHEMAS}
    assert set(schemas) == {
        "private_workspace_search",
        "private_workspace_read_node",
        "private_workspace_add_node",
        "private_workspace_find_related",
    }
    for name, schema in schemas.items():
        assert schema["description"]
        params = schema["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_register_wires_tools_and_hook():
    """ctx.register_tool is called for each private_workspace_* schema."""
    plug = _load_plugin()
    registered_tools: list[dict] = []
    registered_hooks: list[tuple[str, object]] = []

    class _Ctx:
        def register_hook(self, hook_name, callback):
            registered_hooks.append((hook_name, callback))

        def register_tool(self, **kwargs):
            registered_tools.append(kwargs)

    plug.register(_Ctx())

    names = [t["name"] for t in registered_tools]
    assert names == [
        "private_workspace_search",
        "private_workspace_read_node",
        "private_workspace_add_node",
        "private_workspace_find_related",
    ]
    assert all(t["toolset"] == "workspace" for t in registered_tools)
    assert registered_hooks and registered_hooks[0][0] == "pre_tool_call"


def test_forward_private_workspace_search(monkeypatch):
    """private_workspace_search routes to the executor like file/bash do."""
    plug = _load_plugin()
    captured: dict = {}

    class _FakeResponse:
        status_code = 200
        text = "fine"

        def json(self):
            return {"ok": True, "result": '{"ok": true, "results": []}', "request_id": "x"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(plug.httpx, "post", fake_post)
    plug.configure_session(
        agent_slug="jorge", container_ip="10.0.0.5",
        api_token="tok", port=9091, timeout_seconds=10.0,
    )
    try:
        result = plug._on_pre_tool_call(
            "private_workspace_search",
            {"query": "mariposas"},
            tool_call_id="c-1",
        )
    finally:
        plug.clear_session()

    assert result is not None
    assert result["action"] == "replace"
    assert captured["url"] == "http://10.0.0.5:9091/exec"
    assert captured["json"]["tool"] == "private_workspace_search"
    assert captured["json"]["args"] == {"query": "mariposas"}


def test_stub_handler_returns_error_when_no_context():
    """If the LLM calls a forwarded tool without context, the local stub
    is registered as a clear-error fallback (real call would be intercepted
    earlier by the pre_tool_call hook → executor)."""
    plug = _load_plugin()
    msg = plug._stub_handler(path="/tmp/x")
    assert "no executor context" in msg or "configure_session" in msg


def test_thread_isolation():
    """Each thread sees its own session context."""
    import threading

    plug = _load_plugin()
    plug.clear_session()
    seen: dict[str, str | None] = {}

    def worker_a():
        plug.configure_session(agent_slug="A", container_ip="1.1.1.1", api_token="ta")
        seen["a"] = plug._session_ctx.agent_slug

    def worker_b():
        # No configure → should see None
        seen["b"] = plug._session_ctx.agent_slug

    ta = threading.Thread(target=worker_a)
    tb = threading.Thread(target=worker_b)
    ta.start(); ta.join()
    tb.start(); tb.join()
    assert seen["a"] == "A"
    assert seen["b"] is None


def test_per_tool_timeout_overrides_session_default(monkeypatch):
    """`bash` uses 180s even when the session default is 30s; `read_file` uses
    the session default (no override). The executor's bash worst case is
    BASH_TIMEOUT_MAX=600s, but the forwarder default 30s would falsely
    timeout legitimately slow commands like `apt update`."""
    plug = _load_plugin()

    class _FakeResponse:
        status_code = 200
        text = "fine"
        def json(self):
            return {"ok": True, "result": "x"}

    captures: list[float | None] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        captures.append(timeout)
        return _FakeResponse()

    monkeypatch.setattr(plug.httpx, "post", fake_post)

    plug.configure_session(
        agent_slug="x", container_ip="10.0.0.5", api_token="t",
        port=9091, timeout_seconds=30.0,
    )
    try:
        plug._on_pre_tool_call("bash", {"command": "apt update"})
        plug._on_pre_tool_call("read_file", {"path": "/x"})
        plug._on_pre_tool_call("apply_patch", {"path": "/x", "old_string": "a", "new_string": "b"})
    finally:
        plug.clear_session()

    assert captures[0] == plug.EXECUTOR_TOOL_TIMEOUTS["bash"]
    assert captures[1] == 30.0
    assert captures[2] == plug.EXECUTOR_TOOL_TIMEOUTS["apply_patch"]
