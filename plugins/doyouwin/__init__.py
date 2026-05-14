"""doyouwin — Context engine plugin that injects memories/doyouwin/ as system-prompt context.

Reads all .md files under memories/doyouwin/ (recursively) and makes them
available to the agent via system_prompt_block(). The built-in memory
(MEMORY.md / USER.md) remains active alongside this plugin.

Config in $HERMES_HOME/config.yaml:
  plugins:
    doyouwin:
      directory: memories/doyouwin     # relative to HERMES_HOME (default)
      max_chars: 4000                # truncate total content (default: 4000)
      recursive: true                # include subdirectories (default: true)

Activate: set memory.provider: doyouwin in config.yaml
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

# Rel path to memories dir (relative to HERMES_HOME)
DEFAULT_MEMORIES_DIR = "memories/doyouwin"
DEFAULT_MAX_CHARS = 4000
DEFAULT_RECURSIVE = True

ENTRY_BOUNDARY_RE = re.compile(r'^#{1,3}\s+', re.MULTILINE)


def _load_plugin_config() -> dict:
    """Read plugins.doyouwin from config.yaml."""
    try:
        from hermes_constants import get_hermes_home
        config_path = get_hermes_home() / "config.yaml"
        if not config_path.exists():
            return {}
        import yaml
        with open(config_path) as f:
            all_config = yaml.safe_load(f) or {}
        return all_config.get("plugins", {}).get("doyouwin", {}) or {}
    except Exception:
        return {}


def _resolve_memories_dir(hermes_home: str, cfg: dict) -> Path:
    """Resolve the memories directory path."""
    rel = cfg.get("directory", DEFAULT_MEMORIES_DIR)
    # Support both absolute and relative paths
    p = Path(rel)
    if p.is_absolute():
        return p
    return Path(hermes_home) / rel


def _read_markdown_files(memories_dir: Path, recursive: bool) -> List[tuple[str, Path]]:
    """Read all .md files under memories_dir, return [(relative_content, full_path)].

    For each file, the relative_content is the first 120 chars of the file
    name (without extension) + the full file content.
    """
    results: List[tuple[str, Path]] = []
    if not memories_dir.is_dir():
        logger.debug("doyouwin memories dir not found: %s", memories_dir)
        return results

    pattern = "**/*.md" if recursive else "*.md"
    for md_file in sorted(memories_dir.glob(pattern)):
        if md_file.name.startswith("."):
            continue
        try:
            content = md_file.read_text(encoding="utf-8").strip()
            if content:
                # Derive a short name from the file path for disambiguation
                rel_path = md_file.relative_to(memories_dir)
                display_name = str(rel_path).replace(".md", "").replace("/", " / ").replace("\\", " / ")
                results.append((f"[Source: {display_name}]\n\n{content}", md_file))
        except Exception as e:
            logger.debug("Failed to read %s: %s", md_file, e)

    return results


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, preserving boundary."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 80] + f"\n\n[... truncated to {max_chars} chars ...]"


# --------------------------------------------------------------------------


class DoYouWinMemoryProvider(MemoryProvider):
    """Reads memories/doyouwin/*.md and exposes them as system-prompt context."""

    def __init__(self, config: dict | None = None):
        self._config = config or _load_plugin_config()
        self._hermes_home: Optional[str] = None
        self._memories_dir: Optional[Path] = None
        self._cached_block: Optional[str] = None
        self._file_mtimes: dict = {}

    @property
    def name(self) -> str:
        return "doyouwin"

    def is_available(self) -> bool:
        """Always available — no external deps needed."""
        return True

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "directory",
                "description": "Directory to scan for .md files (relative to HERMES_HOME, or absolute)",
                "default": DEFAULT_MEMORIES_DIR,
            },
            {
                "key": "max_chars",
                "description": "Maximum total characters to inject into the system prompt",
                "default": str(DEFAULT_MAX_CHARS),
            },
            {
                "key": "recursive",
                "description": "Scan subdirectories recursively",
                "default": "true",
                "choices": ["true", "false"],
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write config to config.yaml under plugins.doyouwin."""
        from pathlib import Path
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path) as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["doyouwin"] = values
            with open(config_path, "w") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as e:
            logger.warning("Failed to save doyouwin config: %s", e)

    def initialize(self, session_id: str, **kwargs) -> None:
        """Resolve memories dir and load all .md files."""
        hermes_home = kwargs.get("hermes_home")
        if not hermes_home:
            from hermes_constants import get_hermes_home
            hermes_home = str(get_hermes_home())

        self._hermes_home = hermes_home
        self._memories_dir = _resolve_memories_dir(hermes_home, self._config)
        self._rebuild_block()

    def _rebuild_block(self) -> None:
        """Reload all .md files and build the cached system prompt block."""
        if not self._memories_dir:
            return

        recursive = self._config.get("recursive", DEFAULT_RECURSIVE)
        max_chars = int(self._config.get("max_chars", DEFAULT_MAX_CHARS))

        files = _read_markdown_files(self._memories_dir, recursive)
        if not files:
            self._cached_block = ""
            return

        # Update mtimes for change detection
        self._file_mtimes = {p: p.stat().st_mtime for _, p in files}

        # Concatenate all files
        parts = [content for content, _ in files]
        combined = "\n\n---\n\n".join(parts)
        self._cached_block = _truncate(combined, max_chars)

    def _check_for_changes(self) -> bool:
        """Return True if any .md file changed since last load."""
        if not self._memories_dir or not self._file_mtimes:
            return False
        recursive = self._config.get("recursive", DEFAULT_RECURSIVE)
        pattern = "**/*.md" if recursive else "*.md"
        try:
            current_files = [
                p for p in sorted(self._memories_dir.glob(pattern))
                if not p.name.startswith(".")
            ]
            return any(
                p.stat().st_mtime != self._file_mtimes.get(p, 0)
                for p in current_files
            )
        except Exception:
            return False

    def system_prompt_block(self) -> str:
        """Return the doyouwin context block for the system prompt.

        Check for file changes on every call so edits during a session
        are picked up without requiring a restart.
        """
        if self._cached_block is None:
            return ""  # Not initialized yet

        if self._check_for_changes():
            self._rebuild_block()

        if not self._cached_block:
            return ""

        index_file = self._memories_dir / "00-indice.md" if self._memories_dir else None
        index_note = (
            ""
        )

        return (
            f"{index_note}"
            f"<!-- doyouwin context start -->\n"
            f"{self._cached_block}\n"
            f"<!-- doyouwin context end -->"
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Context-only provider — everything is in system_prompt_block()."""
        return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Nothing to persist."""
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """No tools — context-only provider."""
        return []

    def shutdown(self) -> None:
        self._cached_block = None
        self._file_mtimes.clear()


# --------------------------------------------------------------------------


def register(ctx) -> None:
    """Register the doyouwin memory provider."""
    config = _load_plugin_config()
    provider = DoYouWinMemoryProvider(config=config)
    ctx.register_memory_provider(provider)
