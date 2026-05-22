"""Clone-from-another-machine flow.

User journey:

1. ``source_kind``   — pick LAN IP / Tailscale / Custom user@host.
2. ``source_host``   — depending on kind, ask for the host string.
3. ``ssh_auth``      — choose: existing key / generate new key / password.
4. ``ssh_password``  — only when the user picked password auth.
5. ``options``       — bandwidth limit, keep-session, --resume.
6. ``confirm``       — summary + ``run``.

If the user picks Tailscale and tailscale is missing, the screen explains how
to set it up and offers to switch to the connectivity flow first. We do NOT
auto-install Tailscale from inside clone — keeps blast radius small.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..contract import (
    ACTION_BACK,
    ACTION_NEXT,
    Action,
    Choice,
    Field,
    ProgressEvent,
    WizardScreen,
)
from ._subprocess import repo_root, stream_command

flow_id = "clone"
first_screen_id = "source_kind"


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

_SOURCE_KIND_SCREEN = WizardScreen(
    id="source_kind",
    title="¿Desde dónde clonar?",
    description=(
        "El servidor nuevo se conecta por SSH al viejo (PULL pattern). "
        "Elige cómo lo identificas."
    ),
    fields=(
        Field(
            name="source_kind",
            type="choice",
            label="Tipo de origen",
            default="lan",
            choices=(
                Choice(value="lan", label="IP en la red local",
                       description="Ambas máquinas en la misma LAN. Ej: 192.168.1.10."),
                Choice(value="tailscale", label="Tailscale (recomendado)",
                       description="Funciona entre redes distintas. Requiere `tailscale up` en ambas."),
                Choice(value="custom", label="user@host personalizado",
                       description="IP pública, dominio, hostname interno con .ssh/config, etc."),
            ),
            validator="non_empty",
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)


def _source_host_screen(state) -> WizardScreen:
    kind = state.values.get("source_kind", "lan")
    placeholders = {
        "lan":       "laia-hermes@192.168.1.10",
        "tailscale": "laia-hermes@laia-old        (tailscale magic hostname)",
        "custom":    "laia-hermes@viejo.example.com",
    }
    if kind == "tailscale" and not shutil.which("tailscale"):
        # Inform but don't block — the user might be entering a tailscale
        # hostname that resolves via DNS without local tailscale.
        ts_warning = (
            "⚠  No detecté `tailscale` instalado en este host. "
            "Puedes salir y elegir 'connectivity' para configurarlo, "
            "o continuar si el host objetivo resuelve por DNS."
        )
    else:
        ts_warning = None

    return WizardScreen(
        id="source_host",
        title="Origen",
        description=ts_warning,
        fields=(
            Field(
                name="source_host",
                type="text",
                label="user@host",
                placeholder=placeholders.get(kind, placeholders["lan"]),
                validator="ssh_target",
            ),
        ),
        actions=(ACTION_BACK, ACTION_NEXT),
    )


_SSH_AUTH_SCREEN = WizardScreen(
    id="ssh_auth",
    title="Autenticación SSH",
    description="¿Cómo se conecta este host al viejo?",
    fields=(
        Field(
            name="ssh_auth_mode",
            type="choice",
            label="Método",
            default="existing",
            choices=(
                Choice(value="existing", label="Usar mi clave SSH existente",
                       description="~/.ssh/id_* debe estar autorizada en el viejo."),
                Choice(value="password", label="Password SSH",
                       description="Se pedirá interactivamente; usa sshpass por debajo."),
                Choice(value="setup", label="Generar clave y copiarla al viejo",
                       description="Salta al flow de connectivity y vuelve."),
            ),
            validator="non_empty",
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)


_SSH_PASSWORD_SCREEN = WizardScreen(
    id="ssh_password",
    title="Password SSH",
    description=(
        "Se usará sólo para esta ejecución. El wizard lo pasa por un archivo "
        "temporal 0600 y lo borra antes de empezar la transferencia."
    ),
    fields=(
        Field(
            name="ssh_password",
            type="password",
            label="Password SSH del origen",
            secret=True,
            validator="non_empty",
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)


_OPTIONS_SCREEN = WizardScreen(
    id="options",
    title="Opciones de transferencia",
    fields=(
        Field(
            name="bwlimit",
            type="text",
            label="Límite de ancho de banda rsync (opcional)",
            placeholder="50M (vacío = sin límite)",
            default="50M",
            validator="rsync_bwlimit",
            help_text="50M ≈ 50 MB/s. Útil sobre WAN.",
        ),
        Field(
            name="keep_session",
            type="yesno",
            label="¿Mantener sesión de admin del viejo?",
            default=False,
            help_text=(
                "Por defecto se descarta admin-session.json y se reseta el "
                "password admin del importado (recomendado)."
            ),
        ),
        Field(
            name="resume",
            type="yesno",
            label="¿Modo --resume (saltar fases ya completadas)?",
            default=False,
            help_text="Sólo útil si una ejecución previa dejó datos parcialmente migrados.",
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)


def _confirm_screen(state) -> WizardScreen:
    v = state.values
    summary = (
        f"  Origen:       {v.get('source_host', '?')}  ({v.get('source_kind', '?')})\n"
        f"  Auth:         {v.get('ssh_auth_mode', '?')}\n"
        f"  Bwlimit:      {v.get('bwlimit') or '(ninguno)'}\n"
        f"  Keep session: {'sí' if v.get('keep_session') else 'no'}\n"
        f"  Resume:       {'sí' if v.get('resume') else 'no'}"
    )
    return WizardScreen(
        id="confirm",
        title="Confirmar clone",
        description=(
            "Esto invocará `bin/laia-clone` con tus elecciones. "
            "Si /opt/laia no existe en este host, se instalará primero "
            "automáticamente (laia-install --minimal)."
        ),
        fields=(
            Field(name="_summary", type="info", label="Resumen", default=summary),
        ),
        actions=(
            ACTION_BACK,
            Action(name="run", label="Clonar", kind="submit"),
        ),
    )


screens: dict[str, Any] = {
    "source_kind": _SOURCE_KIND_SCREEN,
    "source_host": _source_host_screen,
    "ssh_auth":    _SSH_AUTH_SCREEN,
    "ssh_password": _SSH_PASSWORD_SCREEN,
    "options":     _OPTIONS_SCREEN,
    "confirm":     _confirm_screen,
}


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def next_screen_id(screen_id: str, state) -> str | None:
    if screen_id == "ssh_auth":
        if state.values.get("ssh_auth_mode") == "password":
            return "ssh_password"
        return "options"
    order = ["source_kind", "source_host", "ssh_auth", "ssh_password", "options", "confirm"]
    try:
        idx = order.index(screen_id)
    except ValueError:
        return order[0]
    if idx + 1 >= len(order):
        return None
    return order[idx + 1]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _secret_to_tempfile(secret: str, prefix: str = "laia-ssh-pass-"):
    fd, path_str = tempfile.mkstemp(prefix=prefix, dir=tempfile.gettempdir())
    path = Path(path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secret)
        os.chmod(path, 0o600)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

def execute(state) -> Iterator[ProgressEvent]:
    v = state.values
    source = v.get("source_host")
    if not source:
        yield ProgressEvent(
            type="step_error",
            step_id="validate",
            label="Origen no especificado.",
        )
        return

    # The `setup` ssh_auth_mode means the user has no key set up yet. We
    # don't auto-jump flows in MVP — refuse with a clear, actionable error
    # rather than letting laia-clone fail mid-rsync with an opaque SSH
    # message. This matches the "fail loudly at the boundary" principle.
    if v.get("ssh_auth_mode") == "setup":
        yield ProgressEvent(
            type="step_error",
            step_id="ssh-auth",
            label=(
                "Necesitas configurar la clave SSH antes de clonar. "
                "Sal de este flow, ejecuta `sudo laia-wizard` y elige "
                "el modo Connectivity. Luego vuelve aquí con "
                "'usar mi clave SSH existente'."
            ),
            extra={"hint": "laia-wizard --mode connectivity (también disponible)"},
        )
        return

    root: Path = repo_root()
    laia_clone = root / "bin" / "laia-clone"
    if not laia_clone.is_file():
        yield ProgressEvent(
            type="step_error",
            step_id="locate",
            label=f"No encuentro {laia_clone}",
            extra={"hint": "Set LAIA_ROOT or run wizard from the repo."},
        )
        return

    cmd: list[str] = [
        "sudo", "-E", "bash", str(laia_clone),
        "--source", source,
        "--yes",
        "--json-progress",
    ]
    bwlimit = v.get("bwlimit")
    if bwlimit:
        # The bwlimit value is regex-validated by validators.rsync_bwlimit on
        # the wizard side AND by bin/laia-clone::validate_options (block 1) so
        # passing it as argv here is safe. Using --bwlimit= form is fine for
        # positional safety because shell=False is implicit in subprocess.
        cmd.append(f"--bwlimit={bwlimit}")
    if v.get("keep_session"):
        cmd.append("--keep-session")
    if v.get("resume"):
        cmd.append("--resume")

    env_extra: dict[str, str] = {}
    if v.get("ssh_auth_mode") == "password":
        password = v.get("ssh_password") or ""
        if not password:
            yield ProgressEvent(
                type="step_error",
                step_id="ssh-auth",
                label="Password SSH no especificado.",
            )
            return
        yield ProgressEvent(
            type="info",
            step_id="ssh-auth",
            label="Modo password SSH: el wizard lo pasará por archivo temporal seguro.",
        )
        with _secret_to_tempfile(password) as pass_file:
            cmd.extend(["--ssh-pass-file", str(pass_file)])
            yield from stream_command(
                cmd,
                step_id="laia-clone",
                label=f"Clonando desde {source}",
                cwd=root,
                env_extra=env_extra or None,
            )
    else:
        yield from stream_command(
            cmd,
            step_id="laia-clone",
            label=f"Clonando desde {source}",
            cwd=root,
            env_extra=env_extra or None,
        )

    # Post-clone tip (real summary is logged by bin/laia-clone itself).
    yield ProgressEvent(
        type="summary",
        step_id="laia-clone",
        label="Validación recomendada",
        extra={
            "rows": [
                ("Health endpoint", "curl -fsS http://127.0.0.1:8088/api/health"),
                ("Containers",      "lxc list"),
                ("Smoke completo",  "sudo bash /opt/laia/tests/installer/vm-smoke.sh"),
                ("Admin creds",     "cat $LAIA_HOME/.admin-credentials"),
            ],
        },
    )


__all__ = ["flow_id", "first_screen_id", "screens", "next_screen_id", "execute"]
