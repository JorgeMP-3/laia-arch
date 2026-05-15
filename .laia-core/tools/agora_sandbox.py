"""Sandbox layer for the `agora-agent` toolset profile.

When `LAIA_PROFILE=agora-agent`, file-system tools and the terminal tool
gain extra restrictions:

  - File ops (read/write/patch/search): the target path MUST resolve inside one
    of the whitelisted roots (``/opt/laia/data``, ``/opt/laia/plugins``,
    ``/tmp/laia-scratch``). Anything else (notably ``/opt/laia/agent`` where
    .laia-core lives) is rejected.

  - Terminal: the first command word is matched against a blacklist of
    host-management binaries (lxc, systemctl, apt, docker, mount, sudo, ...).
    Pipes / && / ; are scanned for the same blacklist.

These helpers are pure: they return ``None`` if the operation is allowed,
or a short string error message if it must be blocked. The decision to
activate sandboxing is driven solely by the ``LAIA_PROFILE`` env var, so
the LAIA ARCH agent in the host stays untouched.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Iterable, Optional


SANDBOX_ENV_VAR = "LAIA_PROFILE"
SANDBOX_ACTIVE_VALUE = "agora-agent"

# Roots an Agora Agent may read/write into. Symlinks resolved via Path.resolve().
DEFAULT_WHITELISTED_ROOTS: tuple[str, ...] = (
    "/opt/laia/data",
    "/opt/laia/plugins",
    "/tmp/laia-scratch",
)

# Substrings that always indicate a path into the agent's own code.
FORBIDDEN_PATH_SUBSTRINGS: tuple[str, ...] = (
    ".laia-core",
    "/opt/laia/agent",   # whole tree owned root:laia-agent 0750
    "/opt/laia/runtime/venv",
)

# Commands forbidden under the agora-agent sandbox. Matched against the first
# token of every segment of a compound command (split on |, &, ;, &&, ||).
COMMAND_BLACKLIST: frozenset[str] = frozenset({
    "lxc", "lxd",
    "systemctl", "journalctl",
    "apt", "apt-get", "dpkg",
    "docker", "podman",
    "mount", "umount",
    "sudo", "su", "doas",
    "useradd", "userdel", "usermod", "groupadd", "groupdel",
    "chown", "chmod",      # would let agent edit /opt/laia/agent perms
    "iptables", "nft",
    "modprobe", "insmod", "rmmod",
})

# Regex used to split compound commands into individual command segments.
_COMPOUND_SPLIT_RE = re.compile(r"[|&;]+")


def is_sandbox_active() -> bool:
    return os.environ.get(SANDBOX_ENV_VAR, "").strip() == SANDBOX_ACTIVE_VALUE


def enforce_path_sandbox(
    path: str | Path,
    *,
    whitelist: Iterable[str] | None = None,
) -> Optional[str]:
    """Return ``None`` if *path* is acceptable, else a short error string.

    Always returns ``None`` when the sandbox isn't active (the host's
    LAIA ARCH agent has unrestricted file access by design).

    Reads ``DEFAULT_WHITELISTED_ROOTS`` lazily from the module attribute
    so tests / runtime callers can mutate it.
    """
    if not is_sandbox_active():
        return None

    if whitelist is None:
        whitelist = DEFAULT_WHITELISTED_ROOTS
    whitelist = tuple(whitelist)

    raw = str(path)
    lowered = raw.lower()
    for needle in FORBIDDEN_PATH_SUBSTRINGS:
        if needle in lowered:
            return f"Path rejected: agents may not access agent code ({needle})"

    try:
        resolved = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        return f"Path could not be resolved: {exc}"

    resolved_str = str(resolved)
    for needle in FORBIDDEN_PATH_SUBSTRINGS:
        if needle in resolved_str:
            return f"Path rejected: resolves into protected area ({needle})"

    for root in whitelist:
        try:
            root_resolved = Path(root).resolve()
        except (OSError, RuntimeError):
            continue
        try:
            resolved.relative_to(root_resolved)
            return None  # inside whitelisted root → allowed
        except ValueError:
            continue

    return (
        "Path rejected: agents may only access "
        + ", ".join(whitelist)
        + f" (got {raw!r})"
    )


def enforce_command_sandbox(
    command: str,
    *,
    blacklist: Iterable[str] | None = None,
) -> Optional[str]:
    """Return ``None`` if *command* is acceptable, else a short error string.

    Looks at the first token of every segment of the compound command.
    Does not validate against arg injection; the goal is hard-blocking of
    host-administration binaries, not full shell sandboxing.
    """
    if not is_sandbox_active():
        return None

    if not command or not command.strip():
        return None

    if blacklist is None:
        blacklist = COMMAND_BLACKLIST
    blacklist_set = set(blacklist)

    # Split on shell control operators: | || & && ;
    segments = _COMPOUND_SPLIT_RE.split(command)
    for segment in segments:
        seg = segment.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg, comments=False, posix=True)
        except ValueError:
            # Unbalanced quote — let the underlying shell raise; we don't
            # try to be cleverer than shlex.
            tokens = seg.split()
        if not tokens:
            continue
        # First non-assignment token is the command (skip `VAR=value` prefixes).
        cmd = None
        for tok in tokens:
            if "=" in tok and not tok.startswith("="):
                # Looks like ENV=value prefix; skip.
                continue
            cmd = tok
            break
        if cmd is None:
            continue
        # Strip path: /usr/bin/sudo -> sudo
        binary = os.path.basename(cmd)
        if binary in blacklist_set:
            return f"Command rejected: {binary!r} is not available to Agora Agents"

    return None
