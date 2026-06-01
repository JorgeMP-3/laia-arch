"""Webhook receiver router (Fase A).

Accepts ``POST /api/webhooks/{slug}`` with an HMAC-SHA256 signature in
``X-Laia-Signature``. Validates the signature against the per-subscription
``secret``, then triggers an AGORA AIAgent for the owner with the request
body as ``{"webhook_payload": ...}`` in the prompt context.

The trigger is **synchronous** for v0.3 — we wait for the agent's reply
and echo a truncated preview. For very long-running webhooks the caller
should accept the 30s timeout and trust the audit log.
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets as _secrets
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def generate_secret() -> str:
    """Cryptographically strong secret for HMAC. 32 bytes → 64 hex chars."""
    return _secrets.token_hex(32)


def compute_hmac(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()


def constant_time_compare(expected: str, given: str) -> bool:
    return hmac.compare_digest(expected.encode("utf-8"), given.encode("utf-8"))


@router.post("/{slug}")
async def receive_webhook(
    slug: str,
    request: Request,
    x_laia_signature: str | None = Header(default=None, alias="X-Laia-Signature"),
):
    """Handle POST /{slug}."""
    body = await request.body()
    if len(body) > 64 * 1024:
        raise HTTPException(status_code=413, detail="payload too large")

    from .storage import store
    sub = store.get_webhook_by_slug(slug)
    if sub is None:
        # Don't leak existence — 404 looks the same as 401.
        raise HTTPException(status_code=404, detail="webhook not found")

    if x_laia_signature is None:
        raise HTTPException(status_code=401, detail="missing X-Laia-Signature")
    expected = compute_hmac(sub.secret, body)
    if not constant_time_compare(expected, x_laia_signature):
        store.update_webhook(
            sub.id, last_status="signature_invalid",
            triggers_total=sub.triggers_total,  # don't bump on invalid
        )
        raise HTTPException(status_code=401, detail="invalid signature")

    # Parse body (best-effort JSON; else expose as raw text).
    try:
        payload: Any = json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        payload = {"raw": body.decode("utf-8", errors="replace")[:4096]}

    # Trigger AIAgent for the owner. Sync: blocks up to 30s.
    response_preview: str | None = None
    error: str | None = None
    try:
        from .agent_pool import LLMSessionConfig
        from .chat_engine import get_pool
        user = store.user_by_id(sub.user_id)
        if user is None:
            raise RuntimeError(f"owner {sub.user_id} not found")
        cfg = LLMSessionConfig(
            provider=user.llm_provider, api_key=user.llm_api_key,
            base_url=user.llm_base_url, model=user.llm_model,
            api_mode=user.llm_api_mode,
        )
        pool = get_pool()
        session_id = f"webhook-{sub.id}-{sub.triggers_total}"
        session = pool.get_or_create(
            user_id=user.id, session_id=session_id,
            agent_slug=user.username, llm_config=cfg,
        )
        try:
            wrapped_prompt = (
                f"{sub.prompt}\n\nWebhook payload:\n```json\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)[:4096]}\n```"
            )
            run = getattr(session.aiagent, "run_conversation", None)
            if run is None:
                raise RuntimeError("AIAgent has no run_conversation")
            result = run(wrapped_prompt)
            try:
                from .agent_pool import record_usage_for_session
                record_usage_for_session(
                    user_id=user.id, session_id=session_id,
                    llm_config=cfg, run_output=result, kind="webhook",
                )
            except Exception:
                logger.debug("webhook: usage hook failed", exc_info=True)
            if isinstance(result, dict):
                response_preview = (result.get("response") or "")[:500]
            else:
                response_preview = str(result)[:500]
        finally:
            pool.evict(user.id, session_id)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("webhook %s trigger failed", slug)

    from .models import now_iso
    store.update_webhook(
        sub.id,
        last_trigger_at=now_iso(),
        last_status="ok" if error is None else f"error:{error[:200]}",
        triggers_total=sub.triggers_total + 1,
    )
    try:
        from .models import Event, new_id
        store.record_event(Event(
            id=new_id("evt"),
            event_type="webhook_received",
            actor_id=sub.user_id,
            summary=f"webhook {slug} → {'ok' if error is None else 'error'}",
        ))
    except Exception:
        pass

    if error is not None:
        return {"ok": False, "error": error}
    return {"ok": True, "response_preview": response_preview}
