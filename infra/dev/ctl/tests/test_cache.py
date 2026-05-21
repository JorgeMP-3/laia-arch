"""Unit tests for :class:`ctl.cache.TTLCache`."""

from __future__ import annotations

import time

from ctl.cache import TTLCache


def test_set_get_roundtrip():
    c = TTLCache()
    c.set("GET", "/api/admin/users", {"users": [1, 2, 3]})
    assert c.get("GET", "/api/admin/users") == {"users": [1, 2, 3]}


def test_get_returns_none_for_unset():
    c = TTLCache()
    assert c.get("GET", "/missing") is None


def test_ttl_expires():
    c = TTLCache(default_ttl_seconds=0.01)
    c.set("GET", "/x", 1)
    time.sleep(0.05)
    assert c.get("GET", "/x") is None


def test_invalidate_by_prefix():
    c = TTLCache()
    c.set("GET", "/api/admin/users", 1)
    c.set("GET", "/api/admin/usage", 2)
    c.set("GET", "/api/me", 3)
    removed = c.invalidate(path_prefix="/api/admin")
    assert removed == 2
    assert c.get("GET", "/api/admin/users") is None
    assert c.get("GET", "/api/me") == 3


def test_invalidate_all():
    c = TTLCache()
    c.set("GET", "/a", 1)
    c.set("GET", "/b", 2)
    assert c.invalidate() == 2
    assert len(c) == 0


def test_method_case_insensitive():
    c = TTLCache()
    c.set("get", "/a", 1)
    assert c.get("GET", "/a") == 1


def test_invalidate_by_method_only():
    c = TTLCache()
    c.set("GET", "/a", 1)
    c.set("POST", "/a", 2)
    removed = c.invalidate(method="POST")
    assert removed == 1
    assert c.get("GET", "/a") == 1
