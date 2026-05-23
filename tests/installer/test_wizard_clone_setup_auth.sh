#!/usr/bin/env bash
# Verifies clone auth "setup" configures SSH and then continues to clone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PYTHONPATH="$ROOT/.laia-core" LAIA_ROOT="$ROOT" python3 - <<'PY'
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from laia_cli.install_wizard.contract import ProgressEvent
from laia_cli.install_wizard.flows import clone

tmp = tempfile.TemporaryDirectory()
home = Path(tmp.name)
os.environ["LAIA_USER"] = "testuser"
os.environ["LAIA_USER_HOME"] = str(home)

calls = []

def fake_stream_command(cmd, **kwargs):
    calls.append((list(cmd), kwargs))
    yield ProgressEvent(
        type="step_done",
        step_id=kwargs.get("step_id"),
        label=kwargs.get("label", "done"),
    )

clone.stream_command = fake_stream_command

state = SimpleNamespace(values={
    "source_host": "olduser@192.0.2.44",
    "source_kind": "lan",
    "ssh_auth_mode": "setup",
    "bwlimit": "",
    "keep_session": False,
    "resume": False,
})

events = list(clone.execute(state))
errors = [ev.label for ev in events if ev.type == "step_error"]
assert not errors, errors

cmd_text = "\n".join(" ".join(cmd) for cmd, _kwargs in calls)
assert "ssh-keygen" in cmd_text, cmd_text
assert "ssh-copy-id" in cmd_text, cmd_text
assert "ssh -o BatchMode=yes" in cmd_text, cmd_text
assert "bin/laia-clone" in cmd_text, cmd_text
assert "Necesitas configurar la clave SSH antes de clonar" not in "\n".join(
    ev.label for ev in events
)

print("ok: setup auth configures SSH and continues to laia-clone")
PY
