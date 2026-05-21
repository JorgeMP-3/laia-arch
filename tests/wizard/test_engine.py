"""Engine state-machine behavior (no flows mocked, just dispatch)."""

from __future__ import annotations

import pytest

from laia_cli.install_wizard import contract
from laia_cli.install_wizard.engine import WizardEngine, MODE_SELECT_SCREEN


def test_initial_screen_is_mode_select():
    eng = WizardEngine(autosave=False)
    s = eng.next_screen()
    assert s.id == MODE_SELECT_SCREEN.id
    assert s.title.startswith("LAIA")


def test_submit_quit_marks_done():
    eng = WizardEngine(autosave=False)
    r = eng.submit("quit")
    assert r.ok is True
    assert eng.is_done()


def test_submit_invalid_mode_returns_errors():
    eng = WizardEngine(autosave=False)
    r = eng.submit({"mode": ""})
    assert r.ok is False
    assert "mode" in r.errors
    r = eng.submit({"mode": "not-a-real-mode"})
    assert r.ok is False
    assert "mode" in r.errors


@pytest.mark.parametrize("mode", ["install", "clone", "diagnose", "reset", "connectivity"])
def test_each_mode_dispatches_to_a_flow(mode, tmp_home):
    eng = WizardEngine(autosave=False)
    r = eng.submit({"mode": mode})
    assert r.ok, r.errors
    assert r.next_screen is not None
    # After choosing a mode, next_screen() must return something from the flow.
    s = eng.next_screen()
    assert s.id != MODE_SELECT_SCREEN.id


def test_back_goes_to_previous_screen(tmp_home):
    eng = WizardEngine(autosave=False)
    eng.submit({"mode": "install"})
    s_admin = eng.next_screen()
    assert s_admin.id == "admin"
    r = eng.submit("back")
    assert r.ok is True


def test_unknown_screen_returns_default_confirm(tmp_home):
    eng = WizardEngine(autosave=False)
    eng.submit({"mode": "install"})
    # Force a non-existent current_screen_id; engine should produce a default
    # confirm screen instead of crashing.
    eng.state.current_screen_id = "nope-does-not-exist"
    s = eng.next_screen()
    assert s.id == "_confirm"


def test_execute_without_ready_action_emits_clean_error(tmp_home):
    eng = WizardEngine(autosave=False)
    eng.submit({"mode": "install"})
    events = list(eng.execute())
    assert any(e.type == "step_error" for e in events)


def test_validation_blocks_transition(tmp_home):
    """Submitting bad values keeps us on the same screen."""
    eng = WizardEngine(autosave=False)
    eng.submit({"mode": "install"})
    # Submit invalid admin user
    r = eng.submit({"admin_user": "Bad Name", "admin_pass": ""})
    assert r.ok is False
    assert "admin_user" in r.errors


def test_state_records_history(tmp_home):
    eng = WizardEngine(autosave=False)
    eng.submit({"mode": "install"})
    assert eng.state.mode == "install"
    assert "admin" in eng.state.history
