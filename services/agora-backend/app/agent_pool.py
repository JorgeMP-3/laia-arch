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


def seed_agora_config_yaml() -> None:
    """Materialise ``$LAIA_HOME/config.yaml`` with AGORA's plugin defaults.

    Idempotent. Safe to call multiple times. **Must run before
    ``laia_cli.plugins.discover_plugins()`` at lifespan startup** — the
    plugin manager reads ``plugins.enabled`` from this file once, and if
    the file doesn't yet list ``agora-executor-forwarder`` then the
    forwarder hook is never registered, and every filesystem/bash tool
    call from the LLM runs on the host instead of being forwarded to the
    user's executor container. That defeats the whole rediseño.

    Two paths:
      1. File missing → write a fresh seed including ``enabled`` + the
         workspace-context section.
      2. File present → merge: if ``agora-executor-forwarder`` is not
         already in ``plugins.enabled``, append it.

    Pulled out of ``_ensure_collective_workspace_env`` so the lifespan
    can call this *before* ``discover_plugins`` (the workspace bootstrap
    waits for the first chat, which is too late for plugin discovery).
    """
    try:
        from .config import settings  # local import — avoid cycle on module import
    except Exception:
        logger.debug("seed_agora_config_yaml: settings unavailable; skipping")
        return

    required_plugins = ["agora-executor-forwarder"]
    cfg_path = settings.data_dir / "config.yaml"
    collective = settings.collective_workspace_name

    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        if not cfg_path.exists():
            cfg_path.write_text(
                "# Auto-seeded by agora-backend on first boot.\n"
                "plugins:\n"
                "  enabled:\n"
                + "".join(f"    - {p}\n" for p in required_plugins) +
                "  workspace-context:\n"
                f"    workspace: {collective}\n"
                "    inject_mode: index\n"
                "    active_workspaces:\n"
                f"      - {collective}\n"
                "memory:\n"
                "  provider: workspace-context\n",
                encoding="utf-8",
            )
            logger.info("seed_agora_config_yaml: created %s with forwarder enabled", cfg_path)
            return

        # Merge: parse, ensure plugins.enabled contains the required entries.
        try:
            import yaml as _yaml
            data = _yaml.safe_load(cfg_path.read_text()) or {}
        except Exception as exc:
            logger.warning("seed_agora_config_yaml: could not parse %s: %s", cfg_path, exc)
            return
        if not isinstance(data, dict):
            return
        plugins_cfg = data.get("plugins")
        if not isinstance(plugins_cfg, dict):
            plugins_cfg = {}
            data["plugins"] = plugins_cfg
        enabled = plugins_cfg.get("enabled")
        if not isinstance(enabled, list):
            enabled = []
        changed = False
        for p in required_plugins:
            if p not in enabled:
                enabled.append(p)
                changed = True
        if changed:
            plugins_cfg["enabled"] = enabled
            try:
                import yaml as _yaml
                cfg_path.write_text(
                    _yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                logger.info("seed_agora_config_yaml: added %s to plugins.enabled in %s", required_plugins, cfg_path)
            except Exception as exc:
                logger.warning("seed_agora_config_yaml: could not rewrite %s: %s", cfg_path, exc)
    except Exception as exc:  # pragma: no cover — never block boot
        logger.warning("seed_agora_config_yaml: failed: %s", exc)


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

        # Seed config.yaml is the lifespan's job now (must run BEFORE
        # discover_plugins). We still call it here as a safety net for
        # tests/callers that bypass the lifespan path.
        seed_agora_config_yaml()

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
            elif agora_auth.is_file():
                auth_json_status = "linked"
                logger.info(
                    "agent_pool: using existing AGORA auth.json at %s "
                    "(admin auth.json %s not readable from this process)",
                    agora_auth,
                    admin_auth,
                )
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


def _extract_tokens(run_output: Any) -> tuple[int, int, bool]:
    """Best-effort extraction of (tokens_in, tokens_out, estimated).

    Tries the common provider shapes; falls back to a coarse length-based
    estimate (4 chars ≈ 1 token) so usage tracking is *never* a silent zero
    when the provider doesn't expose a usage block.
    """
    usage = None
    if isinstance(run_output, dict):
        usage = run_output.get("usage")
        if usage is None:
            # Some providers nest under "response" or similar.
            for k in ("response", "result", "data"):
                v = run_output.get(k)
                if isinstance(v, dict) and isinstance(v.get("usage"), dict):
                    usage = v["usage"]
                    break
    if isinstance(usage, dict):
        # Anthropic style
        if "input_tokens" in usage or "output_tokens" in usage:
            return (
                int(usage.get("input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
                False,
            )
        # OpenAI style
        if "prompt_tokens" in usage or "completion_tokens" in usage:
            return (
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
                False,
            )
        # Generic "tokens_input"/"tokens_output"
        if "tokens_input" in usage or "tokens_output" in usage:
            return (
                int(usage.get("tokens_input") or 0),
                int(usage.get("tokens_output") or 0),
                False,
            )
    # Fallback: estimate from response length. Better than dropping the call.
    text = ""
    if isinstance(run_output, dict):
        text = str(
            run_output.get("response")
            or run_output.get("final_response")
            or run_output.get("text")
            or ""
        )
    elif run_output is not None:
        text = str(run_output)
    # 4 chars ≈ 1 token heuristic. Input is unknown → 0; only output is
    # estimable from what we have. The :est suffix on kind warns callers.
    return (0, max(1, len(text) // 4) if text else 0, True)


def record_usage_for_session(
    *,
    user_id: str,
    session_id: str | None,
    llm_config: "LLMSessionConfig",
    run_output: Any,
    kind: str = "chat",
) -> None:
    """Best-effort: extract token counts from ``run_output`` and persist a row.

    Never raises — usage tracking must never break a chat. Estimated rows get
    a ``:est`` suffix on ``kind`` so budget reconciliation knows the figure
    is heuristic.
    """
    try:
        from .storage import store
        from .pricing import cost_for
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("record_usage_for_session: imports failed: %s", exc)
        return
    try:
        tokens_in, tokens_out, estimated = _extract_tokens(run_output)
        if tokens_in == 0 and tokens_out == 0 and not estimated:
            # Nothing to record (provider exposed an explicit zero — odd, but skip).
            return
        provider = (llm_config.provider or "") if llm_config else ""
        model = (llm_config.model or "") if llm_config else ""
        cost = cost_for(provider, model, tokens_in, tokens_out)
        actual_kind = f"{kind}:est" if estimated else kind
        store.record_usage(
            user_id=user_id,
            session_id=session_id,
            provider=provider,
            model=model,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=cost,
            kind=actual_kind,
        )
    except Exception as exc:
        logger.warning("record_usage_for_session: failed for user=%s: %s", user_id, exc)


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


# Toolsets that the AIAgent in laia-agora is allowed to load. Derived from
# the ``agora-orchestrator`` profile in
# ``.laia-core/toolset_distributions.py`` but applied here as an explicit
# enabled_toolsets list — the AIAgent default loads every toolset, so
# without this guard tools like ``execute_code``, ``cronjob``,
# ``skill_manage`` and ``delegate_task`` would run locally in laia-agora
# and a prompt-injected user could pivot from the chat to arbitrary code
# execution in the orchestrator container.
#
# What gets loaded:
#   - file       → read_file, write_file, patch, search_files  (forwarded by plugin)
#   - terminal   → terminal, process                            (terminal forwarded; process blocked by A2 deny-list)
#   - web        → web_search, web_extract                      (network only, AGORA-local)
#   - vision     → image analysis                               (network only, AGORA-local)
#   - image_gen  → image generation                             (network only, AGORA-local)
#   - browser    → headless browser tools                       (network only, AGORA-local)
#   - fetch_url  → HTTP fetch                                   (network only, AGORA-local)
#   - workspace  → collective workspace_* tools                 (AGORA-local DB)
#   - clarify    → ask-the-user prompt                          (no side effects)
#   - todo       → in-memory todo list                          (no side effects)
#
# What is NOT loaded (would otherwise execute locally in laia-agora):
#   - code_execution (execute_code) → Python eval
#   - cronjob → scheduling persistent jobs in AGORA
#   - skills (skill_manage, skills_list, skill_view) → dynamic Python load
#   - memory → workspace nodes via memory provider
#   - delegation (delegate_task) → spawn subagents
#   - moa (mixture_of_agents) → recursive agent invocation
#   - discord, discord_admin, homeassistant, feishu_*, spotify, …
AGORA_ENABLED_TOOLSETS: list[str] = [
    "file",
    "terminal",
    "web",
    "vision",
    "image_gen",
    "browser",
    "fetch_url",
    "workspace",
    "clarify",
    "todo",
    # Safe equivalents of execute_code/process/cronjob — registered by the
    # forwarder plugin in this toolset. They are forwarded to the user's
    # executor, never run locally in laia-agora.
    "user_runtime",
    # Self-edit + learning tools (plugin .laia-core/plugins/agent-self-edit).
    # Run locally in laia-agora — they need direct access to agora.db.
    "agent_self",
    # Read-only secondary workspaces (plugin .laia-core/plugins/secondary-workspaces).
    "secondary_workspace",
    # Scheduling + webhooks (plugin .laia-core/plugins/agent-scheduler).
    "agent_scheduler",
    # Multi-agent delegation (plugin .laia-core/plugins/agent-delegation).
    "agent_delegation",
]


def _build_aiagent(
    cfg: LLMSessionConfig,
    *,
    session_metadata: dict[str, Any],
    extra_toolsets: list[str] | None = None,
    ephemeral_system_prompt: str | None = None,
) -> Any:
    """Build a real AIAgent if available; otherwise a placeholder.

    ``session_metadata`` is a dict with keys ``user_id``, ``session_id``,
    ``agent_slug`` — we unpack the parts AIAgent actually accepts as
    individual kwargs (``user_id``, ``session_id``, ``platform``). The full
    dict is also retained on the placeholder for test introspection.

    ``extra_toolsets`` (marketplace-v0.1): toolsets contributed by the
    user's installed plugins. Appended to ``AGORA_ENABLED_TOOLSETS`` so
    the AIAgent's toolset filter doesn't strip out marketplace tools.
    """
    enabled = list(AGORA_ENABLED_TOOLSETS)
    if extra_toolsets:
        for ts in extra_toolsets:
            if ts and ts not in enabled:
                enabled.append(ts)

    try:
        from run_agent import AIAgent  # type: ignore[import-not-found]
    except Exception as exc:
        logger.warning("AIAgent unavailable, using placeholder: %s", exc)
        return _PlaceholderAgent(
            llm_config=cfg,
            session_metadata=session_metadata,
            ephemeral_system_prompt=ephemeral_system_prompt,
        )

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
        ephemeral_system_prompt=ephemeral_system_prompt,
        skip_context_files=True,
        # Restrict the tool surface — see AGORA_ENABLED_TOOLSETS above.
        # The plugin agora-executor-forwarder routes filesystem/bash to the
        # user's executor; what remains here MUST be safe to run locally.
        enabled_toolsets=enabled,
    )


def _build_agent_area_prompt(user_id: str) -> str | None:
    try:
        from .storage import store  # local import — avoid cycle
    except Exception:
        return None
    user = store.user_by_id(user_id)
    if user is None:
        return None
    area = store.agent_area_for_user(user, create=True)
    if area is None:
        return None

    blocks: list[str] = []
    if area.agent_display_name:
        blocks.append(f"Nombre visible del agente: {area.agent_display_name}")
    if area.soul_md.strip():
        blocks.append("Soul/persona del agente:\n" + area.soul_md.strip())
    if area.instructions_md.strip():
        blocks.append("Instrucciones persistentes del usuario:\n" + area.instructions_md.strip())
    if area.behavior_preferences:
        import json as _json
        blocks.append(
            "Preferencias de comportamiento:\n"
            + _json.dumps(area.behavior_preferences, ensure_ascii=False, indent=2)
        )
    if area.memory_preferences:
        import json as _json
        blocks.append(
            "Preferencias de memoria:\n"
            + _json.dumps(area.memory_preferences, ensure_ascii=False, indent=2)
        )

    # Coordinator inbox (Fase 1.4): if LAIA pushed messages for this user
    # we inject them here and mark them read so we don't repeat on the
    # next session. Best-effort — never blocks the build.
    try:
        inbox = store.list_inbox(user_id, only_unread=True, limit=10)
    except Exception as exc:
        logger.debug("agent_pool: list_inbox unavailable: %s", exc)
        inbox = []
    if inbox:
        lines = [
            f"Mensajes de LAIA pendientes ({len(inbox)} sin leer):"
        ]
        for m in inbox:
            lines.append(f"  - [{m.severity}] {m.text}")
        blocks.append("\n".join(lines))
        try:
            store.mark_inbox_read(user_id, [m.id for m in inbox])
        except Exception as exc:
            logger.debug("agent_pool: mark_inbox_read failed: %s", exc)

    # Organic learnings (Fase 3): inject the top-N most relevant learnings so
    # the agent recalls past errors/insights without needing an explicit tool
    # call on every turn. Best-effort — never blocks agent construction.
    try:
        recent = store.recent_learnings_for_user(user_id, limit=8)
    except Exception as exc:
        logger.debug("agent_pool: recent_learnings unavailable: %s", exc)
        recent = []
    if recent:
        bullets = []
        for L in recent:
            head = L.title[:80]
            body = (L.content_md or "").strip().replace("\n", " ")
            if len(body) > 240:
                body = body[:240].rstrip() + "…"
            bullets.append(f"- [{L.kind}] {head}: {body}")
        blocks.append(
            "Aprendizajes recientes del agente "
            f"(top {len(recent)}, ordenados por relevancia):\n"
            + "\n".join(bullets)
        )

    return "\n\n".join(blocks) if blocks else None


def _bind_self_edit_session(user_id: str, session_id: str = "") -> None:
    """Bind plugin threading.locals for the current AIAgent thread.

    The agent-self-edit / agent-scheduler / agent-delegation plugins keep a
    threading.local of the active ``user_id`` (and, for delegation,
    ``session_id``) so their tools mutate the right rows. Best-effort: if
    a plugin isn't loaded (unit tests that skip discovery), we silently
    skip. In production the plugins are bundled in the image so these
    imports succeed.
    """
    for module_path in (
        "laia_plugins.agent_self_edit",
        "laia_plugins.agent_scheduler",
        "laia_plugins.laia_coordinator",
    ):
        try:
            mod = __import__(module_path, fromlist=["set_session_context"])
            set_ctx = getattr(mod, "set_session_context", None)
        except Exception:
            continue
        if set_ctx is None:
            continue
        try:
            set_ctx(user_id)
        except Exception as exc:
            logger.debug("agent_pool: bind %s session failed: %s", module_path, exc)

    # agent-delegation needs the session_id too (to scope children).
    try:
        mod = __import__("laia_plugins.agent_delegation",
                         fromlist=["set_session_context"])
        set_ctx = getattr(mod, "set_session_context", None)
        if set_ctx is not None:
            set_ctx(user_id, session_id)
    except Exception as exc:
        logger.debug("agent_pool: bind agent_delegation failed: %s", exc)


def _bind_laia_chat_mode(actor_role: str | None) -> None:
    """Mark the current thread as inside a LAIA chat for the plugin.

    The laia-coordinator plugin keeps a ``threading.local`` flag (``_chat``)
    so its tool handlers can refuse to act outside LAIA chat mode, and so
    admin tools can additionally check the actor's role. Best-effort: if
    the plugin isn't loaded (unit tests that skip discovery), we silently
    skip.
    """
    try:
        mod = __import__("laia_plugins.laia_coordinator",
                         fromlist=["set_laia_chat_mode"])
        setter = getattr(mod, "set_laia_chat_mode", None)
        if setter is not None:
            setter(actor_role or "employee")
    except Exception as exc:
        logger.debug("agent_pool: bind laia_chat mode failed: %s", exc)


def _materialize_marketplace_for(user_id: str, user_slug: str) -> list[str]:
    """Set LAIA_EXTRA_PLUGIN_DIRS + LAIA_FORWARDED_TOOLS_EXTRA for this user.

    Best-effort: failures are logged but never block agent creation. The
    storage layer materialises the per-user dir on disk; the env vars wire
    the LAIA plugin loader (Fase D) and the forwarder plugin (Fase F).

    Returns the list of *extra toolsets* declared by the user's installed
    plugins — the caller (``get_or_create``) appends them to
    ``AGORA_ENABLED_TOOLSETS`` so the AIAgent's tool filter doesn't strip
    out marketplace tools. Empty list if no installs / errors.

    NOTE: env vars are *process-global*. This is OK only because AgentPool
    serialises session creation under its lock — concurrent users still
    create their AIAgents one at a time. The discovered plugin set lives
    on the global PluginManager, so two consecutive users with different
    install sets will each see their own set at agent-build time.
    """
    try:
        from .storage import store  # local import — avoid cycle
        from . import marketplace_storage as ms
    except Exception as exc:
        logger.debug("agent_pool: marketplace storage unavailable: %s", exc)
        return []

    try:
        plugin_dir = ms.materialize_installed_plugins(store, user_id=user_id, user_slug=user_slug)
        forward_tools = ms.collect_forward_tools_for_user(store, user_id)
    except Exception as exc:
        logger.warning("agent_pool: failed to materialise marketplace for %s: %s", user_slug, exc)
        return []

    os.environ["LAIA_EXTRA_PLUGIN_DIRS"] = str(plugin_dir)
    os.environ["LAIA_FORWARDED_TOOLS_EXTRA"] = ",".join(forward_tools)

    # Also materialise personal skills so the .laia-core skill discovery
    # picks them up (best-effort).
    try:
        ms.materialize_installed_skills(store, user_id=user_id, user_slug=user_slug)
    except Exception as exc:
        logger.debug("agent_pool: skill materialisation failed: %s", exc)

    # Force re-discovery so the new env takes effect for this build.
    extra_toolsets: list[str] = []
    try:
        from laia_cli.plugins import discover_plugins, get_plugin_manager  # type: ignore[import-not-found]
        discover_plugins(force=True)
        # Inspect the registry for toolsets owned by tools registered via
        # the LAIA plugin manager. We union them with AGORA_ENABLED_TOOLSETS
        # at AIAgent build time. Without this, marketplace tools get
        # filtered out by the toolset gate even though they're loaded.
        try:
            from tools.registry import registry  # type: ignore[import-not-found]
            mgr = get_plugin_manager()
            plugin_tool_names = set(getattr(mgr, "_plugin_tool_names", set()))
            for tool_name in plugin_tool_names:
                entry = registry.get_entry(tool_name)
                ts = getattr(entry, "toolset", None) if entry else None
                # The ``laia_coordinator_*`` toolsets are reserved for
                # LAIA chat mode. The plugin is bundled in the global
                # .laia-core/plugins directory so its tools register on
                # every backend discovery, but we MUST NOT expose them
                # via the marketplace path — ``get_or_create`` re-adds
                # them only when ``mode='laia'``. Keep the legacy name
                # too for any older build that still tags tools with it.
                if ts in {
                    "laia_coordinator",
                    "laia_coordinator_base",
                    "laia_coordinator_admin",
                }:
                    continue
                if ts and ts not in extra_toolsets:
                    extra_toolsets.append(ts)
        except Exception as exc:
            logger.debug("agent_pool: toolset introspection failed: %s", exc)
    except Exception as exc:
        logger.debug("agent_pool: rediscover after marketplace materialise failed: %s", exc)

    return extra_toolsets


class AgentPool:
    """In-memory pool of AgentSession instances.

    Thread-safe under an internal RLock. The pool itself does not start any
    background tasks; call `evict_idle()` periodically or schedule a janitor
    via `asyncio.create_task(pool.background_janitor())`.
    """

    # Class-level reference to the most recently constructed pool, used by
    # marketplace endpoints to invalidate sessions on install/uninstall
    # without holding the pool object directly.
    _active_instance: "AgentPool | None" = None

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
        AgentPool._active_instance = self

    def _key(self, user_id: str, session_id: str) -> str:
        return f"{user_id}::{session_id}"

    def get_or_create(
        self,
        user_id: str,
        session_id: str,
        agent_slug: str,
        llm_config: LLMSessionConfig,
        *,
        mode: str | None = None,
        actor_role: str | None = None,
    ) -> AgentSession:
        """Get or build an AgentSession.

        ``mode='laia'`` switches the build to the coordinator path:
          - skip ``_materialize_marketplace_for`` (LAIA does not load the
            actor's marketplace plugins)
          - skip ``_bind_self_edit_session`` (rule ⑪: LAIA does not
            self-edit, schedule, or delegate)
          - system prompt comes from ``agent_areas[user_laia]`` regardless
            of which user_id is keyed
          - toolsets are restricted to ``laia_coordinator_base`` plus
            ``laia_coordinator_admin`` when ``actor_role == 'agora_admin'``
          - the laia-coordinator plugin's chat-mode flag is set so handler
            checks pass (and admin tools see the right role)
        """
        _ensure_collective_workspace_env()
        key = self._key(user_id, session_id)
        with self._lock:
            existing = self._sessions.get(key)
            if existing is not None:
                existing.touch()
                # For LAIA sessions re-bind the chat-mode flag every turn —
                # threading.local is per-thread and the AIAgent may run on a
                # different worker than the one that built the session.
                if mode == "laia":
                    _bind_laia_chat_mode(actor_role)
                return existing
            if len(self._sessions) >= self.max_sessions:
                self._evict_lru_locked()
            metadata = {
                "user_id": user_id,
                "session_id": session_id,
                "agent_slug": agent_slug,
            }
            if mode == "laia":
                # Rule ⑨/⑩/⑪ aligned: LAIA chat builds a coordinator
                # AIAgent that uses the actor's executor binding (the
                # forwarder will route any executor-bound tool to
                # actor's container — but the coordinator toolset has
                # none of those: all are local DB/workspace reads).
                extra_toolsets = ["laia_coordinator_base"]
                if actor_role == "agora_admin":
                    extra_toolsets.append("laia_coordinator_admin")
                area_prompt = _build_agent_area_prompt("user_laia")
                _bind_laia_chat_mode(actor_role)
            else:
                # marketplace-v0.1: materialise per-user plugin/skill
                # installs and wire the env vars before AIAgent
                # construction. The AgentPool lock guarantees serial
                # execution so env-var races between users are avoided.
                extra_toolsets = _materialize_marketplace_for(user_id, agent_slug)
                area_prompt = _build_agent_area_prompt(user_id)
                # agent-self-edit (and learning) tools need to know the
                # active user_id. We expose it via threading.local in the
                # plugin module. The AgentPool lock + AIAgent's
                # single-thread execution mean this binding is stable
                # for the lifetime of the session's run_conversation
                # calls.
                _bind_self_edit_session(user_id, session_id)
            aiagent = _build_aiagent(
                llm_config,
                session_metadata=metadata,
                extra_toolsets=extra_toolsets,
                ephemeral_system_prompt=area_prompt,
            )
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

    def invalidate_user(self, user_id: str) -> int:
        """Drop every session for `user_id`. Next chat rebuilds with current installs.

        Returns the number of sessions evicted.
        """
        prefix = f"{user_id}::"
        with self._lock:
            keys = [k for k in self._sessions if k.startswith(prefix)]
            for k in keys:
                self._sessions.pop(k, None)
        if keys:
            logger.info("agent_pool: invalidated %d session(s) for user %s", len(keys), user_id)
        return len(keys)

    @staticmethod
    def invalidate_user_static(user_id: str) -> int:
        """Class-level shortcut so callers don't need a pool reference."""
        pool = AgentPool._active_instance
        if pool is None:
            return 0
        return pool.invalidate_user(user_id)

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
