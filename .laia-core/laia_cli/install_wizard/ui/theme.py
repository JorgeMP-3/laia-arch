"""Visual theme — the single source of truth for colors, glyphs, and titles.

C2 deliberately keeps everything cosmetic in one place so a theme swap is a
one-file change. Override via ``$LAIA_WIZARD_THEME`` env var (``default`` is
the only built-in for now).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

ThemeName = Literal["default", "mono"]


@dataclass(frozen=True)
class Theme:
    """Named color tokens + glyph set used across the wizard UI.

    Colors are rich-style strings (``"cyan"``, ``"bold bright_blue"``, etc.).
    NO_COLOR=1 in the environment forces the ``mono`` variant automatically.
    """

    # ---- colors --------------------------------------------------------------
    primary: str = "bold cyan"
    secondary: str = "bright_blue"
    accent: str = "bold magenta"
    success: str = "bold green"
    warning: str = "bold yellow"
    error: str = "bold red"
    danger: str = "bold red on black"
    muted: str = "dim white"
    title: str = "bold bright_white on blue"
    panel_border: str = "cyan"
    field_label: str = "bold"
    field_value: str = "bright_white"
    field_placeholder: str = "italic dim white"
    code: str = "bold bright_yellow on grey15"

    # ---- glyphs --------------------------------------------------------------
    g_ok: str = "✓"
    g_err: str = "✗"
    g_warn: str = "⚠"
    g_info: str = "ℹ"
    g_arrow: str = "▸"
    g_busy: str = "⏳"
    g_check: str = "■"
    g_dot: str = "·"
    g_run: str = "▶"
    g_back: str = "←"
    g_next: str = "→"
    g_quit: str = "✕"

    # ---- copy ---------------------------------------------------------------
    brand: str = "LAIA"
    tagline: str = "Setup Wizard"

    # ---- progress ------------------------------------------------------------
    log_tail_lines: int = 8     # how many log lines to keep visible at once
    progress_refresh_hz: int = 10

    # ---- typography ----------------------------------------------------------
    bullet: str = "•"


_MONO = Theme(
    primary="bold",
    secondary="bold",
    accent="bold",
    success="bold",
    warning="bold",
    error="bold",
    danger="bold reverse",
    muted="dim",
    title="bold reverse",
    panel_border="white",
    field_label="bold",
    field_value="default",
    field_placeholder="dim",
    code="bold",
)


def get_theme(name: ThemeName | None = None) -> Theme:
    """Resolve the active theme.

    Priority: explicit ``name`` arg > ``$LAIA_WIZARD_THEME`` env var > default.
    ``$NO_COLOR=1`` overrides everything and forces the ``mono`` variant
    (per https://no-color.org/).
    """
    if os.environ.get("NO_COLOR"):
        return _MONO
    chosen = name or os.environ.get("LAIA_WIZARD_THEME") or "default"
    if chosen == "mono":
        return _MONO
    return Theme()


# A module-level singleton so call sites don't pass the theme around.
THEME: Theme = get_theme()


def refresh_theme() -> Theme:
    """Re-read the env var; useful from tests that patch ``$NO_COLOR``."""
    global THEME
    THEME = get_theme()
    return THEME


__all__ = ["Theme", "ThemeName", "THEME", "get_theme", "refresh_theme"]
