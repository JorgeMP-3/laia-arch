"""Tests for Fase E (AgentPool integration) and Fase F (forwarder extras)."""

from __future__ import annotations

import os

import pytest


def test_agent_pool_exposes_invalidate_user():
    from app.agent_pool import AgentPool

    pool = AgentPool()
    # No sessions yet — invalidate returns 0.
    assert pool.invalidate_user("user_nobody") == 0

    # Static accessor (used by marketplace.py) routes to the active instance.
    assert AgentPool.invalidate_user_static("user_nobody") == 0


def test_forwarder_reads_extra_tools_from_env():
    # The plugin's helper must read the env at call time so install/uninstall
    # takes effect without a process restart.
    #
    # The forwarder ships with .laia-core, so it lives at different paths
    # depending on context (repo checkout vs container image vs venv). We
    # resolve it by scanning PYTHONPATH/sys.path for plugins/agora-executor-forwarder.
    import importlib.util
    import sys
    from pathlib import Path

    init_py = None
    for root in [Path(p) for p in sys.path if p]:
        candidate = root / "plugins" / "agora-executor-forwarder" / "__init__.py"
        if candidate.is_file():
            init_py = candidate
            break
    if init_py is None:
        # Last-resort: scan upwards from this test file (repo layout fallback).
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / ".laia-core" / "plugins" / "agora-executor-forwarder" / "__init__.py"
            if candidate.is_file():
                init_py = candidate
                break
    assert init_py is not None, "could not locate agora-executor-forwarder/__init__.py"

    spec = importlib.util.spec_from_file_location("_agora_forwarder_test", init_py)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Empty env → empty set.
    old = os.environ.pop("LAIA_FORWARDED_TOOLS_EXTRA", None)
    try:
        assert mod._extra_forwarded_tools() == frozenset()

        os.environ["LAIA_FORWARDED_TOOLS_EXTRA"] = "custom_a, custom_b ,custom_c"
        got = mod._extra_forwarded_tools()
        assert "custom_a" in got
        assert "custom_b" in got
        assert "custom_c" in got
        assert len(got) == 3
    finally:
        if old is None:
            os.environ.pop("LAIA_FORWARDED_TOOLS_EXTRA", None)
        else:
            os.environ["LAIA_FORWARDED_TOOLS_EXTRA"] = old


def test_combined_marketplace_install_and_area_edit_pass_through_to_aiagent(
    tmp_path, monkeypatch
):
    """C.3 — verify the full combined path:
        1. User PATCHes /api/me/agent-area (soul + display_name).
        2. User installs a published plugin.
        3. AgentPool.get_or_create() materialises the marketplace AND builds
           the area prompt, both of which arrive at _build_aiagent.

    The AIAgent constructor is mocked so we don't need a real LLM or OAuth.
    """
    import base64
    import io
    import tarfile
    import uuid

    from fastapi.testclient import TestClient

    from app import agent_pool as ap
    from app.agent_pool import AgentPool, LLMSessionConfig
    from app.config import settings as cfg
    from app.main import app
    from app.storage import store

    client = TestClient(app)
    admin_h = {"Authorization": "Bearer dev-admin-token"}

    # Isolate the per-user materialisation dir so we don't pollute /srv.
    monkeypatch.setattr(cfg, "installed_plugins_root", tmp_path / "installed-plugins")
    monkeypatch.setattr(cfg, "installed_skills_root", tmp_path / "installed-skills")
    monkeypatch.setattr(cfg, "plugin_store_dir", tmp_path / "plugin-store")
    cfg.plugin_store_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create user + login.
    username = f"combo_{uuid.uuid4().hex[:6]}"
    password = f"pw_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/users", headers=admin_h,
                    json={"username": username, "display_name": username,
                          "role": "employee", "password": password})
    assert r.status_code in (200, 201), r.text
    user_id = r.json()["user"]["id"]
    tok = client.post("/api/login",
                      json={"username": username, "password": password}).json()["access_token"]
    user_h = {"Authorization": f"Bearer {tok}"}

    # 2. PATCH agent-area with soul + name.
    r = client.patch("/api/me/agent-area", headers=user_h, json={
        "agent_display_name": "Combo",
        "soul_md": "# Soul\nSoy Combo y demuestro el flujo combinado.",
        "instructions_md": "Responde como si fueras Combo.",
        "behavior_preferences": {"tone": "didáctico"},
    })
    assert r.status_code == 200, r.text

    # 3. Publish + approve + install a tiny plugin.
    slug = f"combo-{uuid.uuid4().hex[:6]}"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=f"{slug}/")
        info.type = tarfile.DIRTYPE
        tf.addfile(info)
        manifest = f"slug: {slug}\nversion: 0.1.0\nkind: standalone\n".encode()
        info = tarfile.TarInfo(name=f"{slug}/plugin.yaml")
        info.size = len(manifest)
        tf.addfile(info, io.BytesIO(manifest))
        code = b'def register(ctx): pass\n'
        info = tarfile.TarInfo(name=f"{slug}/__init__.py")
        info.size = len(code)
        tf.addfile(info, io.BytesIO(code))
    r = client.post("/api/me/plugins/upload", headers=user_h, json={
        "slug": slug, "version": "0.1.0", "kind": "standalone",
        "forward_tools": [], "blob_b64": base64.b64encode(buf.getvalue()).decode(),
    })
    assert r.status_code == 200, r.text
    plg_id = r.json()["id"]
    client.post(f"/api/me/plugins/{plg_id}/publish", headers=user_h)
    client.post(f"/api/admin/plugins/{plg_id}/approve", headers=admin_h)
    r = client.post("/api/me/plugins/install", headers=user_h, json={"slug": slug})
    assert r.status_code == 200, r.text

    # 4. Stub _build_aiagent so we can inspect the kwargs it receives without
    #    touching real LLM/OAuth code. The static helper used by marketplace
    #    invalidation routes to the active pool too.
    captured = {}

    def _stub_build(cfg_arg, **kwargs):
        captured["llm_cfg"] = cfg_arg
        captured["extra_toolsets"] = kwargs.get("extra_toolsets")
        captured["ephemeral_system_prompt"] = kwargs.get("ephemeral_system_prompt")
        return object()

    monkeypatch.setattr(ap, "_build_aiagent", _stub_build)

    pool = AgentPool()
    pool.get_or_create(
        user_id=user_id,
        session_id=f"sess-{uuid.uuid4().hex[:6]}",
        agent_slug=username,
        llm_config=LLMSessionConfig(
            provider="deepseek", api_key="sk-test", base_url=None,
            model="deepseek-chat", api_mode=None,
        ),
    )

    # Area prompt should mention the soul body.
    prompt = captured.get("ephemeral_system_prompt") or ""
    assert "Combo" in prompt, f"area prompt missing display_name: {prompt!r}"
    assert "Soy Combo" in prompt, f"area prompt missing soul: {prompt!r}"

    # Marketplace plugin dir was materialised for this user.
    user_dir = cfg.installed_plugins_root / username
    assert user_dir.exists()
    assert (user_dir / slug).exists()
    assert os.environ.get("LAIA_EXTRA_PLUGIN_DIRS") == str(user_dir)


def test_materialize_helper_sets_env(tmp_path, monkeypatch):
    """End-to-end-ish: materialise sets LAIA_EXTRA_PLUGIN_DIRS to a real dir."""
    from app.agent_pool import _materialize_marketplace_for
    from app.config import settings as cfg

    monkeypatch.setattr(cfg, "installed_plugins_root", tmp_path / "installed-plugins")
    monkeypatch.setattr(cfg, "installed_skills_root", tmp_path / "installed-skills")

    # Use the seed user "user_jorge" which exists thanks to _ensure_seed_data.
    _materialize_marketplace_for("user_jorge", "jorge")
    target = tmp_path / "installed-plugins" / "jorge"
    assert os.environ.get("LAIA_EXTRA_PLUGIN_DIRS") == str(target)
    # The dir exists (even if empty) — marketplace storage creates it.
    assert target.exists()
