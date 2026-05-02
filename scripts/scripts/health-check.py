#!/usr/bin/env python3
# Verifica el estado estructural y DB-only de los workspaces de Hermes.

from __future__ import annotations

import argparse
import importlib.util
import shutil
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
if str(HERMES_HOME) not in sys.path:
    sys.path.insert(0, str(HERMES_HOME))

from workspace_store import STANDARD_FOLDERS, WorkspaceStore

WORKSPACES_DIR = HERMES_HOME / "workspaces"
CONFIG_PATH = HERMES_HOME / "config.yaml"
CREATE_SCRIPT = HERMES_HOME / "scripts" / "create-workspace.py"
BACKUP_ROOT = HERMES_HOME / "backups" / "taxonomy-repair"


def _load_create_workspace_module():
    spec = importlib.util.spec_from_file_location("create_workspace_dbfirst", CREATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def get_active_workspace() -> str:
    if not CONFIG_PATH.exists():
        return ""
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("plugins", {}).get("workspace-context", {}).get("workspace", "")
    except Exception:
        return ""


def backup_workspace_db(name: str) -> str | None:
    db_path = WORKSPACES_DIR / name / "workspace.db"
    if not db_path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target_dir = BACKUP_ROOT / name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"workspace-{stamp}.db"
    shutil.copy2(db_path, target)
    return str(target)


def check_workspace(name: str, fix: bool) -> dict:
    ws_path = WORKSPACES_DIR / name
    store = WorkspaceStore(ws_path)
    issues = []
    fixed = []

    for folder in STANDARD_FOLDERS:
        if not (ws_path / folder).exists():
            issues.append(f"FALTA: carpeta {folder}/")

    audit = store.audit()
    for issue in audit["issues"]:
        prefix = issue.severity.upper()
        issues.append(f"{prefix}: {issue.message}")

    if fix and issues:
        backup = backup_workspace_db(name)
        if backup:
            fixed.append(f"backup: {backup}")
        mod = _load_create_workspace_module()
        result = mod.repair_workspace(name, interactive=False, force_import=False)
        fixed.extend(result["created"])
        taxonomy = store.ensure_workspace_taxonomy()
        edge_repair = store.repair_contains_edges()
        cleanup = taxonomy.get("cleanup", {})
        fixed.append(
            "taxonomy plana: "
            f"reparentados={cleanup.get('reparented', 0)} "
            f"eliminados={cleanup.get('deleted', 0)} "
            f"convertidos={cleanup.get('converted', 0)} "
            f"renombrados={cleanup.get('renamed', 0)}"
        )
        if edge_repair["contains_inserted"] or edge_repair["contains_removed"]:
            fixed.append(
                "contains sincronizados: "
                f"+{edge_repair['contains_inserted']} -{edge_repair['contains_removed']}"
            )
        if result["migration"].get("created"):
            fixed.append("workspace.db inicializado")
        audit = store.audit()
        issues = []
        for folder in STANDARD_FOLDERS:
            if not (ws_path / folder).exists():
                issues.append(f"FALTA: carpeta {folder}/")
        for issue in audit["issues"]:
            prefix = issue.severity.upper()
            issues.append(f"{prefix}: {issue.message}")

    return {
        "name": name,
        "issues": issues,
        "fixed": fixed,
        "stats": audit["stats"],
        "exports": "bajo demanda",
    }


def print_report(result: dict, active: str) -> None:
    name = result["name"]
    active_marker = " [ACTIVO]" if name == active else ""
    print(f"\nworkspace: {name}{active_marker}")

    if not result["issues"]:
        print("  ✓ OK — sin problemas detectados")
    else:
        for issue in result["issues"]:
            print(f"  ✗ {issue}")

    for item in result["fixed"]:
        print(f"  → FIX aplicado: {item}")

    stats = result["stats"]
    print(f"  → nodes={stats['nodes']} edges={stats['edges']} artifacts={stats['artifacts']}")
    print(f"  → exports_markdown={result['exports']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica el estado DB-only de los workspaces de Hermes.")
    parser.add_argument("--workspace", metavar="NOMBRE", help="Verificar solo este workspace")
    parser.add_argument("--fix", action="store_true", help="Reparar automáticamente estructura mínima y DB")
    args = parser.parse_args()

    if not WORKSPACES_DIR.exists():
        print(f"ERROR: {WORKSPACES_DIR} no existe")
        sys.exit(1)

    active = get_active_workspace()

    if args.workspace:
        names = [args.workspace]
        if not (WORKSPACES_DIR / args.workspace).exists():
            print(f"ERROR: workspace '{args.workspace}' no encontrado")
            sys.exit(1)
    else:
        names = sorted(d.name for d in WORKSPACES_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))

    if not names:
        print("No hay workspaces.")
        sys.exit(0)

    if args.fix:
        print("Modo --fix activo: se repararán estructura mínima y DB.\n")

    total_issues = 0
    total_fixed = 0
    for name in names:
        result = check_workspace(name, args.fix)
        print_report(result, active)
        total_issues += len(result["issues"])
        total_fixed += len(result["fixed"])

    print()
    if total_issues == 0:
        print("✓ Todos los workspaces están en buen estado.")
    else:
        print(f"Total: {total_issues} problema(s) encontrado(s)", end="")
        if total_fixed:
            print(f", {total_fixed} corrección(es) aplicada(s).")
        else:
            print(". Usa --fix para reparar automáticamente.")


if __name__ == "__main__":
    main()
