"""Unit tests for the agora-plane-forwarder plugin (no live Plane, no token).

Loaded by file path like the executor-forwarder tests. The PlaneClient calls
are exercised through a fake injected via the `_client_factory` seam — the
real client surface is pinned by test_bridge_contract (skips cleanly when the
satellite package is absent).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_tools(monkeypatch, tmp_path, *, with_bridge=True, token="tok-123"):
    # tools.registry only exists inside .laia-core; the module's faithful
    # local fallbacks (same output shape) take over here.
    if with_bridge:
        bridge_pkg = types.ModuleType("laia_plane_bridge")
        client_mod = types.ModuleType("laia_plane_bridge.client")

        class PlaneClientError(Exception):
            pass

        class FakePlaneClient:
            calls: list = []

            def __init__(self, base_url, api_key, workspace, **kw):
                self.base_url, self.api_key, self.workspace = base_url, api_key, workspace

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def create_work_item(self, project_id, name,
                                       description_html=None, extra=None):
                self.calls.append(("create", project_id, name))
                return {"id": "wi_new", "name": name}

            async def add_comment(self, project_id, work_item_id, comment_html):
                self.calls.append(("comment", project_id, work_item_id))
                return {"id": "c_1"}

            async def update_work_item(self, project_id, work_item_id, patch):
                self.calls.append(("update", project_id, work_item_id, patch))
                return {"id": work_item_id, **patch}

            async def add_link(self, project_id, work_item_id, url, title=None):
                self.calls.append(("link", project_id, work_item_id, url))
                return {"id": "l_1"}

        client_mod.PlaneClient = FakePlaneClient
        client_mod.PlaneClientError = PlaneClientError
        bridge_pkg.client = client_mod
        sys.modules["laia_plane_bridge"] = bridge_pkg
        sys.modules["laia_plane_bridge.client"] = client_mod
    else:
        sys.modules.pop("laia_plane_bridge", None)
        sys.modules.pop("laia_plane_bridge.client", None)

    if token is not None:
        key_file = tmp_path / "plane-api-key"
        key_file.write_text(token, encoding="utf-8")
        monkeypatch.setenv("LAIA_PLANE_API_KEY_FILE", str(key_file))
    else:
        monkeypatch.setenv("LAIA_PLANE_API_KEY_FILE", str(tmp_path / "missing"))
    monkeypatch.setenv("LAIA_PLANE_WORKSPACE", "doyouwin")

    sys.modules.pop("agora_plane_forwarder_tools", None)
    spec = importlib.util.spec_from_file_location(
        "agora_plane_forwarder_tools", PLUGIN_DIR / "tools.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agora_plane_forwarder_tools"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── availability gating ───────────────────────────────────────────────────────

def test_unavailable_without_token(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path, token=None)
    assert mod.check_plane_available() is False
    out = json.loads(mod.handle_plane_comment(
        project_id="p", work_item_id="w", comment_html="<p>x</p>"))
    assert "token" in out["error"]


def test_unavailable_without_bridge_package(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path, with_bridge=False)
    assert mod.check_plane_available() is False
    out = json.loads(mod.handle_plane_attach(
        project_id="p", work_item_id="w", url="https://x"))
    assert "laia_plane_bridge" in out["error"]


def test_unavailable_without_workspace(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    monkeypatch.delenv("LAIA_PLANE_WORKSPACE")
    assert mod.check_plane_available() is False


# ── happy paths through the fake client ──────────────────────────────────────

def test_create_work_item_calls_client(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    out = json.loads(mod.handle_plane_create_work_item(
        project_id="proj-1", name="Campaña"))
    assert out["id"] == "wi_new"


def test_update_state_patches_state(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    out = json.loads(mod.handle_plane_update_state(
        project_id="proj-1", work_item_id="wi-1", state_id="st-9"))
    assert out["state"] == "st-9"


def test_attach_and_comment(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    assert "error" not in json.loads(mod.handle_plane_attach(
        project_id="p", work_item_id="w", url="https://r/x.png", title="render"))
    assert "error" not in json.loads(mod.handle_plane_comment(
        project_id="p", work_item_id="w", comment_html="<p>ok</p>"))


# ── argument validation (no client call on bad input) ───────────────────────

def test_missing_required_args_is_tool_error(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    assert "required" in json.loads(mod.handle_plane_create_work_item())["error"]
    assert "required" in json.loads(mod.handle_plane_update_state(
        project_id="p", work_item_id="w"))["error"]


# ── client errors surface as tool_error, never raise ────────────────────────

def test_plane_client_error_becomes_tool_error(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    err = sys.modules["laia_plane_bridge.client"].PlaneClientError

    class Boom:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def add_comment(self, *a, **k):
            raise err("auth failed (401)")

    monkeypatch.setattr(mod, "_client_factory", lambda: Boom())
    out = json.loads(mod.handle_plane_comment(
        project_id="p", work_item_id="w", comment_html="<p>x</p>"))
    assert "Plane API error" in out["error"]


# ── schemas / registration ───────────────────────────────────────────────────

def test_schemas_declare_required_params(monkeypatch, tmp_path):
    mod = _load_tools(monkeypatch, tmp_path)
    for schema, required in (
        (mod.PLANE_CREATE_WORK_ITEM_SCHEMA, {"project_id", "name"}),
        (mod.PLANE_COMMENT_SCHEMA, {"project_id", "work_item_id", "comment_html"}),
        (mod.PLANE_UPDATE_STATE_SCHEMA, {"project_id", "work_item_id", "state_id"}),
        (mod.PLANE_ATTACH_SCHEMA, {"project_id", "work_item_id", "url"}),
    ):
        assert set(schema["parameters"]["required"]) == required
        assert schema["name"].startswith("plane_")


def test_plugin_register_binds_four_tools(monkeypatch, tmp_path):
    _load_tools(monkeypatch, tmp_path)  # ensures stubs + tools module present

    plugin_init = PLUGIN_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location("agora_plane_forwarder", plugin_init)
    plug = importlib.util.module_from_spec(spec)
    sys.modules["agora_plane_forwarder"] = plug
    spec.loader.exec_module(plug)

    registered = []

    class Ctx:
        def register_tool(self, **kw):
            registered.append(kw)

    plug.register(Ctx())
    assert {r["name"] for r in registered} == {
        "plane_create_work_item", "plane_comment",
        "plane_update_state", "plane_attach"}
    assert all(r["toolset"] == "plane" for r in registered)
