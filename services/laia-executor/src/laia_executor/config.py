"""Executor configuration loaded from env vars and on-disk files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TOKEN_FILE = "/etc/laia/executor-token"
DEFAULT_PROFILE_FILE = "/etc/laia/agent.json"


@dataclass(frozen=True)
class ExecutorConfig:
    """Runtime configuration for the executor.

    Values come from (in priority order): env var override, on-disk file, default.
    """

    bind_host: str
    bind_port: int
    token: str
    slug: str
    workspace_root: str
    plugins_root: str

    @classmethod
    def load(cls) -> "ExecutorConfig":
        token = _read_token(os.environ.get("LAIA_EXECUTOR_TOKEN_FILE", DEFAULT_TOKEN_FILE))
        slug = os.environ.get("LAIA_EXECUTOR_SLUG") or _read_slug_from_profile(DEFAULT_PROFILE_FILE)
        return cls(
            bind_host=os.environ.get("LAIA_EXECUTOR_HOST", "0.0.0.0"),
            bind_port=int(os.environ.get("LAIA_EXECUTOR_PORT", "9091")),
            token=token,
            slug=slug or "unknown",
            workspace_root=os.environ.get("LAIA_EXECUTOR_WORKSPACE_ROOT", "/var/lib/laia/workspace"),
            plugins_root=os.environ.get("LAIA_EXECUTOR_PLUGINS_ROOT", "/opt/laia/plugins"),
        )


def _read_token(path: str) -> str:
    p = Path(path)
    if not p.exists():
        env_token = os.environ.get("LAIA_EXECUTOR_TOKEN", "").strip()
        if env_token:
            return env_token
        raise RuntimeError(
            f"executor token file missing: {path}. "
            "Provide one via the file (mode 0600) or LAIA_EXECUTOR_TOKEN env var."
        )
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        # An empty token would silently disable auth (compare_digest("", "") is
        # True). Fail loudly at startup so the operator notices instead of
        # discovering it via failed /exec calls later.
        raise RuntimeError(
            f"executor token file {path} is empty. "
            "create-agent.sh should have written it; "
            "regenerate the container or write a fresh token (mode 0600)."
        )
    return text


def _read_slug_from_profile(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("slug") or data.get("agent_slug")
    except Exception:
        return None
