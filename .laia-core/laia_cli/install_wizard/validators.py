"""Input validators referenced by name from :class:`contract.Field`.

A validator is a callable that returns ``(ok, error_msg_or_none)``. The engine
resolves the name to the function via :data:`VALIDATORS` and calls it on the
raw value the UI handed in. Errors go back to C2 in
:attr:`contract.ValidationResult.errors`.

Adding a new validator
----------------------
1. Define it below following the ``Result`` signature.
2. Register it in :data:`VALIDATORS`.
3. Tests in ``tests/wizard/test_validators.py`` cover the happy and unhappy
   paths.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable

Result = tuple[bool, str | None]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def non_empty(value: Any) -> Result:
    if value is None:
        return False, "Este campo es obligatorio."
    if isinstance(value, str) and not value.strip():
        return False, "Este campo no puede estar vacío."
    if isinstance(value, (list, tuple)) and not value:
        return False, "Selecciona al menos una opción."
    return True, None


def password_strength(value: Any) -> Result:
    if not isinstance(value, str):
        return False, "Password inválido."
    if len(value) < 8:
        return False, "Mínimo 8 caracteres."
    if value.lower() in {"password", "admin", "12345678", "laia"}:
        return False, "Demasiado común — elige algo más fuerte."
    return True, None


# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

# user@host where host is either a hostname (RFC 1123 chunked) or an IPv4.
_SSH_TARGET_RE = re.compile(
    r"^(?P<user>[a-z_][a-z0-9_-]{0,31})@"
    r"(?P<host>"
    r"(?:\d{1,3}\.){3}\d{1,3}"             # IPv4
    r"|"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,62}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,62}[a-zA-Z0-9])?)*"  # hostname.tld
    r")$"
)

def ssh_target(value: Any) -> Result:
    if not isinstance(value, str) or not value.strip():
        return False, "Especifica user@host."
    if not _SSH_TARGET_RE.match(value.strip()):
        return False, "Formato esperado: user@host (ej: laia@10.0.0.5 o jorge@laia.example)."
    # Reject obvious nonsense like trailing octets > 255.
    host = value.split("@", 1)[1]
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", host):
        if any(int(p) > 255 for p in host.split(".")):
            return False, "IPv4 con octeto fuera de rango (0-255)."
    return True, None


_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,62}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,62}[a-zA-Z0-9])?)*$"
)

def valid_hostname(value: Any) -> Result:
    if not isinstance(value, str) or not _HOSTNAME_RE.match(value.strip()):
        return False, "Hostname inválido (sólo letras, dígitos, '-' y '.')."
    return True, None


_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")

def ipv4(value: Any) -> Result:
    if not isinstance(value, str) or not _IPV4_RE.match(value.strip()):
        return False, "IPv4 inválida (ej: 192.168.1.10)."
    if any(int(p) > 255 for p in value.split(".")):
        return False, "Octeto fuera de rango (0-255)."
    return True, None


# rsync --bwlimit accepts integer KB/s or values like 50M, 1G, 250K.
_BWLIMIT_RE = re.compile(r"^\d+[KMGkmg]?$")

def rsync_bwlimit(value: Any) -> Result:
    if value in (None, ""):
        return True, None  # optional
    if not isinstance(value, str) or not _BWLIMIT_RE.match(value.strip()):
        return False, "Formato: número con sufijo opcional K/M/G (ej: 50M, 1G, 200K)."
    return True, None


def port_number(value: Any) -> Result:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return False, "Puerto debe ser un entero."
    if not (1 <= n <= 65535):
        return False, "Puerto fuera de rango (1-65535)."
    return True, None


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------

def existing_path(value: Any) -> Result:
    if not isinstance(value, str) or not value:
        return False, "Especifica una ruta."
    p = Path(os.path.expanduser(value))
    if not p.exists():
        return False, f"No existe: {p}"
    return True, None


def writable_dir(value: Any) -> Result:
    if not isinstance(value, str) or not value:
        return False, "Especifica un directorio."
    p = Path(os.path.expanduser(value))
    if not p.exists():
        # OK if parent is writable — we may create it.
        if p.parent.exists() and os.access(p.parent, os.W_OK):
            return True, None
        return False, f"No existe y el padre no es escribible: {p}"
    if not p.is_dir():
        return False, f"No es un directorio: {p}"
    if not os.access(p, os.W_OK):
        return False, f"Sin permisos de escritura en {p}"
    return True, None


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

# Posix username, used for admin_user and for slugs that become container names.
_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

def posix_username(value: Any) -> Result:
    if not isinstance(value, str) or not _USERNAME_RE.match(value):
        return False, "Username inválido (a-z, 0-9, _, -; debe empezar con letra o _, máx 32 chars)."
    return True, None


# LLM provider name used by .laia-core. We accept the canonical set; the
# wizard will offer a choice rather than free text, but a custom provider
# string is also tolerated as long as it's slug-shaped.
_LLM_KNOWN: frozenset[str] = frozenset({
    "deepseek", "openai", "anthropic", "claude",
    "openai-codex", "azure-openai", "ollama", "local", "unset",
})
_LLM_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")

def llm_provider_name(value: Any) -> Result:
    if not isinstance(value, str):
        return False, "Provider name debe ser texto."
    v = value.strip().lower()
    if v in _LLM_KNOWN:
        return True, None
    if _LLM_SLUG_RE.match(v):
        return True, None
    return False, "Provider inválido (sólo a-z, 0-9, '-'; empezando con letra)."


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

VALIDATORS: dict[str, Callable[[Any], Result]] = {
    "non_empty": non_empty,
    "password_strength": password_strength,
    "ssh_target": ssh_target,
    "valid_hostname": valid_hostname,
    "ipv4": ipv4,
    "rsync_bwlimit": rsync_bwlimit,
    "port_number": port_number,
    "existing_path": existing_path,
    "writable_dir": writable_dir,
    "posix_username": posix_username,
    "llm_provider_name": llm_provider_name,
}


def run(name: str | None, value: Any) -> Result:
    """Look up a validator by name and run it.

    Unknown names return ``(False, "...")`` rather than raising — that way a
    typo in a flow surfaces as a visible error during testing instead of a
    crash mid-wizard.
    """
    if not name:
        return True, None
    fn = VALIDATORS.get(name)
    if fn is None:
        return False, f"Validator desconocido: {name}"
    return fn(value)


__all__ = [
    "Result",
    "VALIDATORS",
    "run",
    "non_empty",
    "password_strength",
    "ssh_target",
    "valid_hostname",
    "ipv4",
    "rsync_bwlimit",
    "port_number",
    "existing_path",
    "writable_dir",
    "posix_username",
    "llm_provider_name",
]
