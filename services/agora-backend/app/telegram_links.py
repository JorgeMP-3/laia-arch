"""Helpers for AGORA ↔ Telegram identity linking.

The user flow is:

1. Authenticated AGORA user calls ``POST /api/user/telegram/link-token`` and
   receives a short-lived bearer string (default TTL: 15 min).
2. The same user opens Telegram, finds the AGORA bot and sends
   ``/link <token>``.
3. The bot handler calls :func:`consume_link_token`, which atomically maps
   the token → AGORA user id and writes the binding into
   :class:`AgoraStore.link_telegram_user`.
4. From that point on, every Telegram message from that ``telegram_user_id``
   is dispatched against the bound AGORA user's session / LLM config.

Tokens live only in-process memory — fine for a single backend instance.
If we ever scale horizontally, swap for Redis (already noted in the redesign
plan as a fase-7 ``[PENDIENTE]``).
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional


DEFAULT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class IssuedLinkToken:
    token: str
    agora_user_id: str
    expires_at: float


class TelegramLinkTokenStore:
    """Thread-safe ephemeral store mapping link tokens to AGORA user ids."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._tokens: dict[str, IssuedLinkToken] = {}
        self._user_tokens: dict[str, str] = {}
        self._lock = threading.RLock()

    def issue(self, agora_user_id: str) -> IssuedLinkToken:
        """Generate a fresh token; supersedes any previous one for the user."""
        token = secrets.token_urlsafe(24)
        expires_at = time.time() + self.ttl_seconds
        issued = IssuedLinkToken(token=token, agora_user_id=agora_user_id, expires_at=expires_at)
        with self._lock:
            previous = self._user_tokens.get(agora_user_id)
            if previous and previous in self._tokens:
                self._tokens.pop(previous, None)
            self._tokens[token] = issued
            self._user_tokens[agora_user_id] = token
        return issued

    def consume(self, token: str) -> Optional[IssuedLinkToken]:
        """Atomically remove + return a valid token, or None if absent/expired."""
        with self._lock:
            self._evict_expired_locked()
            entry = self._tokens.pop(token, None)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                self._user_tokens.pop(entry.agora_user_id, None)
                return None
            self._user_tokens.pop(entry.agora_user_id, None)
            return entry

    def revoke_for_user(self, agora_user_id: str) -> None:
        """Drop any outstanding token belonging to this user."""
        with self._lock:
            token = self._user_tokens.pop(agora_user_id, None)
            if token:
                self._tokens.pop(token, None)

    def _evict_expired_locked(self) -> None:
        now = time.time()
        expired = [t for t, entry in self._tokens.items() if entry.expires_at < now]
        for t in expired:
            entry = self._tokens.pop(t, None)
            if entry is not None:
                self._user_tokens.pop(entry.agora_user_id, None)

    # Read-only inspection helpers for tests / observability.

    def size(self) -> int:
        with self._lock:
            self._evict_expired_locked()
            return len(self._tokens)


link_token_store = TelegramLinkTokenStore()
