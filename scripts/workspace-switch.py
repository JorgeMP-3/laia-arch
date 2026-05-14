#!/usr/bin/env python3
"""workspace-switch.py — activa, desactiva y consulta el workspace activo."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - Hermes suele tener PyYAML.
    yaml = None

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
WORKSPACES_DIR = HERMES_HOME / "workspaces"

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def die(message: str, code: int = 1) -> None:
    print(f"{RED}ERROR:{RESET} {message}")
    raise SystemExit(code)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        die(f"no existe {CONFIG_PATH}")
    if yaml is None:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        cfg: dict[str, Any] = {"__raw_text": text, "plugins": {"workspace-context": {}}, "memory": {}}
        ws_cfg = cfg["plugins"]["workspace-context"]
        in_ws = False
        current_list_key = ""
        for line in text.splitlines():
            if re.match(r"^plugins:\s*$", line):
                continue
            if re.match(r"^\s{2}workspace-context:\s*$", line):
                in_ws = True
                continue
            if in_ws and line.strip() and not line.startswith("    "):
                in_ws = False
                current_list_key = ""
            if in_ws:
                m = re.match(r"^\s{4}(workspace|inject_mode|max_chars|recursive):\s*([^#\n]+)", line)
                if m:
                    value: Any = m.group(2).strip().strip("'\"")
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif str(value).isdigit():
                        value = int(value)
                    ws_cfg[m.group(1)] = value
                    current_list_key = ""
                    continue
                list_start = re.match(r"^\s{4}(workspaces):\s*$", line)
                if list_start:
                    current_list_key = list_start.group(1)
                    ws_cfg[current_list_key] = []
                    continue
                item = re.match(r"^\s{6}-\s*([^#\n]+)", line)
                if current_list_key and item:
                    ws_cfg.setdefault(current_list_key, []).append(item.group(1).strip().strip("'\""))
        in_memory = False
        for line in text.splitlines():
            if re.match(r"^memory:\s*$", line):
                in_memory = True
                continue
            if in_memory and line.strip() and not line.startswith("  "):
                in_memory = False
            if in_memory:
                provider = re.match(r"^\s{2}provider:\s*([^\n#]+)", line)
                if provider:
                    cfg["memory"]["provider"] = provider.group(1).strip().strip("'\"")
        return cfg
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict[str, Any]) -> None:
    if yaml is None:
        save_config_text(config)
        return
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def save_config_text(config: dict[str, Any]) -> None:
    text = str(config.get("__raw_text") or CONFIG_PATH.read_text(encoding="utf-8"))
    ws_cfg = config.get("plugins", {}).get("workspace-context", {}) or {}
    mem_cfg = config.get("memory", {}) or {}

    def upsert_memory_provider(src: str) -> str:
        provider = mem_cfg.get("provider")
        lines = src.splitlines(keepends=True)
        result: list[str] = []
        in_memory = False
        memory_provider_written = False
        for line in lines:
            if re.match(r"^memory:\s*$", line):
                in_memory = True
                memory_provider_written = False
                result.append(line)
                continue
            if in_memory:
                if line.strip() and not line.startswith("  "):
                    # Leaving memory block; inject provider line if not yet written
                    if provider and not memory_provider_written:
                        result.append(f"  provider: {provider}\n")
                    in_memory = False
                    result.append(line)
                    continue
                if re.match(r"^\s{2}provider:\s*", line):
                    if provider:
                        result.append(f"  provider: {provider}\n")
                    # else: drop the line (deactivate)
                    memory_provider_written = True
                    continue
                result.append(line)
                continue
            result.append(line)
        # Handle memory block at end of file
        if in_memory and provider and not memory_provider_written:
            result.append(f"  provider: {provider}\n")
        out = "".join(result)
        if not re.search(r"^memory:\s*$", out, re.MULTILINE):
            if provider:
                out = f"memory:\n  provider: {provider}\n" + out
        return out

    def render_ws_block() -> str:
        lines = ["  workspace-context:"]
        if "inject_mode" in ws_cfg:
            lines.append(f"    inject_mode: {ws_cfg['inject_mode']}")
        if "max_chars" in ws_cfg:
            lines.append(f"    max_chars: {ws_cfg['max_chars']}")
        if "recursive" in ws_cfg:
            lines.append(f"    recursive: {str(ws_cfg['recursive']).lower()}")
        if "workspace" in ws_cfg:
            lines.append(f"    workspace: {ws_cfg['workspace']}")
        if ws_cfg.get("workspaces"):
            lines.append("    workspaces:")
            for name in ws_cfg["workspaces"]:
                lines.append(f"      - {name}")
        return "\n".join(lines) + "\n"

    text = upsert_memory_provider(text)
    block = render_ws_block()
    if re.search(r"^plugins:\s*$", text, re.MULTILINE):
        if re.search(r"^\s{2}workspace-context:\n(?:^\s{4}.*\n)*", text, re.MULTILINE):
            text = re.sub(r"^\s{2}workspace-context:\n(?:^\s{4}.*\n)*", block, text, flags=re.MULTILINE)
        else:
            text = text.replace("plugins:\n", f"plugins:\n{block}", 1)
    else:
        text = text.rstrip() + f"\nplugins:\n{block}"
    CONFIG_PATH.write_text(text, encoding="utf-8")


def workspace_names() -> list[str]:
    if not WORKSPACES_DIR.exists():
        return []
    return sorted(
        path.name
        for path in WORKSPACES_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def workspace_exists(name: str) -> bool:
    return (WORKSPACES_DIR / name / "workspace.db").exists()


def workspace_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.setdefault("plugins", {}).setdefault("workspace-context", {})


def memory_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.setdefault("memory", {})


def get_state(config: dict[str, Any]) -> dict[str, Any]:
    ws_cfg = config.get("plugins", {}).get("workspace-context", {}) or {}
    mem_cfg = config.get("memory", {}) or {}
    workspace = ws_cfg.get("workspace", "")
    provider = mem_cfg.get("provider", "")
    return {
        "workspace": workspace,
        "provider": provider,
        "enabled": provider == "workspace-context",
        "inject_mode": ws_cfg.get("inject_mode", "index"),
        "max_chars": ws_cfg.get("max_chars", ""),
        "workspaces": ws_cfg.get("workspaces", []),
        "exists": bool(workspace and workspace_exists(workspace)),
    }


def print_status(config: dict[str, Any]) -> None:
    state = get_state(config)
    enabled = state["enabled"]
    workspace = state["workspace"] or "(sin configurar)"
    exists = state["exists"]
    print(f"{BOLD}Hermes workspace-context{RESET}")
    print(f"  Provider memoria : {BOLD}{state['provider'] or '(sin provider)'}{RESET}")
    print(f"  Estado           : {GREEN + 'activo' + RESET if enabled else YELLOW + 'desactivado' + RESET}")
    print(f"  Workspace        : {BOLD}{workspace}{RESET}")
    if state["workspace"]:
        print(f"  workspace.db     : {GREEN + 'OK' + RESET if exists else RED + 'NO EXISTE' + RESET}")
    print(f"  Inject mode      : {state['inject_mode']}")
    if state["workspaces"]:
        print(f"  Workspaces       : {', '.join(state['workspaces'])}")
    print(f"  Max chars        : {state['max_chars']}")
    print()
    print(f"{DIM}Nota: reinicia Hermes/el agente para que una sesion nueva cargue el cambio.{RESET}")


def list_workspaces(config: dict[str, Any]) -> None:
    state = get_state(config)
    active = state["workspace"]
    configured = set(state.get("workspaces") or [])
    enabled = state["enabled"]
    names = workspace_names()
    if not names:
        print(f"{YELLOW}No hay workspaces en {WORKSPACES_DIR}{RESET}")
        return
    for name in names:
        marker = ""
        if name == active:
            marker = f" {GREEN}[activo]{RESET}" if enabled else f" {YELLOW}[seleccionado, provider desactivado]{RESET}"
        elif name in configured:
            marker = f" {GREEN}[incluido]{RESET}" if enabled else f" {YELLOW}[incluido, provider desactivado]{RESET}"
        db = WORKSPACES_DIR / name / "workspace.db"
        db_status = "db" if db.exists() else "sin-db"
        print(f"- {name}{marker} {DIM}({db_status}){RESET}")


def restart_gateway() -> bool:
    label = f"gui/{os.getuid()}/ai.hermes.gateway"
    try:
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", label],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def activate(args: argparse.Namespace) -> None:
    name = args.workspace
    if name not in workspace_names():
        die(f"workspace no encontrado: {name}")
    if not workspace_exists(name):
        die(f"{name} existe como carpeta pero no tiene workspace.db; repara/crea el workspace primero")

    config = load_config()
    ws_cfg = workspace_config(config)
    ws_cfg["workspace"] = name
    ws_cfg["inject_mode"] = args.mode
    if args.mode == "all-indexes":
        existing = ws_cfg.get("workspaces")
        if not existing:
            ws_cfg["workspaces"] = workspace_names()
        elif name not in existing:
            ws_cfg["workspaces"] = [name, *existing]
    else:
        ws_cfg.pop("workspaces", None)
    ws_cfg.setdefault("max_chars", 8000)
    if args.max_chars is not None:
        ws_cfg["max_chars"] = args.max_chars
    memory_config(config)["provider"] = "workspace-context"
    save_config(config)

    print(f"{GREEN}✓{RESET} workspace activo: {BOLD}{name}{RESET}")
    print(f"{GREEN}✓{RESET} memory.provider: workspace-context")
    print(f"{GREEN}✓{RESET} inject_mode: {args.mode}")
    if args.mode == "all-indexes":
        print(f"{GREEN}✓{RESET} workspaces incluidos: {', '.join(ws_cfg.get('workspaces', []))}")
    if args.restart:
        print(f"{GREEN + '✓' + RESET if restart_gateway() else YELLOW + '!' + RESET} gateway reiniciado")
    else:
        print(f"{DIM}Reinicia Hermes/el agente para cargarlo en una nueva sesion.{RESET}")


def enable(args: argparse.Namespace) -> None:
    config = load_config()
    state = get_state(config)
    workspace = args.workspace or state["workspace"]
    if not workspace:
        die("no hay workspace configurado; usa activate NOMBRE")
    if workspace not in workspace_names():
        die(f"workspace no encontrado: {workspace}")
    if not workspace_exists(workspace):
        die(f"{workspace} no tiene workspace.db")

    ws_cfg = workspace_config(config)
    ws_cfg["workspace"] = workspace
    ws_cfg.setdefault("inject_mode", "index")
    ws_cfg.setdefault("max_chars", 8000)
    memory_config(config)["provider"] = "workspace-context"
    save_config(config)
    print(f"{GREEN}✓{RESET} workspace-context activado con workspace: {BOLD}{workspace}{RESET}")
    if args.restart:
        print(f"{GREEN + '✓' + RESET if restart_gateway() else YELLOW + '!' + RESET} gateway reiniciado")


def deactivate(args: argparse.Namespace) -> None:
    config = load_config()
    mem_cfg = memory_config(config)
    old_provider = mem_cfg.get("provider", "")
    if old_provider == "workspace-context":
        mem_cfg.pop("provider", None)
    save_config(config)
    print(f"{YELLOW}✓{RESET} workspace-context desactivado como memory provider")
    if old_provider and old_provider != "workspace-context":
        print(f"{DIM}El provider anterior era {old_provider}; no se ha tocado.{RESET}")
    print(f"{DIM}La clave plugins.workspace-context.workspace se conserva para reactivar rapido.{RESET}")
    if args.restart:
        print(f"{GREEN + '✓' + RESET if restart_gateway() else YELLOW + '!' + RESET} gateway reiniciado")


def activate_many(args: argparse.Namespace) -> None:
    names = args.workspaces
    available = set(workspace_names())
    missing = [name for name in names if name not in available]
    if missing:
        die(f"workspace(s) no encontrado(s): {', '.join(missing)}")
    missing_db = [name for name in names if not workspace_exists(name)]
    if missing_db:
        die(f"workspace(s) sin workspace.db: {', '.join(missing_db)}")

    config = load_config()
    ws_cfg = workspace_config(config)
    ws_cfg["workspace"] = args.active or names[0]
    if ws_cfg["workspace"] not in names:
        die("--active debe estar dentro de la lista de workspaces")
    ws_cfg["inject_mode"] = "all-indexes"
    ws_cfg["workspaces"] = names
    ws_cfg.setdefault("max_chars", 20000)
    if args.max_chars is not None:
        ws_cfg["max_chars"] = args.max_chars
    memory_config(config)["provider"] = "workspace-context"
    save_config(config)

    print(f"{GREEN}✓{RESET} workspace activo: {BOLD}{ws_cfg['workspace']}{RESET}")
    print(f"{GREEN}✓{RESET} inject_mode: all-indexes")
    print(f"{GREEN}✓{RESET} workspaces incluidos: {', '.join(names)}")
    if args.restart:
        print(f"{GREEN + '✓' + RESET if restart_gateway() else YELLOW + '!' + RESET} gateway reiniciado")
    else:
        print(f"{DIM}Reinicia Hermes/el agente para cargarlo en una nueva sesion.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activa, desactiva y consulta el workspace activo de Hermes.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Mostrar workspace/provider activo")
    sub.add_parser("list", help="Listar workspaces disponibles")

    p_activate = sub.add_parser("activate", help="Activar un workspace y el provider workspace-context")
    p_activate.add_argument("workspace", help="Nombre del workspace")
    p_activate.add_argument("--mode", choices=["index", "all-indexes", "full"], default="index", help="Modo de inyeccion")
    p_activate.add_argument("--max-chars", type=int, help="Limite max_chars para el provider")
    p_activate.add_argument("--restart", action="store_true", help="Reiniciar gateway launchctl si existe")

    p_many = sub.add_parser("activate-many", help="Activar all-indexes con una lista concreta de workspaces")
    p_many.add_argument("workspaces", nargs="+", help="Workspaces a incluir")
    p_many.add_argument("--active", help="Workspace principal; por defecto el primero de la lista")
    p_many.add_argument("--max-chars", type=int, help="Limite max_chars para el provider")
    p_many.add_argument("--restart", action="store_true", help="Reiniciar gateway launchctl si existe")

    p_enable = sub.add_parser("enable", help="Reactivar workspace-context usando el workspace configurado o uno dado")
    p_enable.add_argument("workspace", nargs="?", help="Workspace opcional")
    p_enable.add_argument("--restart", action="store_true", help="Reiniciar gateway launchctl si existe")

    p_deactivate = sub.add_parser("deactivate", help="Desactivar workspace-context como memory provider")
    p_deactivate.add_argument("--restart", action="store_true", help="Reiniciar gateway launchctl si existe")

    args = parser.parse_args()
    if args.cmd == "status":
        print_status(load_config())
    elif args.cmd == "list":
        list_workspaces(load_config())
    elif args.cmd == "activate":
        activate(args)
    elif args.cmd == "activate-many":
        activate_many(args)
    elif args.cmd == "enable":
        enable(args)
    elif args.cmd == "deactivate":
        deactivate(args)
    else:  # pragma: no cover
        parser.print_help()


if __name__ == "__main__":
    main()
