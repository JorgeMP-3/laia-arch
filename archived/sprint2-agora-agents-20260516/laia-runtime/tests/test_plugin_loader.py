"""Tests for laia_agent.plugin_loader — discovery + register flow."""
from __future__ import annotations

from pathlib import Path

import pytest

from laia_agent.plugin_loader import (
    Plugin,
    PluginContext,
    discover_plugins,
    register_all,
)


def _write_plugin(root: Path, name: str, *, init_src: str, manifest: dict | None = None) -> Path:
    p = root / name
    p.mkdir(parents=True)
    (p / "__init__.py").write_text(init_src, encoding="utf-8")
    if manifest is not None:
        lines = [f"{k}: {v}" for k, v in manifest.items()]
        (p / "manifest.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ── PluginContext ────────────────────────────────────────────────────────────


def test_context_registers_tool():
    ctx = PluginContext()
    ctx.register_tool("hello", lambda: "world")
    assert "hello" in ctx.tools
    assert ctx.tools["hello"]() == "world"


def test_context_rejects_duplicate_tool():
    ctx = PluginContext()
    ctx.register_tool("hello", lambda: "a")
    with pytest.raises(ValueError, match="already registered"):
        ctx.register_tool("hello", lambda: "b")


def test_context_rejects_invalid_args():
    ctx = PluginContext()
    with pytest.raises(ValueError):
        ctx.register_tool("", lambda: None)
    with pytest.raises(ValueError):
        ctx.register_tool("x", "not callable")


# ── discover_plugins ─────────────────────────────────────────────────────────


def test_discover_returns_empty_when_no_root(tmp_path):
    assert discover_plugins(tmp_path / "nonexistent") == []


def test_discover_returns_empty_when_no_plugins(tmp_path):
    (tmp_path / "plugins").mkdir()
    assert discover_plugins(tmp_path / "plugins") == []


def test_discover_loads_python_plugin(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "greet",
        init_src="def register(ctx):\n    ctx.register_tool('hi', lambda: 'hola')\n",
        manifest={"name": "greet", "version": "1.2.3", "language": "python", "description": "test"},
    )
    plugins = discover_plugins(root)
    assert len(plugins) == 1
    p = plugins[0]
    assert p.name == "greet"
    assert p.version == "1.2.3"
    assert p.error is None
    assert callable(p.register_fn)


def test_discover_marks_plugin_without_register(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "broken",
        init_src="# no register here\n",
        manifest={"name": "broken", "language": "python"},
    )
    plugins = discover_plugins(root)
    assert len(plugins) == 1
    assert plugins[0].error is not None
    assert "register" in plugins[0].error


def test_discover_skips_hidden_dirs(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(root, ".hidden", init_src="def register(ctx): pass\n")
    _write_plugin(root, "_private", init_src="def register(ctx): pass\n")
    _write_plugin(root, "visible", init_src="def register(ctx): pass\n")
    plugins = discover_plugins(root)
    assert len(plugins) == 1
    assert plugins[0].name == "visible"


def test_discover_skips_dir_without_init(tmp_path):
    root = tmp_path / "plugins"
    (root / "noinit").mkdir(parents=True)
    plugins = discover_plugins(root)
    assert plugins == []


def test_discover_marks_unsupported_language(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "nodething",
        init_src="def register(ctx): pass\n",
        manifest={"name": "nodething", "language": "node"},
    )
    plugins = discover_plugins(root)
    assert len(plugins) == 1
    assert plugins[0].error is not None
    assert "unsupported language" in plugins[0].error.lower() or "node" in plugins[0].error


def test_discover_handles_import_error(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "syntaxerr",
        init_src="def register(ctx:\n    pass\n",  # bad syntax
    )
    plugins = discover_plugins(root)
    assert len(plugins) == 1
    assert plugins[0].error is not None


# ── register_all ─────────────────────────────────────────────────────────────


def test_register_all_invokes_register(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "p1",
        init_src="def register(ctx):\n    ctx.register_tool('t1', lambda: 'p1')\n",
    )
    _write_plugin(
        root, "p2",
        init_src="def register(ctx):\n    ctx.register_tool('t2', lambda: 'p2')\n",
    )
    plugins = discover_plugins(root)
    ctx = PluginContext()
    result = register_all(plugins, ctx)
    assert result == {"p1": None, "p2": None}
    assert ctx.tools["t1"]() == "p1"
    assert ctx.tools["t2"]() == "p2"


def test_register_all_captures_register_crash(tmp_path):
    root = tmp_path / "plugins"
    _write_plugin(
        root, "crashy",
        init_src="def register(ctx):\n    raise RuntimeError('boom')\n",
    )
    plugins = discover_plugins(root)
    result = register_all(plugins, PluginContext())
    assert "boom" in result["crashy"]
