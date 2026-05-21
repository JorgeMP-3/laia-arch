"""End-to-end render() coverage with stdin scripted via pytest's monkeypatch.

We rely on Prompt.ask reading from rich.Console.input() which in turn calls
the underlying console's input function. Rather than going through the full
prompt-reading machinery, we monkeypatch the prompt classes' ``.ask``
methods so each call returns the next value from a queue.

This lets us walk through real WizardScreens (engine.MODE_SELECT_SCREEN,
flow's screens) and assert what render() returns.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from rich.console import Console

from laia_cli.install_wizard.contract import (
    ACTION_BACK,
    ACTION_NEXT,
    ACTION_QUIT,
    Action,
    Choice,
    Field,
    WizardScreen,
)
from laia_cli.install_wizard.ui import render
from laia_cli.install_wizard.ui import console as ui_console


@pytest.fixture(autouse=True)
def quiet_console(monkeypatch):
    """Replace the wizard's shared Console with a recording, non-color one."""
    buf = io.StringIO()
    monkeypatch.setenv("NO_COLOR", "1")
    rec = Console(file=buf, width=80, no_color=True, force_terminal=False)
    ui_console.set_console(rec)
    yield buf
    ui_console.reset_console()


def _queue(monkeypatch, answers: list[str]) -> list[str]:
    """Patch rich.prompt.Prompt.ask + Confirm.ask to consume `answers` in order."""
    from rich.prompt import Confirm, Prompt
    log: list[str] = []
    iterator = iter(answers)

    def fake_prompt(*args, **kwargs):
        try:
            v = next(iterator)
        except StopIteration as exc:
            raise AssertionError(
                f"Render asked for more input than scripted. Already used: {log}"
            ) from exc
        log.append(v)
        return v

    def fake_confirm(*args, **kwargs):
        try:
            v = next(iterator)
        except StopIteration as exc:
            raise AssertionError(
                f"Render asked for more confirms than scripted. Already used: {log}"
            ) from exc
        log.append(v)
        return v.lower().startswith(("y", "s", "t", "1"))

    monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, *a, **kw: fake_prompt(*a, **kw)))
    monkeypatch.setattr(Confirm, "ask", classmethod(lambda cls, *a, **kw: fake_confirm(*a, **kw)))
    return log


def test_render_quit_action(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        actions=(ACTION_QUIT, ACTION_NEXT),
    )
    _queue(monkeypatch, ["2"])  # pick action [2] = Continue → would be next, but for quit:
    # Pick [1] which is QUIT
    monkeypatch.undo()
    _queue(monkeypatch, ["1"])
    assert render(screen) == "quit"


def test_render_back_action(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        actions=(ACTION_BACK, ACTION_NEXT),
    )
    _queue(monkeypatch, ["1"])
    assert render(screen) == "back"


def test_render_text_field_returns_dict(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        fields=(Field(name="user", type="text", label="Usuario", default="admin"),),
        actions=(ACTION_NEXT,),
    )
    _queue(monkeypatch, ["alice"])  # text field answer
    result = render(screen)
    assert result == {"user": "alice"}


def test_render_choice_returns_value(monkeypatch):
    choices = (
        Choice("deepseek", "DeepSeek"),
        Choice("openai", "OpenAI"),
    )
    screen = WizardScreen(
        id="x", title="X",
        fields=(Field(name="provider", type="choice", label="Provider",
                       choices=choices),),
        actions=(ACTION_NEXT,),
    )
    _queue(monkeypatch, ["2"])
    result = render(screen)
    assert result == {"provider": "openai"}


def test_render_yesno_field(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        fields=(Field(name="ok", type="yesno", label="¿Continuar?", default=True),),
        actions=(ACTION_NEXT,),
    )
    _queue(monkeypatch, ["y"])
    result = render(screen)
    assert result == {"ok": True}


def test_render_letter_b_at_action_returns_back(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        actions=(ACTION_BACK, ACTION_NEXT),
    )
    _queue(monkeypatch, ["b"])
    assert render(screen) == "back"


def test_render_submit_action_stamps_action_field(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        fields=(Field(name="_info", type="info", label="Resumen", default="..."),),
        actions=(
            ACTION_BACK,
            Action(name="run", label="Ejecutar", kind="submit"),
        ),
    )
    _queue(monkeypatch, ["2"])
    result = render(screen)
    assert isinstance(result, dict)
    assert result.get("_action") == "run"


def test_render_info_field_does_not_consume_input(monkeypatch):
    """An info-type field is decorative — should NOT prompt the user."""
    screen = WizardScreen(
        id="x", title="X",
        fields=(
            Field(name="_info", type="info", label="Detalle", default="hola"),
            Field(name="user", type="text", label="Usuario", default="x"),
        ),
        actions=(ACTION_NEXT,),
    )
    _queue(monkeypatch, ["bob"])  # only one input expected
    result = render(screen)
    assert result == {"user": "bob"}


def test_render_dependent_field_skipped(monkeypatch):
    """``depends_on`` should hide a field until its dependency is satisfied."""
    screen = WizardScreen(
        id="x", title="X",
        fields=(
            Field(
                name="provider", type="choice", label="Provider",
                choices=(Choice("unset", "Saltar"), Choice("openai", "OpenAI")),
            ),
            Field(
                name="api_key", type="password", label="API Key",
                depends_on={"provider": "openai"},
            ),
        ),
        actions=(ACTION_NEXT,),
    )
    # Pick provider [1] = "unset" → api_key field shouldn't be asked.
    _queue(monkeypatch, ["1"])
    result = render(screen)
    assert result == {"provider": "unset"}
    assert "api_key" not in result


def test_render_dependent_field_asked(monkeypatch):
    screen = WizardScreen(
        id="x", title="X",
        fields=(
            Field(
                name="provider", type="choice", label="Provider",
                choices=(Choice("unset", "Saltar"), Choice("openai", "OpenAI")),
            ),
            Field(
                name="api_key", type="password", label="API Key",
                depends_on={"provider": "openai"},
            ),
        ),
        actions=(ACTION_NEXT,),
    )
    # Pick provider [2] = "openai" → api_key IS asked.
    _queue(monkeypatch, ["2", "sk-secret"])
    result = render(screen)
    assert result == {"provider": "openai", "api_key": "sk-secret"}
