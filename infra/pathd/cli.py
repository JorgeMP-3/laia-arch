"""Entrypoint for laia-pathd (the daemon) and laia-path (the client CLI)."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Make .laia-core importable
_CORE = Path(__file__).resolve().parents[2] / ".laia-core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

try:
    from laia_paths import load_config, regenerate_env_file, resolve, render_env_file  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        f"laia-path: cannot import laia_paths from {_CORE}. "
        f"Ensure .laia-core/ exists and is readable. Original error: {exc}"
    ) from exc

from .ipc import IpcClient
from .restarts import (
    PendingRestartStore,
    PendingRestart,
    apply_restart,
)
from .server import PathDaemon
from .state import StateStore
from .validate import format_report, validate_paths


def _laia_home() -> Path:
    val = os.environ.get("LAIA_HOME", "").strip()
    return Path(val) if val else Path.home() / ".laia"


def _defaults() -> dict[str, Path]:
    home = _laia_home()
    return {
        "config": home / "config.yaml",
        "env_file": home / ".env.paths",
        "socket": home / "pathd.sock",
        "state": home / "state" / "path-cache.json",
        "farm": home / "atlas",
        "pending": home / "state" / "pending-restarts.json",
    }


# ----------------------------------------------------------------------------
# Daemon entrypoint  (laia-pathd)
# ----------------------------------------------------------------------------

def daemon_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="laia-pathd")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--socket", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--farm", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    d = _defaults()
    daemon = PathDaemon(
        config_path=args.config or d["config"],
        env_file=args.env_file or d["env_file"],
        socket_path=args.socket or d["socket"],
        state_path=args.state or d["state"],
        farm_dir=args.farm or d["farm"],
        poll_interval=args.poll_interval,
    )
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass
    return 0


# ----------------------------------------------------------------------------
# Client CLI  (laia-path)
# ----------------------------------------------------------------------------

def _client(socket_path: Path) -> IpcClient:
    return IpcClient(socket_path)


def _via_daemon_or_local(socket_path: Path, config_path: Path):
    """Return a callable resolving the current path map.

    Tries the daemon first; falls back to direct config resolution.
    """
    client = _client(socket_path)

    def _all() -> dict[str, str]:
        if client.available():
            try:
                return dict(client.call("resolve_all"))
            except Exception:
                pass
        return resolve(load_config(config_path))

    return _all


def client_resolve(args: argparse.Namespace) -> int:
    paths = _via_daemon_or_local(args.socket, args.config)()
    if args.key not in paths:
        print(f"error: unknown alias {args.key!r}", file=sys.stderr)
        return 1
    print(paths[args.key])
    return 0


def client_list(args: argparse.Namespace) -> int:
    paths = _via_daemon_or_local(args.socket, args.config)()
    if args.json:
        print(json.dumps(paths, indent=2))
    else:
        for k, v in paths.items():
            print(f"{k}\t{v}")
    return 0


def client_env(args: argparse.Namespace) -> int:
    paths = _via_daemon_or_local(args.socket, args.config)()
    sys.stdout.write(render_env_file(paths, source_path=args.config))
    return 0


def client_status(args: argparse.Namespace) -> int:
    client = _client(args.socket)
    if not client.available():
        print("daemon: not running (socket missing)")
        return 1
    info = client.call("status")
    for k, v in info.items():
        print(f"{k}: {v}")
    return 0


def client_doctor(args: argparse.Namespace) -> int:
    client = _client(args.socket)
    if client.available():
        report = client.call("doctor")
    else:
        paths = resolve(load_config(args.config))
        report = {
            "paths": {
                k: {"path": v, "exists": Path(v).exists()}
                for k, v in paths.items()
            },
            "ok": all(Path(v).exists() for v in paths.values()),
        }
    bad = []
    for alias, info in report["paths"].items():
        flag = "OK" if info["exists"] else "MISSING"
        print(f"  [{flag}]  {alias:14s} {info['path']}")
        if not info["exists"]:
            bad.append(alias)
    if bad:
        print(f"\n{len(bad)} path(s) missing:", ", ".join(bad))
        return 1
    print("\nAll paths OK.")
    return 0


def client_pending_restarts(args: argparse.Namespace) -> int:
    d = _defaults()
    client = _client(args.socket)
    if client.available():
        entries = client.call("pending_restarts")
    else:
        store = PendingRestartStore(d["pending"])
        from dataclasses import asdict
        entries = [asdict(e) for e in store.load()]
    if not entries:
        print("No pending restarts.")
        return 0
    print(f"{len(entries)} pending restart(s):")
    for e in entries:
        print(f"\n  unit:     {e['unit']}")
        print(f"  alias:    {e['alias']}")
        print(f"  changed:  {e['old_path']}")
        print(f"        ->  {e['new_path']}")
        print(f"  detected: {e['detected_at']:.0f}  reason: {e['reason']}")
    print()
    print("Apply with: laia-path apply-restarts")
    return 0


def client_apply_restarts(args: argparse.Namespace) -> int:
    d = _defaults()
    client = _client(args.socket)
    if client.available():
        entries_raw = client.call("pending_restarts")
        entries = [PendingRestart(**e) for e in entries_raw]
    else:
        store = PendingRestartStore(d["pending"])
        entries = store.load()
    if not entries:
        print("No pending restarts.")
        return 0

    print(f"About to restart {len(entries)} unit(s):")
    for e in entries:
        print(f"  - {e.unit}  (alias {e.alias} moved {e.old_path} -> {e.new_path})")

    if not args.yes:
        try:
            reply = input("\nProceed? [y/N] ").strip().lower()
        except EOFError:
            reply = "n"
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 1

    failures = 0
    seen: set[str] = set()
    for e in entries:
        if e.unit in seen:
            continue
        seen.add(e.unit)
        ok, msg = apply_restart(e.unit, user=args.user)
        marker = "✓" if ok else "✗"
        print(f"  [{marker}] {e.unit}: {msg}")
        if not ok:
            failures += 1

    if failures == 0:
        # Clear pending only if everything succeeded
        if client.available():
            client.call("clear_pending")
        else:
            PendingRestartStore(d["pending"]).clear()
        print("\nAll restarts succeeded. Cleared pending list.")
        return 0
    print(f"\n{failures} restart(s) failed. Pending list kept.")
    return 1


def _format_history(transitions: list[dict], *, as_json: bool, alias: str) -> str:
    if as_json:
        return json.dumps(transitions, indent=2) + "\n"
    if not transitions:
        return f"no transitions recorded for {alias!r}\n"
    from datetime import datetime
    lines = []
    for t in transitions:
        ts = datetime.fromtimestamp(t.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"  {ts} · {t.get('from')!r} → {t.get('to')!r} · reason={t.get('reason','?')}")
    return "\n".join(lines) + "\n"


def client_history(args: argparse.Namespace) -> int:
    client = _client(args.socket)
    transitions: list[dict] | None = None
    if client.available():
        try:
            transitions = client.call("history", alias=args.alias)
        except Exception as e:
            # Daemon may be running an older binary that doesn't know "history".
            # Fall through to direct state-file read instead of failing.
            if "Method not found" not in str(e) and "history" not in str(e):
                print(f"daemon error: {e}", file=sys.stderr)
                return 1
    if transitions is None:
        d = _defaults()
        store = StateStore(d["state"])
        state = store.load()
        entry = state.paths.get(args.alias)
        if entry is None:
            print(f"error: unknown alias {args.alias!r}", file=sys.stderr)
            return 1
        transitions = list(entry.history)

    if args.last is not None and args.last > 0:
        transitions = transitions[-args.last:]
    sys.stdout.write(_format_history(transitions, as_json=args.json, alias=args.alias))
    return 0


def client_validate(args: argparse.Namespace) -> int:
    paths = _via_daemon_or_local(args.socket, args.config)()
    report = validate_paths(paths, check_existence=not args.no_existence_check)
    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    sys.stdout.write(format_report(report, use_color=use_color))
    return report.exit_code()


def client_reload(args: argparse.Namespace) -> int:
    client = _client(args.socket)
    if client.available():
        result = client.call("reload")
        print(f"reload: changed={result.get('changed', False)}")
        return 0
    # No daemon: just regen the env file from config
    out = regenerate_env_file()
    print(f"daemon not running; regenerated {out}")
    return 0


def client_main(argv: list[str] | None = None) -> int:
    d = _defaults()
    parser = argparse.ArgumentParser(prog="laia-path")
    parser.add_argument("--socket", type=Path, default=d["socket"])
    parser.add_argument("--config", type=Path, default=d["config"])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("resolve", help="Resolve a single alias")
    p.add_argument("key")
    p.set_defaults(func=client_resolve)

    p = sub.add_parser("list", help="List all resolved paths")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=client_list)

    p = sub.add_parser("env", help="Print bash-source export lines")
    p.set_defaults(func=client_env)

    p = sub.add_parser("status", help="Daemon status")
    p.set_defaults(func=client_status)

    p = sub.add_parser("doctor", help="Validate all paths")
    p.set_defaults(func=client_doctor)

    p = sub.add_parser("reload", help="Force re-read of config.yaml")
    p.set_defaults(func=client_reload)

    p = sub.add_parser("validate", help="Detect conflicts, missing paths, reserved names")
    p.add_argument("--no-existence-check", action="store_true",
                   help="Skip checking that each path exists on disk")
    p.set_defaults(func=client_validate)

    p = sub.add_parser("history", help="Show past transitions for an alias")
    p.add_argument("alias")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human format")
    p.add_argument("--last", type=int, default=None, help="Limit to last N transitions")
    p.set_defaults(func=client_history)

    p = sub.add_parser("pending-restarts", help="Show queued service restarts")
    p.set_defaults(func=client_pending_restarts)

    p = sub.add_parser("apply-restarts", help="Apply queued restarts (with confirmation)")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p.add_argument("--user", action="store_true", help="Use systemctl --user")
    p.set_defaults(func=client_apply_restarts)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(client_main())
