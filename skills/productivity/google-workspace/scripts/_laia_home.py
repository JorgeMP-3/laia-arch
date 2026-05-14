"""Resolve LAIA_HOME for standalone skill scripts.

Skill scripts may run outside the LAIA process (e.g. system Python,
nix env, CI) where ``laia_constants`` is not importable.  This module
provides the same ``get_laia_home()`` and ``display_laia_home()``
contracts as ``laia_constants`` without requiring it on ``sys.path``.

When ``laia_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``laia_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``LAIA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from laia_constants import display_laia_home as display_laia_home
    from laia_constants import get_laia_home as get_laia_home
except (ModuleNotFoundError, ImportError):

    def get_laia_home() -> Path:
        """Return the LAIA home directory (default: ~/.laia).

        Mirrors ``laia_constants.get_laia_home()``."""
        val = os.environ.get("LAIA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".laia"

    def display_laia_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``laia_constants.display_laia_home()``."""
        home = get_laia_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
