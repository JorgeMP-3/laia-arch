"""End-to-end: daemon detects filesystem changes and updates the registry.

These tests start a real PathDaemon against a tmpdir, rename/delete
directories on disk, and verify the daemon reacts (via inotify+watchdog).
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest
import pytest_asyncio

from pathd.server import PathDaemon


async def _wait_for(condition, timeout=3.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


@pytest_asyncio.fixture
async def running_daemon(tmp_path):
    """Yield a running PathDaemon with a single 'service' alias pointing to
    tmp_path/services/agora. The daemon runs as an asyncio task; the fixture
    cleans up at teardown."""
    services = tmp_path / "services"
    services.mkdir()
    agora = services / "agora"
    agora.mkdir()

    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  agora: {agora}\n")

    daemon = PathDaemon(
        config_path=cfg,
        env_file=tmp_path / ".env.paths",
        socket_path=tmp_path / "sock",
        state_path=tmp_path / "state.json",
        farm_dir=tmp_path / "atlas",
        poll_interval=0.5,
    )
    task = asyncio.create_task(daemon.run())
    # Give the daemon a moment to set up watches
    await asyncio.sleep(0.3)
    try:
        yield daemon
    finally:
        daemon._stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()


@pytest.mark.asyncio
async def test_rename_in_place_is_detected(running_daemon, tmp_path):
    new_path = tmp_path / "services" / "agora-api"
    old_path = tmp_path / "services" / "agora"
    os.rename(old_path, new_path)

    ok = await _wait_for(
        lambda: running_daemon.state.paths["agora"].current_path == str(new_path),
        timeout=3.0,
    )
    assert ok, (
        f"alias not updated; current: "
        f"{running_daemon.state.paths['agora'].current_path}"
    )

    # .env.paths reflects the new path
    env_content = (tmp_path / ".env.paths").read_text()
    assert str(new_path) in env_content

    # Symlink farm reflects the new path
    farm_link = tmp_path / "atlas" / "agora"
    assert farm_link.is_symlink()
    assert os.readlink(farm_link) == str(new_path)


@pytest.mark.asyncio
async def test_delete_marks_missing(running_daemon, tmp_path):
    import shutil
    shutil.rmtree(tmp_path / "services" / "agora")

    ok = await _wait_for(
        lambda: running_daemon.state.paths["agora"].status == "missing",
        timeout=3.0,
    )
    assert ok, (
        f"alias not marked missing; status: "
        f"{running_daemon.state.paths['agora'].status}"
    )


@pytest.mark.asyncio
async def test_rename_writes_pending_restart_marker(tmp_path):
    """End-to-end: rename detected → unit with X-LaiaPathDeps gets queued."""
    services = tmp_path / "services"
    services.mkdir()
    agora = services / "agora"
    agora.mkdir()

    units_dir = tmp_path / "units"
    units_dir.mkdir()
    (units_dir / "agora-backend.service").write_text(
        "[Unit]\nX-LaiaPathDeps=agora\n"
        "[Service]\nExecStart=/bin/true\n"
    )

    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  agora: {agora}\n")

    daemon = PathDaemon(
        config_path=cfg,
        env_file=tmp_path / ".env.paths",
        socket_path=tmp_path / "sock",
        state_path=tmp_path / "state.json",
        farm_dir=tmp_path / "atlas",
        pending_restarts_path=tmp_path / "pending.json",
        poll_interval=0.5,
    )
    # Inject the controlled units index (skip system scan)
    daemon._units_index = {"agora-backend.service": ["agora"]}

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.3)
    try:
        new_path = tmp_path / "services" / "agora-api"
        import os
        os.rename(agora, new_path)

        ok = await _wait_for(
            lambda: (tmp_path / "pending.json").exists()
            and "agora-backend.service" in (tmp_path / "pending.json").read_text(),
            timeout=3.0,
        )
        assert ok, "pending-restart marker not written"

        entries = daemon.restarts.load()
        assert len(entries) == 1
        assert entries[0].unit == "agora-backend.service"
        assert entries[0].alias == "agora"
        assert entries[0].new_path == str(new_path)
    finally:
        daemon._stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
