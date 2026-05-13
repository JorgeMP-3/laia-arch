from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
request_user_var: ContextVar[str] = ContextVar("request_user", default="")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": _now_utc(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        req_id = request_id_var.get()
        if req_id:
            log_entry["req"] = req_id
        user = request_user_var.get()
        if user:
            log_entry["user"] = user
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = str(record.exc_info[1])
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    logger = logging.getLogger("agora.request")
    logger.info(
        "%s %s -> %d (%.1fms)",
        method,
        path,
        status_code,
        duration_ms,
    )


class RequestTimer:
    def __init__(self, method: str, path: str) -> None:
        self.method = method
        self.path = path
        self.start = time.monotonic()

    def finish(self, status_code: int) -> float:
        elapsed = (time.monotonic() - self.start) * 1000
        log_request(self.method, self.path, status_code, elapsed)
        return elapsed
