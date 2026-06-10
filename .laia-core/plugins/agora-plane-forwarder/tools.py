"""Plane tools for AGORA (agora-plane-forwarder plugin).

Four thin handlers over the satellite's ``laia_plane_bridge.client.PlaneClient``
(the single source of truth for Plane's REST contract — S6 §3.1). Handlers are
async and registered ``is_async=True``; the registry dispatches them as
``entry.handler(args, **kwargs)`` and bridges to the sync path via
``model_tools._run_async`` (same pattern as ``vision_analyze``), so there is no
nested ``asyncio.run``. Every call emits one audit line on ``agora.plane.audit``.

Config (read per call, so ops changes need no restart):
- ``LAIA_PLANE_BASE_URL``   default ``http://10.99.0.56:80`` (LXD bridge — never the edge)
- ``LAIA_PLANE_WORKSPACE``  workspace slug (required; no guessing)
- ``LAIA_PLANE_API_KEY_FILE`` default ``/etc/laia/plane-api-key`` (0600, RO mount
  from /srv/laia/agora/secrets/ — generated and held by the operator, HITL)

Until the token/package are provisioned the tools answer with a structured
``tool_error`` instead of breaking the agent.
"""

from __future__ import annotations

import json as _json
import logging
import os
from pathlib import Path
from typing import Any

try:  # satellite package, installed at deploy time (S6: installable package)
    from laia_plane_bridge.client import PlaneClient, PlaneClientError
except Exception:  # pragma: no cover - exercised via _bridge_missing tests
    PlaneClient = None  # type: ignore[assignment]
    PlaneClientError = Exception  # type: ignore[assignment]

try:
    from tools.registry import tool_error, tool_result
except Exception:  # pragma: no cover - outside .laia-core (tests, dev shells)
    # Faithful local fallbacks (same output shape as tools/registry.py) so the
    # module imports anywhere; inside laia-agora the real registry wins.
    def tool_error(message, **extra) -> str:  # type: ignore[misc]
        out = {"error": str(message)}
        out.update(extra)
        return _json.dumps(out, ensure_ascii=False)

    def tool_result(data=None, **kwargs) -> str:  # type: ignore[misc]
        if data is not None:
            return _json.dumps(data, ensure_ascii=False)
        return _json.dumps(kwargs, ensure_ascii=False)

logger = logging.getLogger(__name__)
_audit = logging.getLogger("agora.plane.audit")

DEFAULT_BASE_URL = "http://10.99.0.56:80"
DEFAULT_API_KEY_FILE = "/etc/laia/plane-api-key"


def _api_key() -> str | None:
    path = Path(os.environ.get("LAIA_PLANE_API_KEY_FILE", DEFAULT_API_KEY_FILE))
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _workspace() -> str | None:
    return os.environ.get("LAIA_PLANE_WORKSPACE") or None


def check_plane_available() -> bool:
    """Gate for the tool registry: package + token + workspace present."""
    return PlaneClient is not None and _api_key() is not None and _workspace() is not None


def _unavailable_reason() -> str:
    if PlaneClient is None:
        return ("laia_plane_bridge is not installed in this environment "
                "(satellite package; installed at deploy time)")
    if _api_key() is None:
        return ("Plane bot token not provisioned at "
                f"{os.environ.get('LAIA_PLANE_API_KEY_FILE', DEFAULT_API_KEY_FILE)} "
                "(HITL: the operator creates it)")
    if _workspace() is None:
        return "LAIA_PLANE_WORKSPACE is not set"
    return "plane tools unavailable"


def _make_client():
    """Client per call — cheap (one short REST op) and config stays live.
    Overridable in tests."""
    return PlaneClient(
        os.environ.get("LAIA_PLANE_BASE_URL", DEFAULT_BASE_URL),
        _api_key(),
        _workspace(),
    )


# test seam: tests replace this with a factory returning a mocked client
_client_factory = _make_client


async def _call(tool: str, op_name: str, op, **audit_fields: Any) -> str:
    """Run one async client op, with audit + errors. Awaited by the registry
    (``is_async=True``) — never spins its own event loop (would crash under the
    gateway's running loop)."""
    if not check_plane_available():
        reason = _unavailable_reason()
        _audit.info("plane_tool tool=%s status=unavailable reason=%s", tool, reason)
        return tool_error(reason)

    try:
        async with _client_factory() as client:
            out = await op(client)
    except PlaneClientError as exc:
        _audit.info("plane_tool tool=%s op=%s status=error err=%s",
                    tool, op_name, exc)
        return tool_error(f"Plane API error: {exc}")
    except Exception as exc:  # never crash the agent loop
        logger.exception("plane tool %s failed", tool)
        _audit.info("plane_tool tool=%s op=%s status=crash err=%s",
                    tool, op_name, exc)
        return tool_error(f"plane tool failed: {type(exc).__name__}: {exc}")

    _audit.info("plane_tool tool=%s op=%s status=ok %s", tool, op_name,
                " ".join(f"{k}={v}" for k, v in audit_fields.items()))
    return tool_result(out)


# ── handlers ─────────────────────────────────────────────────────────────────

async def handle_plane_create_work_item(args: dict, **_: Any) -> str:
    project_id = args.get("project_id", "")
    name = args.get("name", "")
    if not project_id or not name:
        return tool_error("project_id and name are required")
    description_html = args.get("description_html")
    return await _call(
        "plane_create_work_item", "create",
        lambda c: c.create_work_item(project_id, name,
                                     description_html=description_html),
        project=project_id)


async def handle_plane_comment(args: dict, **_: Any) -> str:
    project_id = args.get("project_id", "")
    work_item_id = args.get("work_item_id", "")
    comment_html = args.get("comment_html", "")
    if not project_id or not work_item_id or not comment_html:
        return tool_error("project_id, work_item_id and comment_html are required")
    return await _call(
        "plane_comment", "comment",
        lambda c: c.add_comment(project_id, work_item_id, comment_html),
        project=project_id, work_item=work_item_id)


async def handle_plane_update_state(args: dict, **_: Any) -> str:
    project_id = args.get("project_id", "")
    work_item_id = args.get("work_item_id", "")
    state_id = args.get("state_id", "")
    if not project_id or not work_item_id or not state_id:
        return tool_error("project_id, work_item_id and state_id are required")
    return await _call(
        "plane_update_state", "update",
        lambda c: c.update_work_item(project_id, work_item_id,
                                     {"state": state_id}),
        project=project_id, work_item=work_item_id, state=state_id)


async def handle_plane_attach(args: dict, **_: Any) -> str:
    project_id = args.get("project_id", "")
    work_item_id = args.get("work_item_id", "")
    url = args.get("url", "")
    if not project_id or not work_item_id or not url:
        return tool_error("project_id, work_item_id and url are required")
    title = args.get("title")
    return await _call(
        "plane_attach", "attach",
        lambda c: c.add_link(project_id, work_item_id, url, title=title),
        project=project_id, work_item=work_item_id)


# ── schemas (tool registry) ──────────────────────────────────────────────────

_ID = {"type": "string", "description": "Plane UUID."}

PLANE_CREATE_WORK_ITEM_SCHEMA: dict[str, Any] = {
    "name": "plane_create_work_item",
    "description": (
        "Crea un work item (campaña/tarea) en un project de Plane de Doyouwin. "
        "Usa IDs de Plane (UUID), no nombres."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": _ID,
            "name": {"type": "string", "description": "Título del work item."},
            "description_html": {"type": "string",
                                 "description": "Descripción (HTML) opcional."},
        },
        "required": ["project_id", "name"],
    },
}

PLANE_COMMENT_SCHEMA: dict[str, Any] = {
    "name": "plane_comment",
    "description": "Añade un comentario (HTML) a un work item de Plane.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": _ID,
            "work_item_id": _ID,
            "comment_html": {"type": "string", "description": "Cuerpo HTML."},
        },
        "required": ["project_id", "work_item_id", "comment_html"],
    },
}

PLANE_UPDATE_STATE_SCHEMA: dict[str, Any] = {
    "name": "plane_update_state",
    "description": (
        "Mueve un work item de Plane a otro estado. Requiere el state_id "
        "(UUID del estado en ese project); la resolución nombre→id llegará "
        "con PlaneClient.list_states."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": _ID,
            "work_item_id": _ID,
            "state_id": _ID,
        },
        "required": ["project_id", "work_item_id", "state_id"],
    },
}

PLANE_ATTACH_SCHEMA: dict[str, Any] = {
    "name": "plane_attach",
    "description": (
        "Adjunta un enlace (URL con título opcional) a un work item de Plane — "
        "p. ej. un render de Grapheus publicado en almacenamiento."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": _ID,
            "work_item_id": _ID,
            "url": {"type": "string", "description": "URL a adjuntar."},
            "title": {"type": "string", "description": "Título visible."},
        },
        "required": ["project_id", "work_item_id", "url"],
    },
}
