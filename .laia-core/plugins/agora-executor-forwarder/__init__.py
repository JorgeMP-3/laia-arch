"""AGORA executor forwarder plugin.

This plugin lives inside the laia-agora orchestrator container. Each time the
in-process AIAgent decides to invoke a tool that is on the "executor side"
(filesystem and shell), the plugin's ``pre_tool_call`` hook intercepts the
call, performs an HTTP POST to the user's ``laia-executor`` container, and
returns the result via the ``action="replace"`` directive — making the LLM
see the remote-executed result as if the tool had run locally.

Tools that are network-bound or use AGORA's shared API keys (web_search,
vision, image_gen, browser, fetch_url, workspace_* for the collective
workspace, etc.) are NOT forwarded — they run inside laia-agora.

Per-session context is injected by AGORA before invoking the AIAgent via
:func:`configure_session` / :func:`clear_session`. The forwarder uses a
``threading.local`` so concurrent AIAgent sessions (each in its own thread)
each see their own ``agent_slug`` / ``container_ip`` / ``api_token``.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

try:
    import httpx
except Exception:  # pragma: no cover - executor side may not have httpx in tests
    httpx = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# Tools whose execution requires the user's filesystem / shell. These get
# forwarded to laia-executor in the user's container.
EXECUTOR_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "write_file",
    "apply_patch",
    "list_dir",
    "glob",
    "grep",
    "bash",
    # NOTE: "terminal" was previously in this set as a legacy alias but
    # neither .laia-core/tools/registry.py nor the executor registry
    # registers that name — the actual tool is "bash". Removed 2026-05.
    "delete_file",
    "move_file",
    "make_dir",
    # Private workspace tools — namespaced so the LLM can pick the
    # right one for personal vs collective memory.
    "private_workspace_search",
    "private_workspace_add_node",
    "private_workspace_find_related",
    "private_workspace_read_node",
})


# Thread-local session context (per-AIAgent thread).
class _SessionContext(threading.local):
    agent_slug: Optional[str] = None
    container_ip: Optional[str] = None
    api_token: Optional[str] = None
    port: int = 9091
    timeout_seconds: float = 30.0


_session_ctx = _SessionContext()


# Per-tool timeout overrides (seconds). Tools that legitimately take longer
# (`apt update`, builds, big patches) need more headroom than the 30s default;
# anything not listed falls back to ``_session_ctx.timeout_seconds``. Matches
# the executor's own ``BASH_TIMEOUT_DEFAULT=120`` (and MAX=600), so we leave a
# small safety margin past the bash worst case.
EXECUTOR_TOOL_TIMEOUTS: Dict[str, float] = {
    "bash": 180.0,
    "apply_patch": 60.0,
    "private_workspace_search": 60.0,
    "private_workspace_find_related": 60.0,
}


def _timeout_for(tool_name: str) -> float:
    override = EXECUTOR_TOOL_TIMEOUTS.get(tool_name)
    if override is not None:
        return override
    return _session_ctx.timeout_seconds or 30.0


def configure_session(
    *,
    agent_slug: str,
    container_ip: str,
    api_token: str,
    port: int = 9091,
    timeout_seconds: float = 30.0,
) -> None:
    """Attach forwarder context to the current thread.

    AGORA must call this before invoking ``AIAgent.run_conversation`` for
    a given session; the plugin uses these values to route tool calls to
    the right user's executor.
    """
    _session_ctx.agent_slug = agent_slug
    _session_ctx.container_ip = container_ip
    _session_ctx.api_token = api_token
    _session_ctx.port = port
    _session_ctx.timeout_seconds = timeout_seconds


def clear_session() -> None:
    """Drop forwarder context from the current thread."""
    _session_ctx.agent_slug = None
    _session_ctx.container_ip = None
    _session_ctx.api_token = None


def _on_pre_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
) -> Optional[Dict[str, Any]]:
    """``pre_tool_call`` hook handler.

    Returns a ``replace`` directive carrying the remote executor's response
    when ``tool_name`` is in :data:`EXECUTOR_TOOLS` AND a session context
    is configured. Returns ``None`` otherwise, letting the AIAgent execute
    the tool locally inside laia-agora.
    """
    if tool_name not in EXECUTOR_TOOLS:
        return None

    container_ip = _session_ctx.container_ip
    api_token = _session_ctx.api_token
    if not container_ip or not api_token:
        # No session context — fall through to local execution. This is the
        # safe default for tests and for any caller that isn't AGORA.
        return None

    if httpx is None:
        logger.error("agora-executor-forwarder: httpx not installed")
        return {"action": "replace", "message": json.dumps(
            {"ok": False, "error": "executor forwarder unavailable: httpx missing"}
        )}

    url = f"http://{container_ip}:{_session_ctx.port}/exec"
    payload = {
        "tool": tool_name,
        "args": args or {},
        "request_id": tool_call_id or task_id or "unknown",
    }
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        response = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=_timeout_for(tool_name),
        )
    except httpx.TimeoutException:
        result_str = json.dumps({"ok": False, "error": "executor timeout"})
        return {"action": "replace", "message": result_str}
    except Exception as exc:  # network failure, executor down, etc.
        logger.warning("forwarder %s → %s failed: %s", tool_name, container_ip, exc)
        result_str = json.dumps({"ok": False, "error": f"executor request failed: {exc}"})
        return {"action": "replace", "message": result_str}

    if response.status_code != 200:
        body = (response.text or "")[:500]
        result_str = json.dumps(
            {"ok": False, "error": f"executor returned {response.status_code}: {body}"}
        )
        return {"action": "replace", "message": result_str}

    try:
        body = response.json()
    except Exception:
        body = {"ok": False, "error": "executor returned non-JSON"}

    # The executor returns {ok, result|error, request_id}.
    # We expose `result` (or the full error envelope) to the LLM, so the
    # tool's downstream consumer sees a normal-looking string.
    if body.get("ok"):
        msg = body.get("result")
        if not isinstance(msg, str):
            msg = json.dumps(body)
    else:
        msg = json.dumps({"ok": False, "error": body.get("error", "unknown")})

    return {"action": "replace", "message": msg}


def _local_stub_message() -> str:
    """Result returned if the LLM invokes a forwarded tool without session ctx.

    The plugin's whole purpose is to remote-execute these tools. If we end up
    in the local handler it means AGORA forgot to call
    :func:`configure_session` (probably a bug in the surrounding code). Return
    a clear, structured error instead of crashing or pretending it worked.
    """
    return json.dumps(
        {
            "ok": False,
            "error": (
                "private_workspace_* / file / bash tools are forwarded to the "
                "user's laia-executor; this AGORA session has no executor "
                "context configured (configure_session was not called)."
            ),
        }
    )


def _stub_handler(**_kwargs: Any) -> str:
    return _local_stub_message()


PRIVATE_WORKSPACE_TOOLSET = "workspace"


PRIVATE_WORKSPACE_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "name": "private_workspace_search",
        "description": (
            "Busca nodos en el workspace privado del usuario (almacenado en su "
            "container). Usar para memoria personal — para el workspace "
            "colectivo compartido entre usuarios usa `workspace_search_nodes`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda FTS."},
                "limit": {"type": "integer", "description": "Resultados máximos.", "default": 8},
                "kind": {"type": "string", "description": "Filtrar por kind (`topic`, `doc`, ...)."},
                "include_index": {"type": "boolean", "description": "Incluir el nodo index.", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "private_workspace_read_node",
        "description": (
            "Lee un nodo del workspace privado del usuario por slug, filename, "
            "alias o id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Slug, filename, alias o id del nodo."},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "private_workspace_add_node",
        "description": (
            "Crea o actualiza un nodo en el workspace privado del usuario. Para "
            "el workspace colectivo usa `workspace_upsert_node`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug estable del nodo."},
                "title": {"type": "string", "description": "Título del nodo."},
                "kind": {"type": "string", "description": "Tipo de nodo (`doc`, `topic`, `important`, ...).", "default": "doc"},
                "summary": {"type": "string", "description": "Resumen breve."},
                "body": {"type": "string", "description": "Cuerpo en Markdown."},
                "status": {"type": "string", "description": "Estado del nodo.", "default": "active"},
                "parent": {"type": "string", "description": "Slug/filename/id del nodo padre."},
                "aliases": {"type": "array", "items": {"type": "string"}, "description": "Aliases adicionales."},
                "filename": {"type": "string", "description": "Filename derivado opcional."},
            },
            "required": ["slug", "title"],
        },
    },
    {
        "name": "private_workspace_find_related",
        "description": (
            "Devuelve los nodos vecinos (conectados por algún edge) de un nodo "
            "en el workspace privado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Slug, filename, alias o id del nodo origen."},
                "limit": {"type": "integer", "description": "Vecinos máximos.", "default": 10},
            },
            "required": ["ref"],
        },
    },
)


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    # Register the private_workspace_* schemas so the LLM sees them in its
    # tool surface. The real execution lives in laia-executor; the
    # ``pre_tool_call`` hook above forwards every call before this local
    # stub ever runs.
    for schema in PRIVATE_WORKSPACE_TOOL_SCHEMAS:
        try:
            ctx.register_tool(
                name=schema["name"],
                toolset=PRIVATE_WORKSPACE_TOOLSET,
                schema=schema,
                handler=_stub_handler,
                emoji="🧠",
            )
        except Exception as exc:  # noqa: BLE001 — keep plugin load resilient
            logger.warning(
                "agora-executor-forwarder: failed to register %s: %s",
                schema["name"], exc,
            )


__all__ = [
    "EXECUTOR_TOOLS",
    "PRIVATE_WORKSPACE_TOOL_SCHEMAS",
    "configure_session",
    "clear_session",
    "register",
]
