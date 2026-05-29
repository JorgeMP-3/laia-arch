"""Atlas v2 — Universal reference registry for the LAIA ecosystem.

Single source of truth for every cross-component reference: paths, services,
containers, sockets, env files.  Reads ~/.laia/atlas.yaml by default (override
with ATLAS_CONFIG env var).

Public API
----------
    get(name)                      → str            resolved value
    get_path(name, default=None)   → Path           (path-type refs)
    resolve_service(name)          → str            "http://host:port"
    all_refs(config_path=None)     → dict[str, dict]
    health(name)                   → HealthResult
    doctor(config_path=None)       → dict[str, HealthResult]
    validate_registry(cfg=None)    → list[str]      error strings
    invalidate_cache()             → None           force re-read on next call

Exceptions
----------
    AtlasError       base
    AtlasConfigError malformed or unreadable atlas.yaml
    AtlasKeyError    reference name not found in registry
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket as _socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AtlasError(Exception):
    """Base class for Atlas errors."""


class AtlasConfigError(AtlasError):
    """atlas.yaml cannot be read or is structurally invalid."""


class AtlasKeyError(AtlasError, KeyError):
    """Named reference not found in the registry."""


# ---------------------------------------------------------------------------
# Config location
# ---------------------------------------------------------------------------

def _atlas_config_path() -> Path:
    # ATLAS_CONFIG is the explicit override (full path to atlas.yaml).
    # Default: <config home>/atlas.yaml. Layout v2 (slice C1) the config home is
    # /srv/laia/arch (anchor LAIA_CONFIG_HOME) — SEPARATE from LAIA_HOME (the
    # interactive mesa viva ~/LAIA-ARCH). Pre-v2 this was ~/.laia.
    env = os.environ.get("ATLAS_CONFIG", "").strip()
    if env:
        return Path(env)
    from laia_paths import laia_config_home
    return laia_config_home() / "atlas.yaml"


# ---------------------------------------------------------------------------
# Mtime-based in-process cache (thread-safe via GIL for CPython)
# ---------------------------------------------------------------------------

_CACHE: dict[Path, tuple[float, dict[str, Any]]] = {}  # path → (mtime, refs)


def _load_raw(config_path: Path | None = None) -> dict[str, Any]:
    """Parse atlas.yaml, returning the refs dict.  Caches by mtime.

    Raises AtlasConfigError on unreadable or structurally invalid YAML.
    Returns {} if the file doesn't exist yet (not an error — first run).
    """
    import yaml  # type: ignore[import-untyped]

    cp = config_path or _atlas_config_path()

    try:
        mtime = cp.stat().st_mtime
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise AtlasConfigError(f"Cannot stat {cp}: {exc}") from exc

    cached = _CACHE.get(cp)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        with open(cp) as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise AtlasConfigError(f"YAML parse error in {cp}: {exc}") from exc
    except OSError as exc:
        raise AtlasConfigError(f"Cannot read {cp}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise AtlasConfigError(f"{cp}: top-level must be a YAML mapping, got {type(raw).__name__}")

    refs = raw.get("refs", {})
    if not isinstance(refs, dict):
        raise AtlasConfigError(f"{cp}: 'refs' key must be a mapping")

    _CACHE[cp] = (mtime, refs)
    logger.debug("atlas: loaded %d refs from %s", len(refs), cp)
    return refs


def invalidate_cache() -> None:
    """Force re-read of atlas.yaml on the next call."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

_VALID_TYPES: frozenset[str] = frozenset(
    {"path", "service", "container", "socket", "env_file"}
)
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "path":     ("value",),
    "service":  ("host", "port"),
    "container":("value",),
    "socket":   ("value",),
    "env_file": ("path",),
}


def validate_registry(config_path: Path | None = None) -> list[str]:
    """Validate atlas.yaml structure.  Returns a list of error strings.

    An empty list means the registry is valid.
    Does NOT check whether paths exist on disk — use doctor() for that.
    """
    try:
        refs = _load_raw(config_path)
    except AtlasConfigError as exc:
        return [str(exc)]

    errors: list[str] = []
    for name, entry in refs.items():
        if not isinstance(entry, dict):
            errors.append(f"{name}: entry must be a YAML mapping, got {type(entry).__name__}")
            continue

        ref_type = entry.get("type")
        if ref_type is None:
            errors.append(f"{name}: missing required field 'type'")
            continue
        if ref_type not in _VALID_TYPES:
            errors.append(
                f"{name}: unknown type {ref_type!r} "
                f"(valid: {', '.join(sorted(_VALID_TYPES))})"
            )
            continue

        for req in _REQUIRED_FIELDS.get(ref_type, ()):
            if req not in entry:
                errors.append(f"{name} (type={ref_type}): missing required field {req!r}")

    return errors


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------

def _interpolate(
    value: str,
    refs: dict[str, Any],
    _seen: frozenset[str] = frozenset(),
) -> str:
    """Expand ${ref.<name>} placeholders and ~ in *value*.

    _seen tracks the expansion stack to detect circular references.
    It is passed explicitly so nested re.sub callbacks inherit the correct set.
    """
    # Expand only a leading ~ (expanduser semantics); a ~ mid-string is literal.
    value = os.path.expanduser(value)

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in _seen:
            raise AtlasError(f"circular reference detected: {' → '.join(_seen | {key})}")
        entry = refs.get(key)
        if entry is None:
            raise AtlasKeyError(f"interpolation refers to undefined ref {key!r}")
        if not isinstance(entry, dict):
            raise AtlasConfigError(f"ref {key!r} is not a dict (bad atlas.yaml)")
        raw_val = str(entry.get("value") or entry.get("host") or "")
        return _interpolate(raw_val, refs, _seen | {key})

    return re.sub(r"\$\{ref\.([^}]+)\}", _sub, value)


def _resolved_value(name: str, entry: dict[str, Any], refs: dict[str, Any]) -> str:
    """Compute the canonical string value for one ref entry."""
    ref_type = entry.get("type", "path")

    if ref_type == "path":
        return _interpolate(str(entry.get("value", "")), refs)

    if ref_type == "service":
        proto = entry.get("protocol", "http")
        host  = _interpolate(str(entry.get("host", "127.0.0.1")), refs)
        port  = entry.get("port", 80)
        return f"{proto}://{host}:{port}"

    if ref_type == "container":
        return str(entry.get("value", ""))

    if ref_type == "socket":
        return _interpolate(str(entry.get("value", "")), refs)

    if ref_type == "env_file":
        return _interpolate(str(entry.get("path", "")), refs)

    # Fallback
    return _interpolate(str(entry.get("value", "")), refs)


# ---------------------------------------------------------------------------
# Public API — resolution
# ---------------------------------------------------------------------------

def all_refs(config_path: Path | None = None) -> dict[str, Any]:
    """Return the raw ref entries dict from atlas.yaml (cached)."""
    return _load_raw(config_path)


def get(name: str, config_path: Path | None = None) -> str:
    """Resolve a reference by name.

    Resolution order:
    1. ATLAS_<NAME> environment variable override.
    2. atlas.yaml (cached by mtime).

    Raises AtlasKeyError if not found.
    Raises AtlasConfigError if atlas.yaml is malformed.
    """
    env_val = os.environ.get(f"ATLAS_{name.upper()}", "").strip()
    if env_val:
        return env_val

    refs = _load_raw(config_path)
    if name not in refs:
        cp = config_path or _atlas_config_path()
        raise AtlasKeyError(
            f"reference {name!r} not found in {cp}. "
            f"Available: {', '.join(sorted(refs)) or '(empty registry)'}"
        )
    return _resolved_value(name, refs[name], refs)


def get_path(
    name: str,
    default: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Resolve a path-type reference. Returns *default* if not found."""
    try:
        return Path(get(name, config_path=config_path))
    except AtlasKeyError:
        if default is not None:
            return default
        raise


def resolve_service(name: str, config_path: Path | None = None) -> str:
    """Resolve a service reference to a base URL string."""
    refs = _load_raw(config_path)
    entry = refs.get(name)
    if entry is None:
        raise AtlasKeyError(f"service {name!r} not found in registry")
    if not isinstance(entry, dict):
        raise AtlasConfigError(f"ref {name!r} is not a dict (bad atlas.yaml)")
    if entry.get("type") != "service":
        raise AtlasError(
            f"{name!r} has type {entry.get('type')!r}, not 'service'"
        )
    return _resolved_value(name, entry, refs)


# ---------------------------------------------------------------------------
# Health checking
# ---------------------------------------------------------------------------

@dataclass
class HealthResult:
    name: str
    ref_type: str
    value: str
    alive: bool
    detail: str
    latency_ms: float | None = None
    optional: bool = False
    repair_hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        mark = "OK  " if self.alive else ("WARN" if self.optional else "DEAD")
        lat  = f" ({self.latency_ms:.0f}ms)" if self.latency_ms is not None else ""
        return f"[{mark}] {self.name} ({self.ref_type}) = {self.value}{lat} — {self.detail}"


def health(name: str, config_path: Path | None = None) -> HealthResult:
    """Check whether a single reference is alive/reachable.

    Never raises — failures are encoded in HealthResult.alive=False.
    """
    try:
        refs = _load_raw(config_path)
    except AtlasConfigError as exc:
        return HealthResult(name=name, ref_type="?", value="?",
                            alive=False, detail=f"config error: {exc}")

    entry = refs.get(name)
    if entry is None:
        return HealthResult(name=name, ref_type="?", value="?",
                            alive=False,
                            detail=f"reference not found in {config_path or _atlas_config_path()}")

    if not isinstance(entry, dict):
        return HealthResult(name=name, ref_type="?", value=str(entry),
                            alive=False, detail="registry entry is not a dict (bad atlas.yaml)")

    ref_type = entry.get("type", "path")
    try:
        value = _resolved_value(name, entry, refs)
    except AtlasError as exc:
        return HealthResult(name=name, ref_type=ref_type, value="<interpolation error>",
                            alive=False, detail=str(exc))

    dispatch = {
        "path":     _health_path,
        "service":  _health_service,
        "container":_health_container,
        "socket":   _health_socket,
        "env_file": _health_env_file,
    }
    fn = dispatch.get(ref_type)
    if fn is None:
        return HealthResult(name=name, ref_type=ref_type, value=value,
                            alive=True, detail="no health check defined for this type")
    result = fn(name, entry, value)
    result.optional = bool(entry.get("optional", False))
    hint = entry.get("repair_hint")
    result.repair_hint = str(hint) if hint else None
    return result


def doctor(config_path: Path | None = None) -> dict[str, HealthResult]:
    """Health-check every reference in the registry in definition order."""
    try:
        refs = _load_raw(config_path)
    except AtlasConfigError as exc:
        return {"__config__": HealthResult(
            name="__config__", ref_type="?", value="?",
            alive=False, detail=str(exc),
        )}

    results: dict[str, HealthResult] = {}
    for name in refs:
        results[name] = health(name, config_path)
    return results


# ---------------------------------------------------------------------------
# Health check implementations (each returns a HealthResult, never raises)
# ---------------------------------------------------------------------------

def _health_path(name: str, _entry: dict, value: str) -> HealthResult:
    p = Path(value)
    if p.exists():
        return HealthResult(name=name, ref_type="path", value=value,
                            alive=True, detail="exists")
    return HealthResult(name=name, ref_type="path", value=value,
                        alive=False, detail="path does not exist on disk")


def _health_service(name: str, entry: dict, url: str) -> HealthResult:
    import urllib.request
    import urllib.error

    host = str(entry.get("host", "127.0.0.1"))
    port = int(entry.get("port", 80))
    health_path = entry.get("health_path")
    t0 = time.monotonic()

    # Try HTTP health endpoint if declared
    if health_path:
        target = f"{url.rstrip('/')}{health_path}"
        try:
            with urllib.request.urlopen(target, timeout=3) as resp:
                lat = (time.monotonic() - t0) * 1000
                alive = resp.status < 500
                return HealthResult(name=name, ref_type="service", value=url,
                                    alive=alive, detail=f"HTTP {resp.status}",
                                    latency_ms=lat)
        except urllib.error.HTTPError as exc:
            lat = (time.monotonic() - t0) * 1000
            return HealthResult(name=name, ref_type="service", value=url,
                                alive=exc.code < 500, detail=f"HTTP {exc.code}",
                                latency_ms=lat)
        except urllib.error.URLError as exc:
            lat = (time.monotonic() - t0) * 1000
            reason = str(exc.reason)
            detail = (
                "connection refused" if "refused" in reason.lower()
                else "name resolution failed" if "name resolution" in reason.lower() or "errno -3" in reason.lower()
                else f"unreachable: {reason}"
            )
            return HealthResult(name=name, ref_type="service", value=url,
                                alive=False, detail=detail, latency_ms=lat)
        except OSError as exc:
            lat = (time.monotonic() - t0) * 1000
            return HealthResult(name=name, ref_type="service", value=url,
                                alive=False, detail=str(exc), latency_ms=lat)

    # Fallback: TCP connect
    try:
        with _socket.create_connection((host, port), timeout=3):
            lat = (time.monotonic() - t0) * 1000
            return HealthResult(name=name, ref_type="service", value=url,
                                alive=True, detail="TCP connect OK", latency_ms=lat)
    except ConnectionRefusedError:
        lat = (time.monotonic() - t0) * 1000
        return HealthResult(name=name, ref_type="service", value=url,
                            alive=False, detail="connection refused", latency_ms=lat)
    except _socket.gaierror as exc:
        lat = (time.monotonic() - t0) * 1000
        return HealthResult(name=name, ref_type="service", value=url,
                            alive=False, detail=f"DNS/name error: {exc}", latency_ms=lat)
    except OSError as exc:
        lat = (time.monotonic() - t0) * 1000
        return HealthResult(name=name, ref_type="service", value=url,
                            alive=False, detail=str(exc), latency_ms=lat)


def _health_container(name: str, _entry: dict, container_name: str) -> HealthResult:
    try:
        result = subprocess.run(
            ["lxc", "info", container_name],
            capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        return HealthResult(name=name, ref_type="container", value=container_name,
                            alive=False, detail="lxc not found — LXD not installed")
    except subprocess.TimeoutExpired:
        return HealthResult(name=name, ref_type="container", value=container_name,
                            alive=False, detail="lxc info timed out (>5s)")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        detail = stderr if stderr else f"lxc info exit {result.returncode}"
        return HealthResult(name=name, ref_type="container", value=container_name,
                            alive=False, detail=detail)

    for line in result.stdout.splitlines():
        if line.strip().startswith("Status:"):
            status = line.split(":", 1)[1].strip()
            alive = status.lower() == "running"
            return HealthResult(name=name, ref_type="container", value=container_name,
                                alive=alive, detail=f"Status: {status}")

    return HealthResult(name=name, ref_type="container", value=container_name,
                        alive=True, detail="container found (no Status line)")


def _health_socket(name: str, _entry: dict, socket_path: str) -> HealthResult:
    p = Path(socket_path)
    if not p.exists():
        return HealthResult(name=name, ref_type="socket", value=socket_path,
                            alive=False, detail="socket file does not exist")
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(socket_path)
        s.close()
        return HealthResult(name=name, ref_type="socket", value=socket_path,
                            alive=True, detail="socket connectable")
    except OSError as exc:
        return HealthResult(name=name, ref_type="socket", value=socket_path,
                            alive=False, detail=str(exc))


def _health_env_file(name: str, entry: dict, file_path: str) -> HealthResult:
    p = Path(file_path)
    if not p.exists():
        return HealthResult(name=name, ref_type="env_file", value=file_path,
                            alive=False, detail="file does not exist")

    keys: list[str] = entry.get("keys") or []
    if not keys:
        return HealthResult(name=name, ref_type="env_file", value=file_path,
                            alive=True, detail="file exists (no keys to verify)")

    try:
        content = p.read_text(errors="replace")
    except OSError as exc:
        return HealthResult(name=name, ref_type="env_file", value=file_path,
                            alive=False, detail=f"cannot read: {exc}")

    defined: set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            defined.add(line.split("=", 1)[0].strip())

    missing = [k for k in keys if k not in defined]
    if missing:
        return HealthResult(name=name, ref_type="env_file", value=file_path,
                            alive=False,
                            detail=f"missing key(s): {', '.join(missing)}")
    return HealthResult(name=name, ref_type="env_file", value=file_path,
                        alive=True, detail=f"{len(keys)} key(s) present")


# ---------------------------------------------------------------------------
# Backward-compat bridge: keep laia_paths.py API importable from here too
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict[str, Any]:
    """laia_paths compat: load raw YAML config dict."""
    import yaml  # type: ignore[import-untyped]
    try:
        with open(config_path) as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as exc:
        raise AtlasConfigError(f"YAML error in {config_path}: {exc}") from exc
