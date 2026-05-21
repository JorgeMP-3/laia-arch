"""LAIA chat endpoint — coordinator chat surface (Fase 2).

LAIA, the coordinator, is a chat-mode rather than a separate agent
(rule ⑨ of the Documento Definitivo). Calling ``POST /api/laia/chat``
borrows an AgentSession from the shared pool under ``mode='laia'``,
which:

  * builds the system prompt from ``agent_areas[user_laia]`` — the
    persona/soul/instructions live in the same store as a regular
    user's agent area, edited by admins.
  * loads ``laia_coordinator_base`` for everyone, plus
    ``laia_coordinator_admin`` when the actor is ``agora_admin``.
  * skips marketplace materialisation (LAIA does not load the actor's
    plugins).
  * skips ``agent-self-edit`` / scheduler / delegation bindings
    (rule ⑪).

Why local execution does not violate rule ⑩
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rule ⑩ ("LAIA nunca ejecuta herramientas en ``laia-agora``; siempre en
el container del usuario que llama") in spirit forbids LAIA from having
shell / file / code-exec privileges inside ``laia-agora``. The two
``laia_coordinator_*`` toolsets satisfy the intent: every handler is a
SELECT against ``agora.db`` or a single-row INSERT into a
coordinator-scoped table (``coordinator_messages``, ``events``). None of
them read the actor's filesystem, run shell, or load Python — those
toolsets are explicitly OUT of LAIA's ``enabled_toolsets``. Routing
``agora.db`` SELECTs through the actor's executor would be
architecturally inverted: only ``laia-agora`` has the DB. So we keep
the AIAgent reasoning + the DB-bound tools local; the executor
forwarder is wired anyway but has nothing to forward.

Endpoints
~~~~~~~~~

``GET  /api/laia/inbox-count`` — admin-only.
    Per-user roll-up of LAIA's pushed messages. Stays admin-only
    because it touches every user's inbox.

``POST /api/laia/chat`` — any authenticated user.
    Body: ``{"message": str, "session_id": str | None}``.
    Streams SSE (``token``/``tool``/``done``/``error`` events). The
    toolset and the prompt persona are role-aware via the pool.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


from .auth import current_user, require_roles
from .laia_identity import LAIA_USER_ID
from .models import User


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/laia", tags=["laia"])


class LaiaChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.get("/inbox-count")
def laia_inbox_count(_: User = Depends(require_roles("agora_admin"))):
    """Per-user unread roll-up of LAIA's pushed messages.

    The admin sees who has pending mail without touching the read flag —
    the actual mark-read happens when the target user's next chat builds
    its prompt (``agent_pool._build_agent_area_prompt``).
    """
    from .storage import store
    rows = []
    for u in store.users():
        if u.id == LAIA_USER_ID:
            continue
        n = store.unread_count_for_user(u.id)
        if n > 0:
            rows.append({
                "user_id": u.id, "username": u.username,
                "unread": n,
            })
    return {"unread_by_user": rows}


@router.post("/chat")
async def laia_chat(payload: LaiaChatRequest,
                    actor: User = Depends(current_user)):
    """Talk to LAIA. Open to any authenticated user.

    Role-aware toolset:
      * ``agora_admin`` → ``laia_coordinator_base`` + ``laia_coordinator_admin``
        (8 tools total).
      * ``employee``    → ``laia_coordinator_base`` only (2 read-only tools:
        ``laia_list_users``, ``laia_workspace_search``).
      * ``agent``       → same as employee (sub-agents shouldn't get admin
        powers via coordinator chat).
    """
    return StreamingResponse(
        _stream(message=payload.message, session_id=payload.session_id,
                actor=actor),
        media_type="text/event-stream",
    )


def _sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


_STREAM_SENTINEL = object()


async def _stream(*, message: str, session_id: str | None,
                  actor: User) -> AsyncIterator[bytes]:
    from .storage import store
    from .agent_pool import LLMSessionConfig, record_usage_for_session
    from .chat_engine import get_pool

    laia = store.user_by_id(LAIA_USER_ID)
    if laia is None:
        yield _sse({"type": "error",
                    "message": f"{LAIA_USER_ID} not seeded; restart the backend"})
        return

    # Rule ⑩ alignment: the LLM credentials and usage ledger belong to the
    # actor, not the synthetic LAIA user. LAIA's own ``llm_*`` columns are
    # used as a fallback (so a fresh admin without per-user config still
    # works) and ``AGORA_DEFAULT_PROVIDER`` is the last resort.
    default_provider = os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex")
    cfg = LLMSessionConfig(
        provider=(actor.llm_provider or laia.llm_provider or default_provider),
        api_key=(actor.llm_api_key or laia.llm_api_key),
        base_url=(actor.llm_base_url or laia.llm_base_url),
        model=(actor.llm_model or laia.llm_model),
        api_mode=(actor.llm_api_mode or laia.llm_api_mode),
    )

    # Pool keys by (user_id, session_id). For LAIA chat we key under the
    # ACTOR's user_id (not LAIA_USER_ID) so each actor has isolated state,
    # and we ALWAYS pass ``mode='laia'`` so the pool builds a coordinator
    # AIAgent (LAIA persona, restricted toolset, no marketplace, no
    # self-edit). The ``session_id`` is namespaced so the actor's regular
    # PA-chat sessions and her LAIA-chat sessions never collide.
    sid = f"laia-{session_id or 'default'}"
    pool = get_pool()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _push(item: Any) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def _worker() -> None:
        try:
            session = pool.get_or_create(
                user_id=actor.id, session_id=sid,
                agent_slug="laia", llm_config=cfg,
                mode="laia", actor_role=actor.role,
            )
            ai = session.aiagent
            try:
                ai.stream_delta_callback = lambda d: _push({"type": "token", "value": str(d)}) if d else None
                ai.tool_start_callback = lambda call_id, name, args: _push(
                    {"type": "tool", "name": name, "status": "started"})
                ai.tool_complete_callback = lambda call_id, name, args, result: _push(
                    {"type": "tool", "name": name, "status": "complete"})
            except Exception:
                pass  # placeholder agents have no slots
            try:
                result = ai.run_conversation(message)
            except Exception as exc:
                _push({"type": "error", "message": f"run_conversation failed: {exc}"})
                return
            try:
                # Cost is attributed to the ACTOR, not user_laia.
                record_usage_for_session(
                    user_id=actor.id, session_id=sid,
                    llm_config=cfg, run_output=result, kind="laia-chat",
                )
            except Exception:
                pass
            payload: dict[str, Any] = {"type": "done"}
            if isinstance(result, dict):
                payload["response"] = result.get("response") or result.get("final_response") or ""
                payload["iterations"] = result.get("iterations")
            else:
                payload["response"] = str(result) if result is not None else ""
            _push(payload)
        finally:
            _push(_STREAM_SENTINEL)

    fut = loop.run_in_executor(None, _worker)
    while True:
        item = await queue.get()
        if item is _STREAM_SENTINEL:
            break
        yield _sse(item)
    try:
        await fut
    except Exception as exc:
        yield _sse({"type": "error", "message": f"worker crashed: {exc}"})


__all__ = ["router"]
