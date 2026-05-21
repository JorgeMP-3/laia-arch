"""Progress event renderer — visual tokens by event type."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from laia_cli.install_wizard.contract import ProgressEvent
from laia_cli.install_wizard.ui import progress as prog
from laia_cli.install_wizard.ui.theme import THEME


def _console():
    buf = StringIO()
    return Console(file=buf, width=80, no_color=True, force_terminal=False), buf


def test_step_start_has_arrow_glyph():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="step_start", step_id="x", label="Instalando"),
        console=console,
    )
    out = buf.getvalue()
    assert THEME.g_arrow in out
    assert "Instalando" in out


def test_step_done_includes_elapsed_when_present():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="step_done", step_id="x", label="OK",
                      elapsed_s=12.5),
        console=console,
    )
    out = buf.getvalue()
    assert THEME.g_ok in out
    assert "OK" in out
    assert "12.5" in out


def test_step_error_renders_hint():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="step_error", step_id="x", label="Falló",
                      extra={"hint": "revisa el log en /tmp/foo.log"}),
        console=console,
    )
    out = buf.getvalue()
    assert THEME.g_err in out
    assert "Falló" in out
    assert "/tmp/foo.log" in out


def test_log_line_is_clipped_when_too_long():
    console, buf = _console()
    long = "x" * 500
    prog.render_progress(
        ProgressEvent(type="log_line", step_id="x", label=long),
        console=console,
    )
    out = buf.getvalue()
    # The clipped form ends with the ellipsis character we use.
    assert "…" in out
    # Sanity: the captured text shouldn't contain 500 consecutive x's verbatim
    # (it may still be quite long due to soft-wrapping, but the clip caps it).
    assert "x" * 250 not in out


def test_warning_event_uses_warn_glyph():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="warning", step_id="x", label="Cuidado"),
        console=console,
    )
    assert THEME.g_warn in buf.getvalue()
    assert "Cuidado" in buf.getvalue()


def test_info_event_uses_info_glyph():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="info", step_id="x", label="Nota"),
        console=console,
    )
    assert THEME.g_info in buf.getvalue()


def test_summary_event_renders_panel_and_table():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(
            type="summary",
            step_id="install",
            label="Credenciales de admin",
            extra={
                "rows": [("Username", "admin"), ("Password", "20chars")],
                "next_steps": ["Abre la UI"],
            },
        ),
        console=console,
    )
    out = buf.getvalue()
    assert THEME.g_check in out
    assert "Credenciales de admin" in out
    assert "Username" in out and "admin" in out
    assert "Password" in out and "20chars" in out
    assert "Abre la UI" in out
    assert "Siguientes pasos" in out


@pytest.mark.parametrize("ok,glyph,word", [
    (True,  THEME.g_ok, "éxito"),
    (False, THEME.g_err, "falló"),
])
def test_finished_event_glyph(ok, glyph, word):
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(
            type="finished", step_id=None,
            label=("Operación completada con éxito." if ok else "La operación falló."),
            elapsed_s=42.0,
            extra={"ok": ok},
        ),
        console=console,
    )
    out = buf.getvalue()
    assert glyph in out
    assert word in out
    assert "42.0" in out


def test_unknown_event_type_still_emits_something():
    console, buf = _console()
    prog.render_progress(
        ProgressEvent(type="brand_new_kind", step_id="x", label="experimental"),  # type: ignore[arg-type]
        console=console,
    )
    out = buf.getvalue()
    assert "experimental" in out
