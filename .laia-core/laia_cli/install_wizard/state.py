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
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


def load(path: Path | None = None) -> WizardState | None:
    """Load a checkpoint, or return ``None`` if there is none / it's stale.

    A checkpoint is considered stale (and ignored) when its ``contract_version``
    doesn't match the current one — the schema may have shifted and replaying
    would produce nonsense screens.
    """
    from .contract import CONTRACT_VERSION
    path = path or _default_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    saved_version = data.get("contract_version") or ""
    if saved_version != CONTRACT_VERSION:
        # Stale checkpoint — refuse to resume rather than guess.
        return None
    return WizardState.from_dict(data)


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
]
