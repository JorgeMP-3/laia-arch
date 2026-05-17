"""Storage + endpoint tests for the AGORA ↔ Telegram link table."""

from __future__ import annotations

import pytest

from app.storage import store


# ---------------------------------------------------------------------------
# Storage layer
# ---------------------------------------------------------------------------


def _seed_user(username: str = "jorge") -> str:
    """Create (or reuse) a user and return its id."""
    existing = store.user_by_username(username)
    if existing:
        return existing.id
    from app.models import User, now_iso, new_id

    user = User(
        id=new_id("usr"),
        username=username,
        display_name=username.title(),
        role="employee",
        active=True,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    store.save_user(user)
    return user.id


def test_link_and_lookup_telegram_user():
    uid = _seed_user("tg-link-jorge")
    store.link_telegram_user("1234567", uid)
    assert store.agora_user_for_telegram("1234567") == uid
    assert "1234567" in store.telegram_ids_for_user(uid)


def test_link_upserts_on_conflict():
    uid1 = _seed_user("tg-upsert-a")
    uid2 = _seed_user("tg-upsert-b")
    store.link_telegram_user("9000001", uid1)
    store.link_telegram_user("9000001", uid2)
    assert store.agora_user_for_telegram("9000001") == uid2


def test_unlink_by_telegram_id():
    uid = _seed_user("tg-unlink-a")
    store.link_telegram_user("9000002", uid)
    dropped = store.unlink_telegram_user(telegram_user_id="9000002")
    assert dropped == 1
    assert store.agora_user_for_telegram("9000002") is None


def test_unlink_by_agora_id_removes_all():
    uid = _seed_user("tg-unlink-many")
    store.link_telegram_user("9100001", uid)
    store.link_telegram_user("9100002", uid)
    dropped = store.unlink_telegram_user(agora_user_id=uid)
    assert dropped == 2
    assert store.telegram_ids_for_user(uid) == []


def test_unlink_requires_one_identifier():
    with pytest.raises(ValueError):
        store.unlink_telegram_user()


# ---------------------------------------------------------------------------
# Ephemeral link-token store
# ---------------------------------------------------------------------------


def test_link_token_issue_consume_roundtrip():
    from app.telegram_links import TelegramLinkTokenStore

    s = TelegramLinkTokenStore(ttl_seconds=60)
    issued = s.issue("user-abc")
    assert issued.token
    assert issued.agora_user_id == "user-abc"
    consumed = s.consume(issued.token)
    assert consumed is not None
    assert consumed.agora_user_id == "user-abc"
    # Second consume is a no-op (token already burned).
    assert s.consume(issued.token) is None


def test_link_token_supersedes_previous():
    from app.telegram_links import TelegramLinkTokenStore

    s = TelegramLinkTokenStore(ttl_seconds=60)
    first = s.issue("user-supersede")
    second = s.issue("user-supersede")
    assert first.token != second.token
    # Old token no longer consumable.
    assert s.consume(first.token) is None
    assert s.consume(second.token) is not None


def test_link_token_ttl_expiration():
    from app.telegram_links import TelegramLinkTokenStore

    s = TelegramLinkTokenStore(ttl_seconds=0)  # immediate expiration
    issued = s.issue("user-ttl")
    assert s.consume(issued.token) is None  # expired before consumption


def test_link_token_revoke_for_user():
    from app.telegram_links import TelegramLinkTokenStore

    s = TelegramLinkTokenStore(ttl_seconds=60)
    issued = s.issue("user-revoke")
    s.revoke_for_user("user-revoke")
    assert s.consume(issued.token) is None


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


from fastapi.testclient import TestClient
from app.main import app

ADMIN_TOKEN = "dev-admin-token"
ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
client = TestClient(app)


def _login(username: str, password: str) -> str:
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_user(username: str) -> tuple[str, str]:
    r = client.post(
        "/api/users",
        headers=ADMIN,
        json={"username": username, "display_name": username.title()},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"]["id"], body["password"]


def test_endpoint_issue_link_token():
    uid, pw = _create_user("tg_endpoint_a")
    token = _login("tg_endpoint_a", pw)
    r = client.post("/api/user/telegram/link-token", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"]
    assert body["expires_in_seconds"] > 0


def test_endpoint_link_then_status_then_delete():
    uid, pw = _create_user("tg_endpoint_b")
    token = _login("tg_endpoint_b", pw)
    auth = {"Authorization": f"Bearer {token}"}

    # Initially unlinked.
    r = client.get("/api/user/telegram/link", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"linked": False, "telegram_user_ids": []}

    # Link directly via storage to simulate the bot having consumed the token.
    store.link_telegram_user("tg-77001", uid)
    r = client.get("/api/user/telegram/link", headers=auth)
    body = r.json()
    assert body["linked"] is True
    assert body["telegram_user_ids"] == ["tg-77001"]

    # Delete unlinks both binding + outstanding token.
    r = client.delete("/api/user/telegram/link", headers=auth)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["dropped"] == 1

    r = client.get("/api/user/telegram/link", headers=auth)
    assert r.json() == {"linked": False, "telegram_user_ids": []}


def test_endpoint_requires_auth():
    r = client.post("/api/user/telegram/link-token")
    assert r.status_code == 401
    r = client.get("/api/user/telegram/link")
    assert r.status_code == 401
    r = client.delete("/api/user/telegram/link")
    assert r.status_code == 401
