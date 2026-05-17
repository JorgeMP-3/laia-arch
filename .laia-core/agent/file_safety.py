"""Shared file safety rules used by both tools and ACP shims."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _laia_home_path() -> Path:
    """Resolve the active LAIA_HOME (profile-aware) without circular imports."""
    try:
        from laia_constants import get_laia_home  # local import to avoid cycles
        return get_laia_home()
    except Exception:
        return Path(os.path.expanduser("~/.laia"))


def build_write_denied_paths(home: str) -> set[str]:
    """Return exact sensitive paths that must never be written."""
    laia_home = _laia_home_path()
    return {
        os.path.realpath(p)
        for p in [
            os.path.join(home, ".ssh", "authorized_keys"),
            os.path.join(home, ".ssh", "id_rsa"),
            os.path.join(home, ".ssh", "id_ed25519"),
            os.path.join(home, ".ssh", "config"),
            str(laia_home / ".env"),
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".profile"),
            os.path.join(home, ".bash_profile"),
            os.path.join(home, ".zprofile"),
            os.path.join(home, ".netrc"),
            os.path.join(home, ".pgpass"),
            os.path.join(home, ".npmrc"),
            os.path.join(home, ".pypirc"),
            "/etc/sudoers",
            "/etc/passwd",
            "/etc/shadow",
        ]
    }


def build_write_denied_prefixes(home: str) -> list[str]:
    """Return sensitive directory prefixes that must never be written."""
    return [
        os.path.realpath(p) + os.sep
        for p in [
            os.path.join(home, ".ssh"),
            os.path.join(home, ".aws"),
            os.path.join(home, ".gnupg"),
            os.path.join(home, ".kube"),
            "/etc/sudoers.d",
            "/etc/systemd",
            os.path.join(home, ".docker"),
            os.path.join(home, ".azure"),
            os.path.join(home, ".config", "gh"),
        ]
    ]


def get_safe_write_root() -> Optional[str]:
    """Return the resolved LAIA_WRITE_SAFE_ROOT path, or None if unset."""
    root = os.getenv("LAIA_WRITE_SAFE_ROOT", "")
    if not root:
        return None
    try:
        return os.path.realpath(os.path.expanduser(root))
    except Exception:
        return None


def is_write_denied(path: str) -> bool:
    """Return True if path is blocked by the write denylist or safe root."""
    home = os.path.realpath(os.path.expanduser("~"))
    resolved = os.path.realpath(os.path.expanduser(str(path)))

    if resolved in build_write_denied_paths(home):
        return True
    for prefix in build_write_denied_prefixes(home):
        if resolved.startswith(prefix):
            return True

    safe_root = get_safe_write_root()
    if safe_root and not (resolved == safe_root or resolved.startswith(safe_root + os.sep)):
        return True

    return False


def build_read_denied_paths(home: str) -> set[str]:
    """Exact paths that must never be READ.

    These are credentials, secrets and OS-internal files. Even if the LLM
    is told "please read this for context", we refuse — prompt injection
    routinely targets these. The result of a refused read is a clear
    error string the tool surface returns to the model.
    """
    return {
        os.path.realpath(p)
        for p in [
            # OS credentials / secrets
            "/etc/shadow",
            "/etc/gshadow",
            "/etc/sudoers",
            "/etc/master.passwd",
            # User SSH private keys (the *.pub variants stay readable
            # — they're public anyway).
            os.path.join(home, ".ssh", "id_rsa"),
            os.path.join(home, ".ssh", "id_ed25519"),
            os.path.join(home, ".ssh", "id_ecdsa"),
            os.path.join(home, ".ssh", "id_dsa"),
            # Cloud / build credentials
            os.path.join(home, ".aws", "credentials"),
            os.path.join(home, ".aws", "config"),
            os.path.join(home, ".kube", "config"),
            os.path.join(home, ".docker", "config.json"),
            os.path.join(home, ".netrc"),
            os.path.join(home, ".pgpass"),
            os.path.join(home, ".npmrc"),
            os.path.join(home, ".pypirc"),
            # LAIA's own auth + env stash
            str(_laia_home_path() / ".env"),
            str(_laia_home_path() / "auth.json"),
        ]
    }


def build_read_denied_prefixes(home: str) -> list[str]:
    """Directory prefixes that must never be READ from."""
    return [
        os.path.realpath(p) + os.sep
        for p in [
            # SSH dir aside from the .pub keys: deny by default, allow
            # only explicit public-key paths.
            os.path.join(home, ".ssh"),
            "/etc/sudoers.d",
            os.path.join(home, ".gnupg"),
            os.path.join(home, ".aws"),
            os.path.join(home, ".kube"),
            os.path.join(home, ".azure"),
            os.path.join(home, ".config", "gh"),
            os.path.join(home, ".docker"),
            # /proc/<pid>/environ leaks env vars (which often hold
            # tokens) for that process. Block the whole /proc/*/environ
            # surface — there's no legitimate AIAgent need for it.
        ]
    ]


def get_read_block_error(path: str) -> Optional[str]:
    """Return an error message when a read targets a sensitive file.

    Two layers:

    1. **Internal LAIA cache** — prevents prompt injection via the
       skills hub cache (the original protection).
    2. **OS / user credentials** (added in A4 of the AGORA security
       sprint) — refuse reads of /etc/shadow, ~/.ssh private keys,
       ~/.aws/credentials, etc. even when the model insists. The list
       lives in :func:`build_read_denied_paths` and
       :func:`build_read_denied_prefixes` so callers can introspect or
       test against it.
    """
    home = os.path.realpath(os.path.expanduser("~"))
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        # Can't resolve (symlink loop, etc.) — be conservative.
        resolved = Path(os.path.expanduser(str(path)))

    laia_home = _laia_home_path().resolve()
    blocked_dirs = [
        laia_home / "skills" / ".hub" / "index-cache",
        laia_home / "skills" / ".hub",
    ]
    for blocked in blocked_dirs:
        try:
            resolved.relative_to(blocked)
        except ValueError:
            continue
        return (
            f"Access denied: {path} is an internal LAIA cache file "
            "and cannot be read directly to prevent prompt injection. "
            "Use the skills_list or skill_view tools instead."
        )

    resolved_str = str(resolved)

    # Exact-path blocklist
    if resolved_str in build_read_denied_paths(home):
        return (
            f"Access denied: {path} is a credentials / secrets file and "
            "cannot be read by the agent. If you genuinely need its value, "
            "have the operator copy the specific value into the prompt."
        )

    # Prefix blocklist (whole directories of secrets)
    for prefix in build_read_denied_prefixes(home):
        if resolved_str.startswith(prefix):
            # Allow only public SSH keys: ~/.ssh/*.pub
            if prefix.startswith(os.path.realpath(os.path.join(home, ".ssh")) + os.sep):
                if resolved_str.endswith(".pub"):
                    continue
            return (
                f"Access denied: {path} is under a sensitive directory "
                f"({prefix.rstrip(os.sep)}) and cannot be read by the agent."
            )

    # /proc/*/environ leaks tokens — deny regardless of which PID.
    if resolved_str.startswith("/proc/") and resolved_str.endswith("/environ"):
        return (
            f"Access denied: {path} would leak environment variables "
            "(commonly containing tokens) of another process."
        )

    return None
