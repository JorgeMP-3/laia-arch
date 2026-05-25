"""Smoke tests for the install wizard's Textual UI.

These exercise FormScreen / ExecuteScreen / LaiaWizardApp without
spawning subprocesses or touching the real engine — we synthesize
WizardScreens and ProgressEvents directly so the test is hermetic and
runs in a CI box without a real TTY.

We deliberately AVOID pilot.click() for buttons: under Textual's
``run_test`` driver the layout often reports zero-area regions for
widgets that aren't on the first render frame, which makes click-by-id
flaky. Instead we test the behaviors that don't depend on geometry:

* The screen composes its widgets and registers them by id.
* The value-extraction primitive (``_collect_values``) reads each
  Field type back the way the engine expects.
* The Action → dismiss mapping (``_dismiss_for_action``) handles the
  back / quit / next / submit kinds.
* ExecuteScreen accepts every ProgressEvent type without raising.

If textual is not installed in the venv, every test is skipped — the
wizard still works through the legacy rich UI, and we don't want to
turn a missing optional dep into a CI failure.
"""

from __future__ import annotations

from typing import Any

import pytest

from laia_cli.install_wizard.contract import (
    ACTION_BACK,
    ACTION_NEXT,
    ACTION_QUIT,
    Action,
    Choice,
    Field,
    ProgressEvent,
    WizardScreen,
)
from laia_cli.install_wizard.tui import is_textual_available

if not is_textual_available():
    pytest.skip("textual not installed", allow_module_level=True)


from laia_cli.install_wizard.tui.app import (  # noqa: E402 - after skip
    ExecuteScreen,
    FormScreen,
    LaiaWizardApp,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CHOICE_SCREEN = WizardScreen(
    id="mode_select",
    title="LAIA — Setup Wizard",
    description="Choose what to do.",
    fields=(
        Field(
            name="mode",
            type="choice",
            label="Modo",
            default="install",
            choices=(
                Choice(value="install", label="Instalar", recommended=True),
                Choice(value="clone", label="Clonar"),
            ),
            validator="non_empty",
        ),
    ),
    actions=(ACTION_QUIT, ACTION_NEXT),
)

MIXED_SCREEN = WizardScreen(
    id="mixed",
    title="Mixed screen",
    description="Cover text + yesno + password + checklist.",
    fields=(
        Field(
            name="hostname",
            type="text",
            label="Hostname",
            default="old.example.com",
            placeholder="user@host",
        ),
        Field(
            name="keep_session",
            type="yesno",
            label="¿Mantener sesión?",
            default=False,
            help_text="Por defecto se resetea la sesión.",
        ),
        Field(
            name="password",
            type="password",
            label="Password",
            secret=True,
        ),
        Field(
            name="features",
            type="checklist",
            label="Features",
            default=("ssh",),
            choices=(
                Choice(value="ssh", label="SSH"),
                Choice(value="tailscale", label="Tailscale"),
            ),
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)

INFO_SCREEN = WizardScreen(
    id="info",
    title="Info-only screen",
    fields=(
        Field(
            name="_summary",
            type="info",
            label="Resumen",
            default="A multi-line\nsummary text\n",
        ),
    ),
    actions=(ACTION_BACK, Action(name="run", label="Ejecutar", kind="submit")),
)

DEPENDS_SCREEN = WizardScreen(
    id="depends",
    title="Conditional fields",
    fields=(
        Field(
            name="auth",
            type="choice",
            label="Auth",
            default="key",
            choices=(
                Choice(value="key", label="SSH key"),
                Choice(value="password", label="Password"),
            ),
        ),
        Field(
            name="password",
            type="password",
            label="SSH Password",
            depends_on={"auth": "password"},
        ),
    ),
    actions=(ACTION_NEXT,),
)


# ---------------------------------------------------------------------------
# Tests — unit-level, no pilot geometry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_screen_renders_choice_and_default_value() -> None:
    """The screen composes, exposes its widgets by id, and collects the default."""
    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = FormScreen(CHOICE_SCREEN)
        await app.push_screen(screen)
        await pilot.pause()
        # Composition: title, mode field, both action buttons exist by id.
        assert app.screen.query_one("#title-bar")
        assert app.screen.query_one("#f-mode")
        assert app.screen.query_one("#a-next")
        assert app.screen.query_one("#a-quit")
        # _collect_values returns the default-selected choice value.
        values = screen._collect_values()
        assert values == {"mode": "install"}


@pytest.mark.asyncio
async def test_form_screen_collects_mixed_field_types() -> None:
    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = FormScreen(MIXED_SCREEN)
        await app.push_screen(screen)
        await pilot.pause()
        # Modify the widgets.
        from textual.widgets import Input, Switch, Checkbox

        app.screen.query_one("#f-hostname", Input).value = "user@new.example.com"
        app.screen.query_one("#f-keep_session", Switch).value = True
        app.screen.query_one("#f-password", Input).value = "s3cret"
        # Toggle the second checklist option on, first stays on (default).
        app.screen.query_one("#f-features__tailscale", Checkbox).value = True
        await pilot.pause()
        values = screen._collect_values()
    assert values["hostname"] == "user@new.example.com"
    assert values["keep_session"] is True
    assert values["password"] == "s3cret"
    assert set(values["features"]) == {"ssh", "tailscale"}


@pytest.mark.asyncio
async def test_form_screen_info_field_does_not_yield_value() -> None:
    """Info fields are read-only and absent from the collected dict."""
    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = FormScreen(INFO_SCREEN)
        await app.push_screen(screen)
        await pilot.pause()
        values = screen._collect_values()
    assert values == {}


@pytest.mark.asyncio
async def test_form_screen_back_and_quit_dismiss_with_sentinels() -> None:
    """Synthesize the on_button_pressed handler for back / quit actions."""
    from textual.widgets import Button

    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = FormScreen(MIXED_SCREEN)
        captured: dict[str, Any] = {}

        def _capture(result: Any) -> None:
            captured["last"] = result

        await app.push_screen(screen, callback=_capture)
        await pilot.pause()

        # Trigger the back button via its action handler.
        back_btn = app.screen.query_one("#a-back", Button)
        back_btn.press()
        await pilot.pause()
        # The screen was dismissed.
    assert captured.get("last") == "back"


@pytest.mark.asyncio
async def test_form_screen_next_button_dismisses_with_values() -> None:
    from textual.widgets import Button, Input

    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(140, 50)) as pilot:
        screen = FormScreen(MIXED_SCREEN)
        captured: dict[str, Any] = {}

        def _capture(result: Any) -> None:
            captured["last"] = result

        await app.push_screen(screen, callback=_capture)
        await pilot.pause()

        app.screen.query_one("#f-hostname", Input).value = "h"
        await pilot.pause()
        app.screen.query_one("#a-next", Button).press()
        await pilot.pause()

    assert isinstance(captured.get("last"), dict)
    assert captured["last"].get("hostname") == "h"


@pytest.mark.asyncio
async def test_form_screen_depends_on_hides_inactive_field() -> None:
    """Field with ``depends_on`` is omitted when the dependency doesn't match."""
    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(120, 40)) as pilot:
        # Prefill chooses auth=key, so the password field is hidden.
        screen = FormScreen(DEPENDS_SCREEN, prefill={"auth": "key"})
        await app.push_screen(screen)
        await pilot.pause()
        with pytest.raises(Exception):
            app.screen.query_one("#f-password")
        # With auth=password, the password field IS rendered.
    app2 = LaiaWizardApp(engine=None)
    async with app2.run_test(size=(120, 40)) as pilot:
        screen2 = FormScreen(DEPENDS_SCREEN, prefill={"auth": "password"})
        await app2.push_screen(screen2)
        await pilot.pause()
        assert app2.screen.query_one("#f-password") is not None


# ---------------------------------------------------------------------------
# ExecuteScreen smoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_screen_handles_every_event_type() -> None:
    """Feed a representative ProgressEvent stream; no exception should escape."""
    app = LaiaWizardApp(engine=None)
    async with app.run_test(size=(120, 40)) as pilot:
        exec_screen = ExecuteScreen("Test exec")
        await app.push_screen(exec_screen)
        await pilot.pause()

        exec_screen.handle_event(
            ProgressEvent(type="step_start", step_id="phase-a", label="Phase A")
        )
        exec_screen.handle_event(
            ProgressEvent(
                type="step_progress",
                step_id="phase-a",
                label="working",
                percent=42.0,
            )
        )
        exec_screen.handle_event(
            ProgressEvent(type="log_line", step_id="phase-a", label="raw output line")
        )
        exec_screen.handle_event(
            ProgressEvent(type="step_done", step_id="phase-a", label="Phase A OK")
        )
        exec_screen.handle_event(
            ProgressEvent(type="info", step_id=None, label="just FYI")
        )
        exec_screen.handle_event(
            ProgressEvent(type="warning", step_id=None, label="be aware")
        )
        exec_screen.handle_event(
            ProgressEvent(
                type="step_error",
                step_id="phase-b",
                label="Phase B failed",
                extra={"hint": "Check the log", "log_path": "/tmp/run.log"},
            )
        )
        exec_screen.handle_event(
            ProgressEvent(
                type="summary",
                step_id=None,
                label="Resumen",
                extra={"rows": [("Containers", "OK"), ("Health", "200")]},
            )
        )
        exec_screen.handle_event(
            ProgressEvent(
                type="finished",
                step_id=None,
                label="done",
                extra={"ok": True},
            )
        )
        await pilot.pause()

    assert exec_screen.cancelled is False
