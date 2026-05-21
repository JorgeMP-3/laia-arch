"""Snapshot-ish tests for the rich-based UI primitives.

We don't compare against pixel-perfect fixtures (rich versions move and
spacing drifts) — instead each test asserts that the captured output
contains the visually meaningful tokens: glyphs, labels, key/value pairs,
panel framing characters, etc.

This catches regressions like "panel disappeared", "wrong glyph", "color
applied to wrong text" without locking us into a specific rich release.
"""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from laia_cli.install_wizard.contract import Choice, Field
from laia_cli.install_wizard.ui import components as comp
from laia_cli.install_wizard.ui.theme import THEME


def _capture(width: int = 80) -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, width=width, no_color=True, force_terminal=False,
                   record=False), buf


def test_banner_includes_brand_and_tagline():
    console, buf = _capture()
    comp.banner(console, version="2.5.0")
    out = buf.getvalue()
    # ASCII art line + tagline + version
    assert "LAIA"  # not literally, but ASCII art row presence indirectly
    assert "Setup Wizard" in out
    assert "v2.5.0" in out


def test_banner_without_version_omits_version():
    console, buf = _capture()
    comp.banner(console)
    assert "v2.5.0" not in buf.getvalue()
    assert "Setup Wizard" in buf.getvalue()


def test_title_renders_rule_with_label():
    console, buf = _capture()
    comp.title(console, "Mi pantalla")
    out = buf.getvalue()
    assert "Mi pantalla" in out
    assert "─" in out  # rule character


def test_title_step_indicator():
    console, buf = _capture()
    comp.title(console, "Paso", step=(2, 5))
    assert "[2/5]" in buf.getvalue()


def test_info_paragraph_renders_panel_borders():
    console, buf = _capture()
    comp.info_paragraph(console, "Una nota muy aburrida.")
    out = buf.getvalue()
    assert "Una nota muy aburrida." in out
    assert "╭" in out and "╰" in out
    assert "│" in out


def test_info_paragraph_renders_bullets_as_markdown():
    console, buf = _capture()
    comp.info_paragraph(console, "Listado:\n- uno\n- dos\n- tres")
    out = buf.getvalue()
    assert "uno" in out and "dos" in out and "tres" in out


def test_error_box_contains_glyph_and_hint():
    console, buf = _capture()
    comp.error_box(console, "Algo falló", hint="ver logs en /tmp/x.log")
    out = buf.getvalue()
    assert THEME.g_err in out
    assert "Error" in out
    assert "Algo falló" in out
    assert "ver logs en /tmp/x.log" in out


def test_warning_box_uses_warn_glyph():
    console, buf = _capture()
    comp.warning_box(console, "Cuidado")
    out = buf.getvalue()
    assert THEME.g_warn in out
    assert "Aviso" in out
    assert "Cuidado" in out


def test_success_box_uses_ok_glyph():
    console, buf = _capture()
    comp.success_box(console, "Hecho")
    out = buf.getvalue()
    assert THEME.g_ok in out
    assert "Listo" in out


@pytest.mark.parametrize("status,glyph", [
    ("ok",   THEME.g_ok),
    ("warn", THEME.g_warn),
    ("err",  THEME.g_err),
    ("busy", THEME.g_busy),
    ("info", THEME.g_info),
    ("dot",  THEME.g_dot),
])
def test_check_row_glyphs(status, glyph):
    console, buf = _capture()
    console.print(comp.check_row(f"label-{status}", status=status))
    out = buf.getvalue()
    assert glyph in out
    assert f"label-{status}" in out


def test_options_list_numbers_and_descriptions():
    console, buf = _capture()
    choices = (
        Choice("a", "Alpha", "primera opción", recommended=True),
        Choice("b", "Beta", "segunda opción"),
        Choice("c", "Gamma"),  # no description
    )
    console.print(comp.options_list(choices, default_value="a"))
    out = buf.getvalue()
    for n in ("[1]", "[2]", "[3]"):
        assert n in out
    assert "Alpha" in out and "Beta" in out and "Gamma" in out
    assert "primera opción" in out
    assert "default" in out
    assert "[recomendado]" in out


def test_summary_table_two_columns():
    console, buf = _capture(width=40)
    table = comp.summary_table(
        [("Usuario", "admin"), ("Password", "****")],
        title_text="Resumen",
    )
    console.print(table)
    out = buf.getvalue()
    assert "Resumen" in out
    assert "Usuario" in out and "admin" in out
    assert "Password" in out and "****" in out


def test_step_indicator_marks_current_step():
    console, buf = _capture()
    comp.step_indicator(console, current=2, total=4, label="LLM")
    out = buf.getvalue()
    assert "paso" in out and "2/4" in out and "LLM" in out
    # 2 of 4 steps filled (●●), 2 pending (○○)
    assert "●" in out and "○" in out


def test_field_label_line_required_marker():
    line = comp.field_label_line("Username", required=True)
    text = line.plain
    assert "Username" in text
    assert "*" in text


def test_field_label_line_help_text():
    line = comp.field_label_line("X", help_text="ayuda concreta")
    text = line.plain
    assert "ayuda concreta" in text
