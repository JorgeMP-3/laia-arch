"""Textual app, screens and widgets for the install wizard.

Kept in one file deliberately for the first iteration — the wizard is
small enough (one form screen template + one execute screen) that a
multi-file layout would obscure the shape more than it helps. Split if
this passes ~500 LOC.

Threading model
---------------
* The Textual app runs on the main thread (it owns the asyncio loop and
  the terminal).
* The wizard engine is sync (it yields generators, blocks on subprocess
  reads, etc.). We run it in a Textual ``run_worker(..., thread=True)``
  worker.
* Bridge between threads: the worker uses :meth:`App.call_from_thread`
  to schedule UI calls. For pushing a screen and awaiting its result, it
  calls :meth:`App.push_screen_wait` through ``call_from_thread`` — that
  coroutine is awaited on the main thread, and the worker thread blocks
  until the screen dismisses.
* Why not async all the way down: rewriting the engine and flows as
  async coroutines is out of scope for this phase. The threaded bridge
  is the contract surface; once it's stable we can migrate the engine.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

# --- Textual import guard ----------------------------------------------------
# We don't want the import of this module to fail when textual is missing
# (some bash code paths import the package to introspect — e.g. for
# --version). The legacy rich UI keeps working in that case.
try:
    from textual import work as _tx_work  # noqa: F401  (kept for future use)
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import (
        Horizontal,
        ScrollableContainer,
        Vertical,
    )
    from textual.screen import Screen
    from textual.widgets import (
        Button,
        Checkbox,
        Footer,
        Header,
        Input,
        Label,
        ProgressBar,
        RadioButton,
        RadioSet,
        RichLog,
        Static,
        Switch,
    )

    _TEXTUAL_AVAILABLE = True
    _TEXTUAL_IMPORT_ERROR: BaseException | None = None
except Exception as exc:  # pragma: no cover - exercised when textual missing
    _TEXTUAL_AVAILABLE = False
    _TEXTUAL_IMPORT_ERROR = exc

from ..contract import (
    Action,
    Field,
    ProgressEvent,
    WizardScreen,
    field_visible,
)


def is_textual_available() -> bool:
    """Cheap probe used by ``__main__.py`` to decide UI dispatch.

    Returns False when ``import textual`` raised at module load. We swallow
    every import error type (not just :class:`ImportError`) because Textual
    occasionally fails on import with a runtime error in exotic envs.
    """
    return _TEXTUAL_AVAILABLE


# ---------------------------------------------------------------------------
# Form screen — renders any WizardScreen as a Textual form
# ---------------------------------------------------------------------------

if _TEXTUAL_AVAILABLE:

    _STYLES = """
    Screen { background: $surface; }

    #title-bar {
        background: $primary;
        color: $text;
        padding: 0 2;
        text-style: bold;
        height: 1;
    }
    #description {
        padding: 1 2;
        color: $text-muted;
    }
    #form-body {
        height: 1fr;
    }
    .field-label {
        text-style: bold;
        padding: 1 2 0 2;
    }
    .field-help {
        color: $text-muted;
        padding: 0 2;
    }
    .field-error {
        color: $error;
        text-style: italic;
        padding: 0 2 1 2;
    }
    .field-input {
        margin: 0 2;
    }
    .field-info-content {
        padding: 0 2 1 4;
        color: $text-muted;
    }
    .choice-set {
        padding: 0 2;
        margin-bottom: 1;
    }
    .choice-description {
        color: $text-muted;
        padding: 0 4;
    }
    .actions {
        dock: bottom;
        padding: 0 2;
        align: right middle;
        height: 3;
        background: $panel;
    }
    .actions Button {
        margin-left: 1;
        min-width: 12;
    }
    #progress-label {
        padding: 1 2;
        text-style: bold;
    }
    #exec-log {
        height: 1fr;
        border: round $primary;
        margin: 0 2 1 2;
    }
    #exec-progress {
        margin: 0 2;
    }
    """

    class FormScreen(Screen[Any]):
        """Render one :class:`WizardScreen` and dismiss with the values dict.

        Dismiss values:
          * ``dict``     — field name → user value, matches the engine's
                           ``submit()`` input.
          * ``"back"``   — user picked an action of kind ``"back"``.
          * ``"quit"``   — user picked an action of kind ``"quit"``.
        """

        BINDINGS = [
            Binding("escape", "back_or_quit", "Atrás", show=True),
            Binding("ctrl+c", "quit_now", "Salir", show=True),
        ]

        def __init__(
            self,
            wizard_screen: WizardScreen,
            errors: dict[str, str] | None = None,
            prefill: dict[str, Any] | None = None,
        ) -> None:
            super().__init__()
            self.wizard_screen = wizard_screen
            self.errors = errors or {}
            # When the engine re-shows the same screen after a validation
            # error, we want the previous (rejected) values back in the form
            # so the user doesn't have to retype the good ones too.
            self.prefill = prefill or {}

        # -- Composition -----------------------------------------------------

        def compose(self) -> ComposeResult:
            # We build child widgets eagerly into lists and pass them as
            # constructor args, instead of using `with` blocks. The `with`
            # form depends on Textual's compose context, which doesn't fire
            # cleanly under run_test() in some Textual versions — the
            # constructor form is unconditionally robust.
            yield Header(show_clock=False)
            yield Static(self.wizard_screen.title, id="title-bar")
            if self.wizard_screen.description:
                yield Static(self.wizard_screen.description, id="description")
            body_children: list[Any] = []
            for field in self.wizard_screen.fields:
                if not field_visible(field, self.prefill):
                    continue
                body_children.extend(self._compose_field_widgets(field))
            yield ScrollableContainer(*body_children, id="form-body")
            yield Horizontal(
                *[self._action_button(a) for a in self.wizard_screen.actions],
                classes="actions",
            )
            yield Footer()

        def _compose_field_widgets(self, field: Field) -> list[Any]:
            """Return the flat list of widgets that represent one Field.

            Returning a list (not a generator) keeps things composable with
            other widgets' positional-children constructors.
            """
            widgets: list[Any] = []

            if field.type == "info":
                widgets.append(Static(field.label, classes="field-label"))
                if field.default:
                    widgets.append(
                        Static(str(field.default), classes="field-info-content")
                    )
                return widgets

            widgets.append(Static(field.label, classes="field-label"))
            if field.help_text:
                widgets.append(Static(field.help_text, classes="field-help"))

            wid = f"f-{field.name}"
            default_str = "" if field.default is None else str(field.default)
            prefilled = self.prefill.get(field.name)

            if field.type in ("text", "path"):
                widgets.append(
                    Input(
                        value=(
                            str(prefilled) if prefilled is not None else default_str
                        ),
                        placeholder=field.placeholder or "",
                        id=wid,
                        classes="field-input",
                    )
                )
            elif field.type == "password":
                widgets.append(
                    Input(
                        value="",
                        placeholder=field.placeholder or "",
                        id=wid,
                        classes="field-input",
                        password=True,
                    )
                )
            elif field.type == "yesno":
                current = (
                    bool(prefilled) if prefilled is not None else bool(field.default)
                )
                widgets.append(
                    Horizontal(
                        Switch(value=current, id=wid),
                        Static("Sí / No", classes="field-help"),
                    )
                )
            elif field.type == "choice":
                choices = field.choices or ()
                current = prefilled if prefilled is not None else field.default
                rb_widgets = []
                for c in choices:
                    label_text = c.label + (
                        "  [dim](recomendado)[/dim]" if c.recommended else ""
                    )
                    rb = RadioButton(label_text, value=(c.value == current))
                    # Stash the underlying value for retrieval on submit.
                    rb._laia_value = c.value  # type: ignore[attr-defined]
                    rb_widgets.append(rb)
                widgets.append(RadioSet(*rb_widgets, id=wid, classes="choice-set"))
                # Per-choice description as a subdued line under the set.
                for c in choices:
                    if c.description:
                        widgets.append(
                            Static(
                                f"• {c.label}: {c.description}",
                                classes="choice-description",
                            )
                        )
            elif field.type == "checklist":
                choices = field.choices or ()
                current_set: set[str] = set()
                if isinstance(prefilled, (list, tuple, set)):
                    current_set = set(map(str, prefilled))
                elif isinstance(field.default, (list, tuple, set)):
                    current_set = set(map(str, field.default))
                cb_widgets = []
                for c in choices:
                    cb = Checkbox(
                        c.label,
                        value=(c.value in current_set),
                        id=f"{wid}__{c.value}",
                    )
                    cb._laia_value = c.value  # type: ignore[attr-defined]
                    cb_widgets.append(cb)
                widgets.append(Vertical(*cb_widgets, classes="choice-set"))
            else:
                # Unknown type: render a disabled Input so it's visible but inert.
                widgets.append(
                    Input(
                        value=default_str,
                        placeholder=f"<unsupported type: {field.type}>",
                        id=wid,
                        classes="field-input",
                    )
                )

            err = self.errors.get(field.name)
            if err:
                widgets.append(Static(f"⚠ {err}", classes="field-error"))

            return widgets

        def _action_button(self, action: Action) -> Any:
            if action.danger:
                variant = "error"
            elif action.kind in ("next", "submit"):
                variant = "primary"
            elif action.kind == "back":
                variant = "default"
            elif action.kind == "quit":
                variant = "warning"
            else:
                variant = "default"
            return Button(action.label, id=f"a-{action.name}", variant=variant)

        # -- Interaction -----------------------------------------------------

        def on_button_pressed(self, event: Button.Pressed) -> None:
            assert event.button.id is not None
            name = event.button.id.removeprefix("a-")
            # Find the action by name to pick up its kind.
            action = next(
                (a for a in self.wizard_screen.actions if a.name == name),
                None,
            )
            if action is None:
                return
            if action.kind == "back":
                self.dismiss("back")
                return
            if action.kind == "quit":
                self.dismiss("quit")
                return
            # next / submit / custom — collect and dismiss with values.
            self.dismiss(self._collect_values())

        def action_back_or_quit(self) -> None:
            # Escape: if a back action exists, use it; otherwise quit.
            has_back = any(
                a.kind == "back" for a in self.wizard_screen.actions
            )
            self.dismiss("back" if has_back else "quit")

        def action_quit_now(self) -> None:
            self.dismiss("quit")

        # -- Value extraction ------------------------------------------------

        def _collect_values(self) -> dict[str, Any]:
            values: dict[str, Any] = {}
            for field in self.wizard_screen.fields:
                if field.type == "info":
                    continue
                if not field_visible(field, self.prefill):
                    # The field wasn't shown; preserve any default so the
                    # engine doesn't see a missing required key.
                    if field.default is not None:
                        values[field.name] = field.default
                    continue
                values[field.name] = self._read_field_value(field)
            return values

        def _read_field_value(self, field: Field) -> Any:
            wid = f"f-{field.name}"
            if field.type in ("text", "path", "password"):
                try:
                    w = self.query_one(f"#{wid}", Input)
                except Exception:
                    return field.default
                return w.value
            if field.type == "yesno":
                try:
                    w = self.query_one(f"#{wid}", Switch)
                except Exception:
                    return bool(field.default)
                return bool(w.value)
            if field.type == "choice":
                try:
                    rs = self.query_one(f"#{wid}", RadioSet)
                except Exception:
                    return field.default
                pressed = rs.pressed_button
                if pressed is not None:
                    return getattr(pressed, "_laia_value", str(pressed.label))
                return field.default
            if field.type == "checklist":
                picked: list[str] = []
                for c in field.choices or ():
                    cid = f"{wid}__{c.value}"
                    try:
                        cb = self.query_one(f"#{cid}", Checkbox)
                    except Exception:
                        continue
                    if cb.value:
                        picked.append(c.value)
                return picked
            return field.default

    # -----------------------------------------------------------------------
    # Execute screen — RichLog + ProgressBar for ProgressEvent stream
    # -----------------------------------------------------------------------

    class ExecuteScreen(Screen[None]):
        """Stream :class:`ProgressEvent`s into a scrolling log + progress bar."""

        BINDINGS = [Binding("ctrl+c", "request_cancel", "Cancelar", show=True)]

        def __init__(self, title: str = "Ejecutando…") -> None:
            super().__init__()
            self._title = title
            self.log_widget: RichLog | None = None
            self.progress_widget: ProgressBar | None = None
            self.label_widget: Static | None = None
            self.cancelled = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(self._title, id="title-bar")
            self.label_widget = Static("…", id="progress-label")
            yield self.label_widget
            self.progress_widget = ProgressBar(
                total=100, show_eta=False, show_percentage=True, id="exec-progress"
            )
            yield self.progress_widget
            self.log_widget = RichLog(highlight=True, markup=True, id="exec-log")
            yield self.log_widget
            yield Footer()

        def action_request_cancel(self) -> None:
            # Surfaced as an attribute the worker thread can poll. The
            # worker is responsible for terminating subprocesses via
            # _kill_tree() in _subprocess.py.
            self.cancelled = True

        # The worker thread calls this via call_from_thread(...).
        def handle_event(self, event: ProgressEvent) -> None:
            assert self.log_widget is not None and self.progress_widget is not None
            assert self.label_widget is not None
            t = event.type
            if t == "step_start":
                self.label_widget.update(f"▸ {event.label}")
                self.log_widget.write(f"[cyan]→ {event.label}[/cyan]")
                if event.percent is not None:
                    self.progress_widget.update(progress=event.percent)
            elif t == "step_progress":
                if event.label:
                    self.label_widget.update(f"▸ {event.label}")
                if event.percent is not None:
                    self.progress_widget.update(progress=event.percent)
            elif t == "step_done":
                self.log_widget.write(f"[green]✓ {event.label}[/green]")
                if event.percent is None:
                    # Bump bar one notch so it visibly advances per step.
                    cur = float(self.progress_widget.progress or 0.0)
                    self.progress_widget.update(progress=min(cur + 5, 95))
            elif t == "step_error":
                self.log_widget.write(f"[red]✗ {event.label}[/red]")
                hint = (event.extra or {}).get("hint")
                if hint:
                    self.log_widget.write(f"  [dim]{hint}[/dim]")
                log_path = (event.extra or {}).get("log_path")
                if log_path:
                    self.log_widget.write(f"  [dim]Log: {log_path}[/dim]")
            elif t == "log_line":
                self.log_widget.write(event.label)
            elif t == "info":
                self.log_widget.write(f"[blue]ℹ {event.label}[/blue]")
            elif t == "warning":
                self.log_widget.write(f"[yellow]⚠ {event.label}[/yellow]")
            elif t == "summary":
                self.log_widget.write(f"\n[bold]── {event.label} ──[/bold]")
                rows = (event.extra or {}).get("rows") or []
                for row in rows:
                    if isinstance(row, (list, tuple)) and len(row) == 2:
                        self.log_widget.write(f"  [bold]{row[0]}:[/bold] {row[1]}")
                    else:
                        self.log_widget.write(f"  {row}")
            elif t == "finished":
                ok = bool((event.extra or {}).get("ok", True))
                if ok:
                    self.progress_widget.update(progress=100)
                    self.log_widget.write("[bold green]── Completado ──[/bold green]")
                else:
                    self.log_widget.write("[bold red]── Falló ──[/bold red]")

    # -----------------------------------------------------------------------
    # The App — owns the engine loop in a worker thread
    # -----------------------------------------------------------------------

    class LaiaWizardApp(App[int]):
        """Main app. ``return_code`` after :meth:`run` is the wizard's exit."""

        CSS = _STYLES
        TITLE = "LAIA — Setup Wizard"

        BINDINGS = [Binding("ctrl+q", "request_quit", "Salir", show=True)]

        def __init__(self, engine: Any) -> None:
            super().__init__()
            self.engine = engine
            self.final_rc = 0

        def on_mount(self) -> None:
            # umask 077 for any tempfile the wizard creates while running.
            # The plan calls for this as a mitigation for "Textual running
            # under sudo could leak world-readable artifacts otherwise".
            try:
                os.umask(0o077)
            except OSError:
                pass
            # Spin up the engine loop on a thread worker. Exclusive so we
            # only ever have one engine running.
            #
            # When engine is None the App is being driven by tests as a
            # bare host — tests push screens directly via pilot. Skip the
            # worker in that case; otherwise it would dereference None and
            # tear the App down before tests can interact.
            if self.engine is not None:
                self.run_worker(self._engine_loop, thread=True, exclusive=True)

        async def action_request_quit(self) -> None:
            self.final_rc = 130
            self.exit(self.final_rc)

        # -- Worker thread: drive the sync engine -----------------------------

        def _engine_loop(self) -> None:
            try:
                while not self.engine.is_done():
                    screen = self.engine.next_screen()
                    user_input = self._await_form(screen)
                    if user_input == "quit":
                        self.final_rc = 130
                        return
                    if user_input == "back":
                        # The engine doesn't currently expose a "go back"
                        # API; the rich UI handles it by tracking history
                        # outside the engine. For now, treat back at the
                        # first screen as quit, and at later screens as a
                        # repaint of the same screen — TODO once engine
                        # adds a back hook (Fase 4).
                        continue

                    # Submit; on per-field validation errors, repaint the
                    # same screen with errors highlighted, preserving the
                    # values the user already typed.
                    last_values: dict[str, Any] = (
                        user_input if isinstance(user_input, dict) else {}
                    )
                    while True:
                        result = self.engine.submit(last_values)
                        if result.ok:
                            break
                        user_input = self._await_form(
                            screen, errors=result.errors, prefill=last_values
                        )
                        if user_input == "quit":
                            self.final_rc = 130
                            return
                        if user_input == "back":
                            break
                        last_values = (
                            user_input if isinstance(user_input, dict) else {}
                        )

                    if user_input in ("back",):
                        continue

                    if result.ready_action:
                        ok = self._drive_execute()
                        self.final_rc = 0 if ok else 1
                        self.engine.mark_done()
                        return
            finally:
                # Schedule the exit on the main thread.
                self.call_from_thread(self.exit, self.final_rc)

        def _await_form(
            self,
            screen: WizardScreen,
            errors: dict[str, str] | None = None,
            prefill: dict[str, Any] | None = None,
        ) -> Any:
            """Push a FormScreen and block this thread until the user dismisses."""
            form = FormScreen(screen, errors=errors, prefill=prefill)
            # call_from_thread with a coroutine awaits it on the main thread
            # and returns the result back to this thread.
            return self.call_from_thread(self.push_screen_wait, form)

        def _drive_execute(self) -> bool:
            exec_screen = ExecuteScreen()

            def _push() -> None:
                self.push_screen(exec_screen)

            self.call_from_thread(_push)

            ok = True
            for event in self.engine.execute():
                self.call_from_thread(exec_screen.handle_event, event)
                if event.type == "step_error":
                    ok = False
                if event.type == "finished":
                    ok = bool((event.extra or {}).get("ok", True))
                if exec_screen.cancelled:
                    ok = False
                    break
            return ok


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_textual_wizard(
    args: Any,
    state_mod: Any,
    engine_factory: Any,
) -> int:
    """Run the wizard with Textual.

    ``state_mod`` is the wizard's ``state`` module (so we can call
    :func:`state_mod.load`, :func:`state_mod.consume_load_warning`, and
    construct :class:`state_mod.WizardState`). ``engine_factory`` is the
    :class:`WizardEngine` class. We accept both as parameters so this
    module never imports them directly — keeps the import graph
    one-directional and the import cost near-zero when textual is
    missing.

    Returns the process exit code (the same convention as the legacy
    ``_run()`` path).
    """
    if not _TEXTUAL_AVAILABLE:
        raise RuntimeError(
            "Textual is not installed in this environment. "
            "Install with `pip install textual` or "
            "`pip install -e .[install_wizard]`. "
            f"Underlying import error: {_TEXTUAL_IMPORT_ERROR!r}"
        )

    # Same state-construction dance as __main__._run, lifted here so this
    # entry point is self-contained.
    state = state_mod.load() if getattr(args, "resume", False) else None
    if state is None:
        state = state_mod.WizardState()
    if getattr(args, "mode", None) and not state.mode:
        state.mode = args.mode
        state.current_screen_id = None

    engine = engine_factory(state=state)
    app = LaiaWizardApp(engine)
    app.run()
    return app.final_rc
