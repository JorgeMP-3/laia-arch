"""Contract schema tests — they fail if anyone breaks the shape C2 reads."""

from __future__ import annotations

import json

import pytest

from laia_cli.install_wizard import contract


def test_contract_version_is_stable():
    assert contract.CONTRACT_VERSION == "0.1.0"


def test_screen_serializes_to_json_clean_lists():
    s = contract.WizardScreen(
        id="x",
        title="X",
        fields=(contract.Field(name="a", type="text", label="A"),),
        actions=(contract.ACTION_BACK, contract.ACTION_NEXT),
    )
    d = contract.to_dict(s)
    assert isinstance(d["fields"], list)
    assert isinstance(d["actions"], list)
    # Roundtrip via json must succeed.
    json.dumps(d)


def test_field_visible_no_dep_always_visible():
    f = contract.Field(name="a", type="text", label="A")
    assert contract.field_visible(f, {}) is True


def test_field_visible_specific_value():
    f = contract.Field(
        name="key", type="password", label="API Key",
        depends_on={"provider": "openai"},
    )
    assert contract.field_visible(f, {"provider": "openai"}) is True
    assert contract.field_visible(f, {"provider": "deepseek"}) is False
    assert contract.field_visible(f, {}) is False


def test_field_visible_wildcard():
    f = contract.Field(
        name="key", type="password", label="API Key",
        depends_on={"provider": "*"},
    )
    assert contract.field_visible(f, {"provider": "openai"}) is True
    assert contract.field_visible(f, {"provider": ""}) is False
    assert contract.field_visible(f, {}) is False


def test_progress_event_is_immutable():
    ev = contract.ProgressEvent(type="step_done", step_id="x", label="ok")
    with pytest.raises(Exception):
        ev.label = "tampered"  # type: ignore[misc]


def test_action_kinds_are_known():
    assert contract.ACTION_NEXT.kind == "next"
    assert contract.ACTION_BACK.kind == "back"
    assert contract.ACTION_QUIT.kind == "quit"


def test_validation_result_default_errors_is_dict():
    r = contract.ValidationResult(ok=True)
    assert r.errors == {}
    assert r.next_screen is None
    assert r.ready_action is None
