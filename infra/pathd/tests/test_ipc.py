"""Tests for IpcServer / IpcClient over Unix socket."""
from __future__ import annotations

import asyncio

import pytest

from pathd.ipc import IpcClient, IpcServer


@pytest.mark.asyncio
async def test_roundtrip_call(tmp_path):
    async def echo(params):
        return {"echoed": params}

    server = IpcServer(tmp_path / "sock", {"echo": echo})
    await server.start()
    serve_task = asyncio.create_task(server.serve_forever())
    try:
        # Use sync client from a thread to avoid awaiting blocking calls
        result = await asyncio.to_thread(
            IpcClient(tmp_path / "sock").call, "echo", x=1, y="z"
        )
        assert result == {"echoed": {"x": 1, "y": "z"}}
    finally:
        serve_task.cancel()
        await server.stop()


@pytest.mark.asyncio
async def test_unknown_method_returns_error(tmp_path):
    server = IpcServer(tmp_path / "sock", {})
    await server.start()
    serve_task = asyncio.create_task(server.serve_forever())
    try:
        with pytest.raises(RuntimeError, match="Method not found"):
            await asyncio.to_thread(IpcClient(tmp_path / "sock").call, "nope")
    finally:
        serve_task.cancel()
        await server.stop()


@pytest.mark.asyncio
async def test_handler_exception_returned_as_error(tmp_path):
    async def boom(params):
        raise ValueError("kaboom")

    server = IpcServer(tmp_path / "sock", {"boom": boom})
    await server.start()
    serve_task = asyncio.create_task(server.serve_forever())
    try:
        with pytest.raises(RuntimeError, match="kaboom"):
            await asyncio.to_thread(IpcClient(tmp_path / "sock").call, "boom")
    finally:
        serve_task.cancel()
        await server.stop()


def test_client_available_false_when_no_socket(tmp_path):
    assert IpcClient(tmp_path / "missing").available() is False
