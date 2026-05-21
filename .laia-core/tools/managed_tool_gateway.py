"""Legacy managed-tool gateway helpers.

LAIA Ecosystem disables the former Nous-hosted passthroughs at runtime.
The public functions are kept so existing tool modules can import them
without triggering network/auth side effects.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TOOL_GATEWAY_DOMAIN = "laia-ecosystem.local"
_DEFAULT_TOOL_GATEWAY_SCHEME = "https"


@dataclass(frozen=True)
class ManagedToolGatewayConfig:
    vendor: str
    gateway_origin: str
    nous_user_token: str
    managed_mode: bool


def auth_json_path():
    """Return the LAIA auth store path, respecting LAIA_HOME overrides."""
    from laia_constants import get_laia_home

    return get_laia_home() / "auth.json"


def _read_nous_provider_state() -> Optional[dict]:
    return None


def _parse_timestamp(value: object) -> Optional[datetime]:
    return None


def _access_token_is_expiring(expires_at: object, skew_seconds: int) -> bool:
    return True


def read_nous_access_token() -> Optional[str]:
    """Legacy token reader retained for API compatibility."""
    return None


def get_tool_gateway_scheme() -> str:
    """Return configured shared gateway URL scheme."""
    scheme = os.getenv("TOOL_GATEWAY_SCHEME", "").strip().lower()
    if not scheme:
        return _DEFAULT_TOOL_GATEWAY_SCHEME

    if scheme in {"http", "https"}:
        return scheme

    raise ValueError("TOOL_GATEWAY_SCHEME must be 'http' or 'https'")


def build_vendor_gateway_url(vendor: str) -> str:
    """Return the gateway origin for a specific vendor."""
    vendor_key = f"{vendor.upper().replace('-', '_')}_GATEWAY_URL"
    explicit_vendor_url = os.getenv(vendor_key, "").strip().rstrip("/")
    if explicit_vendor_url:
        return explicit_vendor_url

    shared_scheme = get_tool_gateway_scheme()
    shared_domain = os.getenv("TOOL_GATEWAY_DOMAIN", "").strip().strip("/")
    if shared_domain:
        return f"{shared_scheme}://{vendor}-gateway.{shared_domain}"

    return f"{shared_scheme}://{vendor}-gateway.{_DEFAULT_TOOL_GATEWAY_DOMAIN}"


def resolve_managed_tool_gateway(
    vendor: str,
    gateway_builder: Optional[Callable[[str], str]] = None,
    token_reader: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[ManagedToolGatewayConfig]:
    """Managed gateways are disabled in LAIA Ecosystem runtime."""
    return None


def is_managed_tool_gateway_ready(
    vendor: str,
    gateway_builder: Optional[Callable[[str], str]] = None,
    token_reader: Optional[Callable[[], Optional[str]]] = None,
) -> bool:
    """Return True when gateway URL and Nous access token are available."""
    return resolve_managed_tool_gateway(
        vendor,
        gateway_builder=gateway_builder,
        token_reader=token_reader,
    ) is not None
