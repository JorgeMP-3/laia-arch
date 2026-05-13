"""Shared helpers for direct xAI HTTP integrations."""

from __future__ import annotations


def laia_xai_user_agent() -> str:
    """Return a stable LAIA-specific User-Agent for xAI HTTP calls."""
    try:
        from laia_cli import __version__
    except Exception:
        __version__ = "unknown"
    return f"LAIA-Agent/{__version__}"
