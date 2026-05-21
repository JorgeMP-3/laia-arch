"""Reusable visual primitives.

Every screen and every progress event eventually goes through one of these.
Rendering is centralized so:

* The theme is applied in exactly one place.
* Tests can capture output by passing a controlled ``Console``.
* Future polish (animations, alternate themes) lands without touching flows.

Public surface
--------------

``banner()``      — top-of-screen LAIA banner with version line.
``title()``       — single screen title bar.
``panel()``       — wraps content in a themed rich.Panel.
``error_box()``   — red panel for fatal messages.
``warning_box()`` — yellow panel for non-fatal hints.
``success_box()`` — green panel for completions.
``check_row()``   — single ✓/⚠/✗ line for diagnose-style lists.
``step_indicator()`` — "Step 2 / 5: Admin user" style breadcrumb.
``summary_table()`` — two-column key/value rich.Table.
``options_list()`` — numbered list for choice fields.
``hr()``          — horizontal rule.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..contract import Choice
from .theme import THEME

# ---------------------------------------------------------------------------
# Console — single shared instance; tests can substitute via capture_console().
# ---------------------------------------------------------------------------

_BANNER_ART = r"""
 _      _    ___    _
| |    / \  |_ _|  / \
| |   / _ \  | |  / _ \
| |__/ ___ \ | | / ___ \
|____/_/   \_\___/_/   \_\
"""


def banner(console: Console, version: str | None = None) -> None:
    """Print the LAIA brand banner at the top of a fresh screen."""
    art = Text(_BANNER_ART.strip("\n"), style=THEME.primary, justify="center")
    tag = Text(THEME.tagline, style=THEME.muted, justify="center")
    if version:
        tag = Text.assemble(
            (THEME.tagline, THEME.muted),
            ("   ·   ", THEME.muted),
            (f"v{version}", THEME.accent),
        )
        tag.justify = "center"
    body = Group(art, tag)
    console.print(Padding(body, (1, 0)))


def title(console: Console, text: str, *, step: tuple[int, int] | None = None) -> None:
    """Print a single screen title.

    ``step=(n, total)`` adds a discreet step indicator next to the title.
    """
    if step:
        label = Text.assemble(
            (text, THEME.primary),
            ("    ", ""),
            (f"[{step[0]}/{step[1]}]", THEME.muted),
        )
    else:
        label = Text(text, style=THEME.primary)
    console.print(Rule(label, style=THEME.panel_border, align="left"))


def panel(content: RenderableType, *, title_text: str | None = None,
          border_style: str | None = None) -> Panel:
    """Build a themed Panel. Caller console.print()s it."""
    return Panel(
        content,
        title=title_text,
        title_align="left",
        border_style=border_style or THEME.panel_border,
        padding=(1, 2),
    )


def error_box(console: Console, message: str, *, hint: str | None = None) -> None:
    body: list[RenderableType] = [Text(message, style=THEME.error)]
    if hint:
        body.append(Text(""))
        body.append(Text(f"{THEME.g_arrow} {hint}", style=THEME.muted))
    console.print(panel(Group(*body),
                        title_text=f"{THEME.g_err}  Error",
                        border_style=THEME.error))


def warning_box(console: Console, message: str) -> None:
    console.print(panel(Text(message, style=THEME.warning),
                        title_text=f"{THEME.g_warn}  Aviso",
                        border_style=THEME.warning))


def success_box(console: Console, message: str) -> None:
    console.print(panel(Text(message, style=THEME.success),
                        title_text=f"{THEME.g_ok}  Listo",
                        border_style=THEME.success))


def info_paragraph(console: Console, text: str) -> None:
    """Render a multi-line description as a soft-bordered panel.

    Markdown is rendered through rich.markdown so bullet lists in flow
    descriptions look natural without flow code having to know about rich.
    """
    if any(line.lstrip().startswith(("- ", "* ", "1. ")) for line in text.splitlines()):
        body: RenderableType = Markdown(text)
    else:
        body = Text(text)
    console.print(panel(body, border_style=THEME.muted))


def check_row(label: str, *, status: str) -> Text:
    """Build a check row used by diagnose / summary screens.

    ``status`` is one of ``ok|warn|err|busy|info|dot``.
    """
    glyph_map = {
        "ok":   (THEME.g_ok,   THEME.success),
        "warn": (THEME.g_warn, THEME.warning),
        "err":  (THEME.g_err,  THEME.error),
        "busy": (THEME.g_busy, THEME.accent),
        "info": (THEME.g_info, THEME.secondary),
        "dot":  (THEME.g_dot,  THEME.muted),
    }
    glyph, color = glyph_map.get(status, (THEME.g_dot, THEME.muted))
    return Text.assemble(
        ("  ", ""),
        (glyph, color),
        ("  ", ""),
        (label, THEME.field_value),
    )


def step_indicator(console: Console, current: int, total: int, label: str) -> None:
    """Optional sub-title showing where the user is in a multi-step flow."""
    bar = ""
    for i in range(1, total + 1):
        if i < current:
            bar += f"[{THEME.success}]●[/]"
        elif i == current:
            bar += f"[{THEME.accent}]●[/]"
        else:
            bar += f"[{THEME.muted}]○[/]"
        if i < total:
            bar += f"[{THEME.muted}]──[/]"
    console.print(f"  {bar}  [{THEME.muted}]paso[/] {current}/{total}: "
                  f"[{THEME.primary}]{label}[/]")


def summary_table(rows: Iterable[tuple[str, str]],
                  *, title_text: str | None = None) -> Table:
    """Two-column key/value table."""
    table = Table(
        title=title_text,
        title_style=THEME.primary,
        title_justify="left",
        show_header=False,
        show_edge=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column(style=THEME.field_label, justify="right", no_wrap=True)
    table.add_column(style=THEME.field_value, overflow="fold")
    for k, v in rows:
        table.add_row(k, str(v))
    return table


def options_list(choices: Sequence[Choice], *, default_value: str | None = None
                ) -> Table:
    """Render choices as a numbered list with description + recommended badge."""
    table = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    table.add_column(style=THEME.accent, no_wrap=True, justify="right")
    table.add_column(style=THEME.field_value, overflow="fold")
    for i, c in enumerate(choices, start=1):
        head = Text(c.label, style=f"{THEME.field_label}")
        if c.value == default_value:
            head.append(f"  {THEME.g_arrow} default", style=THEME.muted)
        if c.recommended:
            head.append("  [recomendado]", style=THEME.success)
        cell: RenderableType
        if c.description:
            cell = Group(head, Text(c.description, style=THEME.muted))
        else:
            cell = head
        table.add_row(f"[{i}]", cell)
    return table


def actions_hint(console: Console, *, has_back: bool, has_quit: bool) -> None:
    """Discreet footer reminding the user about back/quit shortcuts."""
    parts: list[str] = []
    if has_back:
        parts.append(f"[{THEME.muted}]'b' atrás[/]")
    if has_quit:
        parts.append(f"[{THEME.muted}]'q' salir[/]")
    if not parts:
        return
    console.print("  " + "   ".join(parts))


def hr(console: Console) -> None:
    console.print(Rule(style=THEME.muted))


def field_label_line(label: str, *, required: bool = False,
                     help_text: str | None = None) -> Text:
    line = Text(label, style=THEME.field_label)
    if required:
        line.append(" *", style=THEME.error)
    if help_text:
        line.append("  ", style="")
        line.append(help_text, style=THEME.muted)
    return line


__all__ = [
    "banner",
    "title",
    "panel",
    "error_box",
    "warning_box",
    "success_box",
    "info_paragraph",
    "check_row",
    "step_indicator",
    "summary_table",
    "options_list",
    "actions_hint",
    "hr",
    "field_label_line",
]
