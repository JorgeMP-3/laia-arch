"""C2's TUI — renders ``WizardScreen`` and ``ProgressEvent`` with rich.

Contract (matches what ``__main__.py`` looks for so the dev fallback is
replaced automatically once this module exists):

    render(screen: WizardScreen) -> dict | "back" | "quit"
    render_progress(event: ProgressEvent) -> None

Implementation notes
--------------------

* ``rich`` drives all output. ``rich.prompt`` reads user input with built-in
  validation for choices, integers and confirmations.
* Conditional fields are honored at render time: a field with
  ``depends_on={"provider": "*"}`` is asked only after the provider value
  has been collected on the same screen.
* The user can type ``b`` at any prompt to go back, or ``q`` to quit.
  Those map to the contract's ``"back"`` / ``"quit"`` return sentinels.
* For multi-action screens (back + next, or back + run), we render an
  inline list at the end and ask the user to pick by number.

The render is intentionally a single, generic function rather than one per
flow — each ``WizardScreen`` carries enough metadata to be rendered without
flow-specific code. Specialized polish for individual screens (custom
banners, mode-select layout, etc.) lives in dedicated helpers further down.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.prompt import Confirm, Prompt
from rich.text import Text

from ..contract import (
    Action,
    Field,
    ProgressEvent,
    WizardScreen,
    field_visible,
)
from . import components as comp
from .console import get_console
from .progress import render_progress as _render_progress
from .theme import THEME

# Re-exported for __main__.py.
__all__ = ["render", "render_progress"]


def render_progress(event: ProgressEvent) -> None:  # noqa: D401 - simple wrapper
    """See :func:`progress.render_progress`."""
    _render_progress(event)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render(screen: WizardScreen) -> dict[str, Any] | str:
    """Render a screen and return the user's input.

    Returns:
      * ``dict`` of field name -> value (the engine submits it back).
      * ``"back"`` if the user chose the back action.
      * ``"quit"`` if the user chose quit.
    """
    console = get_console()

    # Welcome polish: print the banner on the very first screen of a run.
    if screen.id == "mode_select":
        console.print()
        comp.banner(console)

    # Title bar
    console.print()
    comp.title(console, screen.title)

    # Description (multi-line, possibly markdown-ish)
    if screen.description:
        comp.info_paragraph(console, screen.description)

    # Field input loop
    values: dict[str, Any] = {}
    for f in screen.fields:
        if not field_visible(f, values):
            continue
        try:
            captured = _ask_field(f, values, console=console)
        except _NavigationSentinel as nav:
            return nav.value
        if f.type != "info":
            values[f.name] = captured

    # Help text (after the fields, before the action buttons).
    if screen.help_text:
        console.print(Text(f"  {THEME.g_info} {screen.help_text}", style=THEME.muted))

    # Actions
    chosen = _ask_action(screen.actions, console=console)
    if chosen is None:
        # Single auto-triggering action (e.g. lone "next") — nothing to record.
        return values
    if chosen.kind == "quit":
        return "quit"
    if chosen.kind == "back":
        return "back"
    if chosen.kind in ("submit", "next") and chosen.name not in ("next", ""):
        # Stamp the action so the engine can detect "run-now" vs "go to next".
        values["_action"] = chosen.name
    return values


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

class _NavigationSentinel(Exception):
    """Raised inside _ask_field to bubble back/quit up to render()."""

    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


def _ask_field(f: Field, current_values: dict[str, Any], *, console) -> Any:
    """Dispatch on field.type and return the captured value."""
    if f.type == "info":
        _print_info_field(f, console)
        return None
    if f.type == "choice":
        return _ask_choice(f, console)
    if f.type == "yesno":
        return _ask_yesno(f, console)
    if f.type == "password":
        return _ask_text(f, console, password=True)
    if f.type == "checklist":
        return _ask_checklist(f, console)
    # text / path / anything else with free text input
    return _ask_text(f, console, password=False)


def _print_info_field(f: Field, console) -> None:
    """Render a read-only label/paragraph field as a soft panel."""
    body: Any
    if isinstance(f.default, dict):
        rows = [(str(k), str(v)) for k, v in f.default.items()]
        body = comp.summary_table(rows)
    else:
        body = Text(str(f.default or ""), style=THEME.field_value)
    console.print(comp.panel(body, title_text=f.label, border_style=THEME.muted))


def _ask_choice(f: Field, console) -> str:
    """Numbered list + numeric prompt with bound checking."""
    choices = list(f.choices or ())
    if not choices:
        # No choices defined — fall back to a free-text input.
        return _ask_text(f, console, password=False)

    console.print()
    console.print(comp.field_label_line(
        f.label, required=bool(f.validator), help_text=f.help_text))
    console.print(comp.options_list(
        choices,
        default_value=str(f.default) if f.default else None,
    ))

    default_idx: int | None = None
    if f.default:
        for i, c in enumerate(choices, start=1):
            if c.value == f.default:
                default_idx = i
                break

    valid_idx = [str(i) for i in range(1, len(choices) + 1)] + ["b", "q"]
    while True:
        raw = Prompt.ask(
            f"  [{THEME.accent}]Elige[/]",
            choices=valid_idx,
            default=str(default_idx) if default_idx else None,
            show_choices=False,
            show_default=default_idx is not None,
            console=console,
        )
        raw = (raw or "").strip().lower()
        if raw == "b":
            raise _NavigationSentinel("back")
        if raw == "q":
            raise _NavigationSentinel("quit")
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1].value
        console.print(Text("  → entrada inválida.", style=THEME.warning))


def _ask_yesno(f: Field, console) -> bool:
    console.print()
    console.print(comp.field_label_line(f.label, help_text=f.help_text))
    return Confirm.ask(
        f"  [{THEME.accent}]>[/]",
        default=bool(f.default),
        console=console,
    )


def _ask_text(f: Field, console, *, password: bool) -> str:
    console.print()
    console.print(comp.field_label_line(
        f.label, required=bool(f.validator), help_text=f.help_text,
    ))
    if f.placeholder and not password:
        console.print(
            Text(f"  {THEME.g_dot} {f.placeholder}", style=THEME.field_placeholder)
        )
    default = f.default if isinstance(f.default, str) and f.default else None
    while True:
        raw = Prompt.ask(
            f"  [{THEME.accent}]>[/]",
            default=default,
            password=password,
            show_default=default is not None and not password,
            console=console,
        )
        if not password and raw in ("b", "B"):
            raise _NavigationSentinel("back")
        if not password and raw in ("q", "Q"):
            raise _NavigationSentinel("quit")
        return raw or ""


def _ask_checklist(f: Field, console) -> list[str]:
    choices = list(f.choices or ())
    if not choices:
        return []
    console.print()
    console.print(comp.field_label_line(
        f.label,
        help_text="Separa los números con coma. Enter sin nada = ninguno.",
    ))
    console.print(comp.options_list(choices))
    while True:
        raw = Prompt.ask(
            f"  [{THEME.accent}]Elige[/]",
            default="",
            console=console,
        )
        raw = (raw or "").strip().lower()
        if raw == "b":
            raise _NavigationSentinel("back")
        if raw == "q":
            raise _NavigationSentinel("quit")
        if raw == "":
            return []
        try:
            picks = [int(tok.strip()) for tok in raw.split(",") if tok.strip()]
        except ValueError:
            console.print(Text("  → sólo números separados por coma.",
                               style=THEME.warning))
            continue
        if any(p < 1 or p > len(choices) for p in picks):
            console.print(Text(f"  → fuera de rango (1-{len(choices)}).",
                               style=THEME.warning))
            continue
        return [choices[p - 1].value for p in picks]


def _ask_action(actions, *, console) -> Action | None:
    """Pick an action button. Returns None if there's only a single benign next."""
    actions = list(actions)
    if not actions:
        return None
    if len(actions) == 1 and actions[0].kind in ("next", "submit"):
        # Avoid an unnecessary prompt when there's only a single forward action.
        return actions[0]

    console.print()
    console.print(Text("  Acciones:", style=THEME.field_label))

    # Map letters 'b' and 'q' onto the back/quit actions when present, so
    # navigation keys work even at the action prompt.
    letter_for: dict[str, Action] = {}
    for a in actions:
        if a.kind == "back":
            letter_for["b"] = a
        elif a.kind == "quit":
            letter_for["q"] = a

    for i, a in enumerate(actions, start=1):
        glyph = _action_glyph(a)
        style = THEME.danger if a.danger else THEME.primary
        line = Text.assemble(
            (f"    [{i}] ", THEME.accent),
            (f"{glyph}  {a.label}", style),
        )
        console.print(line)

    valid = [str(i) for i in range(1, len(actions) + 1)] + list(letter_for)
    default = None
    for i, a in enumerate(actions, start=1):
        if a.kind in ("next", "submit"):
            default = str(i)
            break

    while True:
        raw = Prompt.ask(
            f"  [{THEME.accent}]>[/]",
            choices=valid,
            default=default,
            show_choices=False,
            show_default=default is not None,
            console=console,
        )
        raw = (raw or "").strip().lower()
        if raw in letter_for:
            return letter_for[raw]
        if raw.isdigit() and 1 <= int(raw) <= len(actions):
            return actions[int(raw) - 1]
        console.print(Text("  → entrada inválida.", style=THEME.warning))


def _action_glyph(a: Action) -> str:
    if a.kind == "back":
        return THEME.g_back
    if a.kind == "quit":
        return THEME.g_quit
    if a.kind == "submit":
        return THEME.g_run
    if a.kind == "next":
        return THEME.g_next
    return THEME.g_arrow


# Sanity check at import time. We accept any 0.x contract — breaking changes
# bump the major and will require a UI update anyway.
def _assert_contract_compat() -> None:
    from ..contract import CONTRACT_VERSION
    if not CONTRACT_VERSION.startswith("0."):
        sys.stderr.write(
            "WIZARD UI: contract version {} not supported by this UI build.\n"
            .format(CONTRACT_VERSION)
        )


_assert_contract_compat()
