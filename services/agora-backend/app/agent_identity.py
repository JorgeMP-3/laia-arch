"""Helpers for AGORA user-agent identity and container naming."""

from __future__ import annotations

import re


CANONICAL_CONTAINER_PREFIX = "agent-"
LEGACY_CONTAINER_PREFIX = "laia-"
PROTECTED_LAIA_CONTAINERS = {"laia-agora", "laia-jorge"}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}$")
CONTAINER_RE = re.compile(r"^(agent|laia)-[a-z0-9][a-z0-9_-]{1,40}$")


def validate_slug(slug: str) -> str:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"invalid agent slug: {slug!r}")
    return slug


def canonical_container_name(slug: str) -> str:
    return f"{CANONICAL_CONTAINER_PREFIX}{validate_slug(slug)}"


def legacy_container_name(slug: str) -> str:
    return f"{LEGACY_CONTAINER_PREFIX}{validate_slug(slug)}"


def candidate_container_names(slug: str) -> list[str]:
    return [canonical_container_name(slug), legacy_container_name(slug)]


def is_user_agent_container(name: str) -> bool:
    if name in PROTECTED_LAIA_CONTAINERS:
        return False
    return bool(CONTAINER_RE.fullmatch(name))


def slug_from_container(name: str) -> str:
    if name.startswith(CANONICAL_CONTAINER_PREFIX):
        return name.removeprefix(CANONICAL_CONTAINER_PREFIX)
    if name.startswith(LEGACY_CONTAINER_PREFIX):
        return name.removeprefix(LEGACY_CONTAINER_PREFIX)
    return name


def normalize_container_name(name_or_slug: str) -> str:
    if name_or_slug.startswith(CANONICAL_CONTAINER_PREFIX) or name_or_slug.startswith(LEGACY_CONTAINER_PREFIX):
        if not CONTAINER_RE.fullmatch(name_or_slug):
            raise ValueError(f"invalid container name: {name_or_slug!r}")
        return name_or_slug
    return canonical_container_name(name_or_slug)
