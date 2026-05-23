#!/usr/bin/env bash
# Verifies the rich UI yes/no prompt accepts forgiving human input.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PYTHONPATH="$ROOT/.laia-core" python3 - <<'PY'
from laia_cli.install_wizard.contract import Field
from laia_cli.install_wizard.ui import _NavigationSentinel, _ask_yesno
import laia_cli.install_wizard.ui as ui


class FakeConsole:
    def __init__(self):
        self.lines = []

    def print(self, *args, **kwargs):
        self.lines.append(args)


def ask_sequence(values):
    seq = iter(values)
    original = ui.Prompt.ask
    ui.Prompt.ask = staticmethod(lambda *args, **kwargs: next(seq))
    return original


field = Field(name="init_lxd", type="yesno", label="Auto-instalar LXD", default=True)

original = ask_sequence(["y?"])
try:
    assert _ask_yesno(field, FakeConsole()) is True
finally:
    ui.Prompt.ask = original

original = ask_sequence(["sí!"])
try:
    assert _ask_yesno(field, FakeConsole()) is True
finally:
    ui.Prompt.ask = original

original = ask_sequence(["n."])
try:
    assert _ask_yesno(field, FakeConsole()) is False
finally:
    ui.Prompt.ask = original

original = ask_sequence([""])
try:
    assert _ask_yesno(field, FakeConsole()) is True
finally:
    ui.Prompt.ask = original

original = ask_sequence(["b"])
try:
    try:
        _ask_yesno(field, FakeConsole())
        raise AssertionError("expected back navigation")
    except _NavigationSentinel as exc:
        assert exc.value == "back"
finally:
    ui.Prompt.ask = original

print("ok: yes/no prompt accepts forgiving input")
PY
