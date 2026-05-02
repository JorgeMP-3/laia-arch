#!/usr/bin/env python3
# Muestra qué nodos DB-only se inyectan al agente en cada sesión.

from __future__ import annotations

import argparse
import re
import os
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
if str(HERMES_HOME) not in sys.path:
    sys.path.insert(0, str(HERMES_HOME))

from workspace_store import WorkspaceStore, list_workspaces

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

CONFIG_PATH = HERMES_HOME / "config.yaml"
PREVIEW_CHARS = 300


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"{RED}Error: config.yaml no encontrado en {CONFIG_PATH}{RESET}")
        sys.exit(1)
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        cfg: dict = {"plugins": {"workspace-context": {}}, "memory": {}}
        ws_cfg = cfg["plugins"]["workspace-context"]
        patterns = {
            "workspace": r"^\s{4}workspace:\s*[\"']?([^\s\"'#]+)",
            "inject_mode": r"^\s{4}inject_mode:\s*[\"']?([^\s\"'#]+)",
            "max_chars": r"^\s{4}max_chars:\s*[\"']?([^\s\"'#]+)",
        }
        in_ws = False
        current_list_key = ""
        for line in text.splitlines():
            if "workspace-context:" in line:
                in_ws = True
                continue
            if in_ws:
                if line.strip() and not line.startswith(" "):
                    in_ws = False
                    current_list_key = ""
                    continue
                for key, pattern in patterns.items():
                    match = re.match(pattern, line)
                    if match:
                        ws_cfg[key] = match.group(1).strip()
                        current_list_key = ""
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
            if in_memory:
                if line.strip() and not line.startswith("  "):
                    in_memory = False
                    continue
                m = re.match(r"^\s{2}provider:\s*([^\s#]+)", line)
                if m:
                    cfg["memory"]["provider"] = m.group(1).strip()
        return cfg


def preview(text: str, max_chars: int, show_full: bool) -> str:
    if show_full or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n{DIM}  … [{len(text) - max_chars} chars más]{RESET}"


def section(title: str) -> str:
    return f"\n{BOLD}{CYAN}{title}{RESET}\n{'─' * 70}"


def build_instruction(workspace: str, mode: str, all_workspace_names: list[str] | None = None) -> str:
    """Replica exacta del texto que genera el plugin en system_prompt_block()."""
    names = ", ".join(all_workspace_names or [workspace])
    loaded_text = (
        f"Tienes cargado el nodo index de estos workspaces: {names}. Son brujulas, no fuentes suficientes para detalles.\n"
        if mode == "all-indexes"
        else "Tienes cargado solo el nodo index del workspace desde `workspace.db`. Es una brujula, no una fuente suficiente para detalles.\n"
    )
    return (
        f"[WORKSPACE ACTIVO: {workspace} | MODO: {mode}]\n"
        f"{loaded_text}"
        "Orden obligatorio: `workspace_search_nodes` -> `workspace_get_node` -> "
        "`workspace_list_folder`/`workspace_read_workspace_file` si necesitas artefactos reales -> "
        "`workspace_read_file` solo como compatibilidad.\n"
        "Antes de actuar sobre un area sensible, busca y lee su nodo `important` global o local si existe. "
        "Los `project` funcionan como indices locales; los `topic` son mapas de conocimiento y no tienen subtopics. "
        "No uses `session_search`, `search_files` ni exports Markdown como primer recurso."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Muestra qué se inyecta al agente en cada sesión.")
    parser.add_argument("--workspace", help="Nombre del workspace (por defecto: activo en config.yaml)")
    parser.add_argument("--query", help="Simula prefetch para esta query y muestra qué nodos cargaría")
    parser.add_argument("--full", action="store_true", help="Muestra contenido completo sin truncar preview")
    args = parser.parse_args()

    cfg = load_config()
    ws_cfg = cfg.get("plugins", {}).get("workspace-context", {})

    workspace = args.workspace or ws_cfg.get("workspace", "")
    configured_mode = ws_cfg.get("inject_mode", "index")
    inject_mode = configured_mode if configured_mode in {"index", "all-indexes"} else "index"
    max_chars = int(ws_cfg.get("max_chars", 8000))

    if not workspace:
        print(f"{RED}No hay workspace activo en config.yaml{RESET}")
        sys.exit(1)

    active_store = WorkspaceStore(HERMES_HOME / "workspaces" / workspace)
    if not active_store.exists():
        print(f"{RED}ERROR: falta {active_store.db_path}{RESET}")
        print("La fuente de verdad es workspace.db. Usa create-workspace.py para crear el workspace")
        print("o create-workspace.py --migrate-legacy --name <workspace> para migrar estructura antigua.")
        sys.exit(1)

    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD}  HERMES — Contexto inyectado en sesión{RESET}")
    print(f"{'═'*70}")
    print(f"  Workspace activo : {BOLD}{workspace}{RESET}")
    mode_note = "" if configured_mode in {"index", "all-indexes"} else f" {DIM}(config tenía {configured_mode}; se degrada a index){RESET}"
    print(f"  Modo de inyección: {BOLD}{inject_mode}{RESET}{mode_note}")
    print(f"  Max chars        : {BOLD}{max_chars:,}{RESET}".replace(",", "."))

    print(section("1. AUTO-INYECTADO AL INICIO DE CADA SESIÓN"))
    stores_tmp = list_workspaces(HERMES_HOME)
    configured_names = ws_cfg.get("workspaces") or []
    if isinstance(configured_names, str):
        configured_names = [name.strip() for name in configured_names.split(",") if name.strip()]
    if inject_mode == "all-indexes":
        all_names = list(configured_names) or sorted(p.name for p in stores_tmp)
        if workspace not in all_names:
            all_names.insert(0, workspace)
    else:
        all_names = [workspace]
    instruction = build_instruction(workspace, inject_mode, all_names)
    instruction_chars = len(instruction)

    total_chars = instruction_chars
    stores = []
    for name in all_names:
        store = WorkspaceStore(HERMES_HOME / "workspaces" / name)
        if not store.exists():
            print(f"\n  {RED}✗{RESET} {name}: falta {store.db_path}")
            continue
        store.ensure_workspace_taxonomy()
        stores.append(store)
        index_node = store.get_index_node()
        if not index_node:
            print(f"\n  {RED}✗ CRÍTICO:{RESET} {name} no tiene nodo index")
            continue
        rendered = store.render_node_markdown(index_node).strip()
        if inject_mode == "all-indexes":
            rendered = f"# Workspace: {name}\n\n{rendered}"
        total_chars += len(rendered)
        active_tag = f" {BOLD}[ACTIVO]{RESET}" if name == workspace else ""
        print(f"\n  {GREEN}✓{RESET} {BOLD}{name}/index{RESET}{active_tag}  ({len(rendered):,} chars)".replace(",", "."))
        print(f"  {DIM}{preview(rendered, PREVIEW_CHARS, args.full)}{RESET}")

    print(f"\n  {DIM}── Instrucción del sistema ({instruction_chars} chars) ──{RESET}")
    print(f"  {DIM}{preview(instruction, PREVIEW_CHARS, args.full)}{RESET}")
    print(f"\n  TOTAL inyectado: {BOLD}{total_chars:,} / {max_chars:,} chars{RESET}".replace(",", "."))

    print(section("2. NODOS DISPONIBLES PARA PREFETCH"))
    for store in stores:
        nodes = [node for node in store.list_context_nodes() if node["kind"] != "index"]
        active_tag = f"  {BOLD}[ACTIVO]{RESET}" if store.workspace == workspace else ""
        print(f"\n  {CYAN}{store.workspace}/{RESET}{active_tag}")
        if not nodes:
            print(f"    {DIM}(sin nodos no-index){RESET}")
            continue
        for node in nodes[:12]:
            print(f"    {GREEN}✓{RESET} {node['filename']}  ({node['kind']})")

    if args.query:
        print(section(f"3. SIMULACIÓN DE PREFETCH  query: \"{args.query}\""))
        selected: list[tuple[str, dict]] = []
        results = active_store.search_nodes(args.query, limit=2, include_index=False)
        if not results:
            results = active_store.search_nodes(args.query, limit=2, include_index=True)
        if results:
            for node in results:
                print(f"  {GREEN}CARGARÍA{RESET}: {node['filename']}  ({node['kind']})  score={node.get('score', 0.0):.4f}")
                selected.append((workspace, node))
        else:
            print(f"  {YELLOW}Sin resultados de prefetch{RESET}")

        print(f"\n  {DIM}Flujo ideal para esta query:{RESET}")
        print(f"  1. workspace_search_nodes(query={args.query!r})")
        if selected:
            first_ws, first_node = selected[0]
            if first_ws == workspace:
                print(f"  2. workspace_get_node(ref={first_node['slug']!r})")
            else:
                print(f"  2. workspace_get_node(ref={first_node['slug']!r}, workspace={first_ws!r})")
        else:
            print("  2. workspace_get_node(ref='<slug devuelto por search>')")
        print(f"  3. Solo si falta contexto: workspace_list_folder / workspace_read_workspace_file")
        print(f"  4. Evitar como primer recurso: session_search, search_files, docs/db-export/, context/*.md")

    print(section("4. CÓDIGO DEL WORKSPACE"))
    for folder in ["code", "code/scripts"]:
        folder_path = active_store.root / folder
        if folder_path.is_dir():
            file_count = sum(1 for _ in folder_path.rglob("*") if _.is_file())
            print(f"  {GREEN}✓{RESET} {folder}/  ({file_count} archivos)")
        else:
            print(f"  {DIM}–{RESET} {folder}/  {DIM}(no existe){RESET}")

    print(section("5. EXPORT MARKDOWN BAJO DEMANDA"))
    organized_root = active_store.organized_export_root()
    organized_index = organized_root / "00-index.md"
    if not organized_index.exists():
        print(f"  {DIM}–{RESET} docs/db-export/ no existe todavía")
        print(f"  {DIM}  La ausencia de export no es un problema: workspace.db es la fuente.{RESET}")
        print(f"  {DIM}  Genera snapshot con sync-workspace-markdown.py cuando necesites inspección o diff.{RESET}")
    else:
        file_count = sum(1 for path in organized_root.rglob("*.md") if path.is_file())
        stale = active_store.organized_export_is_stale()
        status = f"{YELLOW}desactualizado{RESET}" if stale else f"{GREEN}sincronizado{RESET}"
        print(f"  {GREEN}✓{RESET} root: {organized_root}")
        print(f"  {GREEN}✓{RESET} archivos: {file_count}")
        print(f"  {GREEN}✓{RESET} estado: {status}")
        print(f"  {GREEN}✓{RESET} índice: {organized_index.relative_to(active_store.root)}")

    print(f"\n{'═' * 70}\n")


if __name__ == "__main__":
    main()
