"""AGORA's multi-tenant Telegram bot — one bot, N users.

Why we don't reuse ``.laia-core/gateway``: that gateway is the LAIA ARCH
gateway (single-user, multi-platform). Making it multi-tenant requires
overriding ``_session_key_for_source`` *and* its AIAgent factory *and*
sharing in-process state with the AgentPool. The plan's "subprocess o
thread" option lets us pick the simpler one — direct in-process bot using
the Telegram HTTP API, so every message resolves the AGORA user and
dispatches against the same :class:`AgentPool` the web ``/chat`` endpoint
already uses.

The bot runs as an asyncio task started from FastAPI's lifespan if
``AGORA_TELEGRAM_TOKEN`` is set. It long-polls ``getUpdates`` so it has no
inbound listener requirements (no webhooks, no public URL).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx


logger = logging.getLogger(__name__)


TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_LONG_POLL_TIMEOUT = 25
ONBOARDING_HINT = (
    "Hola — soy tu agente AGORA en Telegram. Para enlazar tu cuenta envía "
    "/link <token> con el token que generaste en la app web "
    "(`/api/user/telegram/link-token`)."
)
ALREADY_LINKED_HINT = "Ya estás enlazado. Envía /unlink para deshacer la conexión."
HELP_TEXT = (
    "Comandos disponibles:\n"
    "  /start         — saluda y muestra ayuda\n"
    "  /link <token>  — vincula tu Telegram a tu usuario AGORA\n"
    "  /unlink        — corta la vinculación\n"
    "  /help          — esta ayuda\n"
    "Cualquier otro mensaje se envía a tu agente."
)


# ---------------------------------------------------------------------------
# Telegram HTTP client (thin httpx wrapper — easy to fake in tests)
# ---------------------------------------------------------------------------


@dataclass
class TelegramUpdate:
    update_id: int
    message_text: str
    chat_id: int
    telegram_user_id: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Optional["TelegramUpdate"]:
        msg = payload.get("message") or payload.get("edited_message")
        if not msg or "text" not in msg:
            return None
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        if "id" not in chat or "id" not in sender:
            return None
        return cls(
            update_id=int(payload["update_id"]),
            message_text=str(msg["text"]),
            chat_id=int(chat["id"]),
            telegram_user_id=int(sender["id"]),
        )


class TelegramHTTPClient:
    """Thin async client for the Telegram bot API."""

    def __init__(self, token: str, *, base_url: str = TELEGRAM_API_BASE,
                 http: httpx.AsyncClient | None = None) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._http_owned = http is None
        self._http = http or httpx.AsyncClient(timeout=DEFAULT_LONG_POLL_TIMEOUT + 5)

    async def get_updates(self, offset: int, timeout: int = DEFAULT_LONG_POLL_TIMEOUT) -> list[dict[str, Any]]:
        url = f"{self.base_url}/bot{self.token}/getUpdates"
        params = {"offset": offset, "timeout": timeout}
        r = await self._http.get(url, params=params, timeout=timeout + 5)
        r.raise_for_status()
        body = r.json()
        if not body.get("ok"):
            raise RuntimeError(f"telegram getUpdates failed: {body!r}")
        return list(body.get("result", []))

    async def send_message(self, chat_id: int, text: str) -> None:
        if not text:
            return
        url = f"{self.base_url}/bot{self.token}/sendMessage"
        # Telegram caps individual messages at 4096 chars — clip with marker so
        # we never error mid-reply on long agent outputs.
        if len(text) > 4000:
            text = text[:4000] + "\n…(recortado)"
        try:
            r = await self._http.post(url, json={"chat_id": chat_id, "text": text})
            r.raise_for_status()
        except Exception as exc:
            logger.warning("telegram_gateway: send_message to %s failed: %s", chat_id, exc)

    async def close(self) -> None:
        if self._http_owned:
            await self._http.aclose()


# ---------------------------------------------------------------------------
# AgentPool dispatcher — wraps the blocking AIAgent in an executor thread
# ---------------------------------------------------------------------------


AgentTurnFn = Callable[[str, str], Awaitable[str]]


async def _agent_pool_turn(agora_user_id: str, message: str) -> str:
    """Default dispatcher: route through :class:`AgentPool` for *agora_user_id*.

    Lives here (rather than as a method) so tests can substitute their own
    callable without instantiating an entire AgentPool. The real
    implementation looks up the user's stored LLM config + agent slug and
    runs a conversation turn synchronously in an executor.
    """
    from .storage import store
    from .agent_pool import AgentPool, LLMSessionConfig
    from .agent_identity import slug_from_container
    from .chat_engine import provider_uses_oauth

    user = store.user_by_id(agora_user_id)
    if user is None:
        return "⚠ Usuario AGORA no encontrado."
    # OAuth providers (openai-codex, qwen-oauth, google-gemini-cli, …)
    # don't use a per-user api_key — credentials live in the shared
    # auth.json. Only reject when the configured provider *needs* a key.
    if not provider_uses_oauth(user.llm_provider) and not user.llm_api_key:
        return (
            "⚠ Aún no has configurado tu API key del LLM. "
            "Abre la web AGORA y rellena `LLM config` antes de chatear."
        )

    # Resolve agent_slug from the user's bound agent, if any.
    agent_slug = "unknown"
    for a in store.agents():
        if a.user_id == user.id:
            agent_slug = slug_from_container(a.container_name)
            break

    pool = _shared_pool()
    cfg = LLMSessionConfig(
        provider=user.llm_provider,
        api_key=user.llm_api_key,
        base_url=user.llm_base_url,
        model=user.llm_model,
        api_mode=user.llm_api_mode,
    )
    session = pool.get_or_create(
        user_id=user.id,
        session_id=f"telegram:{user.id}",
        agent_slug=agent_slug,
        llm_config=cfg,
    )

    def _run_sync() -> str:
        run = getattr(session.aiagent, "run_conversation", None)
        if run is None:
            return "⚠ AIAgent no disponible en este entorno (placeholder)."
        try:
            result = run(message)
        except Exception as exc:
            logger.exception("telegram_gateway: run_conversation failed")
            return f"⚠ Error procesando el mensaje: {exc}"

        # Token tracking (parity with chat_engine / scheduler / webhooks).
        try:
            from .agent_pool import record_usage_for_session
            record_usage_for_session(
                user_id=user.id, session_id=f"telegram:{user.id}",
                llm_config=cfg, run_output=result, kind="telegram",
            )
        except Exception:
            logger.debug("telegram_gateway: usage hook failed", exc_info=True)

        # Extract the user-facing text. AIAgent returns a dict; the
        # canonical reply lives in ``final_response`` (preferred) or
        # ``response``. Falling back to ``str(result)`` would dump the
        # entire run-trace dict to the chat — unreadable.
        if isinstance(result, dict):
            text = (result.get("final_response")
                    or result.get("response")
                    or "")
            if not text:
                # Last-resort: pick out the last assistant message in the
                # transcript. Keeps us robust if the agent shape changes.
                msgs = result.get("messages") or []
                for m in reversed(msgs):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        text = m.get("content") or ""
                        if text:
                            break
            return text or "(respuesta vacía del agente)"
        return str(result) if result is not None else "(respuesta vacía del agente)"

    return await asyncio.to_thread(_run_sync)


_shared_pool_instance: Any = None


def _shared_pool() -> Any:
    """Process-wide :class:`AgentPool` used by both Telegram and web chat.

    Lazily-created so importing this module doesn't pay for it. Tests can
    monkeypatch ``_shared_pool_instance`` directly.
    """
    global _shared_pool_instance
    if _shared_pool_instance is None:
        from .agent_pool import AgentPool
        _shared_pool_instance = AgentPool()
    return _shared_pool_instance


# ---------------------------------------------------------------------------
# Gateway orchestrator
# ---------------------------------------------------------------------------


class TelegramGateway:
    """Long-polling Telegram bot wired to AGORA's user / agent state.

    Construct with a ``TelegramHTTPClient`` and an optional ``turn_fn``
    callable. Call :meth:`start` from the FastAPI lifespan to spawn the
    polling task; call :meth:`stop` from the shutdown handler.
    """

    def __init__(
        self,
        client: TelegramHTTPClient,
        *,
        turn_fn: AgentTurnFn | None = None,
        poll_timeout_seconds: int = DEFAULT_LONG_POLL_TIMEOUT,
    ) -> None:
        self.client = client
        self.turn_fn = turn_fn or _agent_pool_turn
        self.poll_timeout_seconds = poll_timeout_seconds
        self._offset = 0
        self._task: asyncio.Task[Any] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_forever(), name="agora-telegram-bot")
        logger.info("telegram_gateway: started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self.client.close()
        logger.info("telegram_gateway: stopped")

    async def _run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                updates = await self.client.get_updates(self._offset, timeout=self.poll_timeout_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram_gateway: poll failed: %s — backing off", exc)
                await asyncio.sleep(2.0)
                continue
            for raw in updates:
                update = TelegramUpdate.from_payload(raw)
                if update is None:
                    self._offset = max(self._offset, int(raw.get("update_id", 0)) + 1)
                    continue
                self._offset = update.update_id + 1
                try:
                    await self._handle_update(update)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("telegram_gateway: handler crashed for update %s", update.update_id)

    async def _handle_update(self, update: TelegramUpdate) -> None:
        text = update.message_text.strip()
        if text.startswith("/start"):
            await self._handle_start(update)
            return
        if text.startswith("/help"):
            await self.client.send_message(update.chat_id, HELP_TEXT)
            return
        if text.startswith("/link"):
            await self._handle_link(update, text)
            return
        if text.startswith("/unlink"):
            await self._handle_unlink(update)
            return
        await self._handle_chat(update, text)

    async def _handle_start(self, update: TelegramUpdate) -> None:
        from .storage import store
        if store.agora_user_for_telegram(str(update.telegram_user_id)):
            await self.client.send_message(update.chat_id, ALREADY_LINKED_HINT)
        else:
            await self.client.send_message(update.chat_id, ONBOARDING_HINT)

    async def _handle_link(self, update: TelegramUpdate, text: str) -> None:
        from .storage import store
        from .telegram_links import link_token_store

        parts = text.split(maxsplit=1)
        # Telegram deep-link mode delivers `/start link_<token>` — accept both.
        if len(parts) == 1:
            await self.client.send_message(
                update.chat_id,
                "Uso: /link <token>. Genera uno en la app AGORA.",
            )
            return
        candidate = parts[1].strip()
        if candidate.startswith("link_"):
            candidate = candidate.removeprefix("link_")
        entry = link_token_store.consume(candidate)
        if entry is None:
            await self.client.send_message(
                update.chat_id,
                "Token inválido o caducado. Genera otro desde la app AGORA.",
            )
            return
        store.link_telegram_user(str(update.telegram_user_id), entry.agora_user_id)
        user = store.user_by_id(entry.agora_user_id)
        who = user.username if user else entry.agora_user_id
        await self.client.send_message(
            update.chat_id,
            f"✅ Telegram enlazado a tu cuenta AGORA ({who}). Ya puedes chatear normalmente.",
        )

    async def _handle_unlink(self, update: TelegramUpdate) -> None:
        from .storage import store
        dropped = store.unlink_telegram_user(telegram_user_id=str(update.telegram_user_id))
        if dropped:
            await self.client.send_message(
                update.chat_id,
                "🔓 Desvinculado. Envía /link <token> para volver a conectar.",
            )
        else:
            await self.client.send_message(update.chat_id, ONBOARDING_HINT)

    async def _handle_chat(self, update: TelegramUpdate, text: str) -> None:
        from .storage import store
        agora_user_id = store.agora_user_for_telegram(str(update.telegram_user_id))
        if agora_user_id is None:
            await self.client.send_message(update.chat_id, ONBOARDING_HINT)
            return
        try:
            reply = await self.turn_fn(agora_user_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("telegram_gateway: turn_fn raised")
            reply = f"⚠ Error procesando el mensaje: {exc}"
        await self.client.send_message(update.chat_id, reply or "(respuesta vacía)")


# ---------------------------------------------------------------------------
# Factory for FastAPI lifespan integration
# ---------------------------------------------------------------------------


def build_gateway_from_env() -> TelegramGateway | None:
    """Return a configured gateway if ``AGORA_TELEGRAM_TOKEN`` is set, else None.

    The caller wires ``start()`` / ``stop()`` into FastAPI's lifespan. Returning
    ``None`` is the no-token path so dev environments skip the bot cleanly.
    """
    token = os.environ.get("AGORA_TELEGRAM_TOKEN", "").strip()
    if not token:
        return None
    return TelegramGateway(TelegramHTTPClient(token))


__all__ = [
    "ONBOARDING_HINT",
    "ALREADY_LINKED_HINT",
    "HELP_TEXT",
    "TelegramHTTPClient",
    "TelegramUpdate",
    "TelegramGateway",
    "build_gateway_from_env",
]
