"""Wizard entry point.

The bash wrapper at ``bin/laia-wizard`` ends up doing::

    python3 -m laia_cli.install_wizard [args...]

We dispatch to the engine and the UI. If C2's ``ui`` package isn't ready,
we fall back to the input()-based dev UI in ``_dev_ui.py`` so the wizard
still works end-to-end during development.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from . import state as state_mod
from .contract import CONTRACT_VERSION
from .engine import WizardEngine


def _load_ui(force_dev: bool):
    """Return the UI module the wizard should drive.

    Order:
      * ``--text-ui`` flag → dev UI (forced).
      * Try ``laia_cli.install_wizard.ui`` (C2's package). Must expose
        ``render(screen)`` and ``render_progress(event)``.
      * Otherwise fall back to ``_dev_ui``.
    """
    if force_dev:
        from . import _dev_ui
        return _dev_ui

    try:
        from . import ui as real_ui  # type: ignore[no-redef]
        if hasattr(real_ui, "render") and hasattr(real_ui, "render_progress"):
            return real_ui
    except Exception:
        pass

    from . import _dev_ui
    return _dev_ui


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="laia-wizard",
        description="LAIA installer wizard — install, clone, diagnose, reset",
    )
    parser.add_argument("--resume", action="store_true",
                        help="Restaura el checkpoint y continúa donde te quedaste.")
    parser.add_argument("--text-ui", action="store_true",
                        help="Fuerza la UI mínima de texto (sin colores/rich).")
    parser.add_argument("--mode",
                        choices=("install", "clone", "diagnose", "reset", "connectivity"),
                        help="Salta el menú principal y arranca este modo directamente.")
    parser.add_argument("--version", action="store_true",
                        help="Imprime versión del contrato y sale.")
    args = parser.parse_args(argv)

    if args.version:
        print(f"laia-wizard contract {CONTRACT_VERSION}")
        return 0

    ui = _load_ui(args.text_ui)

    # State: --resume reads checkpoint, else fresh state. If --mode is given,
    # pre-set it (and skip the mode_select screen).
    state = state_mod.load() if args.resume else None
    if state is None:
        state = state_mod.WizardState()
    if args.mode and not state.mode:
        state.mode = args.mode
        state.current_screen_id = None  # let the flow pick its first screen

    engine = WizardEngine(state=state)

    rc = 0
    while not engine.is_done():
        screen = engine.next_screen()
        user_input = ui.render(screen)
        result = engine.submit(user_input)

        if not result.ok:
            # Errors are per-field; ask the UI to show them and re-render.
            for field_name, msg in result.errors.items():
                print(f"  ⚠  {field_name}: {msg}", file=sys.stderr)
            # Loop back; the next next_screen() returns the same screen.
            continue

        if result.ready_action:
            ok = True
            for event in engine.execute():
                ui.render_progress(event)
                if event.type == "step_error":
                    ok = False
                if event.type == "finished":
                    ok = bool((event.extra or {}).get("ok", True))
            rc = 0 if ok else 1
            engine.mark_done()
            break

    return rc


if __name__ == "__main__":
    sys.exit(main())
