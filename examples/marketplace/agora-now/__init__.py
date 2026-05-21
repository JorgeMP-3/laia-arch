"""agora-now — current timestamp tool.

Registers ``current_time`` returning ISO8601 datetimes in UTC and local
timezone. No I/O, no deps, no surprises.

Handler convention: ``def handler(args: dict, **kw) -> str``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _current_time(args: dict | None = None, **_: object) -> str:
    _ = args  # current_time takes no inputs.
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()
    return json.dumps({
        "ok": True,
        "utc": now_utc.isoformat(),
        "local": now_local.isoformat(),
        "tz": str(now_local.tzinfo),
        "epoch": int(now_utc.timestamp()),
    })


def register(ctx) -> None:
    ctx.register_tool(
        name="current_time",
        toolset="clock",
        schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=_current_time,
        description="Returns the current date/time in UTC + local TZ.",
        emoji="🕒",
    )
