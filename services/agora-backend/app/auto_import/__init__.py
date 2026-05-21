"""Auto-import framework (Fase B).

Provider interface + registry + sync runner. The actual external providers
(Notion, Linear, GitHub) are not implemented in v0.3 — they're stubbed by
the ``echo`` provider for testing. Each provider's job is to fetch data
from an external service and upsert workspace nodes into the target
``WorkspaceStore``.

A scheduled tick (added in scheduler.py later iteration) iterates enabled
auto_imports, calls ``run_provider(imp)`` for each whose ``cron_expr`` is
due, and persists ``last_synced_at`` / ``last_status`` / ``last_count``.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from .echo_provider import EchoProvider


logger = logging.getLogger(__name__)


class ImportProvider(Protocol):
    """Interface every external import provider must implement."""

    name: str

    def sync(self, *, user_id: str, config: dict[str, Any], target_ws) -> dict[str, Any]:
        """Pull external data into target_ws. Return ``{count, errors?}``."""
        ...


# Registry of providers known to AGORA. Keys are short slugs the user
# passes via ``auto_import_register(provider=...)``. To add a real
# provider (notion/linear/github), implement the Protocol above and
# register it here. Echo is the canonical stub for tests.
_REGISTRY: dict[str, ImportProvider] = {
    "echo": EchoProvider(),
}


def register_provider(provider: ImportProvider) -> None:
    """Add a custom provider at runtime (used by tests / plugin extensions)."""
    _REGISTRY[provider.name] = provider


def get_provider(name: str) -> ImportProvider | None:
    return _REGISTRY.get(name)


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def run_import(imp) -> dict[str, Any]:
    """Run a single auto_imports row. Persists ``last_*`` fields on the row.

    Errors are caught — the row is updated with ``last_status='error'``
    and ``last_error`` so the user can see why. Never raises.
    """
    from ..storage import store

    provider = get_provider(imp.provider)
    if provider is None:
        store.update_auto_import(
            imp.id, last_status="error",
            last_error=f"unknown provider: {imp.provider}",
        )
        return {"ok": False, "error": "unknown provider"}

    # Resolve target workspace: 'private' is the user's own (executor) — we
    # don't have a python handle here, so v0.3 only supports 'collective'
    # (= AGORA's collective workspace_store). Private writes are TBD.
    target_ws = None
    if imp.target_workspace == "collective":
        target_ws = store.workspace
    else:
        # Best-effort fallback: collective. The "private" mode requires a
        # round-trip to the executor (out of scope for v0.3).
        target_ws = store.workspace

    try:
        result = provider.sync(user_id=imp.user_id, config=imp.config or {},
                                target_ws=target_ws)
        count = int(result.get("count", 0))
        store.update_auto_import(
            imp.id, last_status="ok", last_count=count,
            last_error=None,
        )
        # Best-effort audit.
        try:
            from ..models import Event, new_id
            store.record_event(Event(
                id=new_id("evt"),
                event_type="auto_import_run",
                actor_id=imp.user_id,
                summary=f"{imp.provider} → {count} item(s)",
            ))
        except Exception:
            pass
        return {"ok": True, "count": count}
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.exception("auto_import: provider %s failed", imp.provider)
        store.update_auto_import(
            imp.id, last_status="error", last_error=err,
        )
        return {"ok": False, "error": err}


__all__ = [
    "ImportProvider", "register_provider", "get_provider", "list_providers",
    "run_import", "EchoProvider",
]
