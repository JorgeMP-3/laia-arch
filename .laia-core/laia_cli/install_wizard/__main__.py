"""Wizard entry point.

The bash wrapper at ``bin/laia-wizard`` ends up doing::

    python3 -m laia_cli.install_wizard [args...]

We dispatch to the engine and the UI. If C2's ``ui`` package isn't ready,
we fall back to the input()-based dev UI in ``_dev_ui.py`` so the wizard
still works end-to-end during development.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from . import state as state_mod
from .contract import CONTRACT_VERSION
from .engine import WizardEngine


def _setup_logfile() -> Path:
    """Send wizard logs to a rotating file under ~/.cache (5 MB × 3).

    Returns the resolved path so we can mention it on error.
    """
    cache_dir = Path(
        os.environ.get("XDG_CACHE_HOME") or
        os.path.join(os.path.expanduser("~"), ".cache")
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = cache_dir / "laia-wizard.log"
    handler = RotatingFileHandler(
        str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicating handlers when re-entered from tests.
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler) and h.baseFilename == str(log_path):
            return log_path
    root.addHandler(handler)
    return log_path


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


def _build_headless_ui(config_path: Path, mode_override: str | None):
    """Construct a HeadlessUI from the user's config file.

    Returns (ui_instance, resolved_mode). Raises FileNotFoundError or
    RuntimeError/ValueError on bad input — the caller turns those into
    exit-2 messages.
    """
    from . import _headless_ui

    if not config_path.is_file():
        raise FileNotFoundError(f"--config no encontrado: {config_path}")
    data = _headless_ui.load_config(config_path)

    mode = mode_override or data.get("mode")
    if not mode:
        raise ValueError(
            "Modo headless requiere --mode o un campo `mode:` en el config."
        )
    values = data.get("values") or {}
    if not isinstance(values, dict):
        raise ValueError("El campo `values` del config debe ser un objeto.")
    return _headless_ui.HeadlessUI(values), mode


def _run(args, ui) -> int:
    """The actual loop. Wrapped by ``main()`` for clean Ctrl-C handling."""
    state = state_mod.load() if args.resume else None
    # If load() quarantined a corrupt/stale checkpoint, surface that fact
    # immediately so the user knows why they're not resuming.
    warning = state_mod.consume_load_warning()
    if warning:
        # The UI module may or may not have a banner helper; fall back to
        # plain stderr if not. The engine still proceeds normally.
        try:
            show_panel = getattr(ui, "render_warning_panel", None)
            if callable(show_panel):
                show_panel("Checkpoint inválido", warning)
            else:
                print(f"  ⚠  {warning}", file=sys.stderr)
        except Exception:
            print(f"  ⚠  {warning}", file=sys.stderr)

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
            # Errors are per-field; print them and re-render the same screen.
            for field_name, msg in result.errors.items():
                print(f"  ⚠  {field_name}: {msg}", file=sys.stderr)
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
    parser.add_argument("--config", type=Path,
                        help=("Archivo YAML/JSON con respuestas pre-rellenadas. "
                              "Implica modo headless (no se pide nada al usuario)."))
    parser.add_argument("--yes", "-y", action="store_true",
                        help=("Modo no-interactivo: usa defaults para todo lo que "
                              "no esté en --config y avanza sin confirmar. "
                              "Falla con exit 2 si falta algún campo requerido."))
    parser.add_argument("--version", action="store_true",
                        help="Imprime versión del contrato y sale.")
    parser.add_argument("--debug", action="store_true",
                        help="No oculta tracebacks (sólo desarrollo).")
    args = parser.parse_args(argv)

    if args.version:
        print(f"laia-wizard contract {CONTRACT_VERSION}")
        return 0

    log_path = _setup_logfile()
    logging.getLogger("laia.wizard").info(
        "wizard start argv=%s contract=%s", sys.argv, CONTRACT_VERSION,
    )

    # Headless mode (--config FILE [--yes]) bypasses the interactive UI
    # entirely. --yes alone (no config) means "advance through screens
    # using defaults" — still uses the regular UI but skips prompts. We
    # combine these in _load_ui via the HeadlessUI replacement so the
    # engine doesn't need to know.
    if args.config is not None:
        try:
            headless_ui, resolved_mode = _build_headless_ui(args.config, args.mode)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"  ✗  {exc}", file=sys.stderr)
            return 2
        args.mode = resolved_mode
        ui = headless_ui
    elif args.yes and args.mode:
        # --yes without --config: use HeadlessUI with no values, so every
        # field falls back to its default. Required fields without defaults
        # will exit 2 (intentional — CI must declare them via --config).
        from . import _headless_ui
        ui = _headless_ui.HeadlessUI({})
    else:
        ui = _load_ui(args.text_ui)

    from ._headless_ui import HeadlessMissingField

    try:
        return _run(args, ui)
    except HeadlessMissingField as exc:
        # A required headless field was missing. Surface the field name and
        # exit 2 (matches CLI convention for "bad arguments").
        print(f"  ✗  Campo requerido faltante: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # Ctrl-C / SIGINT: print a clean line, leave checkpoint in place so
        # the user can --resume. 130 is the POSIX convention for SIGINT.
        logging.getLogger("laia.wizard").info("wizard interrupted by user")
        print()
        print("  ✕  Cancelado por el usuario. "
              "Re-ejecuta con --resume para continuar donde lo dejaste.",
              file=sys.stderr)
        return 130
    except EOFError:
        # stdin closed mid-prompt (typically a piped wizard run that ran out
        # of input). Differentiate from Ctrl-C in the exit code.
        logging.getLogger("laia.wizard").info("wizard EOF on stdin")
        print()
        print("  ✕  Fin de entrada antes de completar.",
              file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last-chance handler
        # Always record the full traceback to the rotating log so the user
        # can post-mortem even without --debug.
        logging.getLogger("laia.wizard").exception("wizard crashed: %s", exc)
        if args.debug:
            raise
        print()
        print(f"  ✗  Error inesperado: {exc}", file=sys.stderr)
        print(f"     Detalles completos en {log_path}", file=sys.stderr)
        print("     (Re-ejecuta con --debug para ver el traceback en pantalla.)",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
