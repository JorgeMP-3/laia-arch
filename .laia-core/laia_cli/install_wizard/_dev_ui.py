"""Minimal input()-based UI used by C1 for local testing.

C2 is going to ship the real rich/prompt_toolkit UI in ``ui/__init__.py``.
Until then (and as a permanent fallback for terminals where rich misbehaves),
``__main__.py`` falls back to this module — it implements the same
``render(screen)`` contract using plain ``input()`` so the engine can be
exercised end-to-end without any external dependency beyond stdlib.

This file is NOT meant to be pretty. It's correctness-only.
"""

from __future__ import annotations

import getpass
import os
import sys
from typing import Any

from .contract import WizardScreen, field_visible


def _emit(line: str = "") -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _read_choice(label: str, choices, default: str | None) -> str:
    while True:
        _emit(f"  {label}")
        for i, c in enumerate(choices, 1):
            star = " ★" if c.value == default else ""
            _emit(f"    [{i}] {c.label}{star}")
            if c.description:
                _emit(f"         {c.description}")
        raw = input(f"  Elige 1-{len(choices)} [enter=default]: ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1].value
        _emit("  → entrada inválida, intenta de nuevo.")


def _read_yesno(label: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"  {label} {suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "s", "sí", "si"):
            return True
        if raw in ("n", "no"):
            return False
        _emit("  → responde y/n.")


def render(screen: WizardScreen) -> dict[str, Any] | str:
    """Render ``screen`` via plain stdin/stdout and return user inputs."""
    _emit()
    _emit("═" * 70)
    _emit(f"  {screen.title}")
    if screen.description:
        for line in screen.description.splitlines():
            _emit(f"  {line}")
    _emit("═" * 70)

    values: dict[str, Any] = {}
    for f in screen.fields:
        if not field_visible(f, values):
            continue
        label = f.label + (f"  ({f.help_text})" if f.help_text else "")
        if f.type == "info":
            _emit()
            default = f.default if f.default is not None else ""
            for line in str(default).splitlines():
                _emit(f"  {line}")
            continue
        if f.type == "choice":
            values[f.name] = _read_choice(label, f.choices or (), str(f.default) if f.default else None)
        elif f.type == "yesno":
            values[f.name] = _read_yesno(label, bool(f.default))
        elif f.type == "password":
            raw = getpass.getpass(f"  {label}: ")
            values[f.name] = raw
        elif f.type in ("text", "path"):
            ph = f.placeholder or ""
            default = f.default
            prompt = f"  {label}"
            if ph:
                prompt += f"  [{ph}]"
            if default:
                prompt += f"  (default: {default})"
            prompt += ": "
            raw = input(prompt)
            values[f.name] = raw if raw else (default or "")
        elif f.type == "checklist":
            _emit(f"  {label} (separa números con coma, vacío = ninguno)")
            cs = f.choices or ()
            for i, c in enumerate(cs, 1):
                _emit(f"    [{i}] {c.label}")
            raw = input("  Elige: ").strip()
            selected = []
            for token in raw.split(","):
                token = token.strip()
                if token.isdigit() and 1 <= int(token) <= len(cs):
                    selected.append(cs[int(token) - 1].value)
            values[f.name] = selected

    # Pick an action
    if len(screen.actions) == 1:
        a = screen.actions[0]
        if a.kind in ("quit",):
            return "quit"
        if a.kind == "back":
            return "back"
        return values
    _emit()
    _emit("  Acciones:")
    for i, a in enumerate(screen.actions, 1):
        flag = " (PELIGRO)" if a.danger else ""
        _emit(f"    [{i}] {a.label}{flag}")
    while True:
        raw = input(f"  Elige 1-{len(screen.actions)}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(screen.actions):
            chosen = screen.actions[int(raw) - 1]
            break
        _emit("  → entrada inválida.")
    if chosen.kind == "quit":
        return "quit"
    if chosen.kind == "back":
        return "back"
    if chosen.kind == "submit":
        values["_action"] = chosen.name or "submit"
    return values


def render_progress(event) -> None:
    """Print a ProgressEvent in a single line."""
    glyph = {
        "step_start":    "▸",
        "step_progress": "·",
        "step_done":     "✓",
        "step_error":    "✗",
        "log_line":      " ",
        "info":          "ℹ",
        "warning":       "⚠",
        "summary":       "≡",
        "finished":      "■",
    }.get(event.type, "·")
    _emit(f"  {glyph} {event.label}")
    if event.type == "summary" and event.extra:
        rows = event.extra.get("rows") or []
        for k, v in rows:
            _emit(f"      {k}: {v}")


__all__ = ["render", "render_progress"]
