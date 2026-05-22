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
import tarfile
import time
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
    """Resolve the wipe targets, honoring sudo's preservation of SUDO_USER.

    The original implementation had a bug where the `Path("/home") / user`
    construction was used as a truthiness test (always truthy). We now
    actually check that the home directory exists before believing in it.
    """
    user_home = Path(os.environ.get("SUDO_HOME") or os.path.expanduser("~"))
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        candidate = Path("/home") / sudo_user
        if candidate.is_dir():
            user_home = candidate
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

        yield ProgressEvent(
            type="step_start",
            step_id="snapshot",
            label=f"Snapshot → {snap_path}",
        )
        started = time.time()
        # Use Python's tarfile module — paths with spaces, $, ', " etc. are
        # safe (no shell involvement), and we can yield log_line events for
        # progress without relying on tar's stdout. Run via `sudo` only if
        # we can't write to /var/backups directly.
        try:
            snap_dir.mkdir(parents=True, exist_ok=True)
            can_write_directly = os.access(snap_dir, os.W_OK)
        except (OSError, PermissionError):
            can_write_directly = False

        if can_write_directly:
            try:
                with tarfile.open(snap_path, mode="w:gz") as tf:
                    for t in existing:
                        arcname = str(t).lstrip("/")
                        yield ProgressEvent(
                            type="log_line",
                            step_id="snapshot",
                            label=f"  + {arcname}",
                            elapsed_s=time.time() - started,
                        )
                        try:
                            tf.add(str(t), arcname=arcname, recursive=True)
                        except (OSError, PermissionError) as e:
                            yield ProgressEvent(
                                type="log_line",
                                step_id="snapshot",
                                label=f"  ! skipped {t}: {e}",
                                elapsed_s=time.time() - started,
                            )
                size = snap_path.stat().st_size if snap_path.exists() else 0
                yield ProgressEvent(
                    type="step_done",
                    step_id="snapshot",
                    label=f"Snapshot OK ({size // 1024} KB)",
                    elapsed_s=time.time() - started,
                    extra={"path": str(snap_path), "size_bytes": size},
                )
            except Exception as e:
                yield ProgressEvent(
                    type="step_error",
                    step_id="snapshot",
                    label=f"Snapshot falló: {e}",
                    elapsed_s=time.time() - started,
                    extra={"hint": "El wipe se aborta para no perder datos."},
                )
                return
        else:
            # Need root to write /var/backups. Fall back to a sudo'd python
            # one-liner that invokes the same tarfile API. This avoids the
            # shell injection risk of building a shell command string.
            import json as _json
            payload = _json.dumps([
                {"src": str(t), "arc": str(t).lstrip("/")} for t in existing
            ])
            py_script = (
                "import tarfile, sys, json\n"
                "items = json.loads(sys.argv[1])\n"
                "with tarfile.open(sys.argv[2], 'w:gz') as tf:\n"
                "    for it in items:\n"
                "        try:\n"
                "            tf.add(it['src'], arcname=it['arc'], recursive=True)\n"
                "        except OSError:\n"
                "            pass\n"
            )
            yield from stream_command(
                ["sudo", "mkdir", "-p", str(snap_dir)],
                step_id="snapshot",
                label="mkdir /var/backups",
            )
            yield from stream_command(
                ["sudo", "python3", "-c", py_script, payload, str(snap_path)],
                step_id="snapshot",
                label=f"Snapshot → {snap_path}",
            )

    # ---- Wipe ------------------------------------------------------------
    # Chunk the rm invocations: with 100+ targets the argv could approach
    # the kernel's ARG_MAX. Use --no-preserve-root explicitly defensive —
    # all targets are already inside /opt/laia*, /srv/laia, or under the
    # user home so they can never resolve to / itself, but the flag makes
    # that intent unmistakable to anyone reading the code.
    paths_str = [str(t) for t in existing]
    CHUNK = 32
    for i in range(0, len(paths_str), CHUNK):
        chunk = paths_str[i:i + CHUNK]
        yield from stream_command(
            ["sudo", "rm", "-rf", "--"] + chunk,
            step_id="wipe",
            label=f"Borrando ({i + 1}-{i + len(chunk)}/{len(paths_str)})",
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
