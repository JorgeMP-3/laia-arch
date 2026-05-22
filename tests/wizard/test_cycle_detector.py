"""Engine cycle detection.

A broken flow that keeps returning the same next_screen_id with the same
state values would trap the user in a loop. The engine must:

* Abort with a clear ValidationResult after MAX_VISITS_PER_SIGNATURE
  visits to the same (screen, values) signature.
* Abort with a clear error after MAX_TOTAL_TRANSITIONS absolute, even
  if signatures keep changing (defence against runaway flows).
"""

from __future__ import annotations

import pytest

from laia_cli.install_wizard import state as state_mod
from laia_cli.install_wizard.contract import (
    ACTION_NEXT,
    Action,
    Field,
    ProgressEvent,
    WizardScreen,
)
from laia_cli.install_wizard.engine import WizardEngine


def _make_loop_flow():
    """Build a fake flow module that always returns the same screen."""
    LOOP_SCREEN = WizardScreen(
        id="loop",
        title="loop",
        fields=(
            Field(name="x", type="text", label="x"),
        ),
        actions=(ACTION_NEXT,),
    )

    class _LoopFlow:
        flow_id = "loop"
        first_screen_id = "loop"
        screens = {"loop": LOOP_SCREEN}

        @staticmethod
        def next_screen_id(screen_id, state):
            return "loop"  # always bounces back

        @staticmethod
        def execute(state):
            yield ProgressEvent(type="finished", step_id=None, label="never")

    return _LoopFlow


def test_engine_aborts_on_repeated_same_signature(tmp_path, monkeypatch):
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    flow = _make_loop_flow()

    # Inject our fake flow into the engine's registry.
    from laia_cli.install_wizard import engine as engine_mod
    monkeypatch.setitem(engine_mod._FLOW_MODULES, "loop", "<inline>")
    monkeypatch.setattr(engine_mod, "_load_flow", lambda fid: flow)

    state = state_mod.WizardState(mode="loop")
    eng = engine_mod.WizardEngine(state=state, autosave=False)

    # Drive the engine submitting the SAME values every iteration. After
    # MAX_VISITS_PER_SIGNATURE + 1, submit() should refuse.
    last_result = None
    for _ in range(eng.MAX_VISITS_PER_SIGNATURE + 3):
        eng.next_screen()
        last_result = eng.submit({"x": "same-value"})
        if not last_result.ok:
            break
    assert last_result is not None
    assert not last_result.ok, "engine never detected the cycle"
    errs = " ".join(last_result.errors.values())
    assert "Ciclo detectado" in errs or "cycle" in errs.lower()


def test_engine_aborts_on_total_transition_explosion(tmp_path, monkeypatch):
    """Even with changing signatures, MAX_TOTAL_TRANSITIONS kicks in."""
    monkeypatch.setenv("LAIA_HOME", str(tmp_path))
    flow = _make_loop_flow()
    from laia_cli.install_wizard import engine as engine_mod
    monkeypatch.setitem(engine_mod._FLOW_MODULES, "loop", "<inline>")
    monkeypatch.setattr(engine_mod, "_load_flow", lambda fid: flow)

    eng = engine_mod.WizardEngine(
        state=state_mod.WizardState(mode="loop"), autosave=False,
    )
    eng.MAX_VISITS_PER_SIGNATURE = 10_000  # disable signature check for this test
    eng.MAX_TOTAL_TRANSITIONS = 8           # tight bound

    last = None
    for i in range(20):
        eng.next_screen()
        last = eng.submit({"x": f"value-{i}"})
        if not last.ok:
            break

    assert last is not None and not last.ok
    errs = " ".join(last.errors.values())
    assert "transiciones" in errs.lower() or "transitions" in errs.lower()
