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
# The LLM emits the tool names from .laia-core/tools/registry.py (terminal,
# patch, search_files, …). The executor exposes a smaller native vocabulary
# (bash, apply_patch, grep, …) plus its own ``private_workspace_*`` tools.
# We forward by the LLM-side name and translate inside ``_translate_tool``.
EXECUTOR_TOOLS: frozenset[str] = frozenset({
    # .laia-core-side names that the LLM uses:
    "terminal",       # → executor.bash
    "patch",          # → executor.apply_patch
    "search_files",   # → executor.grep
    # Plus tools whose name already matches on both sides:
    "read_file",
    "write_file",
    "list_dir",
    "glob",
    "grep",
    "bash",
    "apply_patch",
    "delete_file",
    "move_file",
    "make_dir",
    # Private workspace tools — namespaced so the LLM can pick the
    # right one for personal vs collective memory.
    "private_workspace_search",
    "private_workspace_add_node",
    "private_workspace_find_related",
    "private_workspace_read_node",
    # Safe equivalents of the AGORA-local-denied tools (see
    # AGORA_LOCAL_DENY). These execute in the user's container instead of
    # the orchestrator's address space, so the user is root in their own
    # container and the brain stays isolated.
    "python_exec",          # replaces execute_code
    "process_start",        # replaces process.start
    "process_list",         # replaces process.list
    "process_status",       # replaces process.status
    "process_kill",         # replaces process.kill
    "cron_create",          # replaces cronjob.create
    "cron_list",            # replaces cronjob.list
    "cron_delete",          # replaces cronjob.delete
})


# Tools that MUST NOT execute locally in laia-agora regardless of the
# toolset profile. If one of these reaches the hook with an active session
# context (i.e. a real AGORA chat turn) the hook returns a ``block``
# directive carrying a clear error so the LLM doesn't keep retrying.
#
# Without an active session context (unit tests, ad-hoc callers that don't
# call ``register_context``) the hook still returns ``None`` and lets the
# AIAgent decide — those callers aren't the AGORA attack surface and a
# blanket block here would break ARCH and any non-AGORA consumer of the
# same plugin.
#
# Defense in depth: ``agent_pool.AGORA_ENABLED_TOOLSETS`` already strips
# these from the loaded toolset, so this set is a backstop in case:
#   1. The enabled_toolsets list drifts (someone adds back a toolset
#      that pulls in one of these).
#   2. A future plugin registers one of these names directly.
#   3. A toolset_distributions edit accidentally re-enables them.
AGORA_LOCAL_DENY: frozenset[str] = frozenset({
    "execute_code",        # Python eval — RCE in laia-agora
    "process",             # background subprocess spawning
    "cronjob",             # persistent jobs inside the orchestrator
    "skill_manage",        # dynamic Python loading from disk
    "delegate_task",       # spawn subagents in laia-agora
    "mixture_of_agents",   # recursive agent invocation
})


# When the LLM's tool name differs from the executor's, translate the
# {name, args} pair before posting. The forwarder is the only place we do
# this — keeps the executor lean and the .laia-core registry unchanged.
_TOOL_NAME_ALIAS: Dict[str, str] = {
    "terminal": "bash",
    "patch": "apply_patch",
    "search_files": "grep",
}


# Args accepted by each executor handler (signature inspection happens at
# call time in the executor, but pre-filtering here gives a clearer error
# and avoids round-trips when the LLM emits richer kwargs from the
# .laia-core schema). Keys missing → forward all args untouched.
_EXECUTOR_ALLOWED_ARGS: Dict[str, frozenset[str]] = {
    "bash": frozenset({"command", "cwd", "timeout", "env"}),
    "apply_patch": frozenset({"path", "old_string", "new_string", "replace_all"}),
    "grep": frozenset({"pattern", "path", "include"}),
    "glob": frozenset({"pattern", "path"}),
    "read_file": frozenset({"path", "offset", "limit"}),
    "write_file": frozenset({"path", "content"}),
    "list_dir": frozenset({"path"}),
    "delete_file": frozenset({"path"}),
    "move_file": frozenset({"src", "dst"}),
    "make_dir": frozenset({"path", "parents"}),
    # Safe equivalents (run inside the user's container):
    "python_exec": frozenset({"code", "timeout"}),
    "process_start": frozenset({"command", "name", "cwd", "env"}),
    "process_list": frozenset(),  # no args
    "process_status": frozenset({"name_or_pid", "tail_chars"}),
    "process_kill": frozenset({"name_or_pid"}),
    "cron_create": frozenset({"name", "schedule", "command", "description", "cwd"}),
    "cron_list": frozenset(),  # no args
    "cron_delete": frozenset({"name"}),
}


def _translate_tool(name: str, args: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Rename + filter args before sending to the executor.

    Idempotent: if the LLM already used the executor-side name (e.g.
    ``bash``), pass through unchanged.
    """
    target = _TOOL_NAME_ALIAS.get(name, name)
    allowed = _EXECUTOR_ALLOWED_ARGS.get(target)
    if allowed is None:
        return target, args
    filtered = {k: v for k, v in (args or {}).items() if k in allowed}
    return target, filtered


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


# ─── Cross-thread context: registry indexed by task_id ────────────────────
#
# The AIAgent ships tools through an internal ``ThreadPoolExecutor`` (see
# ``.laia-core/run_agent.py:9355``), so the ``pre_tool_call`` hook runs in
# a worker thread that did NOT call ``configure_session``. ``threading.local``
# therefore looks empty and the hook falls through to local execution.
#
# Solution: index the (slug, ip, token) tuple by ``task_id`` — that value
# does travel by value through the whole stack into the hook (run_agent.py
# passes ``task_id=effective_task_id`` to ``get_pre_tool_call_directive``
# at lines 9071 and 9541). Any thread with the same ``task_id`` can look
# it up here without depending on ``copy_context``.
#
# IMPORTANT: this module can be loaded TWICE — once by ``chat_engine`` via
# ``importlib.util.spec_from_file_location`` (registered as
# ``sys.modules["agora_executor_forwarder"]``) and once by the
# ``laia_cli.plugins`` plugin manager (under its own namespace, e.g.
# ``laia_plugins.agora_executor_forwarder``). The two copies have
# independent module globals, so a ``register_context`` on one is invisible
# to ``_on_pre_tool_call`` on the other.
#
# Trick: stash the registry dict + lock in a synthetic module under a
# well-known key in ``sys.modules``. Subsequent loads of THIS file (whatever
# the package namespace) find that stash and reuse the same objects. The
# result is a single process-wide registry shared by every copy.
import sys as _sys
import types as _types

_REGISTRY_MODULE_KEY = "_agora_executor_forwarder_shared_state"
_shared_state = _sys.modules.get(_REGISTRY_MODULE_KEY)
if _shared_state is None:
    _shared_state = _types.ModuleType(_REGISTRY_MODULE_KEY)
    _shared_state.registry = {}                  # type: ignore[attr-defined]
    _shared_state.lock = threading.RLock()       # type: ignore[attr-defined]
    _sys.modules[_REGISTRY_MODULE_KEY] = _shared_state

_context_registry: Dict[str, Dict[str, Any]] = _shared_state.registry  # type: ignore[attr-defined]
_context_registry_lock = _shared_state.lock      # type: ignore[attr-defined]

# Soft cap. The registry is normally drained turn-by-turn via
# ``unregister_context``, but a worker SIGKILL or a bug in the caller can
# leak entries. Past this size we evict the oldest insertion order entry
# and log a warning, so the leak stays bounded.
MAX_REGISTRY_SIZE = 1024


def register_context(
    task_id: str,
    *,
    agent_slug: str,
    container_ip: str,
    api_token: str,
    port: int = 9091,
    timeout_seconds: float = 30.0,
) -> None:
    """Bind a session context to ``task_id`` so ``_on_pre_tool_call`` can
    resolve it from any thread.

    ``chat_engine._worker`` must call this once per turn and pair it with
    ``unregister_context(task_id)`` in a ``finally`` block. The same
    ``task_id`` must then be passed as ``run_conversation(task_id=...)``
    so the AIAgent propagates it to the hook.
    """
    if not task_id:
        logger.warning("register_context: empty task_id ignored")
        return
    with _context_registry_lock:
        if len(_context_registry) >= MAX_REGISTRY_SIZE and task_id not in _context_registry:
            # Oldest by insertion order (dicts preserve it in py 3.7+).
            stale = next(iter(_context_registry))
            _context_registry.pop(stale, None)
            logger.warning(
                "register_context: registry hit cap (%d) — evicted stale task_id=%s",
                MAX_REGISTRY_SIZE, stale,
            )
        _context_registry[task_id] = {
            "agent_slug": agent_slug,
            "container_ip": container_ip,
            "api_token": api_token,
            "port": port,
            "timeout_seconds": timeout_seconds,
        }


def unregister_context(task_id: str) -> None:
    """Drop the entry registered with ``register_context``. Idempotent."""
    if not task_id:
        return
    with _context_registry_lock:
        _context_registry.pop(task_id, None)


def _lookup_context(task_id: str) -> Optional[Dict[str, Any]]:
    """Resolve the active context for a task_id, falling back to threading.local.

    Lookup order:
      1. ``_context_registry[task_id]`` — propagates across threads.
      2. ``_session_ctx`` (threading.local) — backward-compat for tests
         and same-thread callers that still use ``configure_session``.

    Returns ``None`` if neither has a usable (ip, token) pair.
    """
    if task_id:
        with _context_registry_lock:
            ctx = _context_registry.get(task_id)
        if ctx and ctx.get("container_ip") and ctx.get("api_token"):
            return ctx
    if _session_ctx.container_ip and _session_ctx.api_token:
        return {
            "agent_slug": _session_ctx.agent_slug,
            "container_ip": _session_ctx.container_ip,
            "api_token": _session_ctx.api_token,
            "port": _session_ctx.port,
            "timeout_seconds": _session_ctx.timeout_seconds,
        }
    return None


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
    # Resolve session context first — we need it both for the deny-list
    # decision (only enforce in AGORA chat turns, not in ARCH/tests) and
    # for the regular forward path below.
    ctx = _lookup_context(task_id)

    # Deny-list (security backstop): even if AGORA_ENABLED_TOOLSETS drifts
    # or a future plugin registers a dangerous tool, an active AGORA session
    # cannot run it locally. Block with a structured error so the LLM sees
    # the policy and stops retrying.
    if tool_name in AGORA_LOCAL_DENY and ctx is not None:
        logger.warning(
            "FWD-HOOK denied tool=%s task=%s slug=%s (AGORA_LOCAL_DENY)",
            tool_name, task_id, ctx.get("agent_slug"),
        )
        return {"action": "replace", "message": json.dumps({
            "ok": False,
            "error": (
                f"tool {tool_name!r} is disabled in AGORA per security policy. "
                "Use `terminal` or `write_file` (which forward to the user's "
                "executor container) instead of executing code in the orchestrator."
            ),
            "policy": "agora_local_deny",
        })}

    if tool_name not in EXECUTOR_TOOLS:
        return None

    logger.debug(
        "FWD-HOOK tool=%s has_ctx=%s ip=%s task=%s",
        tool_name,
        ctx is not None,
        ctx.get("container_ip") if ctx else None,
        task_id,
    )
    if ctx is None:
        # No session context for this task_id and threading.local is empty —
        # let the AIAgent run the tool locally. Safe default for tests and
        # any non-AGORA caller.
        return None

    container_ip = ctx["container_ip"]
    api_token = ctx["api_token"]
    port = ctx.get("port", 9091)
    timeout_default = ctx.get("timeout_seconds", 30.0)

    if httpx is None:
        logger.error("agora-executor-forwarder: httpx not installed")
        return {"action": "replace", "message": json.dumps(
            {"ok": False, "error": "executor forwarder unavailable: httpx missing"}
        )}

    # Translate LLM-side tool name + args to what the executor's registry
    # actually accepts. Keeps the LLM seeing the .laia-core registry vocab
    # (``terminal``, ``patch``, ``search_files``) while the executor stays
    # lean with its native handlers (``bash``, ``apply_patch``, ``grep``).
    exec_tool, exec_args = _translate_tool(tool_name, args or {})

    url = f"http://{container_ip}:{port}/exec"
    payload = {
        "tool": exec_tool,
        "args": exec_args,
        "request_id": tool_call_id or task_id or "unknown",
    }
    headers = {"Authorization": f"Bearer {api_token}"}

    # Per-tool timeout override, otherwise the ctx default.
    tool_timeout = EXECUTOR_TOOL_TIMEOUTS.get(exec_tool, timeout_default)

    # Structured audit log (A5) — every forward gets a single INFO line so
    # the operator can grep `decision=forwarded` over `/tmp/agora-backend-chat.log`.
    _audit = logging.getLogger("agora.forwarder.audit")

    try:
        response = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=tool_timeout,
        )
    except httpx.TimeoutException:
        _audit.warning(
            "tool_forward decision=timeout tool=%s exec_tool=%s slug=%s task=%s timeout=%ss",
            tool_name, exec_tool, ctx.get("agent_slug"), task_id, tool_timeout,
        )
        result_str = json.dumps({"ok": False, "error": "executor timeout"})
        return {"action": "replace", "message": result_str}
    except Exception as exc:  # network failure, executor down, etc.
        logger.warning("forwarder %s → %s failed: %s", tool_name, container_ip, exc)
        _audit.warning(
            "tool_forward decision=network_error tool=%s exec_tool=%s slug=%s task=%s err=%s",
            tool_name, exec_tool, ctx.get("agent_slug"), task_id, exc,
        )
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
        _audit.info(
            "tool_forward decision=forwarded tool=%s exec_tool=%s slug=%s task=%s status=ok",
            tool_name, exec_tool, ctx.get("agent_slug"), task_id,
        )
    else:
        msg = json.dumps({"ok": False, "error": body.get("error", "unknown")})
        _audit.info(
            "tool_forward decision=forwarded tool=%s exec_tool=%s slug=%s task=%s status=executor_error err=%s",
            tool_name, exec_tool, ctx.get("agent_slug"), task_id, body.get("error"),
        )

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


# Safe equivalents of the AGORA-local-denied tools — execute inside the
# user's container so the orchestrator stays isolated.
SAFE_EXEC_TOOLSET = "user_runtime"


SAFE_EXEC_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "name": "python_exec",
        "description": (
            "Ejecuta un snippet de Python DENTRO del container del usuario "
            "(cwd=/home/user, sin sandbox, root en su propio container). "
            "Cada llamada es un intérprete nuevo — usa `write_file` para "
            "código persistente. Para tareas largas usa `terminal` o "
            "`process_start`. Devuelve `{ok, stdout, stderr, exit_code}`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código Python (multi-línea OK)."},
                "timeout": {"type": "integer", "description": "Segundos antes de matar el proceso (default 60, max 600).", "default": 60},
            },
            "required": ["code"],
        },
    },
    {
        "name": "process_start",
        "description": (
            "Lanza un comando en background dentro del container del usuario. "
            "Captura stdout+stderr a un log (/var/log/laia-processes/<name>.log). "
            "Usa esto para dev servers, watchers o cualquier proceso largo "
            "que sobreviva al turno de chat. El nombre permite referirse al "
            "proceso luego con process_status / process_kill."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando shell completo (se ejecuta con bash -c)."},
                "name": {"type": "string", "description": "Nombre humano para referirse después (auto-generado si se omite)."},
                "cwd": {"type": "string", "description": "Working dir (default /home/user)."},
                "env": {"type": "object", "description": "Variables de entorno extra."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "process_list",
        "description": "Lista todos los procesos en background lanzados con process_start en este container.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "process_status",
        "description": (
            "Inspecciona un proceso en background: estado (alive/exited), "
            "returncode si terminó, y el final del log capturado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name_or_pid": {"type": "string", "description": "Nombre dado en process_start o PID numérico."},
                "tail_chars": {"type": "integer", "description": "Tamaño del tail del log a devolver."},
            },
            "required": ["name_or_pid"],
        },
    },
    {
        "name": "process_kill",
        "description": "Mata un proceso (SIGTERM con gracia de 3s, después SIGKILL).",
        "parameters": {
            "type": "object",
            "properties": {
                "name_or_pid": {"type": "string", "description": "Nombre o PID."},
            },
            "required": ["name_or_pid"],
        },
    },
    {
        "name": "cron_create",
        "description": (
            "Programa una tarea recurrente dentro del container del usuario "
            "via systemd timer. El cron muere cuando el container se borra. "
            "`schedule` es un OnCalendar de systemd (ejemplos: 'daily', "
            "'hourly', '*-*-* 09:00:00', 'Mon..Fri 08:30:00'). Ver `man "
            "systemd.time`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Identificador (letras/dígitos/_/-)."},
                "schedule": {"type": "string", "description": "OnCalendar de systemd."},
                "command": {"type": "string", "description": "Comando shell a ejecutar (bash -lc)."},
                "description": {"type": "string", "description": "Descripción humana opcional."},
                "cwd": {"type": "string", "description": "Working dir (default /home/user)."},
            },
            "required": ["name", "schedule", "command"],
        },
    },
    {
        "name": "cron_list",
        "description": "Lista todos los crons activos en el container del usuario.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cron_delete",
        "description": "Detiene y elimina un cron por nombre.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Identificador usado en cron_create."},
            },
            "required": ["name"],
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
    # Safe equivalents of the AGORA-locally-denied tools (execute_code,
    # process, cronjob). Same forwarding flow: LLM sees the schema, the
    # pre_tool_call hook routes to the user's executor.
    for schema in SAFE_EXEC_TOOL_SCHEMAS:
        try:
            ctx.register_tool(
                name=schema["name"],
                toolset=SAFE_EXEC_TOOLSET,
                schema=schema,
                handler=_stub_handler,
                emoji="🧪" if "exec" in schema["name"] else ("⏱️" if "cron" in schema["name"] else "⚙️"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "agora-executor-forwarder: failed to register %s: %s",
                schema["name"], exc,
            )


__all__ = [
    "EXECUTOR_TOOLS",
    "PRIVATE_WORKSPACE_TOOL_SCHEMAS",
    "SAFE_EXEC_TOOL_SCHEMAS",
    "configure_session",
    "clear_session",
    "register",
    "register_context",
    "unregister_context",
]
