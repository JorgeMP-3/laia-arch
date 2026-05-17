"""Wrapper that exposes a LAIA ``AIAgent`` as an async-streaming chat service.

Imports ``AIAgent`` from ``run_agent.py`` (which lives at
``/opt/laia/agent/.laia-core/run_agent.py`` inside an Agora Agent container),
configures it for the ``agora-agent`` toolset profile, and provides an async
``chat_stream`` method that yields events:

  - ``{"type": "token", "text": "..."}`` — one streaming token from the LLM
  - ``{"type": "tool_start", "tool_id", "tool_name", "args"}``
  - ``{"type": "tool_end", "tool_id", "tool_name", "result"}``
  - ``{"type": "final", "reply": "..."}`` — last event in the stream
  - ``{"type": "error", "message": "..."}`` — terminal error

The wrapper does NOT modify ``run_agent.py``. It uses the existing native
callbacks (``stream_delta_callback``, ``tool_start_callback``,
``tool_complete_callback``).

Threading model: ``AIAgent.run_conversation`` is synchronous. We invoke it
in ``asyncio.to_thread`` and bridge the (sync) callbacks back to the asyncio
event loop using ``loop.call_soon_threadsafe`` to push events onto an
``asyncio.Queue``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)


# Default mount points inside the LXD container. Overridable via env vars
# for tests on the host.
_DEFAULT_LAIA_CORE_PATH = Path(os.environ.get("LAIA_CORE_PATH", "/opt/laia/agent/.laia-core"))
_DEFAULT_PROFILE = "agora-agent"
_DEFAULT_AGORA_BACKEND_URL = "http://10.0.0.1:8088"


def fetch_llm_secret_from_agora(
    slug: str,
    bootstrap_token: str,
    *,
    agora_url: str | None = None,
    timeout: float = 5.0,
) -> tuple[str, str]:
    """POST to AGORA /api/agents/{slug}/secrets and return (api_key, provider).

    Raises RuntimeError on failure. Pure utility: makes a single sync HTTP call,
    never persists the response.
    """
    url = (agora_url or os.environ.get("AGORA_BACKEND_URL") or _DEFAULT_AGORA_BACKEND_URL).rstrip("/")
    target = f"{url}/api/agents/{slug}/secrets"
    try:
        resp = httpx.post(
            target,
            json={"bootstrap_token": bootstrap_token},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"failed to reach AGORA at {url}: {exc}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"AGORA returned {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    key = body.get("llm_api_key", "")
    provider = body.get("llm_provider", "")
    if not key:
        raise RuntimeError("AGORA response missing llm_api_key")
    return key, provider


def _ensure_laia_core_importable() -> None:
    """Make ``import run_agent`` resolve to the .laia-core inside the container."""
    core = _DEFAULT_LAIA_CORE_PATH
    if not core.is_dir():
        raise RuntimeError(
            f"LAIA core not found at {core}. "
            "Set LAIA_CORE_PATH env var or rebuild the container image."
        )
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    # Sandbox env var: file_tools / terminal_tool will enforce path/command whitelists.
    os.environ.setdefault("LAIA_PROFILE", _DEFAULT_PROFILE)


class AgentWrapper:
    """Async-streaming wrapper over a single ``AIAgent`` instance.

    Construct one per chat session. Each session keeps its own conversation
    history inside the AIAgent and can serve multiple turns sequentially.

    Concurrent ``chat_stream`` calls on the same wrapper are NOT supported
    (the underlying ``AIAgent`` is single-turn at a time).
    """

    def __init__(
        self,
        *,
        slug: str,
        api_key: str,
        provider: str = "",
        enabled_toolsets: list[str] | None = None,
        workspace_dir: Path | None = None,
        agent_class: type | None = None,  # for tests: inject a fake AIAgent class
    ) -> None:
        self.slug = slug
        self._api_key = api_key
        self._llm_provider: str = provider
        self._workspace_dir = workspace_dir
        self._lock = asyncio.Lock()

        if agent_class is None:
            _ensure_laia_core_importable()
            from run_agent import AIAgent  # type: ignore
            agent_class = AIAgent

        toolsets = enabled_toolsets or [_DEFAULT_PROFILE]

        # Event queue: every callback empties into this. chat_stream drains it.
        # The queue + loop are bound at the first chat_stream() call so that
        # the wrapper can be constructed from any thread.
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Bind callbacks: each one schedules an event push on the loop.
        self._agent = agent_class(
            api_key=self._api_key,
            provider=self._llm_provider if self._llm_provider else None,
            enabled_toolsets=toolsets,
            stream_delta_callback=self._on_token,
            tool_start_callback=self._on_tool_start,
            tool_complete_callback=self._on_tool_end,
        )

    # ── callback bridges (called from AIAgent's thread) ──────────────────────

    def _push(self, event: dict[str, Any]) -> None:
        loop = self._loop
        queue = self._queue
        if loop is None or queue is None:
            return  # no active chat_stream — drop event
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _on_token(self, text: str) -> None:
        if text:
            self._push({"type": "token", "text": text})

    def _on_tool_start(self, tool_id: str, tool_name: str, args: Any) -> None:
        self._push({
            "type": "tool_start",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "args": args,
        })

    def _on_tool_end(self, tool_id: str, tool_name: str, args: Any, result: Any) -> None:
        self._push({
            "type": "tool_end",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "result": result,
        })

    # ── public API ───────────────────────────────────────────────────────────

    async def chat_stream(self, message: str) -> AsyncIterator[dict[str, Any]]:
        """Send a message and yield events until the agent finishes the turn.

        Yields a `final` event last, with the full assembled reply. Yields
        an `error` event if `AIAgent.run_conversation` raises.
        """
        if self._lock.locked():
            yield {"type": "error", "message": "another turn is in progress"}
            return

        async with self._lock:
            self._loop = asyncio.get_running_loop()
            self._queue = asyncio.Queue()

            run_task = asyncio.create_task(asyncio.to_thread(self._run_blocking, message))

            try:
                while True:
                    # Wait for the next event or for run_task to finish.
                    drain_task = asyncio.create_task(self._queue.get())
                    done, pending = await asyncio.wait(
                        {drain_task, run_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if drain_task in done:
                        event = drain_task.result()
                        yield event
                        if event.get("type") == "final" or event.get("type") == "error":
                            for p in pending:
                                p.cancel()
                            break
                    else:
                        drain_task.cancel()
                        # run_task finished, drain remaining events from the queue.
                        while not self._queue.empty():
                            yield self._queue.get_nowait()
                        # Then emit final from the result of run_task.
                        try:
                            result = run_task.result()
                            reply = self._extract_reply(result)
                            yield {"type": "final", "reply": reply}
                        except Exception as exc:
                            logger.exception("AIAgent.run_conversation crashed")
                            yield {"type": "error", "message": str(exc)}
                        break
            finally:
                if not run_task.done():
                    run_task.cancel()
                self._queue = None

    def _run_blocking(self, message: str) -> Any:
        """Invoke AIAgent.run_conversation synchronously inside a thread."""
        result = self._agent.run_conversation(message)
        # When the agent finishes, push a final event so the consumer sees
        # it even if the result extraction below fails.
        reply = self._extract_reply(result)
        self._push({"type": "final", "reply": reply})
        return result

    @staticmethod
    def _extract_reply(result: Any) -> str:
        """Best-effort extraction of the agent's last textual reply."""
        if isinstance(result, dict):
            for key in ("final_response", "response", "reply", "answer", "content"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            # Conversation result might have a `messages` list with the last
            # assistant turn as the reply.
            messages = result.get("messages") if isinstance(result.get("messages"), list) else None
            if messages:
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        content = msg.get("content")
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            # OpenAI-style content blocks
                            parts = [c.get("text", "") for c in content if isinstance(c, dict)]
                            return "".join(parts).strip()
        if isinstance(result, str):
            return result
        return ""
