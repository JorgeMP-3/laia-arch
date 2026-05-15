"""JSON-RPC server over Unix domain socket for laia-pathd.

Wire format: one JSON object per line.
Request:  {"id": 1, "method": "resolve", "params": {"key": "agora"}}
Response: {"id": 1, "result": "/some/path"}
Error:    {"id": 1, "error": {"code": -32601, "message": "method not found"}}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class IpcServer:
    def __init__(self, socket_path: Path, handlers: dict[str, Handler]):
        self.socket_path = socket_path
        self.handlers = handlers
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        logger.info("ipc listening on %s", self.socket_path)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.socket_path.exists():
            self.socket_path.unlink()

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    self._send(writer, {"error": _err(-32700, "Parse error")})
                    continue
                response = await self._dispatch(msg)
                self._send(writer, response)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _dispatch(self, msg: dict[str, Any]) -> dict[str, Any]:
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if not method or method not in self.handlers:
            return {"id": req_id, "error": _err(-32601, f"Method not found: {method!r}")}
        try:
            result = await self.handlers[method](params)
            return {"id": req_id, "result": result}
        except Exception as e:
            logger.exception("handler %s failed", method)
            return {"id": req_id, "error": _err(-32603, f"{type(e).__name__}: {e}")}

    @staticmethod
    def _send(writer: asyncio.StreamWriter, obj: dict[str, Any]) -> None:
        writer.write((json.dumps(obj) + "\n").encode("utf-8"))


def _err(code: int, message: str) -> dict[str, Any]:
    return {"code": code, "message": message}


# ----------------------------------------------------------------------------
# Client helpers (used by laia_paths.py and laia-path CLI)
# ----------------------------------------------------------------------------

class IpcClient:
    """Synchronous JSON-RPC client over Unix socket.

    Designed for short-lived lookups from Python consumers. Each call opens
    a connection (cheap on a Unix socket) — keeps the client stateless.
    """

    def __init__(self, socket_path: Path, timeout: float = 0.5):
        self.socket_path = socket_path
        self.timeout = timeout

    def available(self) -> bool:
        return self.socket_path.exists()

    def call(self, method: str, **params: Any) -> Any:
        import socket as _socket
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(str(self.socket_path))
        try:
            req = {"id": 1, "method": method, "params": params}
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
            resp = json.loads(buf.decode("utf-8").splitlines()[0])
        finally:
            s.close()
        if "error" in resp:
            raise RuntimeError(resp["error"]["message"])
        return resp.get("result")
