"""Tiny TTL cache used by :class:`ctl.client.AgoraClient`.

We don't pull in cachetools because we only need one cache pattern: GETs
keyed by ``(method, path)`` with a short TTL, plus an ``invalidate``
that matches a path prefix so write paths can wipe stale reads.
"""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Map ``(method, path)`` → ``(value, expires_at)``.

    Not thread-safe. Textual's event loop is single-threaded so we don't
    pay the cost of a lock.
    """

    def __init__(self, default_ttl_seconds: float = 5.0) -> None:
        self.default_ttl = default_ttl_seconds
        self._store: dict[tuple[str, str], tuple[Any, float]] = {}

    def get(self, method: str, path: str) -> Any | None:
        key = (method.upper(), path)
        hit = self._store.get(key)
        if hit is None:
            return None
        value, expires = hit
        if expires < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    def set(self, method: str, path: str, value: Any,
            ttl: float | None = None) -> None:
        key = (method.upper(), path)
        expires = time.monotonic() + (ttl if ttl is not None else self.default_ttl)
        self._store[key] = (value, expires)

    def invalidate(self, *, path_prefix: str | None = None,
                   method: str | None = None) -> int:
        """Drop entries whose path starts with ``path_prefix`` (or all if
        omitted). Returns the number removed."""
        before = len(self._store)
        if path_prefix is None and method is None:
            self._store.clear()
            return before
        keys = list(self._store.keys())
        for m, p in keys:
            if method is not None and m != method.upper():
                continue
            if path_prefix is not None and not p.startswith(path_prefix):
                continue
            self._store.pop((m, p), None)
        return before - len(self._store)

    def __len__(self) -> int:
        return len(self._store)
