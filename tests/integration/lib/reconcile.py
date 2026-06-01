#!/usr/bin/env python3
"""Cross-consistency reconciler for LAIA (Track T · T4).

The ecosystem keeps the same fact in three places: the central ``agora.db``
(``users``/``agents`` rows), the on-disk user zone (``/srv/laia/users/<slug>``)
and the LXD containers (``agent-<slug>`` / legacy ``laia-<slug>``). When a
provision or deprovision is interrupted, these drift apart and leave orphans.
This module reconciles all three in **both** directions and reports every
mismatch, so a half-finished provision cannot masquerade as a healthy system.

It is intentionally dependency-free (standard library only) and side-effect
free (read-only). The container inventory can be injected from a file, which
lets the unit test exercise the logic without LXD; in the live integration
test it is read from ``lxc list``.

Exit codes: ``0`` consistent, ``1`` orphans found, ``2`` usage error.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Container names that are part of the platform, not per-user executors. They
# must never be treated as agent containers (mirrors
# ``infra/orchestrator/lxd.py::list_agent_containers``).
RESERVED_CONTAINERS = {"laia-agora", "laia-jorge"}

# Agent statuses that imply a container and a user-zone directory must exist.
# ``planned`` is pre-provision; ``provisioning``/``error`` are transient and
# only reported as informational, never as hard orphans.
PROVISIONED_STATUSES = {"running", "stopped"}

CONTAINER_PREFIXES = ("agent-", "laia-")


def slug_from_container(name: str) -> str | None:
    """Return the employee slug encoded in a container name, or ``None``.

    ``agent-maria`` and the legacy ``laia-maria`` both map to ``maria``.
    Reserved platform containers map to ``None``.
    """
    if name in RESERVED_CONTAINERS:
        return None
    for prefix in CONTAINER_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return None


@dataclass
class Reconciliation:
    """The full set of cross-layer discrepancies found in one pass."""

    db_provisioned_without_container: list[str] = field(default_factory=list)
    db_provisioned_without_fs: list[str] = field(default_factory=list)
    container_without_db_agent: list[str] = field(default_factory=list)
    fs_dir_without_db: list[str] = field(default_factory=list)
    transient_agents: list[str] = field(default_factory=list)

    def orphan_count(self) -> int:
        """Return the number of hard orphans (transient agents excluded)."""
        return (
            len(self.db_provisioned_without_container)
            + len(self.db_provisioned_without_fs)
            + len(self.container_without_db_agent)
            + len(self.fs_dir_without_db)
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable view of the reconciliation."""
        return {
            "orphan_count": self.orphan_count(),
            "db_provisioned_without_container": self.db_provisioned_without_container,
            "db_provisioned_without_fs": self.db_provisioned_without_fs,
            "container_without_db_agent": self.container_without_db_agent,
            "fs_dir_without_db": self.fs_dir_without_db,
            "transient_agents": self.transient_agents,
        }


def read_db_agents(db_path: Path) -> list[dict[str, str]]:
    """Read agent rows joined with their user, read-only.

    Each record carries the derived ``slug`` (from ``container_name``), the
    agent ``status`` and whether the owning user is ``active``.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT a.container_name AS container_name,
                   a.status         AS status,
                   a.workspace_path AS workspace_path,
                   u.active         AS user_active,
                   u.username       AS username
            FROM agents a
            LEFT JOIN users u ON u.id = a.user_id
            """
        ).fetchall()
    finally:
        conn.close()
    agents: list[dict[str, str]] = []
    for r in rows:
        agents.append(
            {
                "container_name": r["container_name"] or "",
                "slug": slug_from_container(r["container_name"] or "") or "",
                "status": r["status"] or "",
                "workspace_path": r["workspace_path"] or "",
                "user_active": str(r["user_active"]),
            }
        )
    return agents


def list_containers_via_lxc() -> list[str]:
    """Return agent container names from ``lxc list`` (reserved ones excluded)."""
    proc = subprocess.run(
        ["lxc", "list", "--format", "csv", "-c", "n"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    names: list[str] = []
    for row in csv.reader(io.StringIO(proc.stdout)):
        if not row:
            continue
        name = row[0].strip()
        if name in RESERVED_CONTAINERS:
            continue
        if name.startswith(CONTAINER_PREFIXES):
            names.append(name)
    return names


def read_containers_from_file(path: Path) -> list[str]:
    """Read a container inventory from a file (one name per line).

    Used by the unit test to inject a synthetic inventory. Blank lines and
    ``#`` comments are ignored; reserved containers are dropped.
    """
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if name in RESERVED_CONTAINERS:
            continue
        if name.startswith(CONTAINER_PREFIXES):
            names.append(name)
    return names


def list_fs_slugs(users_dir: Path) -> list[str]:
    """Return the per-user directory names under the user zone."""
    if not users_dir.is_dir():
        return []
    return sorted(p.name for p in users_dir.iterdir() if p.is_dir())


def reconcile(
    agents: list[dict[str, str]],
    container_names: list[str],
    fs_slugs: list[str],
) -> Reconciliation:
    """Cross-check DB agents, containers and FS directories in both directions."""
    result = Reconciliation()

    container_slugs = {slug_from_container(n) for n in container_names}
    container_slugs.discard(None)
    fs_slug_set = set(fs_slugs)

    db_slugs: set[str] = set()
    for agent in agents:
        slug = agent["slug"]
        if not slug:
            continue
        db_slugs.add(slug)
        if agent["status"] in PROVISIONED_STATUSES:
            if slug not in container_slugs:
                result.db_provisioned_without_container.append(slug)
            if slug not in fs_slug_set:
                result.db_provisioned_without_fs.append(slug)
        elif agent["status"] not in ("planned", ""):
            result.transient_agents.append(f"{slug}:{agent['status']}")

    for name in container_names:
        slug = slug_from_container(name)
        if slug and slug not in db_slugs:
            result.container_without_db_agent.append(name)

    for slug in fs_slugs:
        if slug not in db_slugs:
            result.fs_dir_without_db.append(slug)

    for bucket in (
        result.db_provisioned_without_container,
        result.db_provisioned_without_fs,
        result.container_without_db_agent,
        result.fs_dir_without_db,
        result.transient_agents,
    ):
        bucket.sort()
    return result


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Reconcile LAIA DB/FS/containers")
    parser.add_argument("--db", required=True, help="path to agora.db (read-only)")
    parser.add_argument("--users-dir", required=True, help="path to the user zone (/srv/laia/users)")
    parser.add_argument(
        "--containers-file",
        help="read the container inventory from this file instead of lxc",
    )
    parser.add_argument("--json", help="write a JSON report to this path, or '-' for stdout")
    return parser


def main(argv: list[str]) -> int:
    """Entry point: load the three views, reconcile and report."""
    args = build_parser().parse_args(argv)
    db_path = Path(args.db)
    users_dir = Path(args.users_dir)
    if not db_path.exists():
        print(f"agora.db not found: {db_path}", file=sys.stderr)
        return 2

    agents = read_db_agents(db_path)
    if args.containers_file:
        containers = read_containers_from_file(Path(args.containers_file))
    else:
        containers = list_containers_via_lxc()
    fs_slugs = list_fs_slugs(users_dir)

    result = reconcile(agents, containers, fs_slugs)

    if args.json:
        text = json.dumps(result.as_dict(), ensure_ascii=False, indent=2)
        if args.json == "-":
            print(text)
        else:
            Path(args.json).write_text(text + "\n", encoding="utf-8")

    if result.orphan_count():
        print(f"T4: {result.orphan_count()} cross-consistency orphan(s):", file=sys.stderr)
        for slug in result.db_provisioned_without_container:
            print(f"  db agent '{slug}' is provisioned but has no container", file=sys.stderr)
        for slug in result.db_provisioned_without_fs:
            print(f"  db agent '{slug}' is provisioned but has no user-zone dir", file=sys.stderr)
        for name in result.container_without_db_agent:
            print(f"  container '{name}' has no matching db agent", file=sys.stderr)
        for slug in result.fs_dir_without_db:
            print(f"  user-zone dir '{slug}' has no matching db agent", file=sys.stderr)
        return 1

    if result.transient_agents:
        print(
            f"T4: consistent ({len(result.transient_agents)} transient agent(s) "
            f"not asserted: {', '.join(result.transient_agents)})",
            file=sys.stderr,
        )
    else:
        print("T4: DB/FS/containers consistent (no orphans).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
