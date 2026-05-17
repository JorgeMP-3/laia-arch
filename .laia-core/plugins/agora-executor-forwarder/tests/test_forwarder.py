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


def test_terminal_translates_to_bash_with_filtered_args(monkeypatch):
    """The LLM emits ``terminal`` from the .laia-core registry; the executor
    only has ``bash``. The forwarder must rename and drop kwargs the
    executor would reject (``background``, ``notify_on_complete``)."""
    plug = _load_plugin()
    captured: dict = {}

    class _FakeResp:
        status_code = 200
        text = "ok"
        def json(self):
            return {"ok": True, "result": "done"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp()

    monkeypatch.setattr(plug.httpx, "post", fake_post)
    plug.configure_session(agent_slug="x", container_ip="10.0.0.5",
                           api_token="t", port=9091, timeout_seconds=5.0)
    try:
        plug._on_pre_tool_call("terminal", {
            "command": "ls /tmp",
            "background": False,           # ← bash() doesn't accept this
            "notify_on_complete": False,   # ← nor this
            "timeout": 60,
        })
    finally:
        plug.clear_session()

    assert captured["json"]["tool"] == "bash", "tool name not translated"
    assert captured["json"]["args"] == {"command": "ls /tmp", "timeout": 60}, \
        "args not filtered to bash signature"


def test_patch_translates_to_apply_patch(monkeypatch):
    plug = _load_plugin()
    captured: dict = {}
    class _FakeResp:
        status_code = 200; text = "ok"
        def json(self): return {"ok": True, "result": "patched"}
    monkeypatch.setattr(plug.httpx, "post",
                        lambda url, json=None, headers=None, timeout=None: (captured.update(json=json), _FakeResp())[1])
    plug.configure_session(agent_slug="x", container_ip="10.0.0.5", api_token="t")
    try:
        plug._on_pre_tool_call("patch", {"path": "/x", "old_string": "a", "new_string": "b"})
    finally:
        plug.clear_session()
    assert captured["json"]["tool"] == "apply_patch"
    assert captured["json"]["args"] == {"path": "/x", "old_string": "a", "new_string": "b"}


def test_search_files_translates_to_grep(monkeypatch):
    plug = _load_plugin()
    captured: dict = {}
    class _FakeResp:
        status_code = 200; text = "ok"
        def json(self): return {"ok": True, "result": ""}
    monkeypatch.setattr(plug.httpx, "post",
                        lambda url, json=None, headers=None, timeout=None: (captured.update(json=json), _FakeResp())[1])
    plug.configure_session(agent_slug="x", container_ip="10.0.0.5", api_token="t")
    try:
        plug._on_pre_tool_call("search_files", {"pattern": "TODO", "path": "/x", "include": "*.py"})
    finally:
        plug.clear_session()
    assert captured["json"]["tool"] == "grep"
    assert captured["json"]["args"] == {"pattern": "TODO", "path": "/x", "include": "*.py"}


# ──────────────────────────────────────────────────────────────────────────
# Cross-thread context: registry by task_id (the F1 fix)
# ──────────────────────────────────────────────────────────────────────────


def test_register_context_visible_from_another_thread(monkeypatch):
    """The whole point of moving off threading.local: a thread that did NOT
    call register_context must still resolve the context if it has the
    task_id. Models the AIAgent's internal ThreadPoolExecutor invoking the
    hook from a worker thread distinct from chat_engine._worker."""
    import threading
    from urllib.parse import urlparse

    plug = _load_plugin()
    plug.clear_session()  # ensure threading.local is empty — only registry should match
    captured_ip: list[str | None] = []

    class _FakeResp:
        status_code = 200; text = "ok"
        def json(self):
            return {"ok": True, "result": "done"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_ip.append(urlparse(url).hostname)
        return _FakeResp()

    monkeypatch.setattr(plug.httpx, "post", fake_post)
    plug.register_context(
        "task-cross", agent_slug="x",
        container_ip="10.0.0.99", api_token="tok",
    )
    try:
        def worker():
            plug._on_pre_tool_call("read_file", {"path": "/x"}, task_id="task-cross")

        t = threading.Thread(target=worker)
        t.start(); t.join()
    finally:
        plug.unregister_context("task-cross")

    assert captured_ip == ["10.0.0.99"], \
        "hook in a different thread must resolve container_ip via the registry"


def test_unregister_context_cleans_up():
    """After unregister, the hook from any thread sees no context for that
    task_id and falls through to local execution (returns None)."""
    plug = _load_plugin()
    plug.clear_session()
    plug.register_context(
        "task-clean", agent_slug="x",
        container_ip="10.0.0.1", api_token="t",
    )
    plug.unregister_context("task-clean")
    result = plug._on_pre_tool_call(
        "read_file", {"path": "/x"}, task_id="task-clean",
    )
    assert result is None, "unregister must drop the context"


def test_registry_isolation_between_tasks(monkeypatch):
    """Two simultaneous tasks must route to their own executors. Models the
    case where Telegram and web chat happen in parallel for two users."""
    from urllib.parse import urlparse

    plug = _load_plugin()
    plug.clear_session()
    seen_by_task: dict[str, str | None] = {}

    class _FakeResp:
        status_code = 200; text = "ok"
        def json(self):
            return {"ok": True, "result": "done"}

    def fake_post(url, json=None, headers=None, timeout=None):
        # Carry the task_id back via the JSON-encoded request body so we
        # can assert each task hit its own ip.
        tid = (json or {}).get("request_id")
        seen_by_task[tid] = urlparse(url).hostname
        return _FakeResp()

    monkeypatch.setattr(plug.httpx, "post", fake_post)
    plug.register_context("t-a", agent_slug="a", container_ip="10.0.0.1", api_token="x")
    plug.register_context("t-b", agent_slug="b", container_ip="10.0.0.2", api_token="y")
    try:
        plug._on_pre_tool_call("read_file", {"path": "/x"}, task_id="t-a", tool_call_id="t-a")
        plug._on_pre_tool_call("read_file", {"path": "/x"}, task_id="t-b", tool_call_id="t-b")
    finally:
        plug.unregister_context("t-a")
        plug.unregister_context("t-b")

    assert seen_by_task == {"t-a": "10.0.0.1", "t-b": "10.0.0.2"}


def test_registry_cap_evicts_oldest():
    """When the registry hits MAX_REGISTRY_SIZE, the oldest entry is dropped
    so a runaway leak stays bounded."""
    plug = _load_plugin()
    plug.clear_session()
    # Drain anything left over from other tests.
    with plug._context_registry_lock:
        plug._context_registry.clear()

    # Temporarily lower the cap.
    original_cap = plug.MAX_REGISTRY_SIZE
    plug.MAX_REGISTRY_SIZE = 3
    try:
        for i, tid in enumerate(("a", "b", "c", "d")):
            plug.register_context(
                tid, agent_slug=tid,
                container_ip=f"10.0.0.{i + 1}", api_token="t",
            )
        with plug._context_registry_lock:
            keys = list(plug._context_registry.keys())
        assert "a" not in keys, "oldest entry should have been evicted"
        assert keys == ["b", "c", "d"]
    finally:
        plug.MAX_REGISTRY_SIZE = original_cap
        for tid in ("b", "c", "d"):
            plug.unregister_context(tid)


def test_unregister_idempotent():
    """unregister_context must be safe to call multiple times — chat_engine
    calls it in a finally that may run after a failed register, and a no-op
    on an unknown task_id should not raise."""
    plug = _load_plugin()
    plug.unregister_context("never-registered")  # must not raise
    plug.register_context("once", agent_slug="x", container_ip="10.0.0.1", api_token="t")
    plug.unregister_context("once")
    plug.unregister_context("once")  # second call no-ops


def test_register_empty_task_id_ignored():
    """An empty task_id is a programming bug; we log and ignore rather
    than corrupting the registry with a None/empty key."""
    plug = _load_plugin()
    plug.unregister_context("")
    plug.register_context("", agent_slug="x", container_ip="10.0.0.1", api_token="t")
    with plug._context_registry_lock:
        assert "" not in plug._context_registry
