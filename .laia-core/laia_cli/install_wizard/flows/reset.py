"""Reset flow — destructive cleanup of a LAIA install.

What it removes:

* ``/opt/laia`` and every ``/opt/laia-v*/`` versioned dir
* ``/srv/laia/`` (agora.db, users data, arch ops data, backups, state)
* ``$LAIA_USER_HOME/.laia/`` (auth.json, .env, atlas runtime, etc.)
* ``$LAIA_USER_HOME/LAIA-ARCH/`` (admin-credentials, cli-config)

Optional pre-step: snapshot the targets into ``/var/backups/laia-reset-*.tar.gz``.

Two confirmations are required:

1. Yes/no checkbox on the warning screen.
2. Type the literal word ``borrar`` on the final screen.

Both must pass before ``execute()`` performs any ``rm -rf``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..contract import (
    ACTION_BACK,
    ACTION_NEXT,
    Action,
    Field,
    ProgressEvent,
    WizardScreen,
)
from ._subprocess import stream_command

flow_id = "reset"
first_screen_id = "warning"


# Paths we'll wipe. Re-computed at execute time using $HOME of SUDO_USER.
def _targets() -> list[Path]:
    user_home = Path(os.environ.get("SUDO_HOME") or os.path.expanduser("~"))
    if os.environ.get("SUDO_USER") and Path("/home") / os.environ["SUDO_USER"]:
        user_home = Path("/home") / os.environ["SUDO_USER"]
    targets = [
        Path("/opt/laia"),
        Path("/srv/laia"),
        user_home / ".laia",
        user_home / "LAIA-ARCH",
    ]
    # Plus every versioned /opt/laia-v*
    opt = Path("/opt")
    if opt.is_dir():
        try:
            targets.extend(sorted(p for p in opt.iterdir() if p.name.startswith("laia-v")))
        except PermissionError:
            pass
    return targets


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

def _warning_screen(_state) -> WizardScreen:
    rows = "\n".join(f"    • {p}" for p in _targets())
    return WizardScreen(
        id="warning",
        title="⚠  Reset / wipe — operación destructiva",
        description=(
            "Esto borra todos los datos y código instalado de LAIA en este host.\n"
            "Containers LXD (laia-agora, agent-*) deben pararse manualmente "
            "antes; el wipe no los toca para evitar dejar bind-mounts huérfanos.\n\n"
            "Se borrará:\n" + rows
        ),
        fields=(
            Field(
                name="snapshot_before",
                type="yesno",
                label="¿Crear snapshot tar.gz antes de borrar?",
                default=True,
                help_text="Guarda en /var/backups/laia-reset-<timestamp>.tar.gz",
            ),
            Field(
                name="confirm_intent",
                type="yesno",
                label="Entiendo que esto NO se puede deshacer",
                default=False,
                validator="non_empty",
            ),
        ),
        actions=(ACTION_BACK, ACTION_NEXT),
    )


_TYPED_CONFIRM_SCREEN = WizardScreen(
    id="typed_confirm",
    title="Confirmación final",
    description=(
        "Escribe la palabra exacta `borrar` (sin comillas) para confirmar. "
        "Cualquier otra cosa aborta la operación."
    ),
    fields=(
        Field(
            name="typed",
            type="text",
            label="Escribe 'borrar' para confirmar",
            placeholder="borrar",
            validator="non_empty",
        ),
    ),
    actions=(
        ACTION_BACK,
        Action(name="run", label="WIPE", kind="submit", danger=True),
    ),
)


screens: dict[str, Any] = {
    "warning":       _warning_screen,
    "typed_confirm": _TYPED_CONFIRM_SCREEN,
}


def next_screen_id(screen_id: str, state) -> str | None:
    if screen_id == "warning":
        if not state.values.get("confirm_intent"):
            return "warning"  # bounce them back
        return "typed_confirm"
    return None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute(state) -> Iterator[ProgressEvent]:
    v = state.values
    typed = (v.get("typed") or "").strip().lower()
    if typed != "borrar":
        yield ProgressEvent(
            type="step_error",
            step_id="confirm",
            label=f"Confirmación inválida: {typed!r}. Esperaba 'borrar'. Abortado.",
        )
        return

    targets = _targets()
    existing = [t for t in targets if t.exists()]
    if not existing:
        yield ProgressEvent(
            type="info",
            step_id="wipe",
            label="Nada que borrar — ningún target existe.",
        )
        return

    # ---- Snapshot --------------------------------------------------------
    if v.get("snapshot_before", True):
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        snap_dir = Path("/var/backups")
        snap_path = snap_dir / f"laia-reset-{ts}.tar.gz"
        # Build tar args: -C / + relative paths so the archive is portable.
        rel_targets = [str(t).lstrip("/") for t in existing]
        yield from stream_command(
            ["sudo", "bash", "-c",
             f"mkdir -p {snap_dir} && tar -czf {snap_path} -C / " +
             " ".join(rel_targets) + f" 2>/dev/null || true && ls -lh {snap_path}"],
            step_id="snapshot",
            label=f"Snapshot → {snap_path}",
        )

    # ---- Wipe ------------------------------------------------------------
    rm_cmd = ["sudo", "rm", "-rf", "--"] + [str(t) for t in existing]
    yield from stream_command(
        rm_cmd,
        step_id="wipe",
        label=f"Borrando {len(existing)} ruta(s)",
    )

    # ---- Summary --------------------------------------------------------
    yield ProgressEvent(
        type="summary",
        step_id="reset",
        label="Reset completado",
        extra={
            "rows": [
                ("Borrado", ", ".join(str(t) for t in existing)),
                ("Snapshot", "guardado" if v.get("snapshot_before") else "omitido"),
                ("Siguiente", "sudo laia-wizard → 'Instalar desde cero'"),
            ],
        },
    )


__all__ = ["flow_id", "first_screen_id", "screens", "next_screen_id", "execute"]
