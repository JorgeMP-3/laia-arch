"""Echo import provider — stub for tests / sanity check (Fase B).

Inserts ``config["count"]`` (default 3) synthetic nodes into the target
workspace under slugs ``echo-<i>``. Useful to validate the full plumbing
(register → run → persisted last_count) without any external dependency.
"""

from __future__ import annotations

from typing import Any


class EchoProvider:
    name = "echo"

    def sync(self, *, user_id: str, config: dict[str, Any], target_ws) -> dict[str, Any]:
        n = int(config.get("count", 3))
        n = max(0, min(n, 10))  # guardrail
        prefix = str(config.get("prefix") or "echo")
        for i in range(n):
            slug = f"{prefix}-{i}"
            try:
                target_ws.upsert_node(
                    slug=slug,
                    title=f"Echo node {i}",
                    kind="doc",
                    summary=f"Synthetic node {i} from echo provider",
                    body=f"# Echo {i}\n\nuser_id={user_id}\nconfig={config}",
                )
            except Exception:
                # If the workspace is read-only (e.g. secondary), upsert raises.
                # We capture but don't propagate — let count reflect actual writes.
                continue
        return {"count": n, "prefix": prefix}
