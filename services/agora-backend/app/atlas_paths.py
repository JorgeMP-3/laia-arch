"""Atlas-backed reference resolution for agora-backend.

Resolves paths, containers, and service URLs via Atlas v2
(``~/.laia/atlas.yaml``) with graceful fallback to a caller-supplied default
when Atlas is unavailable (test isolation, disaster recovery, fresh install
before Atlas is provisioned).

Resolution order: env var override → Atlas → static default.

This is a thin wrapper. The full Atlas library lives in
``.laia-core/atlas.py``; we import it lazily so agora-backend remains
runnable even if ``.laia-core`` is not on the host (e.g. when the backend
runs inside an LXD container that ships only the backend, not the agent
source tree).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_atlas_module = None
_atlas_probed = False


def _atlas():
    """Lazy import of the atlas module. Returns None on any failure."""
    global _atlas_module, _atlas_probed
    if _atlas_probed:
        return _atlas_module
    _atlas_probed = True
    try:
        laia_core = Path(
            os.environ.get("LAIA_ROOT", str(Path.home() / "LAIA"))
        ) / ".laia-core"
        if laia_core.is_dir() and str(laia_core) not in sys.path:
            sys.path.insert(0, str(laia_core))
        import atlas  # type: ignore

        _atlas_module = atlas
    except Exception as exc:  # ImportError, OSError, etc.
        logger.debug("atlas module not available: %s", exc)
        _atlas_module = None
    return _atlas_module


def resolved_path(env_var: str, atlas_ref: str, default: str | Path) -> Path:
    """Resolve a path with precedence ``env_var → atlas → default``.

    Used for filesystem paths like ``/srv/laia/agora`` or ``/srv/laia/users``.
    """
    explicit = os.environ.get(env_var)
    if explicit:
        return Path(explicit)
    atlas = _atlas()
    if atlas is not None:
        try:
            return Path(atlas.get(atlas_ref))
        except Exception as exc:
            logger.debug("atlas.get(%r) failed, using default: %s", atlas_ref, exc)
    return Path(default)


def resolved_container(env_var: str, atlas_ref: str, default: str) -> str:
    """Resolve a container name with precedence ``env_var → atlas → default``."""
    explicit = os.environ.get(env_var)
    if explicit:
        return explicit
    atlas = _atlas()
    if atlas is not None:
        try:
            return str(atlas.get(atlas_ref))
        except Exception as exc:
            logger.debug("atlas.get(%r) failed, using default: %s", atlas_ref, exc)
    return default


def atlas_string(atlas_ref: str, default: str) -> str:
    """Resolve any ref to a string with precedence ``atlas → default``.

    Used when there is no env-var override path (pure literal hardcodes).
    """
    atlas = _atlas()
    if atlas is not None:
        try:
            return str(atlas.get(atlas_ref))
        except Exception as exc:
            logger.debug("atlas.get(%r) failed, using default: %s", atlas_ref, exc)
    return default


__all__ = ["resolved_path", "resolved_container", "atlas_string"]
