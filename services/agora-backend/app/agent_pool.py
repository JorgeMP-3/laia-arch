"""AIAgent pool — keeps one AIAgent instance per active session.

Strategy (per the redesign plan, validated with the user):

- One AgentSession per (user_id, session_id) tuple.
- TTL: idle sessions are evicted after `idle_ttl_seconds` (default 60 min).
- LRU eviction when total pool size exceeds `max_sessions` or RSS pressure
  is detected.
- Each session builds its own AIAgent with the user's per-user LLM config
  (provider, api_key, base_url, model, api_mode), so usage and identity
  are tracked per-user.

Lifecycle:
    pool = AgentPool(...)
    session = pool.get_or_create(user_id, session_id, agent_slug, llm_config)
    # ... use session.aiagent ...
    pool.evict_idle()  # called by background janitor or each request

Importing AIAgent:
    The motor lives in `.laia-core/run_agent.py`. PYTHONPATH for the agora-backend
    process must include `.laia-core/` (the systemd unit set in build-agora-image.sh
    sets PYTHONPATH=/opt/agora/app:/opt/agora/app/.laia-core for this reason).
    If the import fails (e.g. during unit tests in this repo without the full venv),
    we fall back to a minimal placeholder so the pool API stays exercisable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


_collective_workspace_ready = False
_collective_workspace_lock = threading.Lock()

# Status of the auth.json symlink, reported by /api/health. One of:
#   "linked"  : symlink points at a readable file (OAuth providers will work)
#   "missing" : no ~/.laia/auth.json present — admin needs to run `laia auth`
#   "failed"  : tried to link but failed (permissions, FS errors, …)
#   "unknown" : bootstrap hasn't run yet
#
# Ownership convention: ARCH is the canonical writer (refreshes tokens via
# its OAuth flow). AGORA only READS via the symlink. If both ever need to
# refresh, add file locking (POSIX flock) — until then this single-writer
# guarantee avoids the race condition.
auth_json_status: str = "unknown"
auth_json_path: str | None = None


def _ensure_collective_workspace_env() -> None:
    """Wire env vars so the workspace-context plugin finds the collective DB.

    The plugin reads ``LAIA_HOME/workspaces/{active}/workspace.db`` and the
    ``workspace_store`` package; both must be on the AIAgent's process env
    before the first conversation runs. We seed the workspace too — the
    plugin would do it lazily on first write, but seeding upfront means the
    LLM sees a usable workspace index from the first turn.

    Idempotent under a module-level lock; safe to call from every
    ``get_or_create``.
    """
    global _collective_workspace_ready
    if _collective_workspace_ready:
        return
    with _collective_workspace_lock:
        if _collective_workspace_ready:
            return
        try:
            from .config import settings  # local import — avoid cycle on module import
        except Exception:  # pragma: no cover — tests stub out config
            logger.debug("agent_pool: settings unavailable; skipping workspace bootstrap")
            _collective_workspace_ready = True
            return

        # AGORA always owns its own LAIA_HOME so the workspace-context plugin
        # resolves to the per-installation data dir, not an ambient one from
        # the operator's shell. LAIA_ROOT is set the same way for the
        # workspace_store import path resolution.
        os.environ["LAIA_HOME"] = str(settings.data_dir)
        os.environ["LAIA_ROOT"] = str(settings.laia_root)

        # Seed AGORA's own config.yaml when missing. In prod this file gets
        # baked into the laia-agora image (see build-agora-image.sh), but in
        # dev we run the backend on the host and $LAIA_HOME/config.yaml is
        # absent — without it the workspace-context plugin falls back to
        # ~/.laia/config.yaml (ARCH's config) and the AIAgent ends up using
        # the operator's active workspace ("doyouwin", "laia-ecosystem", …)
        # instead of AGORA's "collective". Same content as build-agora-image.sh.
        try:
            cfg_path = settings.data_dir / "config.yaml"
            if not cfg_path.exists():
                collective = settings.collective_workspace_name
                cfg_path.write_text(
                    "# Auto-seeded by agora-backend on first boot.\n"
                    "plugins:\n"
                    "  workspace-context:\n"
                    f"    workspace: {collective}\n"
                    "    inject_mode: index\n"
                    "    active_workspaces:\n"
                    f"      - {collective}\n"
                    "memory:\n"
                    "  provider: workspace-context\n",
                    encoding="utf-8",
                )
                logger.info("agent_pool: seeded %s with collective workspace defaults", cfg_path)
        except Exception as exc:  # pragma: no cover — never block boot
            logger.warning("agent_pool: failed to seed config.yaml: %s", exc)

        # OAuth providers (openai-codex, qwen-oauth, …) read credentials
        # from ``$LAIA_HOME/auth.json``. The admin already configured these
        # via ARCH (``laia auth``), which writes to ``~/.laia/auth.json``.
        # Symlink AGORA's auth.json to that file so both share a single
        # token store. ARCH is the canonical WRITER; AGORA only reads.
        global auth_json_status, auth_json_path
        default_provider = os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex")
        # The chat_engine OAUTH_PROVIDERS set is the source of truth, but we
        # avoid importing it here to keep this module independent.
        oauth_provider_names = {
            "openai-codex", "qwen-oauth", "google-gemini-cli",
            "copilot-acp", "nous",
        }
        default_is_oauth = default_provider in oauth_provider_names

        try:
            admin_auth = Path(
                os.environ.get("AGORA_ARCH_AUTH_JSON")
                or (Path.home() / ".laia" / "auth.json")
            )
            agora_auth = settings.data_dir / "auth.json"
            auth_json_path = str(agora_auth)
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            if admin_auth.is_file():
                if agora_auth.is_symlink() or agora_auth.exists():
                    # If it points elsewhere, leave it alone; only fix the
                    # link if it's missing or pointing somewhere stale.
                    try:
                        if agora_auth.is_symlink() and agora_auth.resolve() == admin_auth.resolve():
                            pass  # already correct
                        elif agora_auth.is_symlink():
                            agora_auth.unlink()
                            agora_auth.symlink_to(admin_auth)
                            logger.info("agent_pool: relinked auth.json → %s", admin_auth)
                    except Exception:
                        pass
                else:
                    agora_auth.symlink_to(admin_auth)
                    logger.info("agent_pool: linked auth.json → %s", admin_auth)
                auth_json_status = "linked"
            else:
                auth_json_status = "missing"
                # If the default provider needs OAuth, this is loud. Otherwise
                # just informational (paid-API providers don't read auth.json).
                if default_is_oauth:
                    logger.warning(
                        "agent_pool: AGORA_DEFAULT_PROVIDER=%s is OAuth but no "
                        "admin auth.json at %s — chat will fail until the admin "
                        "runs `laia auth` (or set AGORA_ARCH_AUTH_JSON).",
                        default_provider, admin_auth,
                    )
                else:
                    logger.info(
                        "agent_pool: no admin auth.json at %s (default provider %s "
                        "does not need OAuth — informational only)",
                        admin_auth, default_provider,
                    )
        except Exception as exc:  # pragma: no cover — never block boot
            auth_json_status = "failed"
            logger.warning("agent_pool: auth.json symlink failed: %s", exc)

        try:
            settings.workspaces_root.mkdir(parents=True, exist_ok=True)
            settings.workspace_root.mkdir(parents=True, exist_ok=True)

            import sys as _sys
            laia_root = str(settings.laia_root)
            if laia_root not in _sys.path:
                _sys.path.insert(0, laia_root)
            from workspace_store import WorkspaceStore  # type: ignore[import-not-found]

            store = WorkspaceStore(settings.workspace_root)
            if not store.exists():
                store.ensure_workspace_layout()
                try:
                    store.seed_workspace(
                        description=(
                            "Workspace colectivo de AGORA — memoria compartida "
                            "entre todos los AIAgents activos."
                        ),
                        areas=[],
                    )
                except Exception as exc:
                    logger.warning("agent_pool: seed_workspace failed (%s); falling back", exc)
                    store.ensure_schema()
                    store.ensure_workspace_taxonomy()
            else:
                store.ensure_schema()
                store.ensure_workspace_taxonomy()
        except Exception as exc:  # pragma: no cover — never block agent startup
            logger.warning("agent_pool: collective workspace bootstrap failed: %s", exc)
        finally:
            _collective_workspace_ready = True


@dataclass
class LLMSessionConfig:
    """Per-user LLM configuration handed to the AIAgent constructor."""

    provider: str | None
    api_key: str | None
    base_url: str | None
    model: str | None
    api_mode: str | None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSession:
    user_id: str
    session_id: str
    agent_slug: str
    aiagent: Any  # AIAgent | _PlaceholderAgent
    llm_config: LLMSessionConfig
    created_at: float
    last_active: float
    message_history: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        self.last_active = time.time()


class _PlaceholderAgent:
    """Stand-in used in environments where `.laia-core/run_agent.py` isn't importable.

    Exposes just enough surface for the pool's unit tests; raises if you try to
    actually run a conversation. In production (inside the laia-agora container)
    we always have the real AIAgent.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    def run_conversation(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "AIAgent placeholder cannot run a conversation. "
            "PYTHONPATH must include .laia-core/ for the real AIAgent to load."
        )


def _build_aiagent(cfg: LLMSessionConfig, *, session_metadata: dict[str, Any]) -> Any:
    """Build a real AIAgent if available; otherwise a placeholder.

    ``session_metadata`` is a dict with keys ``user_id``, ``session_id``,
    ``agent_slug`` — we unpack the parts AIAgent actually accepts as
    individual kwargs (``user_id``, ``session_id``, ``platform``). The full
    dict is also retained on the placeholder for test introspection.
    """
    try:
        from run_agent import AIAgent  # type: ignore[import-not-found]
    except Exception as exc:
        logger.warning("AIAgent unavailable, using placeholder: %s", exc)
        return _PlaceholderAgent(llm_config=cfg, session_metadata=session_metadata)

    # Real AIAgent — match the constructor surface used by ARCH.
    return AIAgent(
        api_key=cfg.api_key or "",
        base_url=cfg.base_url or "",
        provider=cfg.provider or "",
        model=cfg.model or "",
        api_mode=cfg.api_mode or "",
        session_id=session_metadata.get("session_id"),
        user_id=session_metadata.get("user_id"),
        platform="agora",
        skip_context_files=True,
    )


class AgentPool:
    """In-memory pool of AgentSession instances.

    Thread-safe under an internal RLock. The pool itself does not start any
    background tasks; call `evict_idle()` periodically or schedule a janitor
    via `asyncio.create_task(pool.background_janitor())`.
    """

    def __init__(
        self,
        *,
        idle_ttl_seconds: int = 3600,
        max_sessions: int = 30,
    ) -> None:
        self.idle_ttl_seconds = idle_ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, AgentSession] = {}
        self._lock = threading.RLock()

    def _key(self, user_id: str, session_id: str) -> str:
        return f"{user_id}::{session_id}"

    def get_or_create(
        self,
        user_id: str,
        session_id: str,
        agent_slug: str,
        llm_config: LLMSessionConfig,
    ) -> AgentSession:
        _ensure_collective_workspace_env()
        key = self._key(user_id, session_id)
        with self._lock:
            existing = self._sessions.get(key)
            if existing is not None:
                existing.touch()
                return existing
            if len(self._sessions) >= self.max_sessions:
                self._evict_lru_locked()
            metadata = {
                "user_id": user_id,
                "session_id": session_id,
                "agent_slug": agent_slug,
            }
            aiagent = _build_aiagent(llm_config, session_metadata=metadata)
            now = time.time()
            session = AgentSession(
                user_id=user_id,
                session_id=session_id,
                agent_slug=agent_slug,
                aiagent=aiagent,
                llm_config=llm_config,
                created_at=now,
                last_active=now,
            )
            self._sessions[key] = session
            return session

    def get(self, user_id: str, session_id: str) -> AgentSession | None:
        with self._lock:
            session = self._sessions.get(self._key(user_id, session_id))
            if session:
                session.touch()
            return session

    def evict(self, user_id: str, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(self._key(user_id, session_id), None) is not None

    def evict_idle(self) -> int:
        """Drop sessions whose last_active is older than idle_ttl_seconds. Returns count dropped."""
        cutoff = time.time() - self.idle_ttl_seconds
        dropped = 0
        with self._lock:
            to_remove = [k for k, s in self._sessions.items() if s.last_active < cutoff]
            for k in to_remove:
                self._sessions.pop(k, None)
                dropped += 1
        if dropped:
            logger.info("agent_pool: evicted %d idle session(s)", dropped)
        return dropped

    def _evict_lru_locked(self) -> bool:
        """(internal) Remove the single oldest session. Must hold the lock."""
        if not self._sessions:
            return False
        oldest_key = min(self._sessions, key=lambda k: self._sessions[k].last_active)
        self._sessions.pop(oldest_key, None)
        logger.info("agent_pool: LRU-evicted session %s (pool over max=%d)", oldest_key, self.max_sessions)
        return True

    def stats(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            return {
                "size": len(self._sessions),
                "max_sessions": self.max_sessions,
                "idle_ttl_seconds": self.idle_ttl_seconds,
                "sessions": [
                    {
                        "user_id": s.user_id,
                        "session_id": s.session_id,
                        "agent_slug": s.agent_slug,
                        "age_seconds": int(now - s.created_at),
                        "idle_seconds": int(now - s.last_active),
                    }
                    for s in self._sessions.values()
                ],
            }

    async def background_janitor(self, interval_seconds: int = 60) -> None:
        """Periodic idle eviction. Cancel the returned task to stop."""
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                self.evict_idle()
            except Exception:
                logger.exception("agent_pool: janitor pass failed")
