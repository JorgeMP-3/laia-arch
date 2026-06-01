from __future__ import annotations

import csv
import io
import json
import re
import shutil
from pathlib import Path

from . import config
from .shell import Result, run


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")


def valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug))


# NOTE: these naming helpers are duplicated from
# ``services/agora-backend/app/agent_identity.py``. They live here so that
# the host-side orchestrator (which doesn't import the agora-backend
# package) can derive container names without a cross-package dep.
# Keep the two implementations in sync — if you change the prefix
# convention here, also update agent_identity.py.
def container_name(slug: str) -> str:
    return f"agent-{slug}"


def legacy_container_name(slug: str) -> str:
    return f"laia-{slug}"


def candidate_container_names(slug: str) -> list[str]:
    return [container_name(slug), legacy_container_name(slug)]


def script(paths: config.Paths, relative: str) -> Path:
    return paths.infra_root / relative


def lxc(*args: str, check: bool = True) -> Result:
    return run(["lxc", *args], check=check)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def lxd_responds() -> bool:
    return lxc("version", check=False).ok


def storage_exists(name: str = config.DEFAULT_POOL) -> bool:
    result = lxc("storage", "list", "--format", "csv", check=False)
    return _csv_first_column_contains(result.stdout, name)


def network_exists(name: str = config.DEFAULT_NETWORK) -> bool:
    result = lxc("network", "list", "--format", "csv", check=False)
    return _csv_first_column_contains(result.stdout, name)


def profile_exists(name: str = config.DEFAULT_PROFILE) -> bool:
    return lxc("profile", "show", name, check=False).ok


def image_exists(alias: str = config.DEFAULT_IMAGE_ALIAS) -> bool:
    return lxc("image", "info", alias, check=False).ok


def container_exists(slug: str) -> bool:
    return any(lxc("info", name, check=False).ok for name in candidate_container_names(slug))


def list_agent_containers() -> list[dict[str, str]]:
    result = lxc("list", "--format", "csv")
    rows: list[dict[str, str]] = []
    if not result.stdout.strip():
        return rows
    for row in csv.reader(io.StringIO(result.stdout)):
        if row and (row[0].startswith("agent-") or row[0].startswith("laia-")) and row[0] not in {"laia-agora", "laia-jorge"}:
            rows.append(
                {
                    "name": row[0],
                    "state": row[1] if len(row) > 1 else "",
                    "ipv4": row[2] if len(row) > 2 else "",
                    "type": row[4] if len(row) > 4 else "",
                    "snapshots": row[5] if len(row) > 5 else "",
                }
            )
    return rows


def setup_defaults(paths: config.Paths) -> Result:
    return run([str(script(paths, "lxd/scripts/init-defaults.sh"))])


def apply_profile(paths: config.Paths) -> Result:
    return run([str(script(paths, "lxd/scripts/apply-profile.sh"))])


def verify_setup(paths: config.Paths) -> Result:
    return run([str(script(paths, "lxd/scripts/verify-lxd-setup.sh"))])


def build_agent_image(paths: config.Paths, *, force: bool = False) -> Result:
    if image_exists(config.DEFAULT_IMAGE_ALIAS):
        if not force:
            return Result(["build-agent-image"], 0, "Image already exists: laia-agent\n", "")
        lxc("image", "alias", "delete", f"local:{config.DEFAULT_IMAGE_ALIAS}", check=False)
    return run([str(script(paths, "lxd/image-build/build-base-image.sh"))])


def create_agent(paths: config.Paths, slug: str, *, image: str = config.DEFAULT_IMAGE_ALIAS) -> Result:
    if not valid_slug(slug):
        return Result(["create-agent", slug], 2, "", f"Invalid employee slug: {slug}\n")
    if container_exists(slug):
        return Result(["create-agent", slug], 0, f"Container already exists: {container_name(slug)}\n", "")
    return run([str(script(paths, "lxd/scripts/create-agent.sh")), slug, image])


def snapshot_agent(paths: config.Paths, slug: str, snapshot: str) -> Result:
    return run([str(script(paths, "lxd/scripts/snapshot-agent.sh")), slug, snapshot])


def restore_agent(paths: config.Paths, slug: str, snapshot: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["restore-agent", slug, snapshot], 1, "", f"Container not found: {name}\n")
    info = lxc("info", name, check=False)
    if not info.ok:
        return info
    if f"| {snapshot} " not in info.stdout and f" {snapshot} " not in info.stdout:
        return Result(
            ["restore-agent", slug, snapshot],
            1,
            "",
            f"Snapshot not found: {name}/{snapshot}\n",
        )
    return lxc("restore", name, snapshot, check=False)


def delete_agent(slug: str, *, force: bool = False) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["delete-agent", slug], 0, f"Container already absent: {name}\n", "")
    args = ["lxc", "delete"]
    if force:
        args.append("-f")
    args.append(name)
    return run(args, check=False)


def install_agent_runtime(paths: config.Paths, slug: str) -> Result:
    """Centralized-brain model: there is no per-container agent runtime to install.

    The brain now reasons centrally in the ``laia-agora`` container; each user's
    container runs only the thin ``laia-executor.service``, which is installed and
    started by ``create-agent`` (see ``infra/lxd/scripts/create-agent.sh``). The old
    per-container runtime (``services/laia-runtime`` + ``laia-agent.service``) was
    archived in commit 64ba0c2e.

    This step is kept as a name-stable, idempotent no-op so existing callers
    (agora-backend orchestrator, ``provision-agent``, the T3/T6 e2e tests) keep
    working: it just confirms the executor — the per-container runtime in the
    current model — is active. ``paths`` is accepted for signature stability.
    """
    del paths  # no longer needed: nothing to push into the container
    if not valid_slug(slug):
        return Result(["install-agent-runtime", slug], 2, "", f"Invalid employee slug: {slug}\n")
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["install-agent-runtime", slug], 1, "", f"Container not found: {name}\n")
    result = run(["lxc", "exec", name, "--", "systemctl", "is-active", "laia-executor.service"], check=False)
    output = f"$ lxc exec {name} -- systemctl is-active laia-executor.service\n{result.stdout}{result.stderr}"
    if result.stdout.strip() != "active":
        return Result(["install-agent-runtime", slug], 1, output, "laia-executor.service is not active\n")
    return Result(["install-agent-runtime", slug], 0, output, "")


def init_agent_workspace(slug: str) -> Result:
    """Centralized-brain model: the private ``workspace.db`` is created lazily by the
    executor's workspace tools (``services/laia-executor``, root
    ``/var/lib/laia/workspace``) on first use — no explicit init via the archived
    ``laia_agent`` runtime is needed. Kept as a name-stable check that the workspace
    bind-mount is present in the container.
    """
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["init-agent-workspace", slug], 1, "", f"Container not found: {name}\n")
    result = run(["lxc", "exec", name, "--", "test", "-d", "/var/lib/laia/workspace"], check=False)
    output = f"$ lxc exec {name} -- test -d /var/lib/laia/workspace\n{result.stdout}{result.stderr}"
    if not result.ok:
        return Result(["init-agent-workspace", slug], result.returncode, output, "workspace bind-mount /var/lib/laia/workspace missing\n")
    return Result(["init-agent-workspace", slug], 0, output, "")


def init_agent_profile(slug: str) -> Result:
    """Centralized-brain model: the agent profile (persona, instructions, enabled
    skills) lives centrally in ``agora.db`` and is applied by the central brain, not
    in per-container files under ``/opt/laia/data/profile`` (archived in 64ba0c2e).
    Kept as a name-stable no-op so ``provision-agent`` keeps working.
    """
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["init-agent-profile", slug], 1, "", f"Container not found: {name}\n")
    return Result(["init-agent-profile", slug], 0, "profile is managed centrally in agora.db (no per-container init)\n", "")


def get_agent_profile(slug: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["agent-profile", slug], 1, "", f"Container not found: {name}\n")
    script_text = (
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src "
        "/opt/laia/runtime/venv/bin/python - <<'PY'\n"
        "from laia_agent.config import load_config\n"
        "from laia_agent.profile import get_profile\n"
        "import json\n"
        "print(json.dumps(get_profile(load_config()), indent=2, sort_keys=True, ensure_ascii=False))\n"
        "PY"
    )
    return run(["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "sh", "-lc", script_text], check=False)


def update_agent_profile(slug: str, payload: dict[str, object]) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["update-agent-profile", slug], 1, "", f"Container not found: {name}\n")
    encoded = json.dumps(payload, ensure_ascii=False)
    script_text = (
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src "
        "/opt/laia/runtime/venv/bin/python - <<'PY'\n"
        "from laia_agent.config import load_config\n"
        "from laia_agent.profile import update_profile\n"
        "import json\n"
        f"payload = json.loads({encoded!r})\n"
        "print(json.dumps(update_profile(load_config(), payload), indent=2, sort_keys=True, ensure_ascii=False))\n"
        "PY"
    )
    return run(["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "sh", "-lc", script_text], check=False)


def set_agent_skill(slug: str, skill_id: str, enabled: bool) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["set-agent-skill", slug], 1, "", f"Container not found: {name}\n")
    action = "True" if enabled else "False"
    script_text = (
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src "
        "/opt/laia/runtime/venv/bin/python - <<'PY'\n"
        "from laia_agent.config import load_config\n"
        "from laia_agent.profile import set_skill\n"
        "import json\n"
        f"print(json.dumps(set_skill(load_config(), {skill_id!r}, {action}), indent=2, sort_keys=True, ensure_ascii=False))\n"
        "PY"
    )
    return run(["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "sh", "-lc", script_text], check=False)


def start_agent(slug: str) -> Result:
    return _systemctl_agent(slug, "start")


def stop_agent(slug: str) -> Result:
    return _systemctl_agent(slug, "stop")


def restart_agent(slug: str) -> Result:
    return _systemctl_agent(slug, "restart")


def agent_status(slug: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["agent-status", slug], 1, "", f"Container not found: {name}\n")
    checks = [
        ["lxc", "exec", name, "--", "systemctl", "is-active", "laia-executor.service"],
        ["lxc", "exec", name, "--", "curl", "-sf", "--max-time", "5", "http://localhost:9091/health"],
        ["lxc", "exec", name, "--", "journalctl", "-u", "laia-executor.service", "-n", "20", "--no-pager"],
    ]
    output = []
    returncode = 0
    for command in checks:
        result = run(command, check=False)
        output.append(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}")
        if not result.ok and returncode == 0:
            returncode = result.returncode
    return Result(["agent-status", slug], returncode, "\n".join(output), "")


def verify_agent(slug: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["verify-agent", slug], 1, "", f"Container not found: {name}\n")
    # Centralized-brain model: a healthy user container = the thin executor is up
    # and serving /health, with its private-workspace bind-mount present. The old
    # per-container checks (laia-agent.service, /opt/laia/runtime venv, profile
    # files under /opt/laia/data/profile) were archived in 64ba0c2e.
    checks = [
        ["lxc", "exec", name, "--", "systemctl", "is-active", "laia-executor.service"],
        ["lxc", "exec", name, "--", "curl", "-sf", "--max-time", "5", "http://localhost:9091/health"],
        ["lxc", "exec", name, "--", "test", "-d", "/var/lib/laia/workspace"],
    ]
    output = []
    for args in checks:
        result = run(args, check=False)
        output.append(f"$ {' '.join(args)}\n{result.stdout}{result.stderr}")
        if not result.ok:
            return Result(["verify-agent", slug], result.returncode, "\n".join(output), "")
    return Result(["verify-agent", slug], 0, "\n".join(output), "")


def _csv_first_column_contains(output: str, expected: str) -> bool:
    for row in csv.reader(io.StringIO(output)):
        if row and row[0] == expected:
            return True
    return False


def _systemctl_agent(slug: str, action: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result([action + "-agent", slug], 1, "", f"Container not found: {name}\n")
    return run(["lxc", "exec", name, "--", "systemctl", action, "laia-executor.service"], check=False)


# ── fleet / composite operations ───────────────────────────────────────────

def provision_agent(paths: config.Paths, slug: str, *, image: str = config.DEFAULT_IMAGE_ALIAS) -> Result:
    steps = [
        ("create", lambda: create_agent(paths, slug, image=image)),
        ("install-runtime", lambda: install_agent_runtime(paths, slug)),
        ("init-workspace", lambda: init_agent_workspace(slug)),
        ("init-profile", lambda: init_agent_profile(slug)),
        ("verify", lambda: verify_agent(slug)),
    ]
    output: list[str] = []
    for label, action in steps:
        result = action()
        output.append(f"--- {label} ---\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR: {result.stderr}")
        if not result.ok:
            output.append(f"FAILED at step '{label}'")
            return Result(["provision-agent", slug], result.returncode, "\n".join(output), "")
    return Result(["provision-agent", slug], 0, "\n".join(output), "")


def all_slugs() -> list[str]:
    slugs: list[str] = []
    for row in list_agent_containers():
        name = row["name"]
        if name.startswith("agent-"):
            slugs.append(name.removeprefix("agent-"))
        elif name.startswith("laia-") and name not in {"laia-agora", "laia-jorge"}:
            slugs.append(name.removeprefix("laia-"))
    return slugs


def fleet_status() -> list[dict]:
    rows: list[dict] = []
    for row in list_agent_containers():
        slug = row["name"].removeprefix("agent-") if row["name"].startswith("agent-") else row["name"].removeprefix("laia-")
        service = "unknown"
        try:
            svc = run(["lxc", "exec", row["name"], "--", "systemctl", "is-active", "laia-executor.service"], check=False)
            service = svc.stdout.strip()
        except Exception:
            pass
        health = ""
        try:
            hc = run(["lxc", "exec", row["name"], "--", "curl", "-sf", "--max-time", "3", "http://localhost:9091/health"], check=False)
            if hc.ok:
                import json as _json
                hd = _json.loads(hc.stdout)
                health = hd.get("status", "")
        except Exception:
            pass
        rows.append({
            "slug": slug,
            "container": row["name"],
            "lxd_state": row["state"],
            "ipv4": row["ipv4"],
            "snapshots": row["snapshots"],
            "service": service,
            "health": health,
        })
    return rows


def fleet_action(slugs: list[str], action_fn, label: str) -> dict:
    results = {}
    for slug in slugs:
        result = action_fn(slug)
        results[slug] = {
            "ok": result.ok,
            "returncode": result.returncode,
            "output": result.stdout.strip().split("\n")[-1] if result.stdout else "",
            "error": result.stderr.strip()[:100] if result.stderr else "",
        }
    return results


def restart_all_agents() -> dict:
    return fleet_action(all_slugs(), restart_agent, "restart")


def upgrade_all_runtimes(paths: config.Paths, rolling: int = 0) -> dict:
    slugs = all_slugs()
    results = {}
    for i, slug in enumerate(slugs):
        result = install_agent_runtime(paths, slug)
        results[slug] = {"ok": result.ok, "returncode": result.returncode}
        if rolling and not result.ok:
            results["_aborted_after"] = i
            results["_aborted_at"] = slug
            break
    return results
