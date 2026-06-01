from __future__ import annotations

import json
from pathlib import Path
from typing import Any


OAUTH_PROVIDERS = {
    "openai-codex",
    "qwen-oauth",
    "google-gemini-cli",
    "copilot-acp",
    "nous",
    "minimax-oauth",
}


def auth_json_snapshot(path: str | Path | None, status: str, default_provider: str) -> dict[str, Any]:
    """Return a non-secret readiness snapshot for AGORA's shared auth store.

    The health check must prove that the mounted ``auth.json`` has usable
    content, not merely that a mountpoint or empty file exists.
    """
    auth_path = Path(path) if path else None
    display_path = str(auth_path) if auth_path else None
    if auth_path is None or not auth_path.is_file():
        return {
            "ready": False,
            "status": "missing" if status in {"unknown", "linked"} else status,
            "path": display_path,
            "present": False,
            "reason": "not_found",
        }

    try:
        if auth_path.stat().st_size == 0:
            return _invalid_auth(display_path, "empty")
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _invalid_auth(display_path, "invalid_json")
    except OSError:
        return _invalid_auth(display_path, "unreadable")

    if not isinstance(data, dict):
        return _invalid_auth(display_path, "invalid_shape")

    providers = data.get("providers")
    credential_pool = data.get("credential_pool")
    provider_ready = _provider_has_credentials(providers, default_provider)
    pool_ready = _credential_pool_has_credentials(credential_pool, default_provider)
    any_ready = _any_provider_has_credentials(providers) or _any_pool_has_credentials(credential_pool)

    if default_provider in OAUTH_PROVIDERS and not (provider_ready or pool_ready):
        return _invalid_auth(display_path, f"missing_{default_provider}_credentials")
    if default_provider not in OAUTH_PROVIDERS and not any_ready:
        return _invalid_auth(display_path, "no_credentials")

    return {
        "ready": True,
        "status": "linked",
        "path": display_path,
        "present": True,
        "reason": "ok",
    }


def _invalid_auth(path: str | None, reason: str) -> dict[str, Any]:
    """Build a standard failed auth snapshot without leaking secret material."""
    return {
        "ready": False,
        "status": "invalid",
        "path": path,
        "present": True,
        "reason": reason,
    }


def _provider_has_credentials(providers: Any, provider: str) -> bool:
    if not isinstance(providers, dict):
        return False
    state = providers.get(provider)
    if not isinstance(state, dict):
        return False
    return _state_has_secret(state)


def _any_provider_has_credentials(providers: Any) -> bool:
    if not isinstance(providers, dict):
        return False
    return any(isinstance(state, dict) and _state_has_secret(state) for state in providers.values())


def _credential_pool_has_credentials(pool: Any, provider: str) -> bool:
    if not isinstance(pool, dict):
        return False
    return _pool_entries_have_secret(pool.get(provider))


def _any_pool_has_credentials(pool: Any) -> bool:
    if not isinstance(pool, dict):
        return False
    return any(_pool_entries_have_secret(entries) for entries in pool.values())


def _pool_entries_have_secret(entries: Any) -> bool:
    if isinstance(entries, dict):
        return _state_has_secret(entries)
    if not isinstance(entries, list):
        return False
    return any(isinstance(entry, dict) and _state_has_secret(entry) for entry in entries)


def _state_has_secret(state: dict[str, Any]) -> bool:
    tokens = state.get("tokens")
    if isinstance(tokens, dict) and _has_text(tokens.get("access_token")) and _has_text(tokens.get("refresh_token")):
        return True
    return any(
        _has_text(state.get(key))
        for key in (
            "api_key",
            "access_token",
            "refresh_token",
            "runtime_api_key",
            "agent_key",
        )
    )


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
