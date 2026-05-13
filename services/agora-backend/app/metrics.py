from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._requests_total = 0
        self._requests_by_status: dict[int, int] = defaultdict(int)
        self._requests_by_endpoint: dict[str, int] = defaultdict(int)
        self._durations: list[float] = []
        self._last_errors: list[dict[str, Any]] = []

    def record(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._requests_total += 1
            self._requests_by_status[status_code] += 1
            endpoint = f"{method} {path.split('?')[0]}"
            self._requests_by_endpoint[endpoint] += 1
            self._durations.append(duration_ms)
            if self._durations:
                self._durations = self._durations[-1000:]
            if status_code >= 500:
                self._last_errors.append({
                    "ts": time.time(),
                    "endpoint": endpoint,
                    "status": status_code,
                    "duration_ms": duration_ms,
                })
                if len(self._last_errors) > 20:
                    self._last_errors = self._last_errors[-20:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._started_at
            avg_duration = sum(self._durations) / len(self._durations) if self._durations else 0
            top: list[tuple[str, int]] = sorted(
                self._requests_by_endpoint.items(), key=lambda x: x[1], reverse=True
            )[:10]
            return {
                "uptime_seconds": round(uptime, 1),
                "requests_total": self._requests_total,
                "requests_by_status": dict(self._requests_by_status),
                "avg_duration_ms": round(avg_duration, 2),
                "top_endpoints": [{"endpoint": e, "count": c} for e, c in top],
                "last_errors": self._last_errors[-5:] if self._last_errors else [],
            }


metrics = Metrics()
