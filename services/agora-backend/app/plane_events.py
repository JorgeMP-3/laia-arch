"""Inbound Plane events intake (S6 hybrid, minimal Core endpoint).

``POST /api/plane/events`` receives the *normalized* event that the satellite
bridge (laia-plane-bridge, B1) forwards after verifying Plane's HMAC and
deduplicating deliveries. Body = the bridge's NormalizedEvent: short ids and
labels only, never the raw Plane payload (it may carry client data).

Auth calques laia-executor: a static Bearer token compared with
``hmac.compare_digest``, read from a 0600 file (``AGORA_PLANE_EVENTS_TOKEN_FILE``,
default ``/etc/laia/plane-events-token``) mounted from
``/srv/laia/agora/secrets/`` — generated and held by the operator (HITL).
Missing/empty token file → 503 on every request (fail loud, never open).

v1 deliberately does NOT touch the engine: it validates, audit-logs and
records an ``Event`` so the orchestration layer (plan fullauto F4) has a
durable feed to build on. Distinct from the generic ``/api/webhooks/{slug}``
receiver, which fires a synchronous LLM conversation per delivery — board
events must stay cheap and deterministic.
"""

from __future__ import annotations

import hmac
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)
_audit = logging.getLogger("agora.plane.events")

router = APIRouter(prefix="/api/plane", tags=["plane"])

MAX_BODY_BYTES = 64 * 1024  # normalized events are tiny; bigger is misuse

DEFAULT_TOKEN_FILE = "/etc/laia/plane-events-token"

_REQUIRED_FIELDS = ("delivery", "event", "action")


def _expected_token() -> str | None:
    """Read the static token per request (tiny file; ops changes apply live)."""
    path = Path(os.environ.get("AGORA_PLANE_EVENTS_TOKEN_FILE", DEFAULT_TOKEN_FILE))
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


@router.post("/events", status_code=202)
async def receive_plane_event(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = _expected_token()
    if expected is None:
        # Provisioning gap is an operator problem, never an open door.
        raise HTTPException(status_code=503, detail="plane events intake not provisioned")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    presented = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=403, detail="invalid bearer token")

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    try:
        import json
        event = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    missing = [f for f in _REQUIRED_FIELDS
               if not isinstance(event.get(f), str) or not event.get(f)]
    if missing:
        raise HTTPException(status_code=422,
                            detail=f"missing/invalid fields: {missing}")

    _audit.info(
        "plane_event delivery=%s event=%s action=%s project=%s work_item=%s state=%s actor=%s",
        event.get("delivery"), event.get("event"), event.get("action"),
        event.get("project_id"), event.get("work_item_id"),
        event.get("state"), event.get("actor"),
    )

    try:
        from .models import Event
        from .storage import store
        store.record_event(Event(
            event_type="plane_event",
            actor_id=None,  # board events come from the team, not an AGORA user
            summary=(f"plane {event.get('event')}/{event.get('action')} "
                     f"item={event.get('work_item_id')} state={event.get('state')}"),
            payload={k: event.get(k) for k in (
                "delivery", "event", "action", "workspace_id", "project_id",
                "work_item_id", "title", "state", "actor")},
        ))
    except Exception:
        # The audit line above already captured it; storage hiccups must not
        # make the bridge retry forever.
        logger.exception("plane_event store write failed")

    return {"ok": True, "delivery": event["delivery"]}
