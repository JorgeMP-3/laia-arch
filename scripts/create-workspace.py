#!/usr/bin/env python3
# Crea, repara y migra workspaces DB-only en Hermes.
"""create-workspace.py — crea, repara y migra workspaces DB-only en Hermes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

import os
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
if str(HERMES_HOME) not in sys.path:
    sys.path.insert(0, str(HERMES_HOME))

from workspace_store import WorkspaceStore

WORKSPACES_DIR = HERMES_HOME / "workspaces"
CONFIG_PATH = HERMES_HOME / "config.yaml"
SCRIPTS_INDEX = HERMES_HOME / "scripts" / "INDEX.md"
INDEX_SCRIPTS = HERMES_HOME / "scripts" / "index-scripts.py"


def append_agent_log(ws_path: Path, motivo: str, archivos: list[str], descripcion: str) -> None:
    log_path = ws_path / "agents" / "log.md"
    if not log_path.exists():
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n### {ts} — create-workspace.py — {motivo}\n"
        f"- Archivos tocados: {', '.join(archivos)}\n"
        f"- Qué se hizo: {descripcion}\n"
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


def run_index_scripts(workspace_name: str) -> None:
    if INDEX_SCRIPTS.exists():
        subprocess.run([sys.executable, str(INDEX_SCRIPTS), "--workspace", workspace_name], capture_output=True)


def prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{msg}{suffix}: ").strip()
    return value or default


def prompt_list(msg: str) -> list[str]:
    print(f"{msg} (una por línea, línea vacía para terminar):")
    items = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        items.append(line)
    return items


def validate_name(name: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9\-_]*$", name))


def load_config_data() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    if yaml is not None:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}

    text = CONFIG_PATH.read_text(encoding="utf-8")
    data: dict[str, dict[str, dict[str, Any] | str]] = {"plugins": {"workspace-context": {}}, "memory": {}}
    ws_cfg = data["plugins"]["workspace-context"]
    patterns = {
        "workspace": r"^\s{4}workspace:\s*[\"']?([^\s\"'#]+)",
        "inject_mode": r"^\s{4}inject_mode:\s*[\"']?([^\s\"'#]+)",
        "max_chars": r"^\s{4}max_chars:\s*[\"']?([^\s\"'#]+)",
    }
    in_ws = False
    for line in text.splitlines():
        if "workspace-context:" in line:
            in_ws = True
            continue
        if in_ws:
            if line.strip() and not line.startswith(" "):
                in_ws = False
                continue
            for key, pattern in patterns.items():
                match = re.match(pattern, line)
                if match:
                    ws_cfg[key] = match.group(1).strip()
    in_memory = False
    for line in text.splitlines():
        if re.match(r"^memory:\s*$", line):
            in_memory = True
            continue
        if in_memory:
            if line.strip() and not line.startswith("  "):
                in_memory = False
                continue
            m = re.match(r"^\s{2}provider:\s*([^\s#]+)", line)
            if m:
                data["memory"]["provider"] = m.group(1).strip()
    return data


def _as_name_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _append_unique(items: list[str], name: str) -> list[str]:
    return items if name in items else [*items, name]


def update_config_fallback_text(workspace_name: str, activate: bool, editable: bool) -> None:
    if not CONFIG_PATH.exists():
        print(f"  AVISO: config.yaml no encontrado en {CONFIG_PATH}")
        return
    text = CONFIG_PATH.read_text(encoding="utf-8")

    _max = re.search(r'^\s{4}max_chars:\s*([^\n#]+)', text, re.MULTILINE)
    max_chars_val = _max.group(1).strip() if _max else '8000'
    active_block = f"    - {workspace_name}\n" if editable else ""
    plugin_block = (
        "  workspace-context:\n"
        "    inject_mode: index\n"
        f"    max_chars: {max_chars_val}\n"
        f"    workspace: {workspace_name}\n"
        "    workspaces:\n"
        f"    - {workspace_name}\n"
        "    active_workspaces:\n"
        f"{active_block}"
    )

    if re.search(r"(^plugins:\n(?:^[ \t].*\n)*)", text, re.MULTILINE):
        if re.search(r"^\s{2}workspace-context:\n(?:^\s{4}.*\n)*", text, re.MULTILINE):
            text = re.sub(r"^\s{2}workspace-context:\n(?:^\s{4}.*\n)*", plugin_block, text, flags=re.MULTILINE)
        elif "plugins:\n" in text:
            text = text.replace("plugins:\n", f"plugins:\n{plugin_block}", 1)
    else:
        text += f"\nplugins:\n{plugin_block}"

    if activate:
        lines = text.splitlines(keepends=True)
        result: list[str] = []
        in_memory = False
        provider_written = False
        for line in lines:
            if re.match(r"^memory:\s*$", line):
                in_memory = True
                provider_written = False
                result.append(line)
                continue
            if in_memory:
                if line.strip() and not line.startswith("  "):
                    if not provider_written:
                        result.append("  provider: workspace-context\n")
                    in_memory = False
                    result.append(line)
                    continue
                if re.match(r"^\s{2}provider:\s*", line):
                    result.append("  provider: workspace-context\n")
                    provider_written = True
                    continue
                result.append(line)
                continue
            result.append(line)
        if in_memory and not provider_written:
            result.append("  provider: workspace-context\n")
        text = "".join(result)
        if not re.search(r"^memory:\s*$", text, re.MULTILINE):
            text = f"memory:\n  provider: workspace-context\n{text}"

    CONFIG_PATH.write_text(text, encoding="utf-8")


def update_config(workspace_name: str, activate: bool, editable: bool = True) -> None:
    if not CONFIG_PATH.exists():
        print(f"  AVISO: config.yaml no encontrado en {CONFIG_PATH}")
        return

    if yaml is None:
        update_config_fallback_text(workspace_name, activate, editable)
        if activate:
            print(f"  config.yaml actualizado (fallback) → workspace activo: {workspace_name}")
        else:
            print("  config.yaml verificado con fallback textual")
        return

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f) or {}

    config.setdefault("plugins", {}).setdefault("workspace-context", {})
    plugin_cfg = config["plugins"]["workspace-context"]
    plugin_cfg.setdefault("inject_mode", "index")
    plugin_cfg.setdefault("max_chars", 8000)
    plugin_cfg["workspaces"] = _append_unique(_as_name_list(plugin_cfg.get("workspaces")), workspace_name)
    if editable:
        active = _as_name_list(plugin_cfg.get("active_workspaces")) or _as_name_list(plugin_cfg.get("workspace"))
        plugin_cfg["active_workspaces"] = _append_unique(active, workspace_name)

    if activate:
        plugin_cfg["workspace"] = workspace_name
        config.setdefault("memory", {})["provider"] = "workspace-context"

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    if activate:
        print(f"  config.yaml actualizado → workspace activo: {workspace_name}")
    else:
        print("  config.yaml verificado para workspace-context")


def update_scripts_index(workspace_name: str) -> None:
    if not SCRIPTS_INDEX.exists():
        return
    content = SCRIPTS_INDEX.read_text(encoding="utf-8")
    section = f"## {workspace_name}"
    if section not in content:
        addition = (
            f"\n{section}\n\n"
            "| Script | Descripción |\n"
            "|--------|-------------|\n"
            "| _(vacío — añadir scripts en code/scripts/)_ | |\n"
        )
        SCRIPTS_INDEX.write_text(content + addition, encoding="utf-8")
        print(f"  scripts/INDEX.md actualizado con sección '{workspace_name}'")


def sync_exports(store: WorkspaceStore) -> dict:
    return store.sync_markdown_exports()


def export_log_paths(sync_result: dict, workspace_name: str) -> list[str]:
    context_written = sync_result.get("context", {}).get("written", [])
    organized_root = sync_result.get("organized", {}).get("root", "")
    paths = [f"context/{filename}" for filename in context_written]
    if organized_root:
        try:
            rel_root = str(Path(organized_root).relative_to(WORKSPACES_DIR / workspace_name))
        except Exception:
            rel_root = "docs/db-export"
        paths.append(f"{rel_root}/00-index.md")
    return paths


def restart_gateway() -> bool:
    try:
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{__import__('os').getuid()}/ai.hermes.gateway"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def verify_tools_loaded(workspace_name: str, timeout: int = 15) -> bool:
    log_path = HERMES_HOME / "logs" / "agent.log"
    if not log_path.exists():
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines[-50:]):
            if "workspace-context" in line and "registered" in line and "(0 tools)" not in line:
                return True
    return False


def get_active_workspace() -> str:
    config = load_config_data()
    return config.get("plugins", {}).get("workspace-context", {}).get("workspace", "")


def list_workspaces() -> list[str]:
    if not WORKSPACES_DIR.exists():
        return []
    return sorted(d.name for d in WORKSPACES_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))


def ensure_base_files(ws_path: Path) -> list[str]:
    store = WorkspaceStore(ws_path)
    return store.ensure_workspace_layout()


def repair_workspace(name: str, *, interactive: bool = True, force_import: bool = False) -> dict:
    ws_path = WORKSPACES_DIR / name
    store = WorkspaceStore(ws_path)
    created = ensure_base_files(ws_path)

    had_db = store.exists()
    if force_import:
        result = store.migrate_legacy_to_db()
        created.extend(result.get("generated", []))
    elif not had_db:
        seeded = store.seed_workspace(f"Workspace {name}.", [])
        result = {"created": True, "generated": seeded.get("generated", [])}
        created.extend(seeded.get("generated", []))
    else:
        store.ensure_schema()
        store.ensure_workspace_taxonomy()
        store.scan_artifacts()
        result = {"created": False, "reason": "db-exists"}

    created.append("workspace.db")
    append_agent_log(
        ws_path,
        "Reparar workspace DB-only",
        sorted(set(created)),
        "Normalizada la estructura base e inicializada o verificada workspace.db",
    )

    if interactive:
        print(f"  ✓ Workspace '{name}' reparado")
        print(f"    - workspace.db: {'migrado' if force_import else 'creado' if not had_db else 'verificado'}")
        print("    - exports Markdown: bajo demanda con sync-workspace-markdown.py")

    return {"created": created, "migration": result, "export": store._empty_export_result()}


def migrate_legacy_workspace(
    name: str,
    *,
    archive: bool = True,
    remove_legacy: bool = True,
    backup_root: str | None = None,
    interactive: bool = True,
) -> dict:
    ws_path = WORKSPACES_DIR / name
    store = WorkspaceStore(ws_path)
    result = store.migrate_legacy_to_db(backup_root=backup_root, archive=archive, remove_legacy=remove_legacy)
    run_index_scripts(name)

    if interactive:
        print(f"  ✓ Migración legacy completada para '{name}'")
        print(f"    - nodos importados: {len(result['imported'])}")
        print(f"    - archivos movidos a code/: {len(result['moved'])}")
        print(f"    - legacy eliminado: {len(result['removed'])} rutas")
        print(f"    - DB verificada: {'sí' if result['verified'] else 'no'}")
        if result.get("backup"):
            print(f"    - archivo comprimido: {result['backup']}")
        if result["skipped"]:
            print(f"    - omitidos por conflicto: {len(result['skipped'])}")
        if result["missing"]:
            print(f"    - pendientes de verificar: {len(result['missing'])}")

    return result


def show_workspace_status(name: str) -> None:
    ws_path = WORKSPACES_DIR / name
    active = get_active_workspace()
    store = WorkspaceStore(ws_path)

    print(f"\n  Workspace: {name} {'[ACTIVO]' if name == active else ''}")
    print(f"  Ruta: {ws_path}")
    print(f"  DB: {'✓' if store.exists() else '✗'} workspace.db")

    if store.exists():
        audit = store.audit()
        print(f"  Nodos: {audit['stats']['nodes']} | Relaciones: {audit['stats']['edges']} | Artifacts: {audit['stats']['artifacts']}")
        if audit["issues"]:
            print("  Issues:")
            for issue in audit["issues"][:5]:
                print(f"    - {issue.severity}: {issue.message}")
        else:
            print("  Issues: ninguna")

    context_dir = ws_path / "context"
    if context_dir.exists():
        files = sorted(f.name for f in context_dir.glob("*.md") if not f.name.startswith("."))
        print(f"  context/: {len(files)} archivos de export bajo demanda")
        for filename in files[:10]:
            marker = " [index]" if filename == "00-index.md" else ""
            print(f"    {filename}{marker}")

    organized_root = store.organized_export_root()
    if organized_root.exists():
        organized_files = sorted(path for path in organized_root.rglob("*.md") if path.is_file())
        print(f"  docs/db-export/: {len(organized_files)} archivos")
        for path in organized_files[:6]:
            print(f"    {path.relative_to(ws_path)}")

    for folder in ["code", "code/scripts"]:
        print(f"  {'✓' if (ws_path / folder).exists() else '✗'} {folder}/")


def do_apply_restart(name: str) -> None:
    print("\n  Reiniciando gateway de Hermes...")
    ok = restart_gateway()
    if ok:
        print("  Gateway reiniciado. Verificando tools...")
        if verify_tools_loaded(name):
            print("  ✓ workspace-context cargado con tools activos")
        else:
            print("  AVISO: no se pudo verificar en los logs. Comprueba manualmente:")
            print(f"    tail -5 {HERMES_HOME}/logs/agent.log | grep tools")
    else:
        print("  AVISO: no se pudo reiniciar el gateway automáticamente.")
        print("    launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway")


def edit_workspace(name: str) -> None:
    ws_path = WORKSPACES_DIR / name
    store = WorkspaceStore(ws_path)

    print(f"\n=== Editar Workspace: {name} ===")
    show_workspace_status(name)

    options = [
        ("1", "Añadir/actualizar nodo temático"),
        ("2", "Reparar estructura + DB"),
        ("3", "Activar este workspace en config.yaml"),
        ("4", "Migrar legacy a DB + code/"),
        ("5", "Reiniciar gateway"),
        ("6", "Ver contenido de un nodo DB"),
        ("7", "Crear proyecto nuevo en code/"),
        ("8", "Exportar Markdown bajo demanda"),
        ("0", "Salir"),
    ]

    while True:
        print("\n¿Qué quieres hacer?")
        for key, label in options:
            print(f"  {key}. {label}")

        choice = prompt("\nOpción", "0").strip()

        if choice == "1":
            title = prompt("  Título del nodo (ej: Arquitectura)")
            if not title:
                continue
            slug = prompt("  Slug del nodo", re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"))
            body = prompt("  Resumen corto", "")
            store.ensure_workspace_taxonomy()
            node = store.upsert_node(
                slug=slug,
                title=f"{title} — Topic",
                kind="topic",
                summary=body or title,
                body=body or "## Guia\n\n_(añadir mapa del tema)_",
                source_kind="interactive",
                parent_ref="topics",
            )
            store.link_nodes("topics", node["id"], "contains")
            print(f"  ✓ Nodo guardado en workspace.db: {node['slug']}")

        elif choice == "2":
            repair_workspace(name, interactive=True, force_import=False)

        elif choice == "3":
            if get_active_workspace() == name:
                print(f"  '{name}' ya es el workspace activo.")
            else:
                update_config(name, activate=True)
                append_agent_log(ws_path, "Activar workspace", ["config.yaml"], f"Workspace '{name}' activado como workspace activo")
                if prompt("  ¿Reiniciar el gateway para aplicar el cambio? (s/n)", "s").lower() in ("s", "si", "sí", "y", "yes"):
                    do_apply_restart(name)

        elif choice == "4":
            if prompt("  ¿Migrar legacy y archivar comprimido? (s/n)", "s").lower() in ("s", "si", "sí", "y", "yes"):
                migrate_legacy_workspace(name, archive=True, remove_legacy=True, interactive=True)

        elif choice == "5":
            do_apply_restart(name)

        elif choice == "6":
            nodes = store.list_context_nodes()
            if not nodes:
                print("  No hay nodos DB.")
                continue
            for idx, node in enumerate(nodes, 1):
                print(f"    {idx}. {node['filename']}  ({node['kind']})")
            try:
                selected = int(prompt("  Número de nodo", "1")) - 1
                node = nodes[selected]
                print(f"\n--- {node['filename']} ---\n{store.render_node_markdown(node)}---")
            except (ValueError, IndexError):
                print("  Selección inválida.")

        elif choice == "7":
            proj_name = prompt("Nombre del proyecto (ej: api-auth, landing-v2)")
            if not proj_name or not validate_name(proj_name):
                print("  Nombre inválido.")
                continue
            result = store.create_project(proj_name, prompt("Descripción breve del proyecto", ""))
            print(f"  ✓ Proyecto creado: {result['path']}")
            append_agent_log(
                ws_path,
                "Crear proyecto",
                [f"code/{proj_name}"],
                f"Proyecto '{proj_name}' creado y enlazado en workspace.db",
            )

        elif choice == "8":
            export = sync_exports(store)
            print(f"  ✓ context/ regenerado ({len(export['context']['written'])} archivos)")
            print(f"  ✓ docs/db-export/ regenerado ({len(export['organized']['written'])} archivos)")
            if export["context"]["removed"]:
                print(f"    context/ eliminados obsoletos: {', '.join(export['context']['removed'])}")
            if export["organized"]["removed"]:
                print(f"    docs/db-export/ eliminados obsoletos: {', '.join(export['organized']['removed'])}")

        elif choice == "0":
            break
        else:
            print("  Opción no válida.")

    print(f"\nEdición de '{name}' finalizada.\n")


def _init_code_git(ws_path: Path, ws_name: str) -> None:
    """Inicializa un repo git en ws_path/code/ si no existe ya."""
    import os as _os
    code_path = ws_path / "code"
    if not code_path.exists():
        return

    # Si ya hay git en code/ o en algún subproyecto, no hacer nada
    if (code_path / ".git").exists():
        print(f"  ✓ git ya existe en {ws_name}/code")
        return
    has_subgit = any((code_path / d / ".git").exists() for d in _os.listdir(code_path) if (code_path / d).is_dir())
    if has_subgit:
        return

    gitignore = (
        "# macOS\n.DS_Store\n# Node.js\nnode_modules/\n# Python\n__pycache__/\n*.pyc\n.venv/\n"
        "# Xcode\nDerivedData/\n*.xcuserstate\n.build/\nPods/\n# Env\n.env\n*.log\n"
    )
    try:
        (code_path / ".gitignore").write_text(gitignore, encoding="utf-8")
        subprocess.run(["git", "-C", str(code_path), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(code_path), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(code_path), "commit", "-q", "-m", f"chore: init workspace — {ws_name}"],
            check=True, capture_output=True,
        )
        print(f"  ✓ git init en {ws_name}/code")
    except Exception as e:
        print(f"  AVISO: no se pudo inicializar git en {ws_name}/code: {e}")


def create_workspace(args) -> None:
    print("\n=== Crear Workspace DB-only en Hermes ===\n")

    name = args.name
    while not name or not validate_name(name):
        if name:
            print("  Nombre inválido. Usa solo letras minúsculas, números, guiones o guiones bajos.")
        name = prompt("Nombre del workspace (ej: mi-proyecto, cliente-acme)")
    ws_path = WORKSPACES_DIR / name

    if ws_path.exists():
        print(f"\nEl workspace '{name}' ya existe.")
        if prompt("¿Quieres editarlo en lugar de crearlo? (s/n)", "s").lower() in ("s", "si", "sí", "y", "yes"):
            edit_workspace(name)
        return

    description = prompt("\nDescripción breve (2-3 frases sobre el propósito de este workspace)") or f"Workspace {name}."

    print("\nÁreas principales del workspace.")
    print("Formato: 'Nombre' o 'Nombre: descripción en una línea'")
    areas = prompt_list("Áreas")

    activate = args.activate
    if not activate:
        activate = prompt("\n¿Activar como workspace activo en config.yaml? (s/n)", "n").lower() in ("s", "si", "sí", "y", "yes")

    restart = args.restart
    if activate and not restart:
        restart = prompt("\n¿Reiniciar el gateway de Hermes para aplicar cambios? (s/n)", "s").lower() in ("s", "si", "sí", "y", "yes")

    print(f"\n--- Creando workspace '{name}' ---\n")

    store = WorkspaceStore(ws_path)
    created_folders = store.ensure_workspace_layout()
    for folder in created_folders:
        print(f"  ✓ {name}/{folder}/")

    seed = store.seed_workspace(description, areas)
    print(f"  ✓ {name}/workspace.db")
    for rel_path in seed.get("generated", []):
        print(f"  ✓ {name}/{rel_path}")

    _init_code_git(ws_path, name)
    update_config(name, activate, editable=not args.read_only)
    run_index_scripts(name)

    append_agent_log(
        ws_path,
        "Crear workspace",
        sorted(set(created_folders + ["workspace.db", *seed.get("generated", [])])),
        f"Workspace '{name}' creado con source of truth DB-only{', activado' if activate else ''}",
    )

    if restart:
        do_apply_restart(name)

    print(
        f"""
=== Workspace '{name}' creado ===

  Ruta:       {ws_path}
  Source:     {ws_path}/workspace.db
  Código:     {ws_path}/code/
  Exports:    bajo demanda con sync-workspace-markdown.py
  Activo:     {'sí' if activate else 'no (cambiar plugins.workspace-context.workspace en config.yaml)'}
  Editable:   {'sí' if not args.read_only else 'no'}

Próximos pasos:
  1. Usa --migrate-legacy --name {name} si este workspace tenía estructura antigua
  2. Añade o edita nodos desde el store DB-only
  3. Genera exports Markdown solo cuando los necesites
{"  4. El gateway ya está corriendo con el nuevo workspace" if restart else "  4. Reinicia el gateway: launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway"}
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear, editar, reparar o migrar workspaces DB-only en Hermes")
    parser.add_argument("--name", help="Nombre del workspace")
    parser.add_argument("--edit", action="store_true", help="Editar un workspace existente")
    parser.add_argument("--activate", action="store_true", help="Activar como workspace activo")
    parser.add_argument("--restart", action="store_true", help="Reiniciar el gateway tras los cambios")
    parser.add_argument("--repair", action="store_true", help="Reparar un workspace existente (estructura + DB)")
    parser.add_argument("--force-import", action="store_true", help="Compatibilidad: al reparar, ejecutar migración legacy explícita")
    parser.add_argument("--migrate-legacy", action="store_true", help="Migrar estructura legacy a workspace.db, mover código a code/ y archivar")
    parser.add_argument("--no-archive", action="store_true", help="No crear archivo comprimido al migrar legacy")
    parser.add_argument("--keep-legacy", action="store_true", help="No eliminar carpetas legacy tras verificar la migración")
    parser.add_argument("--backup-root", help="Directorio para guardar el archivo comprimido legacy")
    parser.add_argument("--with-nodes", action="store_true", help="Compatibilidad legacy; ahora las áreas siempre crean nodos")
    parser.add_argument("--read-only", action="store_true", help="Crear/registrar el workspace sin añadirlo a active_workspaces")
    args = parser.parse_args()

    if args.migrate_legacy:
        if not args.name:
            print("ERROR: --migrate-legacy requiere --name")
            sys.exit(1)
        if not (WORKSPACES_DIR / args.name).exists():
            print(f"ERROR: Workspace '{args.name}' no encontrado.")
            sys.exit(1)
        migrate_legacy_workspace(
            args.name,
            archive=not args.no_archive,
            remove_legacy=not args.keep_legacy,
            backup_root=args.backup_root,
            interactive=True,
        )
        return

    if args.repair:
        if not args.name:
            print("ERROR: --repair requiere --name")
            sys.exit(1)
        if not (WORKSPACES_DIR / args.name).exists():
            print(f"ERROR: Workspace '{args.name}' no encontrado.")
            sys.exit(1)
        repair_workspace(args.name, interactive=True, force_import=args.force_import)
        return

    if args.edit or (args.name and (WORKSPACES_DIR / args.name).exists() and not args.activate):
        workspaces = list_workspaces()
        if not workspaces:
            print("No hay workspaces existentes. Usa el script sin --edit para crear uno.")
            sys.exit(0)

        name = args.name
        if not name:
            active = get_active_workspace()
            print("\n=== Editar Workspace ===\n")
            print("Workspaces disponibles:")
            for idx, workspace in enumerate(workspaces, 1):
                marker = " [activo]" if workspace == active else ""
                print(f"  {idx}. {workspace}{marker}")
            selection = prompt("\nNúmero o nombre del workspace a editar", "1")
            try:
                name = workspaces[int(selection) - 1]
            except (ValueError, IndexError):
                name = selection.strip()

        if not (WORKSPACES_DIR / name).exists():
            print(f"ERROR: Workspace '{name}' no encontrado.")
            sys.exit(1)

        edit_workspace(name)
        return

    create_workspace(args)


if __name__ == "__main__":
    main()
