"""Side-effect emitters for laia-pathd.

When the resolved snapshot changes, the daemon writes:
- ~/.laia/.env.paths    (bash-source file consumed by scripts + systemd)
- ~/.laia/atlas/<alias> (symlink atlas — phase 4)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

# Make the sibling laia_paths module importable when pathd runs as a script.
import sys as _sys
_CORE = Path(__file__).resolve().parents[2] / ".laia-core"
if str(_CORE) not in _sys.path:
    _sys.path.insert(0, str(_CORE))

from laia_paths import render_env_file  # noqa: E402

logger = logging.getLogger(__name__)


def write_env_file(
    resolved: dict[str, str],
    env_file: Path,
    *,
    source_path: Path | None = None,
) -> bool:
    """Write .env.paths atomically. Returns True if content changed."""
    content = render_env_file(resolved, source_path=source_path)
    if env_file.exists() and env_file.read_text() == content:
        return False
    env_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = env_file.with_suffix(env_file.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, env_file)
    logger.info("wrote %s (%d paths)", env_file, len(resolved))
    return True


def sync_symlink_farm(resolved: dict[str, str], farm_dir: Path) -> None:
    """Ensure ~/.laia/atlas/<alias> points to each resolved path.

    - Creates missing symlinks.
    - Updates symlinks whose target has changed.
    - Removes orphan symlinks no longer in the resolved map.
    Non-symlink entries in farm_dir are left alone (defensive).
    """
    farm_dir.mkdir(parents=True, exist_ok=True)
    expected = set(resolved.keys())

    for alias, target in resolved.items():
        link = farm_dir / alias
        if link.is_symlink():
            try:
                current = os.readlink(link)
            except OSError:
                current = None
            if current == target:
                continue
            link.unlink()
        elif link.exists():
            logger.warning("farm entry %s is not a symlink; leaving alone", link)
            continue
        try:
            link.symlink_to(target)
            logger.debug("symlink %s -> %s", link, target)
        except OSError as e:
            logger.warning("symlink %s failed: %s", link, e)

    for entry in farm_dir.iterdir():
        if entry.is_symlink() and entry.name not in expected:
            entry.unlink()
            logger.info("removed orphan symlink %s", entry)
