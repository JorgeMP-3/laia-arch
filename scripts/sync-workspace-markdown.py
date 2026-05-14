#!/usr/bin/env python3
# Exporta `workspace.db` a Markdown bajo demanda: `context/` y `docs/db-export/`.

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import os
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
if str(HERMES_HOME) not in sys.path:
    sys.path.insert(0, str(HERMES_HOME))

from workspace_store import WorkspaceStore, list_workspaces

WORKSPACES_DIR = HERMES_HOME / "workspaces"


def workspace_names(name: str | None, all_workspaces: bool) -> list[str]:
    if name:
        return [name]
    if all_workspaces or not name:
        return [path.name for path in list_workspaces(HERMES_HOME)]
    return []


def ensure_store(name: str) -> WorkspaceStore:
    store = WorkspaceStore(WORKSPACES_DIR / name)
    if not store.exists():
        raise SystemExit(
            f"ERROR: {store.db_path} no existe. La fuente de verdad es workspace.db; "
            "crea el workspace o ejecuta create-workspace.py --migrate-legacy --name "
            f"{name}."
        )
    store.ensure_schema()
    return store


def sync_workspace(name: str, output_dir: str | None = None) -> dict:
    store = ensure_store(name)
    store.scan_artifacts()
    result = store.sync_markdown_exports(output_dir=output_dir)
    return {
        "workspace": name,
        "db": str(store.db_path),
        "context_written": len(result["context"]["written"]),
        "organized_written": len(result["organized"]["written"]),
        "organized_root": result["organized"]["root"],
        "context_removed": result["context"]["removed"],
        "organized_removed": result["organized"]["removed"],
        "db_mtime": store.db_mtime(),
    }


def print_sync(result: dict) -> None:
    print(f"[{result['workspace']}]")
    print(f"  fuente: {result['db']}")
    print("  export: bajo demanda desde workspace.db")
    print(f"  context/: {result['context_written']} archivos")
    print(f"  docs/db-export/: {result['organized_written']} archivos")
    print(f"  snapshot: {result['organized_root']}")
    if result["context_removed"]:
        print(f"  context/ eliminados: {', '.join(result['context_removed'])}")
    if result["organized_removed"]:
        print(f"  docs/db-export/ eliminados: {', '.join(result['organized_removed'])}")


def watch(names: list[str], interval: float, output_dir: str | None = None) -> None:
    last_seen: dict[str, float] = {}
    print(f"Watch activo cada {interval:.1f}s. Export bajo demanda desde workspace.db. Ctrl+C para salir.\n")

    while True:
        current_names = names or [path.name for path in list_workspaces(HERMES_HOME)]
        for name in current_names:
            store = ensure_store(name)
            db_mtime = store.db_mtime()
            previous = last_seen.get(name)
            if previous is None or db_mtime > previous:
                result = sync_workspace(name, output_dir=output_dir)
                print_sync(result)
                print()
                last_seen[name] = result["db_mtime"]
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta workspaces DB-only a Markdown bajo demanda.")
    parser.add_argument("--workspace", metavar="NOMBRE", help="Sincronizar solo este workspace")
    parser.add_argument("--all", action="store_true", help="Sincronizar todos los workspaces")
    parser.add_argument("--watch", action="store_true", help="Exportar automáticamente al detectar cambios en workspace.db")
    parser.add_argument("--interval", type=float, default=2.0, metavar="SEG", help="Intervalo de watch en segundos")
    parser.add_argument("--output-dir", metavar="RUTA", help="Ruta relativa o absoluta para el snapshot organizado (por defecto: docs/db-export)")
    args = parser.parse_args()

    if not WORKSPACES_DIR.exists():
        raise SystemExit(f"ERROR: {WORKSPACES_DIR} no existe")

    if args.workspace and args.all:
        raise SystemExit("ERROR: usa --workspace o --all, no ambos")

    names = workspace_names(args.workspace, args.all)
    if args.workspace and not (WORKSPACES_DIR / args.workspace).exists():
        raise SystemExit(f"ERROR: workspace '{args.workspace}' no encontrado")
    if not names:
        raise SystemExit("No hay workspaces para sincronizar")

    if args.watch:
        try:
            watch(names if args.workspace or args.all else [], args.interval, output_dir=args.output_dir)
        except KeyboardInterrupt:
            print("\nWatch detenido.")
        return

    for name in names:
        print_sync(sync_workspace(name, output_dir=args.output_dir))
        print()


if __name__ == "__main__":
    main()
