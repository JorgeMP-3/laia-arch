"""AGORA → Plane forwarder plugin (S6 hybrid, outbound side).

Registers the four ``plane_*`` tools into the ``plane`` toolset so the
orchestrator's LLM can act on the Doyouwin Plane instance. Thin glue by
design: the REST contract lives in the satellite package
``laia_plane_bridge`` (PlaneClient); this plugin adapts it to the tool
registry and adds the audit trail. See tools.py for config and gating.

Unlike agora-executor-forwarder there is no ``pre_tool_call`` interception:
these tools do not exist elsewhere and execute right here in laia-agora (a
short REST call over the LXD bridge), so they are plain provided tools.
"""

from __future__ import annotations

# NOTE: the plugin dir name uses hyphens (registry convention) so a plain
# relative import is unavailable when loaded by file path. The loader executes
# this file with the plugin dir on sys.path via laia_cli.plugins; both import
# styles below resolve tools.py next to this file.
try:  # package-style load (laia_cli.plugins manager)
    from .tools import (  # type: ignore[attr-defined]
        PLANE_ATTACH_SCHEMA,
        PLANE_COMMENT_SCHEMA,
        PLANE_CREATE_WORK_ITEM_SCHEMA,
        PLANE_UPDATE_STATE_SCHEMA,
        check_plane_available,
        handle_plane_attach,
        handle_plane_comment,
        handle_plane_create_work_item,
        handle_plane_update_state,
    )
except ImportError:  # file-path load (spec_from_file_location, tests)
    import importlib.util
    import sys
    from pathlib import Path

    _spec = importlib.util.spec_from_file_location(
        "agora_plane_forwarder_tools", Path(__file__).parent / "tools.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["agora_plane_forwarder_tools"] = _mod
    _spec.loader.exec_module(_mod)
    PLANE_ATTACH_SCHEMA = _mod.PLANE_ATTACH_SCHEMA
    PLANE_COMMENT_SCHEMA = _mod.PLANE_COMMENT_SCHEMA
    PLANE_CREATE_WORK_ITEM_SCHEMA = _mod.PLANE_CREATE_WORK_ITEM_SCHEMA
    PLANE_UPDATE_STATE_SCHEMA = _mod.PLANE_UPDATE_STATE_SCHEMA
    check_plane_available = _mod.check_plane_available
    handle_plane_attach = _mod.handle_plane_attach
    handle_plane_comment = _mod.handle_plane_comment
    handle_plane_create_work_item = _mod.handle_plane_create_work_item
    handle_plane_update_state = _mod.handle_plane_update_state


PLANE_TOOLSET = "plane"

_TOOLS = (
    ("plane_create_work_item", PLANE_CREATE_WORK_ITEM_SCHEMA,
     handle_plane_create_work_item, "📋"),
    ("plane_comment", PLANE_COMMENT_SCHEMA, handle_plane_comment, "💬"),
    ("plane_update_state", PLANE_UPDATE_STATE_SCHEMA,
     handle_plane_update_state, "🔁"),
    ("plane_attach", PLANE_ATTACH_SCHEMA, handle_plane_attach, "🔗"),
)


def register(ctx) -> None:
    """Register the plane tools. Called once by the plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset=PLANE_TOOLSET,
            schema=schema,
            handler=handler,
            check_fn=check_plane_available,
            is_async=True,
            emoji=emoji,
        )
