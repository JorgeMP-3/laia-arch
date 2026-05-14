from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable

from .config import AgentConfig
from .status import utc_now


_healthcheck_fn: Callable[[], dict] | None = None


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        ok = True
        info = {"service": "laia-runtime", "time": utc_now()}
        if _healthcheck_fn:
            try:
                info.update(_healthcheck_fn())
            except Exception as exc:
                ok = False
                info["error"] = str(exc)
        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(info, ensure_ascii=False).encode())


def start_health_server(config: AgentConfig, port: int = 9090) -> threading.Thread:
    def _run():
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()

    t = threading.Thread(target=_run, daemon=True, name="health-server")
    t.start()
    return t


def set_healthcheck(fn: Callable[[], dict]) -> None:
    global _healthcheck_fn
    _healthcheck_fn = fn
