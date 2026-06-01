#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git-manager.py — Gestor de git/GitHub para workspaces LAIA.

Uso como TUI:     python git-manager.py
Uso como CLI:     python git-manager.py --list | --status WS | --init WS | --push WS
Uso como módulo:  from git_manager import WorkspaceGitManager
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ─── Constantes ───────────────────────────────────────────────────────────────

from _laia_runtime_paths import laia_root, workspaces_dir

LAIA_ROOT = laia_root()
WORKSPACES_DIR = workspaces_dir()
INIT_SCRIPT = LAIA_ROOT / "scripts" / "init-workspace-git.sh"

# Workspaces whose code lives outside their own workspaces/X/code/ folder
EXCLUDED_WORKSPACES = {"laia-arch"}

# ─── WorkspaceGitManager ──────────────────────────────────────────────────────

class WorkspaceGitManager:
    """API programática para gestión de git/GitHub en workspaces LAIA."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self._gh_user: str | None = None

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _ws_path(self, name: str) -> Path:
        p = WORKSPACES_DIR / name
        if not p.is_dir():
            raise ValueError(f"Workspace '{name}' no encontrado en {WORKSPACES_DIR}")
        return p

    def _db_path(self, ws_name: str) -> Path:
        return self._ws_path(ws_name) / "workspace.db"

    def _read_meta(self, ws_name: str) -> dict[str, str]:
        db = self._db_path(ws_name)
        if not db.exists():
            return {}
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute("SELECT key, value FROM workspace_meta").fetchall()
            return dict(rows)
        except Exception:
            return {}
        finally:
            conn.close()

    def _write_meta(self, ws_name: str, key: str, value: str) -> None:
        db = self._db_path(ws_name)
        if not db.exists():
            raise FileNotFoundError(f"workspace.db no encontrado para '{ws_name}'")
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO workspace_meta(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def _run(self, cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def _gh_user_login(self) -> str | None:
        if self._gh_user is None:
            rc, out, _ = self._run(["gh", "api", "user", "--jq", ".login"])
            self._gh_user = out if rc == 0 else None
        return self._gh_user

    def _ensure_git_credentials(self) -> None:
        """Configura gh como credential helper de git (idempotente)."""
        self._run(["gh", "auth", "setup-git"])

    def _is_excluded(self, ws_name: str) -> bool:
        return ws_name in EXCLUDED_WORKSPACES

    def _detect_git_topology(self, ws_name: str) -> dict:
        """
        Detecta topología git de un workspace.
        Devuelve: {"topology": str, "repos": [{"path", "rel_path", "is_root", "name"}]}
        Topologías: excluded | none | root | subprojects | mixed
        """
        if self._is_excluded(ws_name):
            return {"topology": "excluded", "repos": []}

        ws_path = self._ws_path(ws_name)
        code_dir = ws_path / "code"

        if not code_dir.is_dir():
            return {"topology": "none", "repos": []}

        repos: list[dict] = []
        has_root = (code_dir / ".git").is_dir()
        has_subs = False

        if has_root:
            repos.append({
                "path": code_dir,
                "rel_path": "code/",
                "is_root": True,
                "name": f"{ws_name}-code",
            })

        for subdir in sorted(code_dir.iterdir()):
            if subdir.is_dir() and (subdir / ".git").is_dir():
                has_subs = True
                repos.append({
                    "path": subdir,
                    "rel_path": f"code/{subdir.name}/",
                    "is_root": False,
                    "name": subdir.name,
                })

        if not has_root and not has_subs:
            topology = "none"
        elif has_root and not has_subs:
            topology = "root"
        elif not has_root and has_subs:
            topology = "subprojects"
        else:
            topology = "mixed"

        return {"topology": topology, "repos": repos}

    def _git_status_for_repo(self, repo_path: Path) -> dict:
        status: dict[str, Any] = {
            "branch": "main",
            "clean": True,
            "staged": 0,
            "unstaged": 0,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "has_remote": False,
            "remote_url": None,
            "last_commit": None,
            "last_commit_msg": None,
        }

        rc, out, _ = self._run(["git", "branch", "--show-current"], cwd=repo_path)
        if rc == 0 and out:
            status["branch"] = out

        rc, out, _ = self._run(["git", "status", "--porcelain=v1"], cwd=repo_path)
        if rc == 0:
            for line in out.splitlines():
                if line.startswith("??"):
                    status["untracked"] += 1
                elif line and line[0] != " ":
                    status["staged"] += 1
                elif line and len(line) > 1 and line[1] != " ":
                    status["unstaged"] += 1
            status["clean"] = (
                status["staged"] == 0
                and status["unstaged"] == 0
                and status["untracked"] == 0
            )

        rc, out, _ = self._run(["git", "remote", "get-url", "origin"], cwd=repo_path)
        if rc == 0:
            status["has_remote"] = True
            status["remote_url"] = out

        if status["has_remote"]:
            branch = status["branch"]
            rc, out, _ = self._run(
                ["git", "rev-list", "--left-right", "--count",
                 f"origin/{branch}...HEAD"],
                cwd=repo_path,
            )
            if rc == 0 and "\t" in out:
                behind, ahead = out.split("\t")
                try:
                    status["behind"] = int(behind.strip())
                    status["ahead"] = int(ahead.strip())
                except ValueError:
                    pass

        rc, out, _ = self._run(
            ["git", "log", "-1", "--format=%ci|||%s"], cwd=repo_path
        )
        if rc == 0 and "|||" in out:
            ts, msg = out.split("|||", 1)
            status["last_commit"] = ts.strip()
            status["last_commit_msg"] = msg.strip()

        return status

    # ── API pública ────────────────────────────────────────────────────────────

    def get_status(self, ws_name: str) -> dict:
        try:
            topo = self._detect_git_topology(ws_name)
            meta = self._read_meta(ws_name)
            repos_out = []
            for repo_info in topo["repos"]:
                git_state = self._git_status_for_repo(repo_info["path"])
                rk = repo_info["name"]
                suffix = f".{rk}" if not repo_info["is_root"] else ""
                github_repo = (
                    meta.get(f"git.github_repo{suffix}")
                    or meta.get("git.github_repo")
                    or rk
                )
                repos_out.append({
                    "name": rk,
                    "path": str(repo_info["path"]),
                    "rel_path": repo_info["rel_path"],
                    "is_root": repo_info["is_root"],
                    "git": git_state,
                    "github_repo": github_repo,
                    "visibility": (
                        meta.get(f"git.visibility{suffix}")
                        or meta.get("git.visibility")
                        or "private"
                    ),
                    "last_sync": (
                        meta.get(f"git.last_sync{suffix}")
                        or meta.get("git.last_sync")
                    ),
                })
            return {
                "ok": True,
                "workspace": ws_name,
                "excluded": topo["topology"] == "excluded",
                "topology": topo["topology"],
                "repos": repos_out,
                "meta": meta,
            }
        except Exception as e:
            return {"ok": False, "workspace": ws_name, "error": str(e)}

    def list_all(self) -> list[dict]:
        results = []
        for ws_dir in sorted(WORKSPACES_DIR.iterdir()):
            if ws_dir.is_dir():
                results.append(self.get_status(ws_dir.name))
        return results

    def init_git(self, ws_name: str) -> dict:
        if self._is_excluded(ws_name):
            return {
                "ok": False,
                "message": f"'{ws_name}' está excluido: su código se gestiona en el repo raíz de LAIA.",
            }

        topo = self._detect_git_topology(ws_name)
        if topo["topology"] != "none":
            return {
                "ok": True,
                "message": (
                    f"Ya existe git en '{ws_name}' (topology: {topo['topology']}). "
                    f"Repos: {[r['name'] for r in topo['repos']]}"
                ),
                "initialized": [],
                "topology": topo["topology"],
            }

        code_dir = self._ws_path(ws_name) / "code"
        if not code_dir.is_dir():
            return {"ok": False, "message": f"No existe code/ en workspace '{ws_name}'"}

        rc, out, err = self._run(["bash", str(INIT_SCRIPT), ws_name])
        if rc != 0:
            return {"ok": False, "message": f"init-workspace-git.sh falló: {err}"}

        return {
            "ok": True,
            "message": f"git inicializado en {ws_name}/code/",
            "initialized": [str(code_dir)],
            "output": out,
        }

    def configure_repo(
        self,
        ws_name: str,
        repo_name: str | None = None,
        visibility: str | None = None,
        remote_url: str | None = None,
        target_repo: str | None = None,
    ) -> dict:
        if self._is_excluded(ws_name):
            return {"ok": False, "message": f"'{ws_name}' está excluido de la gestión git."}

        changed = []
        try:
            suffix = f".{target_repo}" if target_repo else ""
            if repo_name is not None:
                self._write_meta(ws_name, f"git.github_repo{suffix}", repo_name)
                changed.append(f"github_repo{suffix} = {repo_name}")
            if visibility is not None:
                if visibility not in ("private", "public"):
                    return {"ok": False, "message": "visibility debe ser 'private' o 'public'"}
                self._write_meta(ws_name, f"git.visibility{suffix}", visibility)
                changed.append(f"visibility{suffix} = {visibility}")
            if remote_url is not None:
                self._write_meta(ws_name, f"git.remote_url{suffix}", remote_url)
                changed.append(f"remote_url{suffix} = {remote_url}")
            return {
                "ok": True,
                "message": f"Configuración actualizada: {', '.join(changed)}",
                "changed": changed,
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def push_to_github(
        self,
        ws_name: str,
        target_repo_name: str | None = None,
        commit_message: str | None = None,
    ) -> dict:
        if self._is_excluded(ws_name):
            return {"ok": False, "message": f"'{ws_name}' está excluido de la gestión git."}

        topo = self._detect_git_topology(ws_name)
        if topo["topology"] == "none":
            return {
                "ok": False,
                "message": f"No hay repos git en '{ws_name}'. Ejecuta init_git primero.",
            }

        gh_user = self._gh_user_login()
        if not gh_user:
            return {"ok": False, "message": "gh CLI no autenticado. Ejecuta: gh auth login"}

        repos_to_push = topo["repos"]
        if target_repo_name:
            repos_to_push = [r for r in repos_to_push if r["name"] == target_repo_name]
            if not repos_to_push:
                return {"ok": False, "message": f"Repo '{target_repo_name}' no encontrado"}

        meta = self._read_meta(ws_name)
        msg = commit_message or f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        results = []
        for repo_info in repos_to_push:
            results.append(self._push_single_repo(ws_name, repo_info, meta, gh_user, msg))

        all_ok = all(r["ok"] for r in results)
        return {
            "ok": all_ok,
            "message": f"Push completado: {sum(r['ok'] for r in results)}/{len(results)} repos",
            "repos": results,
        }

    def _push_single_repo(
        self,
        ws_name: str,
        repo_info: dict,
        meta: dict,
        gh_user: str,
        commit_msg: str,
    ) -> dict:
        repo_path = repo_info["path"]
        repo_key = repo_info["name"]
        suffix = "" if repo_info["is_root"] else f".{repo_key}"

        github_repo = (
            meta.get(f"git.github_repo{suffix}")
            or meta.get("git.github_repo")
            or repo_key
        )
        visibility = (
            meta.get(f"git.visibility{suffix}")
            or meta.get("git.visibility")
            or "private"
        )

        try:
            # Stage y commit si hay cambios
            self._run(["git", "add", "-A"], cwd=repo_path)
            rc, _, _ = self._run(["git", "diff", "--cached", "--quiet"], cwd=repo_path)
            if rc != 0:
                self._run(["git", "commit", "-m", commit_msg, "--quiet"], cwd=repo_path)

            # Asegurar rama main
            rc, branch, _ = self._run(["git", "branch", "--show-current"], cwd=repo_path)
            if not branch:
                self._run(["git", "checkout", "-b", "main"], cwd=repo_path)
                branch = "main"
            elif branch == "master":
                self._run(["git", "branch", "-m", "master", "main"], cwd=repo_path)
                branch = "main"

            # Gestionar remote
            rc_remote, _, _ = self._run(
                ["git", "remote", "get-url", "origin"], cwd=repo_path
            )
            has_remote = rc_remote == 0

            # Configurar gh como credential helper antes de cualquier push
            self._ensure_git_credentials()

            if not has_remote:
                rc_view, _, _ = self._run(
                    ["gh", "repo", "view", f"{gh_user}/{github_repo}"]
                )
                if rc_view != 0:
                    # Crear repo en GitHub (sin --push, lo hacemos nosotros)
                    vis_flag = "--private" if visibility == "private" else "--public"
                    rc_create, _, err = self._run([
                        "gh", "repo", "create", github_repo,
                        vis_flag,
                        "--description", f"LAIA workspace: {ws_name}",
                    ])
                    if rc_create != 0:
                        return {"ok": False, "name": repo_key, "error": err}

                remote_url = f"https://github.com/{gh_user}/{github_repo}.git"
                self._run(["git", "remote", "add", "origin", remote_url], cwd=repo_path)
                self._write_meta(ws_name, f"git.remote_url{suffix}", remote_url)

            rc_push, _, err = self._run(
                ["git", "push", "-u", "origin", branch, "--quiet"], cwd=repo_path
            )
            if rc_push != 0:
                return {"ok": False, "name": repo_key, "error": err}

            self._write_meta(
                ws_name,
                f"git.last_sync{suffix}",
                datetime.now(timezone.utc).isoformat(),
            )
            return {"ok": True, "name": repo_key, "action": "pushed"}

        except Exception as e:
            return {"ok": False, "name": repo_key, "error": str(e)}

    def pull_from_github(
        self, ws_name: str, target_repo_name: str | None = None
    ) -> dict:
        if self._is_excluded(ws_name):
            return {"ok": False, "message": f"'{ws_name}' está excluido de la gestión git."}

        topo = self._detect_git_topology(ws_name)
        if topo["topology"] == "none":
            return {"ok": False, "message": "No hay repos git"}

        repos = topo["repos"]
        if target_repo_name:
            repos = [r for r in repos if r["name"] == target_repo_name]

        results = []
        for repo_info in repos:
            rc_remote, _, _ = self._run(
                ["git", "remote", "get-url", "origin"], cwd=repo_info["path"]
            )
            if rc_remote != 0:
                results.append({
                    "ok": False, "name": repo_info["name"], "error": "sin remote configurado"
                })
                continue
            rc, out, err = self._run(["git", "pull", "--quiet"], cwd=repo_info["path"])
            results.append({
                "ok": rc == 0,
                "name": repo_info["name"],
                "output": out,
                "error": err if rc != 0 else None,
            })

        return {"ok": all(r["ok"] for r in results), "repos": results}


# ─── GitManagerTUI ────────────────────────────────────────────────────────────

class GitManagerTUI:
    """TUI interactiva para gestionar git/GitHub en workspaces LAIA."""

    def __init__(self):
        self.console = Console()
        self.manager = WorkspaceGitManager(quiet=True)
        self._cache: list[dict] | None = None
        self._cache_ts: float = 0.0

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _clear(self):
        self.console.clear()

    def _header(self, subtitle: str = ""):
        title = Text("LAIA  ", style="bold white")
        title.append("git-manager", style="bold cyan")
        if subtitle:
            title.append(f"  ›  {subtitle}", style="dim white")
        self.console.print(Panel(title, style="blue", padding=(0, 2)))

    def _ok_panel(self, msg: str):
        self.console.print(Panel(f"[green]{msg}[/green]", border_style="green"))

    def _err_panel(self, msg: str):
        self.console.print(Panel(f"[red]{msg}[/red]", border_style="red"))

    def _refresh_cache(self, force: bool = False):
        if force or self._cache is None or (time.time() - self._cache_ts) > 30:
            self.console.print("[dim]Cargando estado de workspaces...[/dim]")
            self._cache = self.manager.list_all()
            self._cache_ts = time.time()

    def _status_badge(self, topology: str, repos: list[dict]) -> Text:
        if topology == "excluded":
            return Text("LAIA root", style="dim blue")
        if topology == "none":
            return Text("sin git", style="dim")
        has_dirty = any(not r["git"]["clean"] for r in repos)
        has_unsynced = any(
            not r["git"]["has_remote"] or r["git"]["ahead"] > 0 for r in repos
        )
        if has_dirty:
            return Text("cambios", style="yellow bold")
        if has_unsynced:
            return Text("sin sync", style="yellow")
        return Text("ok", style="green bold")

    # ── Pantalla dashboard ─────────────────────────────────────────────────────

    def screen_dashboard(self) -> str:
        self._clear()
        self._header()
        self._refresh_cache()

        table = Table(
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
            expand=True,
        )
        table.add_column("#", style="bold", width=3, justify="right")
        table.add_column("Workspace", style="bold white", min_width=15)
        table.add_column("Estado", min_width=12)
        table.add_column("Repos git", min_width=22)
        table.add_column("GitHub", min_width=20)
        table.add_column("Rama", min_width=8)
        table.add_column("Último sync", min_width=17)

        ws_list: list[str] = []
        selectable: list[str] = []

        for i, ws in enumerate(self._cache or [], 1):
            ws_name = ws["workspace"]
            ws_list.append(ws_name)

            if not ws["ok"]:
                table.add_row(
                    str(i), ws_name,
                    Text("error", style="red bold"),
                    ws.get("error", ""), "", "", "",
                )
                continue

            topology = ws.get("topology", "none")
            repos = ws.get("repos", [])
            excluded = ws.get("excluded", False)

            status_badge = self._status_badge(topology, repos)

            if excluded:
                repos_cell = Text("→ /LAIA (root)", style="dim blue")
                gh_cell = Text("—", style="dim")
                branch_cell = "—"
                last_sync_str = "—"
            elif topology == "none":
                repos_cell = Text("ninguno", style="dim")
                gh_cell = Text("—", style="dim")
                branch_cell = "—"
                last_sync_str = "—"
                selectable.append(ws_name)
            else:
                selectable.append(ws_name)
                if topology == "subprojects":
                    names = ", ".join(r["name"] for r in repos)
                    repos_cell = Text(f"[subs] {names}", style="cyan")
                else:
                    repos_cell = Text(", ".join(r["name"] for r in repos))

                gh_repos = [r["github_repo"] for r in repos if r.get("github_repo")]
                gh_cell = Text(", ".join(gh_repos) if gh_repos else "—",
                               style="" if gh_repos else "dim")

                branches = list({r["git"]["branch"] for r in repos})
                branch_cell = branches[0] if len(branches) == 1 else "múltiples"

                syncs = [r["last_sync"] for r in repos if r.get("last_sync")]
                last_sync_str = max(syncs)[:16].replace("T", " ") if syncs else "—"

            table.add_row(
                str(i), ws_name, status_badge,
                repos_cell, gh_cell, branch_cell, last_sync_str,
            )

        self.console.print(table)
        self.console.print()
        self.console.print(
            "  [dim][[/dim][bold cyan]1-N[/bold cyan][dim]][/dim] seleccionar   "
            "[dim][[/dim][bold cyan]r[/bold cyan][dim]][/dim] refrescar   "
            "[dim][[/dim][bold cyan]q[/bold cyan][dim]][/dim] salir"
        )

        choice = Prompt.ask("\n  Opción").strip().lower()
        if choice == "q":
            return "q"
        if choice == "r":
            self._refresh_cache(force=True)
            return "dashboard"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(ws_list):
                selected = ws_list[idx]
                if selected in EXCLUDED_WORKSPACES:
                    self.console.print(
                        Panel(
                            f"[blue]{selected}[/blue] está excluido — su código vive en /LAIA directamente.",
                            border_style="blue",
                        )
                    )
                    Prompt.ask("  Enter para continuar")
                    return "dashboard"
                return selected
        except ValueError:
            pass
        return "dashboard"

    # ── Pantalla workspace ─────────────────────────────────────────────────────

    def screen_workspace(self, ws_name: str) -> str:
        self._clear()
        self._header(ws_name)

        status = self.manager.get_status(ws_name)
        if not status["ok"]:
            self._err_panel(status.get("error", "Error desconocido"))
            Prompt.ask("  Enter para volver")
            return "back"

        topology = status["topology"]
        repos = status["repos"]

        # Panel info
        topo_style = {"none": "dim", "root": "green", "subprojects": "cyan", "mixed": "yellow"}
        self.console.print(
            Panel(
                f"Topología: [bold {topo_style.get(topology, 'white')}]{topology}[/]   "
                f"Repos: [bold]{len(repos)}[/]",
                border_style="blue",
                padding=(0, 2),
            )
        )

        # Tabla de repos
        if repos:
            rt = Table(show_header=True, header_style="bold cyan", border_style="blue", expand=True)
            rt.add_column("Repo", style="bold")
            rt.add_column("Ruta", style="dim")
            rt.add_column("Rama", width=8)
            rt.add_column("Estado", min_width=12)
            rt.add_column("GitHub repo", min_width=18)
            rt.add_column("↑/↓", width=7)
            rt.add_column("Último sync", min_width=17)

            for r in repos:
                g = r["git"]
                if g["clean"] and g["has_remote"] and g["ahead"] == 0:
                    estado = Text("limpio", style="green")
                elif not g["clean"]:
                    parts = []
                    if g["staged"]:    parts.append(f"{g['staged']}S")
                    if g["unstaged"]:  parts.append(f"{g['unstaged']}M")
                    if g["untracked"]: parts.append(f"{g['untracked']}?")
                    estado = Text("+".join(parts), style="yellow")
                else:
                    estado = Text("sin remote", style="dim")

                ah = f"+{g['ahead']}/-{g['behind']}" if g["has_remote"] else "—"
                last_sync = (r.get("last_sync") or "—")[:16].replace("T", " ")

                rt.add_row(
                    r["name"], r["rel_path"], g["branch"],
                    estado, r.get("github_repo") or "—", ah, last_sync,
                )
            self.console.print(rt)

        # Menú de acciones
        self.console.print()
        actions = self._build_actions(topology, repos)
        for idx, (label, _) in enumerate(actions, 1):
            self.console.print(f"  [bold cyan]{idx}[/bold cyan]. {label}")
        self.console.print(f"  [bold cyan]0[/bold cyan]. Volver al dashboard")

        choice = Prompt.ask("\n  Acción").strip()
        if choice == "0":
            return "back"
        try:
            ai = int(choice) - 1
            if 0 <= ai < len(actions):
                actions[ai][1](ws_name, repos)
                self._cache = None
        except (ValueError, IndexError):
            pass

        return ws_name

    def _build_actions(
        self, topology: str, repos: list[dict]
    ) -> list[tuple[str, Any]]:
        if topology == "none":
            return [("Inicializar git en code/", self._action_init)]
        return [
            ("Push a GitHub",             self._action_push),
            ("Pull desde GitHub",         self._action_pull),
            ("Configurar repo GitHub",    self._action_configure),
            ("Abrir en GitHub (browser)", self._action_open),
        ]

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _action_init(self, ws_name: str, repos: list[dict]):
        self.console.print(f"\n  Inicializando git en [cyan]{ws_name}[/cyan]/code/...")
        result = self.manager.init_git(ws_name)
        if result["ok"]:
            self._ok_panel(result["message"])
        else:
            self._err_panel(result["message"])
        Prompt.ask("  Enter para continuar")

    def _action_push(self, ws_name: str, repos: list[dict]):
        target = None
        if len(repos) > 1:
            self.console.print("\n  Repos disponibles:")
            for i, r in enumerate(repos, 1):
                self.console.print(f"    {i}. {r['name']}")
            self.console.print("    0. Todos")
            choice = IntPrompt.ask("  ¿A cuál?", default=0)
            if choice != 0 and 1 <= choice <= len(repos):
                target = repos[choice - 1]["name"]

        msg = Prompt.ask(
            "  Mensaje commit",
            default=f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

        self.console.print("\n  [dim]Enviando a GitHub...[/dim]")
        result = self.manager.push_to_github(ws_name, target, msg)

        for rr in result.get("repos", []):
            icon = "[green]✓[/green]" if rr["ok"] else "[red]✗[/red]"
            detail = rr.get("action", rr.get("error", ""))
            self.console.print(f"  {icon} [bold]{rr['name']}[/bold]  {detail}")

        if result["ok"]:
            self._ok_panel(result["message"])
        else:
            self._err_panel(result["message"])
        Prompt.ask("  Enter para continuar")

    def _action_pull(self, ws_name: str, repos: list[dict]):
        self.console.print("\n  [dim]Haciendo pull...[/dim]")
        result = self.manager.pull_from_github(ws_name)
        for rr in result.get("repos", []):
            icon = "[green]✓[/green]" if rr["ok"] else "[red]✗[/red]"
            detail = rr.get("output") or rr.get("error") or ""
            self.console.print(f"  {icon} [bold]{rr['name']}[/bold]  {detail}")
        if result["ok"]:
            self._ok_panel("Pull completado")
        else:
            self._err_panel("Algunos pulls fallaron")
        Prompt.ask("  Enter para continuar")

    def _action_configure(self, ws_name: str, repos: list[dict]):
        self._clear()
        self._header(f"{ws_name} › configurar")

        target_repo = None
        if len(repos) > 1:
            self.console.print("\n  Aplicar configuración a:")
            for i, r in enumerate(repos, 1):
                self.console.print(f"    {i}. {r['name']}")
            self.console.print("    0. Global (todos)")
            ch = IntPrompt.ask("  ¿Cuál?", default=0)
            if ch != 0 and 1 <= ch <= len(repos):
                target_repo = repos[ch - 1]["name"]

        meta = self.manager._read_meta(ws_name)
        suffix = f".{target_repo}" if target_repo else ""
        cur_name = (
            meta.get(f"git.github_repo{suffix}")
            or meta.get("git.github_repo")
            or (repos[0]["name"] if repos else ws_name)
        )
        cur_vis = meta.get(f"git.visibility{suffix}") or meta.get("git.visibility") or "private"
        cur_url = meta.get(f"git.remote_url{suffix}") or meta.get("git.remote_url") or "—"

        ct = Table(show_header=False, box=None, padding=(0, 2))
        ct.add_column("Key", style="dim", width=22)
        ct.add_column("Valor", style="cyan")
        ct.add_row("Nombre GitHub repo", cur_name)
        ct.add_row("Visibilidad", cur_vis)
        ct.add_row("Remote URL", cur_url)
        self.console.print(Panel(ct, title="Configuración actual", border_style="blue"))

        self.console.print()
        self.console.print("  [bold cyan]1[/bold cyan]. Cambiar nombre del repo en GitHub")
        self.console.print("  [bold cyan]2[/bold cyan]. Cambiar visibilidad (private/public)")
        self.console.print("  [bold cyan]3[/bold cyan]. Cambiar remote URL")
        self.console.print("  [bold cyan]0[/bold cyan]. Volver")

        choice = IntPrompt.ask("\n  Opción", default=0)
        kwargs: dict[str, Any] = {"target_repo": target_repo}
        result = {"ok": False, "message": "Cancelado"}

        if choice == 1:
            new_name = Prompt.ask("  Nuevo nombre del repo", default=cur_name)
            result = self.manager.configure_repo(ws_name, repo_name=new_name, **kwargs)
        elif choice == 2:
            new_vis = Prompt.ask("  Visibilidad", default=cur_vis, choices=["private", "public"])
            result = self.manager.configure_repo(ws_name, visibility=new_vis, **kwargs)
        elif choice == 3:
            new_url = Prompt.ask("  Remote URL", default=cur_url if cur_url != "—" else "")
            result = self.manager.configure_repo(ws_name, remote_url=new_url, **kwargs)

        if choice != 0:
            if result["ok"]:
                self._ok_panel(result["message"])
            else:
                self._err_panel(result["message"])
            Prompt.ask("  Enter para continuar")

    def _action_open(self, ws_name: str, repos: list[dict]):
        repos_with_remote = [r for r in repos if r["git"].get("has_remote")]
        if not repos_with_remote:
            self._err_panel("No hay repos con remote configurado")
            Prompt.ask("  Enter para continuar")
            return
        target = repos_with_remote[0]
        if len(repos_with_remote) > 1:
            for i, r in enumerate(repos_with_remote, 1):
                self.console.print(f"  {i}. {r['name']}")
            ch = IntPrompt.ask("  ¿Cuál abrir?", default=1)
            target = repos_with_remote[max(0, min(ch - 1, len(repos_with_remote) - 1))]
        self.manager._run(["gh", "browse"], cwd=Path(target["path"]))

    # ── Loop principal ─────────────────────────────────────────────────────────

    def run(self):
        try:
            screen = "dashboard"
            while screen != "q":
                if screen == "dashboard":
                    result = self.screen_dashboard()
                    if result == "q":
                        break
                    screen = result
                else:
                    result = self.screen_workspace(screen)
                    screen = "dashboard" if result == "back" else result
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n  [dim]Hasta luego.[/dim]\n")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Gestor git/GitHub para workspaces LAIA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python git-manager.py                          # TUI interactiva\n"
            "  python git-manager.py --list                   # JSON con todos los workspaces\n"
            "  python git-manager.py --status arete           # Estado de un workspace\n"
            "  python git-manager.py --init servidor-jmp      # Inicializar git\n"
            "  python git-manager.py --push arete             # Push a GitHub\n"
            "  python git-manager.py --configure arete --repo-name mi-repo --visibility private\n"
        ),
    )
    parser.add_argument("--list", action="store_true", help="Lista todos los workspaces (JSON)")
    parser.add_argument("--status", metavar="WS", help="Estado git de un workspace (JSON)")
    parser.add_argument("--init", metavar="WS", help="Inicializar git en un workspace")
    parser.add_argument("--push", metavar="WS", help="Push a GitHub de un workspace")
    parser.add_argument("--pull", metavar="WS", help="Pull desde GitHub de un workspace")
    parser.add_argument("--configure", metavar="WS", help="Configurar repo GitHub de un workspace")
    parser.add_argument("--repo-name", default=None, help="Nombre del repo en GitHub")
    parser.add_argument("--visibility", choices=["private", "public"], default=None)
    parser.add_argument("--remote-url", default=None, help="URL del remote")
    parser.add_argument("--target-repo", default=None, help="Subproyecto específico")
    parser.add_argument("--message", "-m", default=None, help="Mensaje del commit (push)")

    args = parser.parse_args()
    mgr = WorkspaceGitManager()

    def dump(obj: Any):
        print(json.dumps(obj, indent=2, default=str))

    if args.list:
        dump(mgr.list_all())
    elif args.status:
        dump(mgr.get_status(args.status))
    elif args.init:
        dump(mgr.init_git(args.init))
    elif args.push:
        dump(mgr.push_to_github(args.push, args.target_repo, args.message))
    elif args.pull:
        dump(mgr.pull_from_github(args.pull, args.target_repo))
    elif args.configure:
        dump(mgr.configure_repo(
            args.configure,
            repo_name=args.repo_name,
            visibility=args.visibility,
            remote_url=args.remote_url,
            target_repo=args.target_repo,
        ))
    else:
        GitManagerTUI().run()


if __name__ == "__main__":
    main()
