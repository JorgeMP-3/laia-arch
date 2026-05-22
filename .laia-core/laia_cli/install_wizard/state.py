"""Checkpoint persistence for the wizard.

When the user runs ``sudo laia-wizard`` and bails halfway through a clone (or
the SSH password retry times out), the next ``sudo laia-wizard --resume`` reads
the checkpoint and skips ahead to the screen they were on, preserving the
inputs they already gave.

The file lives at ``$LAIA_HOME/wizard-state.json`` (default
``$HOME/LAIA-ARCH/wizard-state.json``) with mode 0600. Secrets (passwords,
SSH passphrases, GitHub tokens) are NEVER persisted — those fields are
filtered out before the write.

Lifecycle::

    load() → either WizardState() or None  (None ⇒ no resume file)
    save(state)                              (atomic write via tmp + rename)
    clear()                                  (delete on successful finish)

The format is purposely simple JSON, not pickle, so the user can inspect it
with ``cat`` and delete it if anything goes weird.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("laia.wizard.state")

# Side-channel: when load() quarantines a corrupted or stale checkpoint, it
# stores a human description here so the engine can surface it on the next
# screen via a warning panel. Module-level state keeps the API stable without
# adding tuples to every callsite.
_last_load_warning: dict[str, str] = {}


def consume_load_warning() -> str | None:
    """Return (and clear) any warning emitted by the last load() call.

    The engine reads this once at start so it can show a panel like
    "checkpoint anterior corrupto, empezando de cero. Detalles: …".
    """
    if not _last_load_warning:
        return None
    msg = _last_load_warning.get("message")
    _last_load_warning.clear()
    return msg

# Field names whose value MUST NOT touch disk. The engine consults this list
# before serialising. Extend as new sensitive fields appear in flows.
SECRET_FIELD_NAMES: frozenset[str] = frozenset({
    "admin_pass",
    "admin_password",
    "ssh_password",
    "github_token",
    "llm_api_key",
    "telegram_token",
    "tailscale_authkey",
    "agora_password",
    "password",
})


def _default_state_path() -> Path:
    """Resolve where the checkpoint lives.

    Honours ``$LAIA_HOME`` first (matches the installer's convention), falls
    back to ``$HOME/LAIA-ARCH``.
    """
    home = os.environ.get("LAIA_HOME")
    if home:
        return Path(home) / "wizard-state.json"
    return Path(os.path.expanduser("~")) / "LAIA-ARCH" / "wizard-state.json"


@dataclass
class WizardState:
    """In-memory wizard state. Persisted via :func:`save`."""

    mode: str | None = None              # "install" | "clone" | "diagnose" | ...
    current_screen_id: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)  # screens already visited
    contract_version: str = ""           # set on save; checked on load
    extra: dict[str, Any] = field(default_factory=dict)

    def remember(self, screen_id: str) -> None:
        """Record that the user just left ``screen_id``. Used for ``back``."""
        if not self.history or self.history[-1] != screen_id:
            self.history.append(screen_id)

    def pop_back(self) -> str | None:
        """Pop one screen from history; engine uses this for the ``back`` action."""
        if len(self.history) <= 1:
            return None
        self.history.pop()
        return self.history[-1] if self.history else None

    def set_value(self, name: str, value: Any) -> None:
        self.values[name] = value

    def get_value(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)

    def to_persistable_dict(self) -> dict[str, Any]:
        """Like asdict() but with secrets scrubbed."""
        from .contract import CONTRACT_VERSION  # local import avoids cycle
        clean_values = {
            k: ("***" if k in SECRET_FIELD_NAMES else v)
            for k, v in self.values.items()
        }
        return {
            "contract_version": CONTRACT_VERSION,
            "mode": self.mode,
            "current_screen_id": self.current_screen_id,
            "values": clean_values,
            "history": list(self.history),
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WizardState":
        return cls(
            mode=data.get("mode"),
            current_screen_id=data.get("current_screen_id"),
            values=dict(data.get("values") or {}),
            history=list(data.get("history") or []),
            contract_version=data.get("contract_version") or "",
            extra=dict(data.get("extra") or {}),
        )


def _quarantine(path: Path, reason: str) -> None:
    """Move a corrupted/stale checkpoint aside so the next run starts clean.

    The renamed file is kept (not deleted) so the user can post-mortem it.
    The warning is also surfaced via consume_load_warning() so the UI can
    show a panel instead of silently losing context.
    """
    suffix = time.strftime(".corrupt-%Y%m%dT%H%M%SZ", time.gmtime())
    target = path.with_name(path.name + suffix)
    try:
        path.rename(target)
        msg = (
            f"Checkpoint anterior inválido ({reason}). "
            f"Movido a {target} para inspección; empezando de cero."
        )
    except OSError as exc:
        # If we can't even rename, fall back to deleting.
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        msg = (
            f"Checkpoint anterior inválido ({reason}); no se pudo "
            f"renombrar para inspección ({exc})."
        )
    logger.warning(msg)
    _last_load_warning["message"] = msg


def load(path: Path | None = None) -> WizardState | None:
    """Load a checkpoint, or return ``None`` if there is none / it's stale.

    A checkpoint is considered stale (and ignored) when its ``contract_version``
    doesn't match the current one — the schema may have shifted and replaying
    would produce nonsense screens.

    Corruption (bad JSON, missing keys, version mismatch) is no longer
    silent: the bad file is renamed to ``<path>.corrupt-<ts>`` and the
    reason is logged + made available via :func:`consume_load_warning`.
    """
    from .contract import CONTRACT_VERSION
    path = path or _default_state_path()
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        _quarantine(path, f"no se pudo leer: {exc}")
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _quarantine(path, f"JSON inválido en línea {exc.lineno}: {exc.msg}")
        return None
    if not isinstance(data, dict):
        _quarantine(path, "JSON no es un objeto raíz")
        return None
    saved_version = data.get("contract_version") or ""
    if saved_version != CONTRACT_VERSION:
        _quarantine(
            path,
            f"versión del contrato cambió ({saved_version!r} → {CONTRACT_VERSION!r})",
        )
        return None
    try:
        return WizardState.from_dict(data)
    except (TypeError, ValueError) as exc:
        _quarantine(path, f"estructura no reconocida: {exc}")
        return None


def save(state: WizardState, path: Path | None = None) -> Path:
    """Atomically write the checkpoint to disk.

    Atomic = write to a sibling tmp file, then ``os.rename`` over the target.
    This survives a Ctrl-C between bytes.
    """
    path = path or _default_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.to_persistable_dict()

    # Tempfile in the same dir so the rename is atomic on the same filesystem.
    fd, tmp_str = tempfile.mkstemp(
        prefix=".wizard-state.", suffix=".tmp", dir=str(path.parent),
    )
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return path


def clear(path: Path | None = None) -> None:
    """Delete the checkpoint. Call from the engine on successful completion."""
    path = path or _default_state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


__all__ = [
    "SECRET_FIELD_NAMES",
    "WizardState",
    "load",
    "save",
    "clear",
    "consume_load_warning",
]
