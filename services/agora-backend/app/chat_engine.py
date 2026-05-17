"""Chat dispatch — wires AgentPool + forwarder + AIAgent into one async stream.

The legacy ``/api/agents/me/chat`` handler proxied SSE to ``/chat`` on the
user's container. That endpoint no longer exists in the redesign — the
executor is fine-grained, only ``/exec`` runs. This module replaces the
relay with a local run:

1. Resolve the user's agent record (container_ip, api_token, slug).
2. Tell the forwarder plugin which executor to hit (thread-local context).
3. Borrow an AIAgent from :class:`AgentPool` (one cached instance per
   ``(user_id, session_id)``), constructed with the user's LLM config.
4. Run :meth:`AIAgent.run_conversation` inside a thread, streaming tokens
   back to the FastAPI handler as Server-Sent Events.

The worker thread is the same one the forwarder uses for its
``threading.local`` context, so tool calls fired by the LLM during
``run_conversation`` see the right executor URL/token automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any, AsyncIterator

from .agent_pool import AgentPool, LLMSessionConfig
from .models import Agent, User


logger = logging.getLogger(__name__)


# Providers that use OAuth / external process auth — no per-user api_key
# needed because credentials live in the shared LAIA_HOME/auth.json store.
# Source of truth: .laia-core/laia_cli/auth.py:PROVIDER_REGISTRY[*].auth_type
# in {"oauth_external", "external_process"}.
OAUTH_PROVIDERS: frozenset[str] = frozenset({
    "openai-codex",       # ChatGPT Teams / OpenAI Codex via OAuth
    "qwen-oauth",         # Alibaba Qwen via OAuth
    "google-gemini-cli",  # Google Gemini OAuth
    "copilot-acp",        # GitHub Copilot ACP (external_process)
    "minimax-oauth",      # MiniMax OAuth
})


def provider_uses_oauth(provider: str | None) -> bool:
    """True when a provider authenticates via the auth.json store, not a per-user api_key.

    Used by both the chat guard (don't reject for missing api_key) and the
    user-creation default (don't force the operator to paste a key).
    """
    return bool(provider) and provider in OAUTH_PROVIDERS


# ---------------------------------------------------------------------------
# Forwarder plugin loader  (single global, reused by every chat)
# ---------------------------------------------------------------------------


_forwarder_module: Any | None = None
_forwarder_lock = threading.Lock()


def _load_forwarder() -> Any | None:
    """Import the ``agora-executor-forwarder`` plugin by file path.

    The plugin's package directory uses hyphens, so we can't ``import`` it
    as a regular module — we resolve the file directly. Caches the module
    on first load so the import cost is paid once per process.

    Returns ``None`` if the plugin file isn't on disk (e.g. the agora-
    backend ships standalone). In that case the chat still runs, but tool
    calls won't be forwarded.
    """
    global _forwarder_module
    if _forwarder_module is not None:
        return _forwarder_module
    with _forwarder_lock:
        if _forwarder_module is not None:
            return _forwarder_module

        # Find the plugin file: try .laia-core relative to this file, then
        # to the LAIA_ROOT env var (set by the systemd unit in production).
        here = Path(__file__).resolve()
        candidates = []
        for parent in here.parents:
            candidate = parent / ".laia-core" / "plugins" / "agora-executor-forwarder" / "__init__.py"
            if candidate.is_file():
                candidates.append(candidate)
                break
        import os
        laia_root = os.environ.get("LAIA_ROOT")
        if laia_root:
            candidate = Path(laia_root) / ".laia-core" / "plugins" / "agora-executor-forwarder" / "__init__.py"
            if candidate.is_file():
                candidates.append(candidate)

        if not candidates:
            logger.warning("chat_engine: agora-executor-forwarder plugin not found — tool calls will run locally (no forwarding)")
            return None

        plugin_init = candidates[0]
        import importlib.util
        spec = importlib.util.spec_from_file_location("agora_executor_forwarder", plugin_init)
        module = importlib.util.module_from_spec(spec)
        sys.modules["agora_executor_forwarder"] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            logger.warning("chat_engine: failed to load forwarder plugin: %s", exc)
            return None
        _forwarder_module = module
        return module


# ---------------------------------------------------------------------------
# Shared AgentPool (one per process; injected by main.py at startup)
# ---------------------------------------------------------------------------


_pool: AgentPool | None = None


def set_pool(pool: AgentPool) -> None:
    """Register the process-wide AgentPool used by this module."""
    global _pool
    _pool = pool


def get_pool() -> AgentPool:
    """Return the registered pool, building a default one if none was set."""
    global _pool
    if _pool is None:
        _pool = AgentPool()
    return _pool


# ---------------------------------------------------------------------------
# Core dispatch
# ---------------------------------------------------------------------------


_STREAM_SENTINEL = object()


async def chat_stream(
    *,
    user: User,
    agent: Agent,
    message: str,
    session_id: str | None,
) -> AsyncIterator[bytes]:
    """Yield SSE-formatted bytes for one chat turn.

    Caller (FastAPI handler) wraps the iterator in ``StreamingResponse``.
    Events emitted, all serialised as ``data: <json>\\n\\n``:

    - ``{"type": "token", "value": "..."}`` — assistant text delta.
    - ``{"type": "tool", "name": "...", "status": "started"}`` — tool call
      observed (forwarder fires this in real time).
    - ``{"type": "done", "response": "...", "iterations": N}`` — final
      payload, includes the full assembled assistant message.
    - ``{"type": "error", "message": "..."}`` — surfaced exception.
    """
    if not agent.container_ip or not agent.api_token:
        yield _sse({"type": "error", "message": "agent not provisioned (no container_ip / api_token)"})
        return
    # API key is only required for providers that authenticate per-request
    # with a static credential. OAuth-based providers (openai-codex,
    # qwen-oauth, google-gemini-cli, ...) read tokens from the shared
    # LAIA_HOME/auth.json that the operator already configured with
    # `laia auth`, so we don't fail on missing api_key.
    if not provider_uses_oauth(user.llm_provider) and not user.llm_api_key:
        yield _sse({"type": "error", "message": "no LLM API key configured for this user — PATCH /api/user/llm-config first"})
        return

    slug = agent.container_name.removeprefix("laia-")
    session_id = session_id or f"u-{user.id}"
    cfg = LLMSessionConfig(
        provider=user.llm_provider,
        api_key=user.llm_api_key,
        base_url=user.llm_base_url,
        model=user.llm_model,
        api_mode=user.llm_api_mode,
    )

    forwarder = _load_forwarder()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _push(item: Any) -> None:
        """Thread-safe enqueue from the worker thread."""
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def _worker() -> None:
        if forwarder is not None:
            forwarder.configure_session(
                agent_slug=slug,
                container_ip=agent.container_ip,
                api_token=agent.api_token,
            )
        try:
            session = get_pool().get_or_create(user.id, session_id, slug, cfg)

            # Wire callbacks so we can stream tokens / tool events from the
            # AIAgent into our asyncio queue. Each is assigned to the
            # instance (the AIAgent reads them as plain attributes).
            ai = session.aiagent
            try:
                ai.stream_delta_callback = lambda delta: _push({"type": "token", "value": str(delta)}) if delta else None
                ai.tool_start_callback = lambda call_id, name, args: _push({"type": "tool", "name": name, "status": "started"})
                ai.tool_complete_callback = lambda call_id, name, args, result: _push({"type": "tool", "name": name, "status": "complete"})
            except Exception:
                pass  # placeholder agents may not have these slots

            try:
                result = ai.run_conversation(message)
            except Exception as exc:
                _push({"type": "error", "message": f"run_conversation failed: {exc}"})
                return

            payload: dict[str, Any] = {"type": "done"}
            if isinstance(result, dict):
                final = result.get("final_response") or result.get("response") or ""
                payload["response"] = final
                payload["iterations"] = result.get("iterations")
            else:
                payload["response"] = str(result) if result is not None else ""
            _push(payload)
        finally:
            if forwarder is not None:
                forwarder.clear_session()
            _push(_STREAM_SENTINEL)

    fut = loop.run_in_executor(None, _worker)

    while True:
        item = await queue.get()
        if item is _STREAM_SENTINEL:
            break
        yield _sse(item)

    # Surface any worker exception that escaped (defensive — _worker catches).
    try:
        await fut
    except Exception as exc:
        yield _sse({"type": "error", "message": f"worker crashed: {exc}"})


def _sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


__all__ = ["chat_stream", "set_pool", "get_pool"]
