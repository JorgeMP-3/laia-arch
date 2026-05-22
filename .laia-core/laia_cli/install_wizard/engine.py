"""Wizard state machine.

This is C1's heart. It owns:

* The user's :class:`state.WizardState` (which screen, what they filled in).
* Dispatch to the per-mode flow module (``flows/install.py`` etc.).
* Validation of submitted field values.
* Streaming of :class:`contract.ProgressEvent`s during the actual execution.

C2 talks to it through three methods only: :meth:`next_screen`,
:meth:`submit`, and :meth:`execute`. Anything else is internal.

A flow module is a thin protocol — see :class:`Flow` below. Adding a new
mode is: write ``flows/yourmode.py`` exporting that protocol, register it in
:data:`_FLOWS`, and add an entry to :data:`MODE_SELECT_SCREEN.fields`.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

from . import state as state_mod
from . import validators as validators_mod
from .contract import (
    ACTION_BACK,
    ACTION_NEXT,
    ACTION_QUIT,
    Action,
    Choice,
    Field,
    ProgressEvent,
    ValidationResult,
    WizardScreen,
)


# ---------------------------------------------------------------------------
# Flow protocol
# ---------------------------------------------------------------------------

class Flow(Protocol):
    """Every flow module must expose these symbols.

    ``flow_id``: short identifier, also the value used in mode_select.
    ``first_screen_id``: which screen the engine should show on entry.
    ``screens``: id → (WizardScreen | callable(state) -> WizardScreen).
                Dynamic screens are useful when content depends on prior values.
    ``next_screen_id(screen_id, state)``: which screen comes next, or ``None``
                                          when the form is complete and ready
                                          for execute().
    ``execute(state)``: generator that yields ProgressEvent during the action.
    """
    flow_id: str
    first_screen_id: str
    screens: dict[str, Any]  # WizardScreen | Callable[[WizardState], WizardScreen]

    def next_screen_id(
        self, screen_id: str, state: "state_mod.WizardState"
    ) -> str | None: ...

    def execute(
        self, state: "state_mod.WizardState"
    ) -> Iterator[ProgressEvent]: ...


# ---------------------------------------------------------------------------
# Registry — keep modules lazily loaded so a broken flow doesn't poison startup
# ---------------------------------------------------------------------------

_FLOW_MODULES: dict[str, str] = {
    "install":      "laia_cli.install_wizard.flows.install",
    "clone":        "laia_cli.install_wizard.flows.clone",
    "diagnose":     "laia_cli.install_wizard.flows.diagnose",
    "reset":        "laia_cli.install_wizard.flows.reset",
    "connectivity": "laia_cli.install_wizard.flows.connectivity",
}


def _load_flow(flow_id: str) -> Flow:
    """Import the flow module on demand and return it as a Flow."""
    module_path = _FLOW_MODULES.get(flow_id)
    if not module_path:
        raise ValueError(f"Modo desconocido: {flow_id}")
    return importlib.import_module(module_path)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# The mode-select screen (engine-owned, doesn't live in any flow)
# ---------------------------------------------------------------------------

MODE_SELECT_SCREEN = WizardScreen(
    id="mode_select",
    title="LAIA — Setup Wizard",
    description=(
        "Bienvenido. Elige qué quieres hacer en esta máquina."
    ),
    fields=(
        Field(
            name="mode",
            type="choice",
            label="Modo",
            choices=(
                Choice(
                    value="install",
                    label="Instalar LAIA desde cero",
                    description="Factory-default: LXD + laia-agora + skills base. Ubuntu limpio.",
                    recommended=True,
                ),
                Choice(
                    value="clone",
                    label="Clonar desde otra máquina",
                    description="Pull de datos + reconstrucción de containers en este destino.",
                ),
                Choice(
                    value="connectivity",
                    label="Configurar conectividad (SSH / Tailscale)",
                    description="Generar SSH key, copiar al destino, opcional Tailscale. Útil pre-clone.",
                ),
                Choice(
                    value="diagnose",
                    label="Diagnosticar instalación existente",
                    description="Verifica health, containers, agora.db, paths. No modifica nada.",
                ),
                Choice(
                    value="reset",
                    label="Reset / wipe (PELIGROSO)",
                    description="Borra /opt/laia, /srv/laia, ~/.laia. Doble confirmación.",
                ),
            ),
            default="install",
            validator="non_empty",
        ),
    ),
    actions=(ACTION_QUIT, ACTION_NEXT),
)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class _ExecPlan:
    """Set by the engine when the user has answered all questions for a flow
    and confirmed. ``execute()`` consumes this and clears it."""
    flow: Flow
    started_at: float = 0.0


class WizardEngine:
    """Drive the wizard from C2's side of the contract.

    Usage from C2::

        engine = WizardEngine()
        while not engine.is_done():
            screen = engine.next_screen()
            user_input = ui.render(screen)
            result = engine.submit(user_input)
            if result.ready_action:
                for event in engine.execute():
                    ui.show_progress(event)
                engine.mark_done()
    """

    # Cycle-detection: a flow that keeps returning the same next_screen_id
    # for the same {screen, values} signature would trap the user in a loop.
    # We abort once we see the same signature this many times.
    MAX_VISITS_PER_SIGNATURE = 5
    # Catch-all for runaway flows: total submit/transitions in one session.
    MAX_TOTAL_TRANSITIONS = 500

    def __init__(
        self,
        *,
        state: state_mod.WizardState | None = None,
        autosave: bool = True,
    ) -> None:
        self.state: state_mod.WizardState = state or state_mod.WizardState()
        self._flow: Flow | None = None
        if self.state.mode:
            self._flow = _load_flow(self.state.mode)
        self._exec_plan: _ExecPlan | None = None
        self._done: bool = False
        self._autosave: bool = autosave
        # In-session counters; not persisted (resume starts fresh).
        self._visit_counts: dict[str, int] = {}
        self._total_transitions: int = 0

    # ---- C2-facing API ----------------------------------------------------

    def next_screen(self) -> WizardScreen:
        """Return the screen the UI should render right now."""
        # No mode chosen yet — always start with the menu.
        if self._flow is None or self.state.mode is None:
            return MODE_SELECT_SCREEN

        # Resume case: the state already remembers where we were.
        screen_id = self.state.current_screen_id or self._flow.first_screen_id
        return self._resolve_screen(screen_id)

    def submit(self, user_input: dict[str, Any] | str) -> ValidationResult:
        """Handle the user's response to the current screen.

        ``user_input`` is either:
          * ``dict`` of field name -> value
          * ``"back"`` — go to previous screen
          * ``"quit"`` — bail out (engine marks itself done)
        """
        if user_input == "quit":
            self._done = True
            state_mod.clear()
            return ValidationResult(ok=True)

        if user_input == "back":
            prev = self.state.pop_back()
            if prev:
                self.state.current_screen_id = prev
                if self._autosave:
                    state_mod.save(self.state)
                return ValidationResult(ok=True, next_screen=self._resolve_screen(prev))
            # No back available — stay where we are.
            current = self.state.current_screen_id or (
                self._flow.first_screen_id if self._flow else MODE_SELECT_SCREEN.id
            )
            return ValidationResult(ok=True, next_screen=self._resolve_screen(current))

        if not isinstance(user_input, dict):
            return ValidationResult(
                ok=False,
                errors={"_form": f"Entrada inesperada: {user_input!r}"},
            )

        # Mode select is a special case before any flow is loaded.
        if self._flow is None:
            return self._submit_mode_select(user_input)

        return self._submit_flow_screen(user_input)

    def execute(self) -> Iterator[ProgressEvent]:
        """Run the action confirmed by the user. Streams ProgressEvents.

        Engine clears its checkpoint on a clean ``finished(ok=True)`` event.
        Caller is responsible for marking the engine done after consuming.
        """
        if self._exec_plan is None:
            yield ProgressEvent(
                type="step_error",
                step_id=None,
                label="Nada que ejecutar — no se han confirmado acciones.",
                extra={"hint": "Avanza por las pantallas hasta el resumen final."},
            )
            return

        self._exec_plan.started_at = time.time()
        flow = self._exec_plan.flow
        ok = True
        try:
            for ev in flow.execute(self.state):
                if ev.type == "step_error":
                    ok = False
                yield ev
        except Exception as exc:  # bubble to UI as a clean event, not a crash
            yield ProgressEvent(
                type="step_error",
                step_id=None,
                label=f"Excepción no controlada: {exc}",
                extra={"exception": exc.__class__.__name__},
            )
            ok = False

        elapsed = time.time() - self._exec_plan.started_at
        yield ProgressEvent(
            type="finished",
            step_id=None,
            label="Operación completada con éxito." if ok else "La operación falló.",
            elapsed_s=elapsed,
            extra={"ok": ok},
        )
        if ok:
            state_mod.clear()
        self._exec_plan = None

    def mark_done(self) -> None:
        """C2 calls this after consuming the execute() iterator."""
        self._done = True

    def is_done(self) -> bool:
        return self._done

    # ---- Internals --------------------------------------------------------

    def _resolve_screen(self, screen_id: str) -> WizardScreen:
        """Look up the screen on the current flow, evaluating callables."""
        if self._flow is None:
            return MODE_SELECT_SCREEN
        entry = self._flow.screens.get(screen_id)
        if entry is None:
            # Unknown id; treat as "we're done with screens, ready to confirm".
            return self._build_confirm_screen()
        if callable(entry):
            return entry(self.state)
        return entry

    def _build_confirm_screen(self) -> WizardScreen:
        """Default final confirmation screen if a flow doesn't supply one."""
        return WizardScreen(
            id="_confirm",
            title="Confirmar y ejecutar",
            description="Revisa los datos. Si todo está correcto, pulsa Ejecutar.",
            fields=(
                Field(
                    name="_summary",
                    type="info",
                    label="Resumen",
                    default=self.state.values,
                ),
            ),
            actions=(
                ACTION_BACK,
                Action(name="run", label="Ejecutar", kind="submit"),
            ),
        )

    def _submit_mode_select(self, values: dict[str, Any]) -> ValidationResult:
        mode = values.get("mode")
        ok, err = validators_mod.run("non_empty", mode)
        if not ok:
            return ValidationResult(ok=False, errors={"mode": err or "Modo requerido."})
        if mode not in _FLOW_MODULES:
            return ValidationResult(ok=False, errors={"mode": f"Modo desconocido: {mode}"})

        # Lazy-import; if a flow module is broken, surface that as an error
        # rather than crashing the whole wizard.
        try:
            flow = _load_flow(mode)
        except Exception as exc:
            return ValidationResult(
                ok=False,
                errors={"mode": f"No pude cargar el flow {mode!r}: {exc}"},
            )

        self.state.mode = mode
        self._flow = flow
        first = flow.first_screen_id
        self.state.current_screen_id = first
        self.state.remember(MODE_SELECT_SCREEN.id)
        self.state.remember(first)
        if self._autosave:
            state_mod.save(self.state)
        return ValidationResult(ok=True, next_screen=self._resolve_screen(first))

    def _submit_flow_screen(self, values: dict[str, Any]) -> ValidationResult:
        assert self._flow is not None  # by construction
        current_id = self.state.current_screen_id or self._flow.first_screen_id
        screen = self._resolve_screen(current_id)

        errors = self._validate_values(screen, values)
        if errors:
            return ValidationResult(ok=False, errors=errors)

        # Persist values (minus secrets, which save() filters anyway).
        for f in screen.fields:
            if f.type == "info":
                continue
            if f.name in values:
                self.state.set_value(f.name, values[f.name])

        # Sentinel action: the screen had a "submit"/run action; that means
        # we're ready to execute().
        if values.get("_action") in ("run", "submit"):
            self._exec_plan = _ExecPlan(flow=self._flow)
            if self._autosave:
                state_mod.save(self.state)
            return ValidationResult(ok=True, ready_action=current_id)

        next_id = self._flow.next_screen_id(current_id, self.state)

        # Runaway / cycle protection. The signature is screen+sorted-values
        # so visiting the same screen with different inputs doesn't trip
        # the detector, but a flow that keeps bouncing the user to the
        # same screen with the same inputs does.
        self._total_transitions += 1
        if self._total_transitions > self.MAX_TOTAL_TRANSITIONS:
            return ValidationResult(
                ok=False,
                errors={"_form": (
                    "Demasiadas transiciones en este flow "
                    f"({self.MAX_TOTAL_TRANSITIONS}+). Esto suele indicar "
                    "un bug en el flow. Abortando para evitar un loop."
                )},
            )
        if next_id is not None:
            sig = f"{next_id}|{sorted(self.state.values.items())}"
            count = self._visit_counts.get(sig, 0) + 1
            self._visit_counts[sig] = count
            if count > self.MAX_VISITS_PER_SIGNATURE:
                return ValidationResult(
                    ok=False,
                    errors={"_form": (
                        f"Ciclo detectado: la pantalla {next_id!r} se ha "
                        f"visitado {count} veces con los mismos valores. "
                        "Cambia algún campo o reporta el bug."
                    )},
                )

        if next_id is None:
            # Flow has no more questions — emit default confirm screen.
            confirm = self._build_confirm_screen()
            self.state.current_screen_id = confirm.id
            self.state.remember(confirm.id)
            if self._autosave:
                state_mod.save(self.state)
            return ValidationResult(ok=True, next_screen=confirm)

        self.state.current_screen_id = next_id
        self.state.remember(next_id)
        if self._autosave:
            state_mod.save(self.state)
        return ValidationResult(ok=True, next_screen=self._resolve_screen(next_id))

    def _validate_values(
        self, screen: WizardScreen, values: dict[str, Any]
    ) -> dict[str, str]:
        from .contract import field_visible  # local import to avoid cycle
        errors: dict[str, str] = {}
        # Only check fields that are visible given the OTHER values supplied.
        for f in screen.fields:
            if f.type == "info":
                continue
            if not field_visible(f, values):
                continue
            ok, msg = validators_mod.run(f.validator, values.get(f.name))
            if not ok:
                errors[f.name] = msg or "Valor inválido."
        return errors


__all__ = ["WizardEngine", "MODE_SELECT_SCREEN", "Flow"]
