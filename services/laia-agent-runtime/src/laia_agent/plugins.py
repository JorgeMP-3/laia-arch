from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from .config import AgentConfig

logger = logging.getLogger("laia.plugins")

TaskHandler = Callable[[AgentConfig, dict[str, Any]], dict[str, Any]]


class PluginRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}
        self._loaded: list[str] = []

    def register(self, task_type: str, handler: TaskHandler) -> None:
        if task_type in self._handlers:
            logger.warning("plugin overwriting task_type=%s", task_type)
        self._handlers[task_type] = handler
        logger.info("plugin registered task_type=%s", task_type)

    def dispatch(self, task_type: str) -> TaskHandler | None:
        return self._handlers.get(task_type)

    @property
    def loaded_plugins(self) -> list[str]:
        return list(self._loaded)

    @property
    def registered_types(self) -> list[str]:
        return sorted(self._handlers.keys())


def load_plugins(config: AgentConfig, registry: PluginRegistry) -> None:
    plugins_dir = config.root / "plugins"
    if not plugins_dir.exists():
        plugins_dir.mkdir(parents=True, exist_ok=True)
        return

    for fpath in sorted(plugins_dir.glob("*.py")):
        name = fpath.stem
        try:
            spec = importlib.util.spec_from_file_location(f"laia_plugin_{name}", str(fpath))
            if spec is None or spec.loader is None:
                logger.warning("plugin skip %s: could not load spec", name)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "register"):
                module.register(registry)
            elif hasattr(module, "TASKS"):
                for task_type, handler in module.TASKS.items():
                    registry.register(task_type, handler)
            else:
                logger.warning("plugin %s has no register() or TASKS", name)
                continue

            registry._loaded.append(name)
            logger.info("plugin loaded: %s", name)
        except Exception as exc:
            logger.error("plugin error %s: %s", name, exc)


_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
