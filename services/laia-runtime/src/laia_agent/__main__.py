from __future__ import annotations

import argparse

from .config import load_config
from .daemon import run_forever, write_status
from .profile import ensure_profile
from .tasks import process_once
from .workspace import init_workspace


def main() -> int:
    parser = argparse.ArgumentParser(prog="laia-agent")
    parser.add_argument("--once", action="store_true", help="Process pending tasks once and exit")
    parser.add_argument("--status", action="store_true", help="Write status once and exit")
    parser.add_argument("--profile-init", action="store_true", help="Initialize editable agent profile files")
    parser.add_argument("--workspace-init", action="store_true", help="Initialize the personal workspace database")
    args = parser.parse_args()

    if args.once:
        config = load_config()
        write_status(config)
        process_once(config)
        return 0
    if args.status:
        write_status(load_config())
        return 0
    if args.profile_init:
        ensure_profile(load_config())
        return 0
    if args.workspace_init:
        init_workspace(load_config())
        return 0
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
