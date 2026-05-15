"""Tests for PathDaemon — config loading, reload, env file regen."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from pathd.server import PathDaemon


@pytest.fixture
def daemon_factory(tmp_path):
    def _make(paths_block: dict[str, str] | None = None) -> PathDaemon:
        cfg = tmp_path / "config.yaml"
        block = paths_block or {"root": str(tmp_path), "sub": "${paths.root}/sub"}
        body = "paths:\n"
        for k, v in block.items():
            body += f"  {k}: {v}\n"
        cfg.write_text(body)
        return PathDaemon(
            config_path=cfg,
            env_file=tmp_path / ".env.paths",
            socket_path=tmp_path / "sock",
            state_path=tmp_path / "state.json",
            farm_dir=tmp_path / "atlas",
            poll_interval=0.1,
        )
    return _make


@pytest.mark.asyncio
async def test_initial_load_writes_env_and_symlinks(daemon_factory, tmp_path):
    d = daemon_factory({"foo": str(tmp_path / "foo")})
    (tmp_path / "foo").mkdir()
    assert await d._reload(force=True) is True
    env_content = (tmp_path / ".env.paths").read_text()
    assert "LAIA_FOO" in env_content
    assert (tmp_path / "atlas" / "foo").is_symlink()


@pytest.mark.asyncio
async def test_reload_detects_config_change(daemon_factory, tmp_path):
    d = daemon_factory({"a": "/initial"})
    await d._reload(force=True)
    assert d.state.paths["a"].current_path == "/initial"

    # Mutate config
    new_body = "paths:\n  a: /updated\n  b: /added\n"
    (tmp_path / "config.yaml").write_text(new_body)
    # Bump mtime explicitly because tests can be too fast
    new_mtime = time.time() + 1
    import os
    os.utime(tmp_path / "config.yaml", (new_mtime, new_mtime))

    changed = await d._reload()
    assert changed is True
    assert d.state.paths["a"].current_path == "/updated"
    assert "b" in d.state.paths
    # History recorded
    assert any(h["to"] == "/updated" for h in d.state.paths["a"].history)


@pytest.mark.asyncio
async def test_reload_idempotent_when_unchanged(daemon_factory):
    d = daemon_factory({"a": "/x"})
    await d._reload(force=True)
    assert await d._reload() is False  # no mtime change


@pytest.mark.asyncio
async def test_rpc_methods(daemon_factory, tmp_path):
    d = daemon_factory({"agora": str(tmp_path / "agora")})
    (tmp_path / "agora").mkdir()
    await d._reload(force=True)

    result = await d._rpc_resolve({"key": "agora"})
    assert result == str(tmp_path / "agora")

    all_ = await d._rpc_resolve_all({})
    assert all_ == {"agora": str(tmp_path / "agora")}

    status = await d._rpc_status({})
    assert status["paths_count"] == 1

    with pytest.raises(KeyError):
        await d._rpc_resolve({"key": "nope"})


@pytest.mark.asyncio
async def test_removed_alias_drops_from_state(daemon_factory, tmp_path):
    d = daemon_factory({"a": "/x", "b": "/y"})
    await d._reload(force=True)
    assert set(d.state.paths) == {"a", "b"}

    (tmp_path / "config.yaml").write_text("paths:\n  a: /x\n")
    import os, time as _t
    new_mtime = _t.time() + 2
    os.utime(tmp_path / "config.yaml", (new_mtime, new_mtime))

    assert await d._reload() is True
    assert set(d.state.paths) == {"a"}
