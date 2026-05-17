#!/usr/bin/env python3
"""Interactive terminal control center for AGORA.

This is intentionally dependency-free: it uses curses and urllib from the
standard library so it can run on the host without changing the backend venv.
"""

from __future__ import annotations

import argparse
import curses
import json
import os
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from getpass import getpass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_URL = os.environ.get("AGORA_API_URL", "http://127.0.0.1:8088")


class ApiError(RuntimeError):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status


class AgoraAdminClient:
    def __init__(self, api_url: str, token: str | None = None, timeout: float = 10.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token or None
        self.timeout = timeout

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self.request("POST", "/api/login", {"username": username, "password": password}, auth=False)
        token = data.get("access_token")
        if not token:
            raise ApiError(None, "login response did not include access_token")
        self.token = str(token)
        return data

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        auth: bool = True,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token:
                raise ApiError(401, "missing admin token")
            headers["Authorization"] = f"Bearer {self.token}"
        req = Request(f"{self.api_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise ApiError(exc.code, _extract_error(raw) or raw or exc.reason) from exc
        except URLError as exc:
            raise ApiError(None, str(exc.reason)) from exc
        except OSError as exc:
            raise ApiError(None, str(exc)) from exc
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(None, f"non-json response: {raw[:300]}") from exc
        if not isinstance(data, dict):
            return {"data": data}
        return data

    def status(self) -> dict[str, Any]:
        return self.request("GET", "/api/admin/status")

    def containers(self) -> dict[str, Any]:
        return self.request("GET", "/api/admin/containers")

    def users(self) -> dict[str, Any]:
        return self.request("GET", "/api/admin/users")

    def jobs(self) -> dict[str, Any]:
        return self.request("GET", "/api/admin/jobs?limit=100")

    def job(self, job_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/admin/jobs/{job_id}")

    def logs(self, name: str, lines: int = 120) -> dict[str, Any]:
        return self.request("GET", f"/api/admin/logs/{name}?lines={lines}")

    def audit(self, limit: int = 120, user_id: str | None = None) -> dict[str, Any]:
        suffix = f"?limit={limit}"
        if user_id:
            suffix += f"&user_id={_url_quote(user_id)}"
        return self.request("GET", f"/api/admin/audit/tools{suffix}")

    def provision_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/api/admin/users/provision", payload)

    def rebuild_user(self, slug: str) -> dict[str, Any]:
        return self.request("POST", f"/api/admin/users/{slug}/rebuild")

    def delete_user(self, slug: str) -> dict[str, Any]:
        return self.request("DELETE", f"/api/admin/users/{slug}")

    def refresh_oauth(self) -> dict[str, Any]:
        return self.request("POST", "/api/admin/system/refresh-oauth")

    def restart_backend(self) -> dict[str, Any]:
        return self.request("POST", "/api/admin/system/restart-backend")

    def restart_container(self, name: str) -> dict[str, Any]:
        return self.request("POST", f"/api/admin/containers/{name}/restart")

    def snapshot_container(self, name: str, snapshot: str) -> dict[str, Any]:
        return self.request("POST", f"/api/admin/containers/{name}/snapshot", {"name": snapshot})

    def restore_container(self, name: str, snapshot: str) -> dict[str, Any]:
        return self.request("POST", f"/api/admin/containers/{name}/restore", {"name": snapshot})


def _url_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _extract_error(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, str):
        return detail
    return json.dumps(detail, ensure_ascii=False) if detail is not None else ""


def _short(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _format_age(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        seconds = max(0, int((now - then).total_seconds()))
    except ValueError:
        return ts
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _status_text(job: dict[str, Any]) -> str:
    status = job.get("status", "unknown")
    progress = job.get("progress")
    return f"{status} {progress}%" if progress not in (None, "") else str(status)


@dataclass
class Screen:
    key: str
    title: str


SCREENS = [
    Screen("dashboard", "Panel"),
    Screen("users", "Usuarios"),
    Screen("containers", "Containers"),
    Screen("jobs", "Jobs"),
    Screen("logs", "Logs"),
    Screen("audit", "Audit"),
    Screen("system", "Sistema"),
]


class ControlCenterTUI:
    def __init__(self, stdscr: Any, client: AgoraAdminClient) -> None:
        self.stdscr = stdscr
        self.client = client
        self.screen_idx = 0
        self.selected = 0
        self.message = ""
        self.error = ""
        self.last_refresh = 0.0
        self.status: dict[str, Any] = {}
        self.users: list[dict[str, Any]] = []
        self.containers: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []
        self.logs_source = "agora-backend"
        self.logs: list[str] = []
        self.audit_user_filter = ""
        self.audit_calls: list[dict[str, Any]] = []

    @property
    def screen(self) -> Screen:
        return SCREENS[self.screen_idx]

    def run(self) -> None:
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(1000)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
        if not self.client.token:
            self.login_wizard()
        self.refresh(force=True)
        while True:
            self.draw()
            key = self.stdscr.getch()
            if key == -1:
                continue
            if self.handle_key(key):
                break

    def login_wizard(self) -> None:
        while not self.client.token:
            self.clear_message()
            username = self.prompt("Usuario admin", os.environ.get("AGORA_ADMIN_USERNAME", "jorge"))
            password = self.prompt_secret("Password")
            try:
                self.client.login(username, password)
                self.message = f"Login OK como {username}"
            except ApiError as exc:
                self.error = f"Login fallo: {exc}"

    def handle_key(self, key: int) -> bool:
        if key in (ord("q"), ord("Q")):
            return self.confirm("Salir del Centro de Control?")
        if key in (ord("?"), ord("h")):
            self.show_help()
            return False
        if key in (ord("r"), ord("R")) and self.screen.key not in {"containers"}:
            self.refresh(force=True)
            return False
        if key in (curses.KEY_RIGHT, ord("\t")):
            self.screen_idx = (self.screen_idx + 1) % len(SCREENS)
            self.selected = 0
            self.refresh()
            return False
        if key == curses.KEY_LEFT:
            self.screen_idx = (self.screen_idx - 1) % len(SCREENS)
            self.selected = 0
            self.refresh()
            return False
        if key == curses.KEY_DOWN:
            self.move_selection(1)
            return False
        if key == curses.KEY_UP:
            self.move_selection(-1)
            return False
        if ord("1") <= key <= ord(str(len(SCREENS))):
            self.screen_idx = key - ord("1")
            self.selected = 0
            self.refresh()
            return False
        return self.handle_screen_key(key)

    def handle_screen_key(self, key: int) -> bool:
        name = self.screen.key
        if name == "users":
            if key == ord("p"):
                self.provision_wizard()
            elif key == ord("b"):
                self.rebuild_selected_user()
            elif key == ord("d"):
                self.delete_selected_user()
        elif name == "containers":
            if key == ord("r"):
                self.refresh(force=True)
            elif key == ord("R"):
                self.restart_selected_container()
            elif key == ord("s"):
                self.snapshot_selected_container()
            elif key == ord("o"):
                self.restore_selected_container()
        elif name == "jobs":
            if key in (ord("\n"), curses.KEY_ENTER, 10, 13):
                self.show_selected_job()
        elif name == "logs":
            if key == ord("n"):
                source = self.prompt("Fuente logs", self.logs_source)
                if source:
                    self.logs_source = source
                    self.refresh_logs()
            elif key == ord("l"):
                self.refresh_logs()
        elif name == "audit":
            if key == ord("u"):
                self.audit_user_filter = self.prompt("Filtrar user_id (vacio=todos)", self.audit_user_filter)
                self.refresh_audit()
        elif name == "system":
            if key == ord("a"):
                self.refresh_oauth()
            elif key == ord("B"):
                self.restart_backend()
        return False

    def move_selection(self, delta: int) -> None:
        max_items = {
            "users": len(self.users),
            "containers": len(self.containers),
            "jobs": len(self.jobs),
            "audit": len(self.audit_calls),
        }.get(self.screen.key, 0)
        if max_items:
            self.selected = max(0, min(max_items - 1, self.selected + delta))

    def refresh(self, *, force: bool = False) -> None:
        if not force and time.time() - self.last_refresh < 0.5:
            return
        self.clear_message()
        try:
            if self.screen.key == "dashboard":
                self.status = self.client.status().get("status", {})
            elif self.screen.key == "users":
                self.users = self.client.users().get("users", [])
            elif self.screen.key == "containers":
                self.containers = self.client.containers().get("containers", [])
            elif self.screen.key == "jobs":
                self.jobs = self.client.jobs().get("jobs", [])
            elif self.screen.key == "logs":
                self.refresh_logs()
            elif self.screen.key == "audit":
                self.refresh_audit()
            elif self.screen.key == "system":
                self.status = self.client.status().get("status", {})
                self.jobs = self.client.jobs().get("jobs", [])
            self.last_refresh = time.time()
        except ApiError as exc:
            self.error = f"API: {exc}"

    def refresh_logs(self) -> None:
        self.logs = self.client.logs(self.logs_source).get("logs", {}).get("lines", [])

    def refresh_audit(self) -> None:
        user_id = self.audit_user_filter.strip() or None
        self.audit_calls = self.client.audit(user_id=user_id).get("tool_calls", [])

    def provision_wizard(self) -> None:
        slug = self.prompt("Slug nuevo usuario (a-z, 0-9, guion)", "")
        if not slug:
            return
        display = self.prompt("Nombre visible", slug)
        role = self.prompt("Rol", "employee") or "employee"
        password = self.prompt_secret("Password opcional (vacio=genera)")
        payload: dict[str, Any] = {"slug": slug, "display_name": display or slug, "role": role}
        if password:
            payload["password"] = password
        if not self.confirm(f"Provisionar usuario/container laia-{slug}?"):
            return
        try:
            job = self.client.provision_user(payload)
            self.message = f"Job provision-user iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"provision fallo: {exc}"

    def selected_user_slug(self) -> str | None:
        if not self.users:
            self.error = "No hay usuarios"
            return None
        row = self.users[max(0, min(self.selected, len(self.users) - 1))]
        return str(row.get("username") or "")

    def rebuild_selected_user(self) -> None:
        slug = self.selected_user_slug()
        if not slug or not self.confirm(f"Recrear container de {slug}?"):
            return
        try:
            job = self.client.rebuild_user(slug)
            self.message = f"Job rebuild-user iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"rebuild fallo: {exc}"

    def delete_selected_user(self) -> None:
        slug = self.selected_user_slug()
        if not slug or not self.confirm(f"Desactivar {slug}, borrar container y bind mount?"):
            return
        try:
            job = self.client.delete_user(slug)
            self.message = f"Job delete-user iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"delete fallo: {exc}"

    def selected_container_name(self) -> str | None:
        if not self.containers:
            self.error = "No hay containers"
            return None
        row = self.containers[max(0, min(self.selected, len(self.containers) - 1))]
        return str(row.get("name") or "")

    def restart_selected_container(self) -> None:
        name = self.selected_container_name()
        if not name or not self.confirm(f"Reiniciar container {name}?"):
            return
        try:
            job = self.client.restart_container(name)
            self.message = f"Job container-restart iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"restart fallo: {exc}"

    def snapshot_selected_container(self) -> None:
        name = self.selected_container_name()
        if not name:
            return
        default = f"snap-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
        snap = self.prompt("Nombre snapshot", default)
        if not snap or not self.confirm(f"Snapshot {name}:{snap}?"):
            return
        try:
            job = self.client.snapshot_container(name, snap)
            self.message = f"Job snapshot iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"snapshot fallo: {exc}"

    def restore_selected_container(self) -> None:
        name = self.selected_container_name()
        if not name:
            return
        snap = self.prompt("Snapshot a restaurar", "")
        if not snap or not self.confirm(f"Restaurar {name} desde {snap}?"):
            return
        try:
            job = self.client.restore_container(name, snap)
            self.message = f"Job restore iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"restore fallo: {exc}"

    def show_selected_job(self) -> None:
        if not self.jobs:
            return
        job_id = str(self.jobs[self.selected].get("id", ""))
        if not job_id:
            return
        try:
            job = self.client.job(job_id).get("job", {})
        except ApiError as exc:
            self.error = f"job detalle fallo: {exc}"
            return
        lines = [
            f"Job {job.get('id')}",
            f"kind={job.get('kind')} status={job.get('status')} progress={job.get('progress')}%",
            f"created={job.get('created_at')} started={job.get('started_at')} finished={job.get('finished_at')}",
            "",
            "Params:",
            json.dumps(job.get("params"), indent=2, ensure_ascii=False),
            "",
            "Result:",
            json.dumps(job.get("result"), indent=2, ensure_ascii=False),
            "",
            "Error:",
            _short(job.get("error")),
            "",
            "Log tail:",
            *job.get("log_tail", []),
        ]
        self.show_text("Detalle job", lines)

    def refresh_oauth(self) -> None:
        if not self.confirm("Re-pushear auth.json al container laia-agora?"):
            return
        try:
            result = self.client.refresh_oauth()
            self.message = f"refresh-oauth OK: {result.get('result', {}).get('target', '')}"
        except ApiError as exc:
            self.error = f"refresh-oauth fallo: {exc}"

    def restart_backend(self) -> None:
        if not self.confirm("Reiniciar agora-backend.service? Perderas esta conexion unos segundos."):
            return
        try:
            job = self.client.restart_backend()
            self.message = f"Job restart-backend iniciado: {job.get('job_id')}"
            self.screen_idx = 3
            self.refresh(force=True)
        except ApiError as exc:
            self.error = f"restart-backend fallo: {exc}"

    def draw(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        if height < 18 or width < 80:
            self.add(0, 0, "Terminal demasiado pequena. Minimo recomendado: 80x18.", curses.A_BOLD)
            self.stdscr.refresh()
            return
        self.draw_header(width)
        self.draw_tabs(width)
        content_top = 4
        if self.screen.key == "dashboard":
            self.draw_dashboard(content_top, height, width)
        elif self.screen.key == "users":
            self.draw_users(content_top, height, width)
        elif self.screen.key == "containers":
            self.draw_containers(content_top, height, width)
        elif self.screen.key == "jobs":
            self.draw_jobs(content_top, height, width)
        elif self.screen.key == "logs":
            self.draw_logs(content_top, height, width)
        elif self.screen.key == "audit":
            self.draw_audit(content_top, height, width)
        elif self.screen.key == "system":
            self.draw_system(content_top, height, width)
        self.draw_footer(height, width)
        self.stdscr.refresh()

    def draw_header(self, width: int) -> None:
        title = f" AGORA Control Center  {self.client.api_url} "
        self.add(0, 0, title[:width].ljust(width), curses.color_pair(5) | curses.A_BOLD)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.add(0, max(0, width - len(timestamp) - 1), f" {timestamp}", curses.color_pair(5))

    def draw_tabs(self, width: int) -> None:
        x = 0
        for idx, screen in enumerate(SCREENS):
            label = f" {idx + 1}:{screen.title} "
            attr = curses.A_REVERSE | curses.A_BOLD if idx == self.screen_idx else curses.A_NORMAL
            self.add(2, x, label, attr)
            x += len(label) + 1
            if x >= width:
                break

    def draw_dashboard(self, top: int, height: int, width: int) -> None:
        if not self.status:
            self.add(top, 2, "Pulsa r para cargar estado.")
            return
        health = self.status.get("health", {})
        auth = self.status.get("auth", {})
        containers = self.status.get("containers", {})
        users = self.status.get("users", {})
        agents = self.status.get("agents", {})
        self.panel(top, 2, 9, width // 2 - 3, "Estado global")
        self.kv(top + 2, 4, "Backend", "UP" if health.get("ok") else "DOWN")
        self.kv(top + 3, 4, "Auth JSON", f"{auth.get('status')} ready={auth.get('ready')}")
        self.kv(top + 4, 4, "LXD backend", "ok" if health.get("lxd_available") else "sin acceso")
        self.kv(top + 5, 4, "Usuarios", f"{users.get('active', 0)} activos / {users.get('total', 0)} total")
        self.kv(top + 6, 4, "Agentes", f"{agents.get('running', 0)} running / {agents.get('registered', 0)} registrados")
        self.kv(top + 7, 4, "Containers", f"{containers.get('running', 0)} running / {containers.get('total', 0)} vistos")

        self.panel(top, width // 2 + 1, 9, width // 2 - 3, "Alertas")
        error = containers.get("error")
        if error:
            self.wrap(top + 2, width // 2 + 3, width // 2 - 7, f"LXD: {error}", curses.color_pair(3))
        else:
            self.add(top + 2, width // 2 + 3, "Sin errores de containers.", curses.color_pair(2))
        recent = self.status.get("recent_errors", [])
        if recent:
            self.add(top + 5, width // 2 + 3, "Errores recientes:", curses.color_pair(4))
            for offset, line in enumerate(recent[:2]):
                self.trunc(top + 6 + offset, width // 2 + 3, width // 2 - 7, line)

        items = containers.get("items", [])
        self.add(top + 11, 2, "Containers detectados", curses.A_BOLD)
        self.table(top + 13, 2, height - top - 16, width - 4, ["Name", "State", "IP", "User"], [
            [c.get("name"), c.get("state"), c.get("ipv4"), c.get("username")]
            for c in items
        ])

    def draw_users(self, top: int, height: int, width: int) -> None:
        self.add(top, 2, "p provisionar  b rebuild  d borrar/desactivar  r refrescar", curses.color_pair(1))
        rows = [[u.get("username"), u.get("role"), u.get("container_state"), u.get("container_ip"), u.get("llm_provider"), u.get("last_chat")]
                for u in self.users]
        self.table(top + 2, 2, height - top - 5, width - 4, ["User", "Role", "Container", "IP", "LLM", "Last chat"], rows, self.selected)

    def draw_containers(self, top: int, height: int, width: int) -> None:
        self.add(top, 2, "r refrescar  R restart  s snapshot  o restore", curses.color_pair(1))
        rows = [[c.get("name"), c.get("state"), c.get("ipv4"), c.get("username"), c.get("registered_status")]
                for c in self.containers]
        self.table(top + 2, 2, height - top - 5, width - 4, ["Name", "State", "IP", "User", "Registered"], rows, self.selected)

    def draw_jobs(self, top: int, height: int, width: int) -> None:
        self.add(top, 2, "Enter detalle  r refrescar", curses.color_pair(1))
        rows = [[j.get("id"), j.get("kind"), _status_text(j), _format_age(j.get("created_at")), j.get("error")]
                for j in self.jobs]
        self.table(top + 2, 2, height - top - 5, width - 4, ["ID", "Kind", "Status", "Age", "Error"], rows, self.selected)

    def draw_logs(self, top: int, height: int, width: int) -> None:
        self.add(top, 2, f"Fuente: {self.logs_source}   n cambiar fuente  l recargar", curses.color_pair(1))
        for idx, line in enumerate(self.logs[: height - top - 5]):
            self.trunc(top + 2 + idx, 2, width - 4, line)

    def draw_audit(self, top: int, height: int, width: int) -> None:
        label = self.audit_user_filter or "todos"
        self.add(top, 2, f"u filtrar user_id ({label})  r refrescar", curses.color_pair(1))
        rows = []
        for call in self.audit_calls:
            rows.append([
                call.get("ts"),
                call.get("user_id"),
                call.get("agent_slug"),
                call.get("phase") or call.get("msg"),
                call.get("tool"),
                call.get("duration_ms"),
            ])
        self.table(top + 2, 2, height - top - 5, width - 4, ["TS", "User", "Agent", "Phase", "Tool", "ms"], rows, self.selected)

    def draw_system(self, top: int, height: int, width: int) -> None:
        self.add(top, 2, "a refresh OAuth  B restart backend  r refrescar", curses.color_pair(1))
        auth = self.status.get("auth", {})
        health = self.status.get("health", {})
        self.panel(top + 2, 2, 9, width - 4, "Sistema")
        self.kv(top + 4, 4, "API", self.client.api_url)
        self.kv(top + 5, 4, "Data dir", health.get("data_dir"))
        self.kv(top + 6, 4, "Auth JSON", f"{auth.get('path')} status={auth.get('status')} ready={auth.get('ready')}")
        self.kv(top + 7, 4, "Default LLM", health.get("default_llm_provider"))
        self.kv(top + 8, 4, "LXD disponible", health.get("lxd_available"))
        recent = self.jobs[: min(5, len(self.jobs))]
        self.add(top + 12, 2, "Ultimos jobs", curses.A_BOLD)
        self.table(top + 14, 2, height - top - 17, width - 4, ["ID", "Kind", "Status", "Age"], [
            [j.get("id"), j.get("kind"), _status_text(j), _format_age(j.get("created_at"))] for j in recent
        ])

    def draw_footer(self, height: int, width: int) -> None:
        line = self.error or self.message or "Tab/flechas cambia vista. ? ayuda. q salir."
        attr = curses.color_pair(4) if self.error else curses.color_pair(2) if self.message else curses.A_DIM
        self.add(height - 1, 0, line[:width].ljust(width), attr)

    def show_help(self) -> None:
        lines = [
            "AGORA Control Center",
            "",
            "Navegacion:",
            "  1-7 / Tab / flechas izquierda-derecha  cambiar vista",
            "  flechas arriba-abajo                    mover seleccion",
            "  r                                      refrescar vista",
            "  q                                      salir",
            "",
            "Usuarios:",
            "  p provisionar usuario + container",
            "  b rebuild del container del usuario",
            "  d soft-delete + borrar container/bind mount",
            "",
            "Containers:",
            "  R restart, s snapshot, o restore",
            "",
            "Jobs:",
            "  Enter muestra detalle y tail de log",
            "",
            "Sistema:",
            "  a refresh OAuth auth.json",
            "  B restart agora-backend",
        ]
        self.show_text("Ayuda", lines)

    def show_text(self, title: str, lines: list[str]) -> None:
        offset = 0
        while True:
            self.stdscr.erase()
            height, width = self.stdscr.getmaxyx()
            self.add(0, 0, f" {title} ".ljust(width), curses.color_pair(5) | curses.A_BOLD)
            visible = lines[offset : offset + height - 3]
            for idx, line in enumerate(visible):
                self.trunc(idx + 2, 2, width - 4, line)
            self.add(height - 1, 0, "Esc/Enter volver  Up/Down scroll".ljust(width), curses.A_DIM)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (27, 10, 13, curses.KEY_ENTER):
                return
            if key == curses.KEY_DOWN:
                offset = min(max(0, len(lines) - 1), offset + 1)
            elif key == curses.KEY_UP:
                offset = max(0, offset - 1)

    def prompt(self, label: str, default: str = "") -> str:
        height, width = self.stdscr.getmaxyx()
        prompt = f"{label}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        self.add(height - 2, 0, " " * (width - 1))
        self.add(height - 2, 0, prompt[: width - 1], curses.A_BOLD)
        curses.echo()
        curses.curs_set(1)
        try:
            raw = self.stdscr.getstr(height - 2, min(len(prompt), width - 2), max(1, width - len(prompt) - 2))
        finally:
            curses.noecho()
            curses.curs_set(0)
        value = raw.decode("utf-8", errors="replace").strip()
        return value or default

    def prompt_secret(self, label: str) -> str:
        height, width = self.stdscr.getmaxyx()
        prompt = f"{label}: "
        self.add(height - 2, 0, " " * (width - 1))
        self.add(height - 2, 0, prompt[: width - 1], curses.A_BOLD)
        curses.noecho()
        curses.curs_set(1)
        try:
            raw = self.stdscr.getstr(height - 2, min(len(prompt), width - 2), max(1, width - len(prompt) - 2))
        finally:
            curses.curs_set(0)
        return raw.decode("utf-8", errors="replace").strip()

    def confirm(self, question: str) -> bool:
        answer = self.prompt(f"{question} (yes/no)", "no").lower()
        return answer in {"y", "yes", "s", "si"}

    def clear_message(self) -> None:
        self.error = ""
        self.message = ""

    def panel(self, y: int, x: int, h: int, w: int, title: str) -> None:
        if h < 3 or w < 8:
            return
        try:
            for col in range(x, min(x + w, self.stdscr.getmaxyx()[1] - 1)):
                self.stdscr.addch(y, col, curses.ACS_HLINE)
                self.stdscr.addch(y + h - 1, col, curses.ACS_HLINE)
            for row in range(y, min(y + h, self.stdscr.getmaxyx()[0] - 1)):
                self.stdscr.addch(row, x, curses.ACS_VLINE)
                self.stdscr.addch(row, x + w - 1, curses.ACS_VLINE)
            self.stdscr.addch(y, x, curses.ACS_ULCORNER)
            self.stdscr.addch(y, x + w - 1, curses.ACS_URCORNER)
            self.stdscr.addch(y + h - 1, x, curses.ACS_LLCORNER)
            self.stdscr.addch(y + h - 1, x + w - 1, curses.ACS_LRCORNER)
            self.add(y, x + 2, f" {title} ", curses.A_BOLD)
        except curses.error:
            pass

    def kv(self, y: int, x: int, key: str, value: Any) -> None:
        self.add(y, x, f"{key:16s}", curses.A_BOLD)
        self.trunc(y, x + 18, max(10, self.stdscr.getmaxyx()[1] - x - 20), _short(value))

    def table(
        self,
        y: int,
        x: int,
        h: int,
        w: int,
        headers: list[str],
        rows: list[list[Any]],
        selected: int | None = None,
    ) -> None:
        if h <= 0 or w <= 10:
            return
        col_count = len(headers)
        widths = self.column_widths(w, headers)
        line = " ".join(str(headers[i])[: widths[i]].ljust(widths[i]) for i in range(col_count))
        self.trunc(y, x, w, line, curses.A_BOLD)
        self.trunc(y + 1, x, w, "-" * min(w, len(line)), curses.A_DIM)
        for idx, row in enumerate(rows[: max(0, h - 2)]):
            parts = []
            for col in range(col_count):
                value = row[col] if col < len(row) else ""
                parts.append(_short(value)[: widths[col]].ljust(widths[col]))
            attr = curses.A_REVERSE if selected is not None and idx == selected else curses.A_NORMAL
            self.trunc(y + 2 + idx, x, w, " ".join(parts), attr)
        if not rows:
            self.add(y + 2, x, "(sin datos)", curses.A_DIM)

    def column_widths(self, total: int, headers: list[str]) -> list[int]:
        if not headers:
            return []
        base = max(8, (total - len(headers) + 1) // len(headers))
        widths = [base for _ in headers]
        if headers[0].lower() in {"id", "ts"}:
            widths[0] = min(36, max(16, base + 8))
        remaining = total - sum(widths) - (len(headers) - 1)
        widths[-1] = max(8, widths[-1] + remaining)
        return widths

    def wrap(self, y: int, x: int, w: int, text: str, attr: int = curses.A_NORMAL) -> None:
        for idx, line in enumerate(textwrap.wrap(text, width=max(10, w))[:4]):
            self.trunc(y + idx, x, w, line, attr)

    def trunc(self, y: int, x: int, w: int, text: Any, attr: int = curses.A_NORMAL) -> None:
        value = _short(text)
        self.add(y, x, value[:w].ljust(w), attr)

    def add(self, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
        try:
            height, width = self.stdscr.getmaxyx()
            if y < 0 or y >= height or x < 0 or x >= width:
                return
            self.stdscr.addstr(y, x, text[: max(0, width - x - 1)], attr)
        except curses.error:
            pass


def print_status(client: AgoraAdminClient) -> int:
    try:
        status = client.status().get("status", {})
    except ApiError as exc:
        print(f"ERROR: {exc}")
        return 1
    health = status.get("health", {})
    auth = status.get("auth", {})
    containers = status.get("containers", {})
    users = status.get("users", {})
    agents = status.get("agents", {})
    print("AGORA Control Center")
    print(f"API:        {client.api_url}")
    print(f"Backend:    {'UP' if health.get('ok') else 'DOWN'}")
    print(f"Auth JSON:  {auth.get('status')} ready={auth.get('ready')} path={auth.get('path')}")
    print(f"Users:      {users.get('active', 0)} active / {users.get('total', 0)} total")
    print(f"Agents:     {agents.get('running', 0)} running / {agents.get('registered', 0)} registered")
    print(f"Containers: {containers.get('running', 0)} running / {containers.get('total', 0)} visible")
    if containers.get("error"):
        print(f"LXD error:  {containers.get('error')}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AGORA interactive admin TUI")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"AGORA API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--token", default=os.environ.get("AGORA_ADMIN_TOKEN"), help="Admin bearer token")
    parser.add_argument("--username", default=os.environ.get("AGORA_ADMIN_USERNAME"), help="Admin username")
    parser.add_argument("--password", default=os.environ.get("AGORA_ADMIN_PASSWORD"), help="Admin password")
    parser.add_argument("--print-status", action="store_true", help="Print one status snapshot and exit")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = AgoraAdminClient(args.api_url, token=args.token, timeout=args.timeout)
    if args.username and args.password and not client.token:
        client.login(args.username, args.password)
    if args.print_status:
        if not client.token:
            username = args.username or input("Admin username: ")
            password = args.password or getpass("Admin password: ")
            client.login(username, password)
        return print_status(client)
    curses.wrapper(lambda stdscr: ControlCenterTUI(stdscr, client).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
