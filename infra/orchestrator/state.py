from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def upsert_agent(path: Path, slug: str, payload: dict[str, Any]) -> None:
    data = load_json(path, {"agents": {}})
    agents = data.setdefault("agents", {})
    current = agents.get(slug, {})
    current.update(payload)
    current["updated_at"] = utc_now()
    current.setdefault("created_at", current["updated_at"])
    agents[slug] = current
    save_json(path, data)
