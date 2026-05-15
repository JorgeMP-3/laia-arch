from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from .agent_client import (
    AgentClient,
    AgentClientError,
    AgentNotFoundError,
    AgentUnreachableError,
)
from .config import settings

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
SNAPSHOT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
TASK_TYPE_RE = re.compile(r"^[a-z_]{1,40}$")


class OrchestratorError(Exception):
    pass


class AgentOrchestrator:
    def __init__(self) -> None:
        self._laiactl = settings.laiactl_path
        self._state_path = settings.lxd_state_path

    # ── internal helpers ──────────────────────────────────────────────────────

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["LAIA_STATE_ROOT"] = str(self._state_path.parent)
        return env

    def _run(self, *args: str, timeout: int = 60) -> tuple[int, str, str]:
        if not self._laiactl.exists():
            raise OrchestratorError(f"laiactl not found: {self._laiactl}")
        try:
            result = subprocess.run(
                [str(self._laiactl), *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._env(),
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise OrchestratorError(f"laiactl timed out after {timeout}s")

    def _validate_slug(self, slug: str) -> None:
        if not SLUG_RE.match(slug):
            raise OrchestratorError(f"invalid slug: {slug!r}")

    def _validate_snapshot(self, name: str) -> None:
        if not SNAPSHOT_RE.match(name):
            raise OrchestratorError(f"invalid snapshot name: {name!r}")

    def _read_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return data.get("agents", {})
        except Exception:
            return {}

    def _lxd_live(self) -> dict[str, dict]:
        try:
            rc, out, _ = self._run("list-agents", timeout=15)
            if rc != 0:
                return {}
            return _parse_lxd_list(out)
        except OrchestratorError:
            return {}

    # ── public API ────────────────────────────────────────────────────────────

    def list_agents(self) -> list[dict]:
        agents = self._read_state()
        lxd = self._lxd_live()
        result = []
        for slug, data in agents.items():
            row = dict(data)
            live = lxd.get(f"laia-{slug}", {})
            row["lxd_state"] = live.get("state", "unknown")
            row["ipv4"] = live.get("ipv4", "")
            row["lxd_snapshots"] = live.get("snapshots", "0")
            result.append(row)
        return result

    def get_agent(self, slug: str) -> dict | None:
        self._validate_slug(slug)
        agents = self._read_state()
        if slug not in agents:
            return None
        data = dict(agents[slug])
        try:
            rc, out, err = self._run("agent-status", slug, timeout=20)
            data["status_output"] = out
            data["status_ok"] = rc == 0
        except OrchestratorError as exc:
            data["status_output"] = str(exc)
            data["status_ok"] = False
        lxd = self._lxd_live()
        live = lxd.get(f"laia-{slug}", {})
        data["lxd_state"] = live.get("state", "unknown")
        data["ipv4"] = live.get("ipv4", "")
        data["lxd_snapshots"] = live.get("snapshots", "0")
        return data

    def start_agent(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("start-agent", slug, timeout=30)
        return _result(rc, out, err)

    def stop_agent(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("stop-agent", slug, timeout=30)
        return _result(rc, out, err)

    def restart_agent(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("restart-agent", slug, timeout=30)
        return _result(rc, out, err)

    def snapshot_agent(self, slug: str, snapshot_name: str) -> dict:
        self._validate_slug(slug)
        self._validate_snapshot(snapshot_name)
        rc, out, err = self._run("snapshot-agent", slug, snapshot_name, timeout=120)
        return _result(rc, out, err)

    def get_agent_logs(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("agent-status", slug, timeout=20)
        return {"ok": rc == 0, "output": out, "error": err}

    def create_agent(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("create-agent", slug, timeout=180)
        return _result(rc, out, err)

    def install_runtime(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("install-agent-runtime", slug, timeout=600)
        return _result(rc, out, err)

    def init_workspace(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("init-agent-workspace", slug, timeout=60)
        return _result(rc, out, err)

    def delete_agent(self, slug: str) -> dict:
        self._validate_slug(slug)
        rc, out, err = self._run("delete-agent", slug, "--yes", "--force", timeout=60)
        return _result(rc, out, err)

    # ── HTTP client to child (preferred channel for sprint 1+) ─────────────────

    def _agent_record(self, slug: str) -> dict | None:
        """Lookup the Agent record from storage (for container_ip + api_token).

        Imported lazily to break the storage→orchestrator circular dependency.
        Returns None if no record exists yet.
        """
        try:
            from .storage import store
        except ImportError:
            return None
        slug_norm = slug.removeprefix("laia-")
        for agent in store.agents():
            if agent.container_name == f"laia-{slug_norm}" or agent.container_name == slug_norm:
                return agent.model_dump()
        return None

    def _make_client(self, slug: str) -> AgentClient | None:
        """Build an AgentClient from the DB record. Returns None if not provisioned."""
        record = self._agent_record(slug)
        if not record:
            return None
        ip = record.get("container_ip")
        token = record.get("api_token")
        if not ip or not token:
            return None
        return AgentClient(slug=slug, host=ip, token=token)

    async def _http_get_profile(self, slug: str) -> dict:
        async with self._make_client(slug) as c:
            return await c.get_profile()

    async def _http_update_profile(self, slug: str, patch: dict) -> dict:
        async with self._make_client(slug) as c:
            return await c.update_profile(patch)

    async def _http_submit_task(self, slug: str, task_type: str, payload: dict) -> dict:
        async with self._make_client(slug) as c:
            return await c.submit_task(task_type, payload)

    async def _http_get_task(self, slug: str, task_id: str) -> dict | None:
        async with self._make_client(slug) as c:
            return await c.get_task(task_id)

    async def _http_status(self, slug: str) -> dict:
        async with self._make_client(slug) as c:
            return await c.status()

    def _exec_python(self, slug: str, script: str, timeout: int = 15) -> dict:
        """Run a Python script inside the agent container as laia-agent user."""
        self._validate_slug(slug)
        container = f"laia-{slug}"
        result = subprocess.run(
            ["lxc", "exec", container, "--",
             "runuser", "-u", "laia-agent", "--",
             "env", "PYTHONDONTWRITEBYTECODE=1",
             "PYTHONPATH=/opt/laia/agent/src",
             "/opt/laia/runtime/venv/bin/python", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        try:
            data = json.loads(result.stdout) if result.stdout else None
        except json.JSONDecodeError:
            data = {"raw": result.stdout}
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "data": data,
            "stderr": result.stderr,
        }

    def get_agent_profile(self, slug: str) -> dict:
        """Read the full agent profile (persona, instructions, skills, preferences).

        Prefers HTTP via AgentClient. Falls back to lxc-exec for unmigrated agents.
        """
        self._validate_slug(slug)
        client = self._make_client(slug)
        if client is not None:
            try:
                data = asyncio.run(self._http_get_profile(slug))
                return {"ok": True, "returncode": 0, "data": data, "stderr": ""}
            except AgentClientError as exc:
                logger.warning("HTTP get_profile %s failed (%s); falling back to lxc-exec", slug, exc)
        # Legacy fallback (lxc exec)
        script = (
            "from laia_agent.config import load_config\n"
            "from laia_agent.profile import get_profile\n"
            "import json\n"
            "p = get_profile(load_config())\n"
            "print(json.dumps(p, ensure_ascii=False))\n"
        )
        return self._exec_python(slug, script)

    def update_agent_profile(self, slug: str, payload: dict) -> dict:
        """Update agent profile fields (persona, instructions, skills, preferences)."""
        self._validate_slug(slug)
        client = self._make_client(slug)
        if client is not None:
            try:
                data = asyncio.run(self._http_update_profile(slug, payload))
                return {"ok": True, "returncode": 0, "data": data, "stderr": ""}
            except AgentClientError as exc:
                logger.warning("HTTP update_profile %s failed (%s); falling back to lxc-exec", slug, exc)
        # Legacy fallback (lxc exec)
        encoded = json.dumps(payload, ensure_ascii=False)
        script = (
            "from laia_agent.config import load_config\n"
            "from laia_agent.profile import update_profile\n"
            "import json\n"
            f"p = update_profile(load_config(), {encoded})\n"
            "print(json.dumps(p, ensure_ascii=False))\n"
        )
        return self._exec_python(slug, script, timeout=30)

    def get_agent_status(self, slug: str) -> dict:
        """Get agent runtime status from inside the container."""
        self._validate_slug(slug)
        container = f"laia-{slug}"
        health = subprocess.run(
            ["lxc", "exec", container, "--", "/opt/laia/healthcheck.sh"],
            capture_output=True, text=True, timeout=15,
        )
        status_json = subprocess.run(
            ["lxc", "exec", container, "--",
             "cat", "/opt/laia/data/status.json"],
            capture_output=True, text=True, timeout=10,
        )
        service = subprocess.run(
            ["lxc", "exec", container, "--",
             "systemctl", "is-active", "laia-agent.service"],
            capture_output=True, text=True, timeout=10,
        )
        status_data = {}
        if status_json.returncode == 0:
            try:
                status_data = json.loads(status_json.stdout)
            except json.JSONDecodeError:
                pass
        lxd = self._lxd_live()
        live = lxd.get(container, {})
        return {
            "ok": health.returncode == 0,
            "slug": slug,
            "container": container,
            "runtime": status_data.get("status", "unknown"),
            "healthcheck": health.stdout.strip(),
            "lxd_state": live.get("state", "unknown"),
            "ipv4": live.get("ipv4", ""),
            "service": service.stdout.strip(),
        }

    def send_task(self, slug: str, task_type: str, payload: dict) -> dict:
        """Submit a task. Prefers HTTP POST /tasks; falls back to filesystem inject."""
        self._validate_slug(slug)
        if not TASK_TYPE_RE.match(task_type):
            raise OrchestratorError(f"invalid task_type: {task_type!r}")

        client = self._make_client(slug)
        if client is not None:
            try:
                result = asyncio.run(self._http_submit_task(slug, task_type, payload))
                return {"ok": True, "task_id": result.get("id"), "error": ""}
            except AgentClientError as exc:
                logger.warning("HTTP send_task %s failed (%s); falling back to lxc-exec", slug, exc)

        # Legacy fallback (lxc exec — file inject)
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task_data = json.dumps({
            "id": task_id,
            "type": task_type,
            "payload": payload,
            "created_at": int(time.time()),
        })
        container = f"laia-{slug}"
        result = subprocess.run(
            ["lxc", "exec", container, "--",
             "sh", "-c",
             "mkdir -p /opt/laia/data/tasks/inbox && "
             f"cat > /opt/laia/data/tasks/inbox/{task_id}.json"],
            input=task_data,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {
            "ok": result.returncode == 0,
            "task_id": task_id,
            "error": result.stderr,
        }

    def read_task_result(self, slug: str, task_id: str) -> dict | None:
        """Read a finished task. Prefers HTTP GET /tasks/{id}; falls back to filesystem."""
        self._validate_slug(slug)
        client = self._make_client(slug)
        if client is not None:
            try:
                return asyncio.run(self._http_get_task(slug, task_id))
            except AgentClientError as exc:
                logger.warning("HTTP read_task %s failed (%s); falling back to lxc-exec", slug, exc)

        # Legacy fallback (lxc exec — direct file read)
        if not re.match(r"^task_[a-f0-9]{12}$", task_id):
            raise OrchestratorError(f"invalid task_id: {task_id!r}")
        container = f"laia-{slug}"
        for folder in ("done", "failed"):
            result = subprocess.run(
                ["lxc", "exec", container, "--",
                 "cat", f"/opt/laia/data/tasks/{folder}/{task_id}.json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"raw": result.stdout}
        return None


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(rc: int, out: str, err: str) -> dict:
    return {"ok": rc == 0, "returncode": rc, "output": out, "error": err}


def _parse_lxd_list(output: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for row in csv.reader(io.StringIO(output)):
        if row and row[0].startswith("laia-"):
            rows[row[0]] = {
                "name": row[0],
                "state": row[1] if len(row) > 1 else "",
                "ipv4": row[2] if len(row) > 2 else "",
                "snapshots": row[5] if len(row) > 5 else "0",
            }
    return rows


orchestrator = AgentOrchestrator()
