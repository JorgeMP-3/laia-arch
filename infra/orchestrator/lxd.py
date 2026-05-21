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
    if not valid_slug(slug):
        return Result(["install-agent-runtime", slug], 2, "", f"Invalid employee slug: {slug}\n")
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["install-agent-runtime", slug], 1, "", f"Container not found: {name}\n")
    if not paths.agent_runtime_root.exists():
        return Result(
            ["install-agent-runtime", slug],
            1,
            "",
            f"Runtime source not found: {paths.agent_runtime_root}\n",
        )
    _remove_pycache(paths.agent_runtime_root)
    _remove_pycache(paths.laia_root / "workspace_store")

    commands = [
        # Estructura de directorios
        ["lxc", "exec", name, "--", "mkdir", "-p",
         "/opt/laia/agent", "/opt/laia/data", "/opt/laia/logs",
         "/opt/laia/runtime", "/opt/laia/workspaces/personal",
         "/opt/laia/data/tasks/inbox", "/opt/laia/data/tasks/done",
         "/opt/laia/data/tasks/failed"],
        # Usuario sin privilegios
        ["lxc", "exec", name, "--", "sh", "-lc",
         "id -u laia-agent >/dev/null 2>&1 || "
         "useradd --system --home /opt/laia --shell /usr/sbin/nologin laia-agent"],
        # Instalar código del runtime
        ["lxc", "exec", name, "--", "rm", "-rf", "/opt/laia/agent", "/tmp/laia-runtime"],
        ["lxc", "file", "push", "-r", "-p", str(paths.agent_runtime_root), f"{name}/tmp"],
        ["lxc", "exec", name, "--", "mv", "/tmp/laia-runtime", "/opt/laia/agent"],
        # Vendor: workspace_store
        ["lxc", "exec", name, "--", "mkdir", "-p", "/opt/laia/agent/vendor"],
        ["lxc", "file", "push", "-r", "-p",
         str(paths.laia_root / "workspace_store"), f"{name}/opt/laia/agent/vendor"],
        ["lxc", "exec", name, "--", "find", "/opt/laia/agent", "-type", "d", "-name", "__pycache__", "-prune", "-exec", "rm", "-rf", "{}", "+"],
        # Virtual environment (instalado como root, ejecutado por laia-agent)
        ["lxc", "exec", name, "--", "python3", "-m", "venv", "/opt/laia/runtime/venv"],
        # Systemd service
        ["lxc", "exec", name, "--", "cp",
         "/opt/laia/agent/systemd/laia-agent.service",
         "/etc/systemd/system/laia-agent.service"],
        # healthcheck
        ["lxc", "exec", name, "--", "cp",
         "/opt/laia/agent/healthcheck.sh", "/opt/laia/healthcheck.sh"],
        ["lxc", "exec", name, "--", "chmod", "+x",
         "/opt/laia/healthcheck.sh", "/opt/laia/agent/healthcheck.sh"],
        # Configuración del agente
        ["lxc", "exec", name, "--", "sh", "-lc", _agent_json_script(slug, name)],
        # Permisos: agent/ y runtime/ ejecutable pero no escribible por el runtime
        ["lxc", "exec", name, "--", "chown", "-R", "root:laia-agent",
         "/opt/laia/agent", "/opt/laia/runtime"],
        ["lxc", "exec", name, "--", "chmod", "-R", "u=rwX,g=rX,o=",
         "/opt/laia/agent", "/opt/laia/runtime"],
        # data/, logs/, workspaces/ escritura exclusiva del runtime
        ["lxc", "exec", name, "--", "chown", "-R", "laia-agent:laia-agent",
         "/opt/laia/data", "/opt/laia/logs", "/opt/laia/workspaces"],
        ["lxc", "exec", name, "--", "chmod", "0750",
         "/opt/laia/data", "/opt/laia/logs", "/opt/laia/workspaces/personal"],
        # agent.json: legible por laia-agent, no modificable
        ["lxc", "exec", name, "--", "chmod", "0640", "/opt/laia/agent.json"],
        ["lxc", "exec", name, "--", "chown", "root:laia-agent", "/opt/laia/agent.json"],
        # Activar servicio
        ["lxc", "exec", name, "--", "systemctl", "daemon-reload"],
        ["lxc", "exec", name, "--", "systemctl", "enable", "laia-agent.service"],
        ["lxc", "exec", name, "--", "systemctl", "restart", "laia-agent.service"],
        ["lxc", "exec", name, "--", "/opt/laia/healthcheck.sh"],
    ]
    output: list[str] = []
    for command in commands:
        result = run(command, check=False)
        output.append(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}")
        if not result.ok:
            return Result(["install-agent-runtime", slug], result.returncode, "\n".join(output), "")
    return Result(["install-agent-runtime", slug], 0, "\n".join(output), "")


def init_agent_workspace(slug: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["init-agent-workspace", slug], 1, "", f"Container not found: {name}\n")
    commands = [
        ["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "env", "PYTHONPATH=/opt/laia/agent/src", "/opt/laia/runtime/venv/bin/python", "-m", "laia_agent", "--workspace-init"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/workspaces/personal/workspace.db"],
        ["lxc", "exec", name, "--", "sh", "-lc", "PYTHONPATH=/opt/laia/agent/src /opt/laia/runtime/venv/bin/python - <<'PY'\nfrom laia_agent.config import load_config\nfrom laia_agent.workspace import workspace_status\nimport json\nprint(json.dumps(workspace_status(load_config()), indent=2, sort_keys=True))\nPY"],
    ]
    output = []
    for command in commands:
        result = run(command, check=False)
        output.append(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}")
        if not result.ok:
            return Result(["init-agent-workspace", slug], result.returncode, "\n".join(output), "")
    return Result(["init-agent-workspace", slug], 0, "\n".join(output), "")


def init_agent_profile(slug: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result(["init-agent-profile", slug], 1, "", f"Container not found: {name}\n")
    commands = [
        ["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "env", "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=/opt/laia/agent/src", "/opt/laia/runtime/venv/bin/python", "-m", "laia_agent", "--profile-init"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/persona.md"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/instructions.md"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/skills.json"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/preferences.json"],
    ]
    output = []
    for command in commands:
        result = run(command, check=False)
        output.append(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}")
        if not result.ok:
            return Result(["init-agent-profile", slug], result.returncode, "\n".join(output), "")
    return Result(["init-agent-profile", slug], 0, "\n".join(output), "")


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
        ["lxc", "exec", name, "--", "systemctl", "is-active", "laia-agent.service"],
        ["lxc", "exec", name, "--", "cat", "/opt/laia/data/status.json"],
        ["lxc", "exec", name, "--", "tail", "-n", "20", "/opt/laia/logs/agent.log"],
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
    checks = [
        ["lxc", "exec", name, "--", "systemctl", "is-active", "laia-agent.service"],
        ["lxc", "exec", name, "--", "/opt/laia/healthcheck.sh"],
        ["lxc", "exec", name, "--", "python3", "-m", "pip", "--version"],
        ["lxc", "exec", name, "--", "/opt/laia/runtime/venv/bin/python", "-m", "pip", "--version"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/persona.md"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/instructions.md"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/skills.json"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/data/profile/preferences.json"],
        ["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "env", "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=/opt/laia/agent/src", "/opt/laia/runtime/venv/bin/python", "-c", "from laia_agent.config import load_config; from laia_agent.profile import get_profile; p=get_profile(load_config()); assert p['persona'] and p['instructions']; print('profile-ok')"],
        ["lxc", "exec", name, "--", "test", "-s", "/opt/laia/workspaces/personal/workspace.db"],
        ["lxc", "exec", name, "--", "runuser", "-u", "laia-agent", "--", "env", "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=/opt/laia/agent/src", "/opt/laia/runtime/venv/bin/python", "-c", "from laia_agent.config import load_config; from laia_agent.workspace import workspace_status; s=workspace_status(load_config()); assert s['exists'] and s['node_count'] >= 1; print('workspace-ok')"],
        ["lxc", "exec", name, "--", "curl", "-4", "-I", "--max-time", "8", "http://ports.ubuntu.com/ubuntu-ports/dists/jammy/InRelease"],
        ["lxc", "exec", name, "--", "curl", "-sf", "--max-time", "5", "http://localhost:9090/health"],
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


def _remove_pycache(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)


def _systemctl_agent(slug: str, action: str) -> Result:
    name = container_name(slug)
    if not container_exists(slug):
        return Result([action + "-agent", slug], 1, "", f"Container not found: {name}\n")
    return run(["lxc", "exec", name, "--", "systemctl", action, "laia-agent.service"], check=False)


def _agent_json_script(slug: str, name: str) -> str:
    return f"""cat > /opt/laia/agent.json <<'JSON'
{{
  "employee": "{slug}",
  "container": "{name}",
  "root": "/opt/laia",
  "agent_dir": "/opt/laia/agent",
  "data_dir": "/opt/laia/data",
  "logs_dir": "/opt/laia/logs",
  "workspace": "/opt/laia/workspaces/personal/workspace.db",
  "heartbeat_interval": 5,
  "status": "runtime-installed"
}}
JSON
chmod 0644 /opt/laia/agent.json
"""


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
            svc = run(["lxc", "exec", row["name"], "--", "systemctl", "is-active", "laia-agent.service"], check=False)
            service = svc.stdout.strip()
        except Exception:
            pass
        health = ""
        try:
            hc = run(["lxc", "exec", row["name"], "--", "curl", "-sf", "--max-time", "3", "http://localhost:9090/health"], check=False)
            if hc.ok:
                import json as _json
                hd = _json.loads(hc.stdout)
                health = hd.get("service", "")
        except Exception:
            pass
        status_json = {}
        try:
            sj = run(["lxc", "exec", row["name"], "--", "cat", "/opt/laia/data/status.json"], check=False)
            if sj.ok:
                import json as _json
                status_json = _json.loads(sj.stdout)
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
            "runtime_status": status_json.get("status", "unknown"),
            "version": status_json.get("version", ""),
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
