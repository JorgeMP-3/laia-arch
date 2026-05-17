"""Tool dispatcher: maps tool names to handler callables."""

from __future__ import annotations

from typing import Callable, Awaitable, Any
import inspect


ToolHandler = Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"tool already registered: {name}")
        self._handlers[name] = handler

    def has(self, name: str) -> bool:
        return name in self._handlers

    def list_tools(self) -> list[str]:
        return sorted(self._handlers.keys())

    async def call(self, name: str, args: dict[str, Any]) -> str:
        if name not in self._handlers:
            raise KeyError(name)
        handler = self._handlers[name]
        result = handler(**args) if not inspect.iscoroutinefunction(handler) else await handler(**args)
        if isinstance(result, str):
            return result
        # JSON-serialize non-string results
        import json
        return json.dumps(result, ensure_ascii=False, default=str)


def _build_default_registry() -> ToolRegistry:
    from laia_executor.tools.file_ops import (
        read_file, write_file, apply_patch, list_dir, glob_tool,
        grep_tool, delete_file, move_file, make_dir,
    )
    from laia_executor.tools.bash_tool import bash
    from laia_executor.tools.private_workspace import (
        private_workspace_search,
        private_workspace_read_node,
        private_workspace_add_node,
        private_workspace_find_related,
    )
    from laia_executor.tools.python_exec import python_exec
    from laia_executor.tools.process_tools import (
        process_start, process_list, process_status, process_kill,
    )
    from laia_executor.tools.cron_tools import (
        cron_create, cron_list, cron_delete,
    )

    reg = ToolRegistry()
    reg.register("read_file", read_file)
    reg.register("write_file", write_file)
    reg.register("apply_patch", apply_patch)
    reg.register("list_dir", list_dir)
    reg.register("glob", glob_tool)
    reg.register("grep", grep_tool)
    reg.register("bash", bash)
    reg.register("delete_file", delete_file)
    reg.register("move_file", move_file)
    reg.register("make_dir", make_dir)
    reg.register("private_workspace_search", private_workspace_search)
    reg.register("private_workspace_read_node", private_workspace_read_node)
    reg.register("private_workspace_add_node", private_workspace_add_node)
    reg.register("private_workspace_find_related", private_workspace_find_related)
    # Safe equivalents of the AGORA-local-denied tools, executed inside the
    # user's container instead of the orchestrator. See:
    #   - python_exec      ← replaces execute_code
    #   - process_*        ← replaces process
    #   - cron_*           ← replaces cronjob
    reg.register("python_exec", python_exec)
    reg.register("process_start", process_start)
    reg.register("process_list", process_list)
    reg.register("process_status", process_status)
    reg.register("process_kill", process_kill)
    reg.register("cron_create", cron_create)
    reg.register("cron_list", cron_list)
    reg.register("cron_delete", cron_delete)
    return reg


default_registry = _build_default_registry()
