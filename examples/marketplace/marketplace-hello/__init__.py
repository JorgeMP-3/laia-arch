"""marketplace-hello — minimal sanity plugin.

Registers a single tool ``say_hello`` that returns a greeting. Useful to
verify the AGORA marketplace install → discover → tool-call flow without
any external dependencies.

LAIA tool handler convention (see .laia-core/tools/registry.py):
  - Signature: ``def handler(args: dict, **kw) -> str``
  - Return:    a string (often json.dumps of a result envelope)
"""

from __future__ import annotations

import json


def _say_hello(args: dict | None = None, **_: object) -> str:
    args = args or {}
    name = str(args.get("name") or "mundo").strip() or "mundo"
    return json.dumps({
        "ok": True,
        "result": f"hola {name} desde el marketplace AGORA 🚀",
        "source": "marketplace-hello@0.1.2",
    }, ensure_ascii=False)


def register(ctx) -> None:
    ctx.register_tool(
        name="say_hello",
        toolset="hello",
        schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre a saludar. Por defecto 'mundo'.",
                },
            },
            "additionalProperties": False,
        },
        handler=_say_hello,
        description="Devuelve un saludo personalizado del marketplace.",
        emoji="👋",
    )
