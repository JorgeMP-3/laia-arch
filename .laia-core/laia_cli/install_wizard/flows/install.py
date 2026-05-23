"""Fresh-install flow.

User journey (each step is a WizardScreen):

1. ``admin``        — admin username + autogen/manual password.
2. ``llm``          — pick LLM provider; if a real provider is chosen, ask key.
3. ``lxd``          — instala LXD si falta.
4. ``confirm``      — read-only summary + ``run`` action.

On ``run``, the engine calls :func:`execute` which invokes ``bin/laia-install``
with the validated flags.

The screen IDs are stable — tests reference them, the checkpoint stores them.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import string
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


@contextlib.contextmanager
def _secret_to_tempfile(secret: str, prefix: str = "laia-secret-"):
    """Write ``secret`` to a freshly-created 0600 tempfile and yield its path.

    The receiving binary is expected to consume and unlink the file (see
    ``bin/laia-install`` ``resolve_admin_pass_file``). We still unlink on
    exit with ``missing_ok=True`` as a belt-and-braces fallback in case
    the subprocess crashed before reading.

    Using a file instead of argv keeps the secret out of ``ps``,
    ``/proc/<pid>/cmdline`` and bash history.
    """
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

flow_id = "install"
first_screen_id = "admin"


# ---------------------------------------------------------------------------
# Screens (static)
# ---------------------------------------------------------------------------

_ADMIN_SCREEN = WizardScreen(
    id="admin",
    title="LAIA admin",
    description=(
        "El admin de LAIA-AGORA: usuario que entra a la UI y registra empleados.\n"
        "Deja el password vacío y se generará uno seguro de 20 caracteres."
    ),
    fields=(
        Field(
            name="admin_user",
            type="text",
            label="Username admin",
            default="admin",
            placeholder="admin",
            validator="posix_username",
        ),
        Field(
            name="admin_pass",
            type="password",
            label="Password admin (opcional)",
            placeholder="(vacío → autogenerado 20 chars)",
            secret=True,
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
    help_text=(
        "El password se guarda en mode 600 en $LAIA_HOME/.admin-credentials, "
        "y se imprime una vez al final."
    ),
)


def _llm_screen(_state) -> WizardScreen:
    """Dynamic — only show the API-key field when a real provider is selected."""
    return WizardScreen(
        id="llm",
        title="Proveedor LLM",
        description="¿Qué motor de lenguaje usará LAIA por defecto?",
        fields=(
            Field(
                name="llm_provider",
                type="choice",
                label="Provider",
                default="unset",
                choices=(
                    Choice(value="unset", label="Configurar después (placeholder)",
                           description="auth.json queda como placeholder; configura desde la UI."),
                    Choice(value="deepseek", label="DeepSeek",
                           description="Económico, multilingüe, buena tool-use."),
                    Choice(value="openai", label="OpenAI"),
                    Choice(value="anthropic", label="Anthropic (Claude)"),
                    Choice(value="local", label="Local / Ollama",
                           description="No requiere key; configura endpoint después."),
                ),
                validator="llm_provider_name",
            ),
            Field(
                name="llm_api_key",
                type="password",
                label="API key",
                placeholder="sk-...",
                secret=True,
                validator="non_empty",
                # Only require the key when a real provider was chosen.
                # Skipped for "unset" (placeholder auth) and "local" (no key).
                depends_on={"llm_provider": ["deepseek", "openai", "anthropic", "claude"]},
                help_text="No se persiste en el checkpoint; sólo se escribe a auth.json.",
            ),
        ),
        actions=(ACTION_BACK, ACTION_NEXT),
    )


_LXD_SCREEN = WizardScreen(
    id="lxd",
    title="LXD",
    description="¿Instalar e inicializar LXD automáticamente si falta?",
    fields=(
        Field(
            name="init_lxd",
            type="yesno",
            label="Auto-instalar LXD",
            default=True,
        ),
    ),
    actions=(ACTION_BACK, ACTION_NEXT),
    help_text=(
        "Si dices que no y LXD no está instalado, laia-install aborta. "
        "Si LXD ya está, este paso es no-op."
    ),
)


def _confirm_screen(state) -> WizardScreen:
    """Build the run-confirmation screen from current values."""
    v = state.values
    summary = (
        f"  Admin:        {v.get('admin_user', 'admin')}\n"
        f"  Password:     {'(autogen al final)' if not v.get('admin_pass') else '(provista)'}\n"
        f"  LLM:          {v.get('llm_provider', 'unset')}\n"
        f"  Init LXD:     {'sí' if v.get('init_lxd', True) else 'no'}"
    )
    return WizardScreen(
        id="confirm",
        title="Confirmar instalación",
        description=(
            "Esto invocará `bin/laia-install` con tus elecciones. "
            "La descarga/instalación de LXD empieza después de pulsar Instalar. "
            "Construir las imágenes LXD puede tomar 10-20 min la primera vez."
        ),
        fields=(
            Field(
                name="_summary",
                type="info",
                label="Resumen",
                default=summary,
            ),
        ),
        actions=(
            ACTION_BACK,
            Action(name="run", label="Instalar", kind="submit"),
        ),
    )


screens: dict[str, Any] = {
    "admin":   _ADMIN_SCREEN,
    "llm":     _llm_screen,
    "lxd":     _LXD_SCREEN,
    "confirm": _confirm_screen,
}


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_ORDER = ["admin", "llm", "lxd", "confirm"]


def next_screen_id(screen_id: str, _state) -> str | None:
    try:
        idx = _ORDER.index(screen_id)
    except ValueError:
        return _ORDER[0]
    if idx + 1 >= len(_ORDER):
        return None
    return _ORDER[idx + 1]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _autogen_password(n: int = 20) -> str:
    """Match factory.sh::fact_random_password — 20-char alphanumeric."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _materialize_auth_file(provider: str, api_key: str | None) -> Path | None:
    """Write a temporary auth.json for the chosen provider.

    laia-install reads ``--auth-file PATH`` and copies it into
    ``$LAIA_HOME/auth.json`` with mode 0600. Returns ``None`` for
    ``provider=unset`` so the installer uses its placeholder.
    """
    if provider in ("unset", "", None):
        return None
    payload: dict[str, Any] = {"provider": provider}
    if api_key:
        # Schema is .laia-core's territory; this matches its expectations.
        payload["api_key"] = api_key
    # Use the system temp dir (XDG_RUNTIME_DIR-aware) rather than hardcoded
    # /tmp — encrypted-home systems and locked-down containers may not have
    # /tmp writable, and /tmp is world-readable by default in many configs.
    fd, tmp_str = tempfile.mkstemp(prefix="auth.", suffix=".json",
                                   dir=tempfile.gettempdir())
    tmp = Path(tmp_str)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.chmod(tmp, 0o600)
    return tmp


def execute(state) -> Iterator[ProgressEvent]:
    """Spawn ``bin/laia-install`` with the validated values and stream events."""
    v = state.values
    admin_user = v.get("admin_user") or "admin"
    admin_pass = v.get("admin_pass") or _autogen_password()
    init_lxd = bool(v.get("init_lxd", True))

    if init_lxd:
        yield ProgressEvent(
            type="info",
            step_id="install:lxd",
            label=(
                "LXD todavía no se descarga en las pantallas de preguntas; "
                "empieza ahora durante la ejecución. Verás salida de snap/lxd "
                "y latidos si tarda."
            ),
        )
    provider = v.get("llm_provider") or "unset"
    api_key = v.get("llm_api_key")

    auth_file = _materialize_auth_file(provider, api_key)

    root = repo_root()
    laia_install = root / "bin" / "laia-install"
    if not laia_install.is_file():
        yield ProgressEvent(
            type="step_error",
            step_id="locate",
            label=f"No encuentro {laia_install}",
            extra={"hint": "Set LAIA_ROOT or run wizard from the repo."},
        )
        return

    # Use an ExitStack so every secret-bearing tempfile we create is unlinked
    # on success AND on KeyboardInterrupt / exception, even if the subprocess
    # was killed mid-flight before it could consume the file.
    with contextlib.ExitStack() as stack:
        pass_file = stack.enter_context(_secret_to_tempfile(
            admin_pass, prefix="laia-admin-pass-"))

        cmd: list[str] = [
            "sudo", "-E", "bash", str(laia_install),
            "--from-local", str(root),
            "--yes",
            "--json-progress",
            "--admin-user", admin_user,
            "--admin-pass-file", str(pass_file),
        ]
        if init_lxd:
            cmd.append("--init-lxd")
        if auth_file:
            cmd.extend(["--auth-file", str(auth_file)])

        try:
            yield from stream_command(
                cmd,
                step_id="laia-install",
                label="Instalando LAIA",
                cwd=root,
            )
        finally:
            if auth_file:
                try:
                    auth_file.unlink()
                except FileNotFoundError:
                    pass

    # Hand the user the autogen password so they can log in.
    yield ProgressEvent(
        type="summary",
        step_id="laia-install",
        label="Credenciales de admin",
        extra={
            "rows": [
                ("Username", admin_user),
                ("Password", admin_pass),
                ("Guardado", "$LAIA_HOME/.admin-credentials (mode 600)"),
            ],
            "next_steps": [
                "Abre la UI de LAIA-AGORA en http://localhost:8088",
                "Loguéate con las creds de arriba y crea el primer empleado.",
            ],
        },
    )


__all__ = [
    "flow_id",
    "first_screen_id",
    "screens",
    "next_screen_id",
    "execute",
]
