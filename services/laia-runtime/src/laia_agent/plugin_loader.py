"""Plugin loader for Agora Agents — Python in-process tier 1.

A plugin lives at ``/opt/laia/plugins/<name>/`` and must contain:

  - ``manifest.yaml``:    metadata (name, version, language, description, entry)
  - ``__init__.py``:      Python module exposing ``register(ctx)`` that calls
                          ``ctx.register_tool(...)`` for each tool the plugin
                          contributes.

Discovery is done at agent startup; new plugins require a container restart
to take effect (hot-reload = sprint 3).

Sprint 2 only supports ``language: python``. Sprint 3 will add sidecar plugins
(Node, Go, binaries, web apps) via manifest declarations and subprocess RPC.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_PLUGINS_ROOT = Path("/opt/laia/plugins")


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    language: str
    path: Path
    register_fn: Callable[[Any], None] | None = None
    error: str | None = None


@dataclass
class PluginContext:
    """Sandbox-friendly registry passed to each plugin's register() function."""
    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("tool name must be a non-empty string")
        if not callable(fn):
            raise ValueError(f"tool {name!r}: fn must be callable")
        if name in self.tools:
            raise ValueError(f"tool {name!r} already registered by another plugin")
        self.tools[name] = fn


def _load_manifest(plugin_dir: Path) -> dict[str, Any]:
    """Read manifest.yaml (or manifest.json). Tolerant to missing PyYAML."""
    yaml_path = plugin_dir / "manifest.yaml"
    json_path = plugin_dir / "manifest.json"
    if yaml_path.is_file():
        try:
            import yaml  # type: ignore
            return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            # Fallback: try to parse a tiny subset (key: value lines)
            return _parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
    if json_path.is_file():
        import json
        return json.loads(json_path.read_text(encoding="utf-8")) or {}
    return {}


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Tiny subset YAML parser for {key: value} flat manifests."""
    out: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def discover_plugins(root: Path | None = None) -> list[Plugin]:
    """Scan ``root`` for plugin subdirectories and load each one.

    Each entry returned has ``.register_fn`` set if the plugin's __init__
    exposes a ``register`` callable, or ``.error`` set with the cause.
    """
    base = root or DEFAULT_PLUGINS_ROOT
    plugins: list[Plugin] = []
    if not base.is_dir():
        return plugins

    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        init = child / "__init__.py"
        if not init.is_file():
            logger.warning("Skipping plugin %s: missing __init__.py", child.name)
            continue

        manifest = _load_manifest(child)
        plugin = Plugin(
            name=str(manifest.get("name", child.name)),
            version=str(manifest.get("version", "0.0.0")),
            description=str(manifest.get("description", "")),
            language=str(manifest.get("language", "python")).lower(),
            path=child,
        )

        if plugin.language != "python":
            plugin.error = f"unsupported language: {plugin.language!r} (sprint 2 = python only)"
            plugins.append(plugin)
            continue

        try:
            mod_name = f"_agora_plugin_{child.name}"
            spec = importlib.util.spec_from_file_location(mod_name, init)
            if spec is None or spec.loader is None:
                plugin.error = "importlib failed to build spec"
                plugins.append(plugin)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            reg = getattr(module, "register", None)
            if reg is None or not callable(reg):
                plugin.error = "module does not expose register(ctx)"
            else:
                plugin.register_fn = reg
        except Exception as exc:
            logger.exception("Plugin %s failed to import", child.name)
            plugin.error = f"import error: {exc}"

        plugins.append(plugin)

    return plugins


def register_all(plugins: list[Plugin], ctx: PluginContext) -> dict[str, str | None]:
    """Invoke ``register(ctx)`` for each successfully-loaded plugin.

    Returns ``{plugin_name: error_message_or_None}``.
    """
    result: dict[str, str | None] = {}
    for p in plugins:
        if p.error:
            result[p.name] = p.error
            continue
        if p.register_fn is None:
            result[p.name] = "register function missing"
            continue
        try:
            p.register_fn(ctx)
            result[p.name] = None
        except Exception as exc:
            logger.exception("Plugin %s register() crashed", p.name)
            result[p.name] = f"register() raised: {exc}"
    return result
