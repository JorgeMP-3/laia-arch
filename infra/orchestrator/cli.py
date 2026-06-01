from __future__ import annotations

import argparse
import json
import sys

from . import config, lxd, state
from .shell import CommandError, print_result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = config.discover_paths()

    try:
        return args.func(args, paths)
    except CommandError as exc:
        print_result(exc.result)
        return exc.result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="laiactl",
        description="LAIA infrastructure orchestrator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check host requirements").set_defaults(func=cmd_doctor)
    sub.add_parser("setup-lxd", help="Create LXD defaults and apply LAIA profile").set_defaults(func=cmd_setup_lxd)

    build = sub.add_parser("build-agent-image", help="Build or verify the laia-agent image")
    build.add_argument("--force", action="store_true", help="Rebuild image if alias exists")
    build.set_defaults(func=cmd_build_agent_image)

    create = sub.add_parser("create-agent", help="Create a personal LXD agent")
    create.add_argument("slug", help="Employee slug, e.g. jorge")
    create.add_argument("--image", default=config.DEFAULT_IMAGE_ALIAS)
    create.add_argument("--snapshot", default="initial")
    create.set_defaults(func=cmd_create_agent)

    install_runtime = sub.add_parser("install-agent-runtime", help="Install runtime inside one agent container")
    install_runtime.add_argument("slug")
    install_runtime.set_defaults(func=cmd_install_agent_runtime)

    init_workspace = sub.add_parser("init-agent-workspace", help="Initialize one agent personal workspace")
    init_workspace.add_argument("slug")
    init_workspace.set_defaults(func=cmd_init_agent_workspace)

    init_profile = sub.add_parser("init-agent-profile", help="Initialize editable profile files for one agent")
    init_profile.add_argument("slug")
    init_profile.set_defaults(func=cmd_init_agent_profile)

    show_profile = sub.add_parser("agent-profile", help="Show editable profile for one agent")
    show_profile.add_argument("slug")
    show_profile.set_defaults(func=cmd_agent_profile)

    set_persona = sub.add_parser("set-agent-persona", help="Replace persona.md from a local file")
    set_persona.add_argument("slug")
    set_persona.add_argument("file")
    set_persona.set_defaults(func=cmd_set_agent_persona)

    set_instructions = sub.add_parser("set-agent-instructions", help="Replace instructions.md from a local file")
    set_instructions.add_argument("slug")
    set_instructions.add_argument("file")
    set_instructions.set_defaults(func=cmd_set_agent_instructions)

    enable_skill = sub.add_parser("enable-agent-skill", help="Enable one skill in the agent profile")
    enable_skill.add_argument("slug")
    enable_skill.add_argument("skill_id")
    enable_skill.set_defaults(func=cmd_enable_agent_skill)

    disable_skill = sub.add_parser("disable-agent-skill", help="Disable one skill in the agent profile")
    disable_skill.add_argument("slug")
    disable_skill.add_argument("skill_id")
    disable_skill.set_defaults(func=cmd_disable_agent_skill)

    verify_agent = sub.add_parser("verify-agent", help="Verify one personal agent")
    verify_agent.add_argument("slug")
    verify_agent.set_defaults(func=cmd_verify_agent)

    snapshot = sub.add_parser("snapshot-agent", help="Create an LXD snapshot for one agent")
    snapshot.add_argument("slug")
    snapshot.add_argument("snapshot")
    snapshot.set_defaults(func=cmd_snapshot_agent)

    restore = sub.add_parser("restore-agent", help="Restore an LXD snapshot for one agent")
    restore.add_argument("slug")
    restore.add_argument("snapshot")
    restore.add_argument("--yes", action="store_true", help="Required confirmation")
    restore.set_defaults(func=cmd_restore_agent)

    delete = sub.add_parser("delete-agent", help="Delete one agent container")
    delete.add_argument("slug")
    delete.add_argument("--yes", action="store_true", help="Required confirmation")
    delete.add_argument("--force", action="store_true", help="Force delete running container")
    delete.set_defaults(func=cmd_delete_agent)

    sub.add_parser("list-agents", help="List real LAIA LXD agent containers").set_defaults(func=cmd_list_agents)
    sub.add_parser("fleet-status", help="Show fleet-wide status with runtime health").set_defaults(func=cmd_fleet_status)

    provision = sub.add_parser("provision-agent", help="Provision one agent end-to-end: create + runtime + workspace + profile + verify")
    provision.add_argument("slug", help="Employee slug")
    provision.add_argument("--image", default=config.DEFAULT_IMAGE_ALIAS)
    provision.set_defaults(func=cmd_provision_agent)

    for cmd_name, action_fn in (
        ("restart-agents", lxd.restart_all_agents),
    ):
        item = sub.add_parser(cmd_name, help=f"Restart all agent services (fleet-wide)")
        item.set_defaults(func=lambda args, paths, fn=action_fn: _fleet_cmd(fn))

    upgrade = sub.add_parser("upgrade-all", help="Upgrade runtime on all agents")
    upgrade.add_argument("--rolling", type=int, default=0, metavar="N",
                         help="Upgrade N at a time, abort on first failure (0 = all at once)")
    upgrade.set_defaults(func=cmd_upgrade_all)

    for cmd_name, help_text, action_slug in (
        ("restart-agent", "Restart laia-executor.service inside one container", "restart"),
        ("stop-agent", "Stop laia-executor.service inside one container", "stop"),
        ("start-agent", "Start laia-executor.service inside one container", "start"),
        ("agent-status", "Show runtime status and recent logs", "status"),
    ):
        item = sub.add_parser(cmd_name, help=help_text)
        item.add_argument("slug", nargs="?", default=None)
        item.add_argument("--all", action="store_true", help="Apply to all agents")
        func = {
            "start": cmd_start_agent,
            "stop": cmd_stop_agent,
            "restart": cmd_restart_agent,
            "status": cmd_agent_status,
        }[action_slug]
        item.set_defaults(func=func)
    return parser


def cmd_doctor(_args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.verify_setup(paths)
    print_result(result)
    return result.returncode


def cmd_setup_lxd(_args: argparse.Namespace, paths: config.Paths) -> int:
    for action in (lxd.setup_defaults, lxd.apply_profile, lxd.verify_setup):
        result = action(paths)
        print_result(result)
    print("If container egress fails, run with sudo:")
    print(f"  sudo {paths.infra_root}/lxd/scripts/fix-egress-root.sh")
    return 0


def cmd_build_agent_image(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.build_agent_image(paths, force=args.force)
    print_result(result)
    return result.returncode


def cmd_create_agent(args: argparse.Namespace, paths: config.Paths) -> int:
    existed = lxd.container_exists(args.slug)
    result = lxd.create_agent(paths, args.slug, image=args.image)
    print_result(result)
    if not result.ok:
        return result.returncode
    if not existed and args.snapshot:
        snap = lxd.snapshot_agent(paths, args.slug, args.snapshot)
        print_result(snap)
    verify = lxd.verify_agent(args.slug)
    print_result(verify)
    if verify.ok:
        state.upsert_agent(
            paths.agents_state,
            args.slug,
            {
                "slug": args.slug,
                "container": lxd.container_name(args.slug),
                "image": args.image,
                "snapshot": args.snapshot,
                "status": "verified",
                "workspace": "/var/lib/laia/workspace/workspace.db",
            },
        )
    return verify.returncode


def cmd_install_agent_runtime(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.install_agent_runtime(paths, args.slug)
    print_result(result)
    if result.ok:
        state.upsert_agent(
            paths.agents_state,
            args.slug,
            {
                "slug": args.slug,
                "container": lxd.container_name(args.slug),
                "status": "executor-ready",
                "runtime": "laia-executor",
                "service": "laia-executor.service",
                "workspace": "/var/lib/laia/workspace/workspace.db",
            },
        )
    return result.returncode


def cmd_init_agent_workspace(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.init_agent_workspace(args.slug)
    print_result(result)
    if result.ok:
        state.upsert_agent(
            paths.agents_state,
            args.slug,
            {
                "slug": args.slug,
                "container": lxd.container_name(args.slug),
                "workspace_status": "initialized",
                "workspace": "/var/lib/laia/workspace/workspace.db",
            },
        )
    return result.returncode


def cmd_init_agent_profile(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.init_agent_profile(args.slug)
    print_result(result)
    if result.ok:
        state.upsert_agent(
            paths.agents_state,
            args.slug,
            {
                "slug": args.slug,
                "container": lxd.container_name(args.slug),
                "profile_status": "initialized",
            },
        )
    return result.returncode


def cmd_agent_profile(args: argparse.Namespace, _paths: config.Paths) -> int:
    result = lxd.get_agent_profile(args.slug)
    print_result(result)
    return result.returncode


def cmd_set_agent_persona(args: argparse.Namespace, paths: config.Paths) -> int:
    file_path = _resolve_local_file(args.file)
    if file_path is None:
        return 1
    payload = {"persona": file_path.read_text(encoding="utf-8")}
    result = lxd.update_agent_profile(args.slug, payload)
    print_result(result)
    if result.ok:
        state.upsert_agent(paths.agents_state, args.slug, {"profile_status": "updated"})
    return result.returncode


def cmd_set_agent_instructions(args: argparse.Namespace, paths: config.Paths) -> int:
    file_path = _resolve_local_file(args.file)
    if file_path is None:
        return 1
    payload = {"instructions": file_path.read_text(encoding="utf-8")}
    result = lxd.update_agent_profile(args.slug, payload)
    print_result(result)
    if result.ok:
        state.upsert_agent(paths.agents_state, args.slug, {"profile_status": "updated"})
    return result.returncode


def cmd_enable_agent_skill(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.set_agent_skill(args.slug, args.skill_id, True)
    print_result(result)
    if result.ok:
        state.upsert_agent(paths.agents_state, args.slug, {"profile_status": "updated"})
    return result.returncode


def cmd_disable_agent_skill(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.set_agent_skill(args.slug, args.skill_id, False)
    print_result(result)
    if result.ok:
        state.upsert_agent(paths.agents_state, args.slug, {"profile_status": "updated"})
    return result.returncode


def cmd_verify_agent(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.verify_agent(args.slug)
    print_result(result)
    if result.ok:
        state.upsert_agent(
            paths.agents_state,
            args.slug,
            {
                "slug": args.slug,
                "container": lxd.container_name(args.slug),
                "status": "verified",
                "workspace": "/var/lib/laia/workspace/workspace.db",
            },
        )
    return result.returncode


def cmd_start_agent(args: argparse.Namespace, _paths: config.Paths) -> int:
    if getattr(args, "all", False):
        return _fleet_action_cmd(lxd.start_agent, "start")
    return _single_cmd(lxd.start_agent, args.slug)


def cmd_stop_agent(args: argparse.Namespace, _paths: config.Paths) -> int:
    if getattr(args, "all", False):
        return _fleet_action_cmd(lxd.stop_agent, "stop")
    return _single_cmd(lxd.stop_agent, args.slug)


def cmd_restart_agent(args: argparse.Namespace, _paths: config.Paths) -> int:
    if getattr(args, "all", False):
        return _fleet_action_cmd(lxd.restart_agent, "restart")
    return _single_cmd(lxd.restart_agent, args.slug)


def cmd_agent_status(args: argparse.Namespace, _paths: config.Paths) -> int:
    if getattr(args, "all", False):
        for slug in lxd.all_slugs():
            print(f"\n=== {slug} ===")
            print_result(lxd.agent_status(slug))
        return 0
    return _single_cmd(lxd.agent_status, args.slug)


def cmd_fleet_status(_args: argparse.Namespace, _paths: config.Paths) -> int:
    rows = lxd.fleet_status()
    if not rows:
        print("No LAIA agent containers found.")
        return 0
    print(f"{'SLUG':12s} {'CONTAINER':18s} {'LXD':10s} {'IP':14s} {'EXECUTOR':10s} {'HEALTH'}")
    print("-" * 80)
    for r in rows:
        print(f"{r['slug']:12s} {r['container']:18s} {r['lxd_state']:10s} {r['ipv4']:14s} {r['service']:10s} {r.get('health', ''):10s}")
    return 0


def cmd_provision_agent(args: argparse.Namespace, paths: config.Paths) -> int:
    print(f"Provisioning agent '{args.slug}'...")
    result = lxd.provision_agent(paths, args.slug, image=args.image)
    print_result(result)
    if result.ok:
        state.upsert_agent(paths.agents_state, args.slug, {
            "slug": args.slug,
            "container": lxd.container_name(args.slug),
            "status": "provisioned",
            "runtime": "laia-runtime",
            "workspace": "/opt/laia/workspaces/personal/workspace.db",
        })
    return result.returncode


def cmd_upgrade_all(args: argparse.Namespace, paths: config.Paths) -> int:
    slugs = lxd.all_slugs()
    if not slugs:
        print("No agents to upgrade.")
        return 0
    print(f"Upgrading runtime on {len(slugs)} agents...")
    results = lxd.upgrade_all_runtimes(paths, rolling=args.rolling)
    failed = 0
    for slug, r in results.items():
        if slug.startswith("_"):
            print(f"  {slug}: {r}")
        elif r["ok"]:
            print(f"  {slug}: OK")
        else:
            print(f"  {slug}: FAILED (rc={r['returncode']})")
            failed += 1
    print(f"\n{len(slugs)-failed}/{len(slugs)} upgraded successfully.")
    return 1 if failed else 0


def _fleet_cmd(fn) -> int:
    result = fn()
    print(json.dumps(result, indent=2))
    return 0


def _fleet_action_cmd(action_fn, label: str) -> int:
    slugs = lxd.all_slugs()
    if not slugs:
        print("No agents found.")
        return 0
    failed = 0
    for slug in slugs:
        print(f"{label} {slug}...")
        result = action_fn(slug)
        print(f"  {'OK' if result.ok else 'FAILED'}")
        if not result.ok:
            failed += 1
    return 1 if failed else 0


def _single_cmd(fn, slug: str) -> int:
    if not slug:
        print(f"Error: slug required (or use --all)")
        return 2
    result = fn(slug)
    print_result(result)
    return result.returncode


def cmd_snapshot_agent(args: argparse.Namespace, paths: config.Paths) -> int:
    result = lxd.snapshot_agent(paths, args.slug, args.snapshot)
    print_result(result)
    return result.returncode


def cmd_restore_agent(args: argparse.Namespace, paths: config.Paths) -> int:
    if not args.yes:
        print("Refusing to restore without --yes")
        return 2
    result = lxd.restore_agent(paths, args.slug, args.snapshot)
    print_result(result)
    return result.returncode


def cmd_delete_agent(args: argparse.Namespace, _paths: config.Paths) -> int:
    if not args.yes:
        print("Refusing to delete without --yes")
        return 2
    result = lxd.delete_agent(args.slug, force=args.force)
    print_result(result)
    return result.returncode


def cmd_list_agents(_args: argparse.Namespace, _paths: config.Paths) -> int:
    rows = lxd.list_agent_containers()
    if not rows:
        print("No LAIA agent containers found.")
        return 0
    for row in rows:
        print(f"{row['name']}\t{row['state']}\t{row['ipv4']}\tsnapshots={row['snapshots']}")
    return 0


def cmd_verify(_args: argparse.Namespace, paths: config.Paths) -> int:
    setup = lxd.verify_setup(paths)
    print_result(setup)
    if not setup.ok:
        return setup.returncode
    failed = 0
    for row in lxd.list_agent_containers():
        slug = row["name"].removeprefix("agent-") if row["name"].startswith("agent-") else row["name"].removeprefix("laia-")
        print(f"\nVerifying {row['name']}...")
        result = lxd.verify_agent(slug)
        print_result(result)
        if not result.ok:
            failed += 1
    return 1 if failed else 0


def cmd_state_path(_args: argparse.Namespace, paths: config.Paths) -> int:
    print(f"state_root={paths.state_root}")
    print(f"agents_state={paths.agents_state}")
    return 0


def _resolve_local_file(path: str):
    from pathlib import Path

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not candidate.exists():
        print(f"File not found: {candidate}")
        return None
    return candidate


if __name__ == "__main__":
    sys.exit(main())
