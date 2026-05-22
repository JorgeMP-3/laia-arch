"""Non-interactive UI for headless / CI invocations.

Drives the wizard from a config file (``--config FILE``) without ever
prompting the user. Used by:

* CI pipelines that need a reproducible install/clone.
* Provisioning scripts that compose a config and shell out to the wizard.
* Tests that exercise the full engine without a TTY.

Config file format (YAML or JSON, auto-detected by extension)::

    mode: install                 # one of install|clone|diagnose|reset|connectivity
    values:
      admin_user: admin
      admin_pass: SuperSecret
      llm_provider: deepseek
      llm_api_key: sk-...
      init_lxd: true

The mode key is optional if ``--mode`` is passed on the command line.

Behaviour
---------
* For each :class:`WizardScreen` the engine asks us to render, we look up
  each :class:`Field` by name in ``values``.
* If a value is present, we return it.
* If a value is absent but the field has a ``default``, we use the default.
* If a value is absent AND there's no default AND the field is required
  (i.e. has a non-``None`` validator), we raise ``HeadlessMissingField``
  which the entry point translates to a clean exit 2 with the field
  name in the error message.
* Action selection: we auto-pick ``next``/``submit``/``run`` so the
  wizard advances through every screen and finally invokes ``execute()``.

The progress renderer just appends to stdout in a stable line format so
CI logs are diff-able.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .contract import WizardScreen, ProgressEvent, field_visible


class HeadlessMissingField(RuntimeError):
    """A required field had no value in the config and no default."""


def load_config(path: Path) -> dict[str, Any]:
    """Read a YAML or JSON file and return its content as a dict."""
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "El archivo de config es YAML pero pyyaml no está instalado. "
                "Usa JSON o instala pyyaml en el venv."
            ) from exc
        data = yaml.safe_load(raw) or {}
    else:
        # Default to JSON for unknown extensions; gives a clear error if wrong.
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Config raíz debe ser un objeto/mapa, no {type(data).__name__}.")
    return data


class HeadlessUI:
    """Drop-in for the UI module the engine expects.

    Exposes ``render(screen)`` and ``render_progress(event)`` so it can be
    passed to ``__main__._run`` as the ``ui`` argument.
    """

    def __init__(self, values: dict[str, Any]):
        self._values = dict(values)
        # Track which screens we've already submitted so we don't loop
        # forever if a flow returns the same screen id (defence in depth;
        # engine's cycle detector should already catch this).
        self._screen_visits: dict[str, int] = {}

    # -- C2 contract -----------------------------------------------------

    def render(self, screen: WizardScreen) -> dict[str, Any] | str:
        sid = screen.id
        self._screen_visits[sid] = self._screen_visits.get(sid, 0) + 1
        if self._screen_visits[sid] > 4:
            # Engine should have aborted us; this is a last-resort safety.
            raise RuntimeError(f"Headless: revisité la pantalla {sid!r} 5 veces.")

        out: dict[str, Any] = {}
        # Two passes: first collect the values we know about so the second
        # pass can evaluate depends_on against them. This matters when a
        # screen has more than one field and a later field depends on an
        # earlier one already in self._values.
        seeded = dict(self._values)
        for f in screen.fields:
            if f.type == "info":
                continue
            if f.name in seeded:
                continue
            if f.default is not None:
                seeded.setdefault(f.name, f.default)

        for f in screen.fields:
            if f.type == "info":
                continue
            if not field_visible(f, seeded):
                # Field is hidden by depends_on; don't even send it back.
                continue
            if f.name in self._values:
                out[f.name] = self._values[f.name]
                continue
            if f.default is not None:
                out[f.name] = f.default
                continue
            if f.validator and f.validator != "non_empty":
                # Let the validator decide; if it fails the engine surfaces
                # a ValidationResult error and the entry point exits 2.
                out[f.name] = ""
            else:
                raise HeadlessMissingField(
                    f"Falta '{f.name}' (pantalla {sid!r}) en el config y no "
                    f"tiene default. Añádelo al archivo de --config."
                )

        # Pick the most "advance" action available.
        action_priority = ("run", "submit", "next")
        chosen = None
        for action in screen.actions:
            if action.name in action_priority or action.kind in action_priority:
                chosen = action.name
                break
        if chosen:
            out["_action"] = "run" if chosen in ("run", "submit") else chosen
        return out

    def render_progress(self, event: ProgressEvent) -> None:
        # Stable, line-based output that's diff-friendly for CI.
        ts = f"+{event.elapsed_s:6.1f}s" if event.elapsed_s else "        "
        prefix = {
            "step_start":    "▶ ",
            "step_progress": "· ",
            "step_done":     "✓ ",
            "step_error":    "✗ ",
            "log_line":      "  ",
            "warning":       "⚠ ",
            "info":          "ℹ ",
            "summary":       "≡ ",
            "finished":      "● ",
        }.get(event.type, "  ")
        line = f"{ts} {prefix}{event.label}"
        print(line, flush=True)

    # The real UI exposes this so the engine's checkpoint-warning surfaces
    # nicely; headless just logs it.
    def render_warning_panel(self, title: str, body: str) -> None:
        print(f"        ⚠ {title}: {body}", flush=True, file=sys.stderr)


__all__ = ["HeadlessUI", "load_config", "HeadlessMissingField"]
