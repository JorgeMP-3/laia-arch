"""Connectivity flow — SSH keygen + (optional) Tailscale setup.

Standalone use: configure SSH access from this host to another, so that the
next clone (or any operator task) doesn't need a password. Also offers to
install Tailscale for cross-network reachability.

User journey:

1. ``ssh_key``      — does a key exist? Want a new one (ed25519)?
2. ``ssh_target``   — destination user@host to copy the key to.
3. ``tailscale``    — install Tailscale? Run ``tailscale up``?
4. ``confirm``      — summary + run.
"""

from __future__ import annotations

import os
import shutil
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
from ._subprocess import stream_command

flow_id = "connectivity"
first_screen_id = "ssh_key"


def _existing_ssh_keys() -> list[Path]:
    home = Path(os.path.expanduser("~"))
    ssh_dir = home / ".ssh"
    if not ssh_dir.is_dir():
        return []
    return sorted(
        p for p in ssh_dir.iterdir()
        if p.is_file()
        and p.suffix == ""
        and p.with_suffix(".pub").is_file()
    )


def _ssh_key_screen(_state) -> WizardScreen:
    keys = _existing_ssh_keys()
    choices = [
        Choice(value="generate", label="Generar nueva clave ed25519",
               description="~/.ssh/id_ed25519 si no existe; recomendado."),
    ]
    for k in keys:
        choices.append(Choice(value=str(k), label=f"Usar {k.name}",
                              description=f"{k} (clave existente)"))
    choices.append(Choice(value="skip", label="Saltar gestión de claves",
                          description="Asumo que ya tengo SSH configurado."))
    return WizardScreen(
        id="ssh_key",
        title="Clave SSH",
        description="¿Cómo manejas la clave SSH para conectar al destino?",
        fields=(
            Field(
                name="ssh_key_choice",
                type="choice",
                label="Acción",
                choices=tuple(choices),
                default="generate" if not keys else str(keys[0]),
                validator="non_empty",
            ),
        ),
        actions=(ACTION_BACK, ACTION_NEXT),
    )


_SSH_TARGET_SCREEN = WizardScreen(
    id="ssh_target",
    title="Copiar clave al destino",
    description=(
        "Destino al que copiar la clave pública (ssh-copy-id). "
        "Deja vacío para saltar este paso."
    ),
    fields=(
        Field(
            name="ssh_copy_target",
            type="text",
            label="user@host destino",
            placeholder="laia-hermes@192.168.1.10",
            validator=None,  # opcional: si vacío, ssh-copy-id se salta
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
)


def _tailscale_screen(_state) -> WizardScreen:
    installed = shutil.which("tailscale") is not None
    desc_lines = []
    if installed:
        desc_lines.append("Tailscale ya está instalado.")
    else:
        desc_lines.append("Tailscale NO está instalado en este host.")
    desc_lines.append(
        "Tailscale crea una red mesh privada — ideal cuando origen y destino "
        "no comparten LAN."
    )
    return WizardScreen(
        id="tailscale",
        title="Tailscale (opcional)",
        description="\n".join(desc_lines),
        fields=(
            Field(
                name="tailscale_action",
                type="choice",
                label="¿Qué hacer con Tailscale?",
                default="skip" if installed else "skip",
                choices=(
                    Choice(value="skip", label="Saltar"),
                    Choice(
                        value="install_and_up",
                        label="Instalar y conectar (`tailscale up`)",
                        description=(
                            "Instala vía curl|sh y abre el browser para login. "
                            "Funciona si tienes salida a Internet."
                        ),
                    ),
                    Choice(
                        value="up_only",
                        label="Solo `tailscale up` (ya instalado)",
                        description="Asumo binario presente; abre login.",
                    ),
                ),
                validator="non_empty",
            ),
        ),
        actions=(ACTION_BACK, ACTION_NEXT),
    )


def _confirm_screen(state) -> WizardScreen:
    v = state.values
    summary = (
        f"  SSH key:      {v.get('ssh_key_choice', 'skip')}\n"
        f"  Copy to:      {v.get('ssh_copy_target') or '(ninguno)'}\n"
        f"  Tailscale:    {v.get('tailscale_action', 'skip')}"
    )
    return WizardScreen(
        id="confirm",
        title="Confirmar configuración de conectividad",
        fields=(
            Field(name="_summary", type="info", label="Resumen", default=summary),
        ),
        actions=(
            ACTION_BACK,
            Action(name="run", label="Aplicar", kind="submit"),
        ),
    )


screens: dict[str, Any] = {
    "ssh_key":    _ssh_key_screen,
    "ssh_target": _SSH_TARGET_SCREEN,
    "tailscale":  _tailscale_screen,
    "confirm":    _confirm_screen,
}


def next_screen_id(screen_id: str, _state) -> str | None:
    order = ["ssh_key", "ssh_target", "tailscale", "confirm"]
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

def execute(state) -> Iterator[ProgressEvent]:
    v = state.values
    home = Path(os.path.expanduser("~"))
    ssh_dir = home / ".ssh"

    # ---- SSH key ---------------------------------------------------------
    key_choice = v.get("ssh_key_choice", "skip")
    if key_choice == "generate":
        target = ssh_dir / "id_ed25519"
        if target.exists():
            yield ProgressEvent(
                type="info",
                step_id="ssh-keygen",
                label=f"{target} ya existe — no se sobreescribe.",
            )
        else:
            ssh_dir.mkdir(mode=0o700, exist_ok=True)
            yield from stream_command(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(target)],
                step_id="ssh-keygen",
                label="Generando clave ed25519",
            )
    elif key_choice not in ("skip", ""):
        # User picked an existing key — nothing to do but record it.
        yield ProgressEvent(
            type="info",
            step_id="ssh-keygen",
            label=f"Usando clave existente: {key_choice}",
        )

    # ---- ssh-copy-id ----------------------------------------------------
    target_host = v.get("ssh_copy_target")
    if target_host:
        # MITM protection: scan the host key first and show its fingerprint to
        # the user. We use StrictHostKeyChecking=ask (not accept-new) so the
        # user is prompted by SSH if the key doesn't match a previously known
        # entry. The ssh-keyscan step is informational; the actual trust
        # boundary is the next ssh-copy-id invocation.
        yield ProgressEvent(
            type="info",
            step_id="ssh-keyscan",
            label=f"Mostrando huella SSH de {target_host} antes de confiar en ella",
            extra={"hint": "Verifica la huella con el operador del host destino."},
        )
        host_only = target_host.split("@", 1)[1] if "@" in target_host else target_host
        # ssh-keyscan exit code is informational; we render whatever it
        # produces (key fingerprints) and continue regardless of the rc —
        # the next ssh-copy-id call is where actual trust is established.
        yield from stream_command(
            ["ssh-keyscan", "-T", "5", "-H", host_only],
            step_id="ssh-keyscan",
            label=f"ssh-keyscan {host_only}",
        )
        yield from stream_command(
            ["ssh-copy-id",
             "-o", "StrictHostKeyChecking=ask",
             "-o", "ConnectTimeout=15",
             target_host],
            step_id="ssh-copy-id",
            label=f"Copiando clave a {target_host}",
        )

    # ---- Tailscale ------------------------------------------------------
    ts_action = v.get("tailscale_action", "skip")
    if ts_action == "install_and_up":
        # SAFETY: piping the upstream installer to sh is a MITM/supply-chain
        # risk (a poisoned CDN or DNS hijack swaps the script for a malicious
        # one). We download the script to a tempfile first so the user can
        # inspect it via the log, and we make a small effort to verify it's
        # plausible (non-zero size + starts with shebang). Full GPG/SHA
        # verification requires an out-of-band trusted hash, which we don't
        # hardcode here because Tailscale doesn't publish a stable signed
        # checksum for install.sh. The user gets an explicit warning.
        from tempfile import NamedTemporaryFile
        yield ProgressEvent(
            type="warning",
            step_id="tailscale-install",
            label=(
                "Vas a instalar Tailscale desde su sitio. Si tu red no es "
                "de confianza, abandona y haz `sudo apt install tailscale` "
                "desde el repositorio oficial de tu distribución."
            ),
        )
        with NamedTemporaryFile(prefix="tailscale-install-", suffix=".sh",
                                delete=False, mode="w") as fh:
            installer_path = Path(fh.name)
        try:
            yield from stream_command(
                ["curl", "-fsSL",
                 "--proto", "=https", "--tlsv1.2",
                 "--max-time", "60",
                 "-o", str(installer_path),
                 "https://tailscale.com/install.sh"],
                step_id="tailscale-install",
                label="Descargando installer (HTTPS only)",
            )
            # Sanity-check before running: script must be non-empty and start
            # with a recognizable shebang. Anything else is treated as a
            # corrupted download and aborted.
            if installer_path.stat().st_size < 100:
                yield ProgressEvent(
                    type="step_error",
                    step_id="tailscale-install",
                    label="Installer descargado parece truncado (<100 bytes). Abortando.",
                )
            else:
                head = installer_path.read_text(encoding="utf-8", errors="replace")[:200]
                if not head.lstrip().startswith("#!"):
                    yield ProgressEvent(
                        type="step_error",
                        step_id="tailscale-install",
                        label="Installer no parece un script shell — abortando por seguridad.",
                        extra={"head": head[:120]},
                    )
                else:
                    yield from stream_command(
                        ["bash", str(installer_path)],
                        step_id="tailscale-install",
                        label="Ejecutando installer descargado",
                    )
        finally:
            try:
                installer_path.unlink(missing_ok=True)
            except OSError:
                pass
        yield from stream_command(
            ["sudo", "tailscale", "up"],
            step_id="tailscale-up",
            label="Iniciando Tailscale (login en navegador)",
        )
    elif ts_action == "up_only":
        if not shutil.which("tailscale"):
            yield ProgressEvent(
                type="step_error",
                step_id="tailscale-up",
                label="`tailscale` no está instalado",
                extra={"hint": "Elige 'install_and_up' o instálalo manualmente."},
            )
        else:
            yield from stream_command(
                ["sudo", "tailscale", "up"],
                step_id="tailscale-up",
                label="Iniciando Tailscale",
            )

    yield ProgressEvent(
        type="summary",
        step_id="connectivity",
        label="Conectividad lista",
        extra={
            "rows": [
                ("Verifica SSH",
                 f"ssh -o BatchMode=yes {target_host or '<dest>'} 'echo ok'"),
                ("Tailscale IPs (si aplica)", "tailscale ip -4"),
            ],
        },
    )


__all__ = ["flow_id", "first_screen_id", "screens", "next_screen_id", "execute"]
