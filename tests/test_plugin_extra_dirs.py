#!/usr/bin/env python3
"""Smoke test for the LAIA_EXTRA_PLUGIN_DIRS loader extension.

Used by Fase D of the marketplace-v0.1 plan. Run with the agora-backend
venv so PyYAML is available and PYTHONPATH points at .laia-core:

    PYTHONPATH=/home/laia-hermes/LAIA/.laia-core \\
    /home/laia-hermes/LAIA/services/agora-backend/.venv/bin/python \\
        /home/laia-hermes/LAIA/tests/test_plugin_extra_dirs.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="laia_extra_plugins_"))
    extra_dir = tmpdir / "extra"
    laia_home = tmpdir / "laia-home"
    extra_dir.mkdir(parents=True)
    laia_home.mkdir(parents=True)

    plugin = extra_dir / "extradir-hello"
    plugin.mkdir()
    (plugin / "plugin.yaml").write_text(
        textwrap.dedent(
            """\
            slug: extradir-hello
            name: extradir-hello
            version: 0.1.0
            kind: standalone
            """
        )
    )
    (plugin / "__init__.py").write_text(
        textwrap.dedent(
            """\
            def register(ctx):
                # Smoke marker on the context — we read it back to confirm the
                # plugin was loaded from the extra dir, not from a bundled path.
                ctx.metadata = getattr(ctx, "metadata", {})
                ctx.metadata["extradir_hello"] = True
            """
        )
    )

    # Force discovery to see the extra dir and ENABLE it via config-style env.
    # The loader is opt-in for non-bundled plugins, so we use LAIA_HOME=isolated
    # plus the project flag to keep the surface small.
    env_old = {k: os.environ.get(k) for k in (
        "LAIA_HOME", "LAIA_EXTRA_PLUGIN_DIRS", "LAIA_ENABLE_PROJECT_PLUGINS",
        "LAIA_PLUGINS_ENABLED",
    )}
    os.environ["LAIA_HOME"] = str(laia_home)
    os.environ["LAIA_EXTRA_PLUGIN_DIRS"] = str(extra_dir)
    os.environ["LAIA_PLUGINS_ENABLED"] = "extradir-hello"

    # Drop any cached PluginManager / config from a previous run.
    for mod in list(sys.modules):
        if mod == "laia_cli.plugins" or mod.startswith("laia_cli.plugins."):
            del sys.modules[mod]

    try:
        from laia_cli import plugins as plugins_mod  # type: ignore
    except Exception as exc:
        print(f"FAIL: cannot import laia_cli.plugins: {exc}", file=sys.stderr)
        return 2

    manager = plugins_mod.PluginManager()
    manager.discover_and_load(force=True)

    keys = list(manager._plugins.keys())
    if "extradir-hello" not in keys:
        print(f"FAIL: plugin not discovered. Loaded keys: {keys}", file=sys.stderr)
        return 1

    loaded = manager._plugins["extradir-hello"]
    if not getattr(loaded, "enabled", False):
        print(f"FAIL: plugin discovered but not enabled: {getattr(loaded, 'error', '?')}", file=sys.stderr)
        return 1

    # Cleanup
    for k, v in env_old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    shutil.rmtree(tmpdir, ignore_errors=True)

    print("test_plugin_extra_dirs: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
