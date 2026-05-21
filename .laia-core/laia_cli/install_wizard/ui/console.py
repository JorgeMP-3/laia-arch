"""Single shared rich.Console instance.

Centralising the Console lets tests substitute a recording one and lets the
``--text-ui`` / ``$NO_COLOR`` paths take effect uniformly.
"""

from __future__ import annotations

import os

from rich.console import Console

_console: Console | None = None


def get_console() -> Console:
    """Lazily build (and cache) the wizard's Console.

    Honors ``$NO_COLOR`` (mono) and ``$FORCE_COLOR``. Width is auto-detected
    but capped at 120 so paragraph panels don't sprawl on wide terminals.
    """
    global _console
    if _console is not None:
        return _console
    width = None
    cols = os.environ.get("COLUMNS")
    if cols:
        try:
            width = min(int(cols), 120)
        except ValueError:
            width = None
    _console = Console(
        no_color=bool(os.environ.get("NO_COLOR")),
        force_terminal=bool(os.environ.get("FORCE_COLOR")),
        width=width,
        emoji=True,
        highlight=False,
    )
    return _console


def set_console(console: Console) -> None:
    """Used by tests to inject a recording Console."""
    global _console
    _console = console


def reset_console() -> None:
    """Drop the cached Console so the next get_console() rebuilds it."""
    global _console
    _console = None


__all__ = ["get_console", "set_console", "reset_console"]
