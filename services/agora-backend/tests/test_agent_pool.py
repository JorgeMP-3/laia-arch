"""Tests for the AIAgent pool — placeholder agent is OK for these checks."""

from __future__ import annotations

import time

from app.agent_pool import AgentPool, LLMSessionConfig


def _cfg(provider="anthropic") -> LLMSessionConfig:
    return LLMSessionConfig(
        provider=provider,
        api_key="sk-test",
        base_url=None,
        model="claude-opus-4-6",
        api_mode=None,
    )


def test_create_and_reuse_session():
    pool = AgentPool(idle_ttl_seconds=60, max_sessions=10)
    s1 = pool.get_or_create("u1", "sess-a", "jorge", _cfg())
    s2 = pool.get_or_create("u1", "sess-a", "jorge", _cfg())
    assert s1 is s2
    assert pool.stats()["size"] == 1


def test_distinct_sessions_for_distinct_users():
    pool = AgentPool()
    pool.get_or_create("u1", "s", "jorge", _cfg())
    pool.get_or_create("u2", "s", "maria", _cfg())
    assert pool.stats()["size"] == 2


def test_evict_idle():
    pool = AgentPool(idle_ttl_seconds=0, max_sessions=10)
    pool.get_or_create("u1", "s", "jorge", _cfg())
    time.sleep(0.01)
    dropped = pool.evict_idle()
    assert dropped == 1
    assert pool.stats()["size"] == 0


def test_lru_eviction_at_max():
    pool = AgentPool(idle_ttl_seconds=3600, max_sessions=2)
    pool.get_or_create("u1", "s1", "jorge", _cfg())
    time.sleep(0.001)
    pool.get_or_create("u2", "s1", "maria", _cfg())
    time.sleep(0.001)
    # Third session triggers LRU eviction of u1::s1.
    pool.get_or_create("u3", "s1", "luis", _cfg())
    assert pool.stats()["size"] == 2
    assert pool.get("u1", "s1") is None
    assert pool.get("u2", "s1") is not None
    assert pool.get("u3", "s1") is not None


def test_explicit_evict():
    pool = AgentPool()
    pool.get_or_create("u1", "s", "jorge", _cfg())
    assert pool.evict("u1", "s") is True
    assert pool.evict("u1", "s") is False
    assert pool.stats()["size"] == 0


def test_touch_via_get():
    pool = AgentPool(idle_ttl_seconds=10)
    pool.get_or_create("u1", "s", "jorge", _cfg())
    first = pool.stats()["sessions"][0]["idle_seconds"]
    time.sleep(0.01)
    pool.get("u1", "s")
    second = pool.stats()["sessions"][0]["idle_seconds"]
    assert second <= first  # touched → idle counter resets


def test_collective_workspace_bootstrap_on_get_or_create(monkeypatch):
    """get_or_create wires LAIA_HOME + creates the collective workspace dir."""
    import os
    from pathlib import Path

    # Force the bootstrap to re-run with the test conftest's AGORA_DATA_DIR.
    from app import agent_pool as ap
    ap._collective_workspace_ready = False
    # Skip the real AIAgent build — we're only exercising the bootstrap
    # side-effect, and a real AIAgent without a DEEPSEEK_API_KEY in the
    # env would raise.
    monkeypatch.setattr(ap, "_build_aiagent", lambda cfg, **kwargs: object())

    pool = AgentPool()
    pool.get_or_create("u-ws", "s-ws", "jorge", _cfg())

    data_dir = Path(os.environ["AGORA_DATA_DIR"])
    assert os.environ.get("LAIA_HOME") == str(data_dir)
    assert (data_dir / "workspaces" / "collective").is_dir()
    # If workspace_store is reachable in this checkout, the DB also exists.
    if (Path(os.environ.get("LAIA_ROOT", "")) / "workspace_store").is_dir() \
            or (Path.home() / "LAIA" / "workspace_store").is_dir():
        db = data_dir / "workspaces" / "collective" / "workspace.db"
        assert db.exists(), "expected collective workspace.db to be seeded"

    # And the AGORA-owned config.yaml is materialised so workspace-context
    # doesn't fall back to ~/.laia/config.yaml (ARCH's workspace).
    cfg = data_dir / "config.yaml"
    assert cfg.is_file(), "expected config.yaml to be seeded for workspace-context"
    cfg_text = cfg.read_text()
    assert "workspace: collective" in cfg_text
    assert "provider: workspace-context" in cfg_text


def test_agent_area_prompt_is_passed_to_aiagent(monkeypatch):
    from app.storage import store
    from app.models import User
    from app import agent_pool as ap

    user = User(
        id="u-area-pool",
        username="areapool",
        display_name="Area Pool",
        password="pw",
        active=True,
    )
    store.save_user(user)
    store.update_agent_area(
        user.id,
        agent_display_name="PoolBot",
        soul_md="Soy PoolBot.",
        instructions_md="Habla claro.",
        behavior_preferences={"tone": "directo"},
    )

    captured = {}
    monkeypatch.setattr(
        ap,
        "_build_aiagent",
        lambda cfg, **kwargs: captured.update(kwargs) or object(),
    )

    pool = AgentPool()
    pool.get_or_create(user.id, "s-area", "areapool", _cfg())

    prompt = captured["ephemeral_system_prompt"]
    assert "PoolBot" in prompt
    assert "Soy PoolBot." in prompt
    assert "Habla claro." in prompt
    assert "directo" in prompt
