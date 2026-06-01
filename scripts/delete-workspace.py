#!/usr/bin/env python3
# Removes a Hermes workspace with strong manual confirmation and prior backup.

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

import os
from _laia_runtime_paths import laia_home, workspaces_dir

LAIA_HOME = laia_home()
WORKSPACES_DIR = workspaces_dir()
CONFIG_PATH = LAIA_HOME / "config.yaml"
BACKUP_ROOT = LAIA_HOME / "backups" / "deleted-workspaces"


def valid_workspace_name(name: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9\-_]*$", name))


def active_workspace() -> str:
    if not CONFIG_PATH.exists() or yaml is None:
        return ""
    try:
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("plugins", {}).get("workspace-context", {}).get("workspace", "") or ""
    except Exception:
        return ""


def human_size(path: Path) -> str:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    value = float(total)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def confirmation_code(workspace: str, path: Path) -> str:
    # Stable for the current UTC day, specific to this machine path and workspace.
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    material = f"{day}|{workspace}|{path.resolve()}|hermes-delete-workspace-v1"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest().upper()
    return "-".join([digest[0:4], digest[4:8], digest[8:12]])


def archive_workspace(workspace_path: Path, workspace: str) -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_ROOT / f"{workspace}-{stamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(workspace_path, arcname=workspace_path.name)
    return backup_path


def print_plan(workspace: str, workspace_path: Path, *, active: str) -> None:
    code = confirmation_code(workspace, workspace_path)
    print(f"Workspace: {workspace}")
    print(f"Ruta:      {workspace_path}")
    print(f"Tamaño:    {human_size(workspace_path)}")
    print(f"Activo:    {'si' if workspace == active else 'no'}")
    print()
    print("DRY RUN: no se ha borrado nada.")
    print("Si realmente quieres eliminarlo, ejecuta manualmente en una terminal:")
    print()
    print(
        f"python3 {LAIA_HOME / 'scripts' / 'delete-workspace.py'} --workspace {workspace} "
        f"--execute --confirm-code {code}"
    )
    print()
    print("El script pedira escribir el nombre del workspace y una frase exacta.")
    if workspace == active:
        print("AVISO: este workspace esta activo; primero activa otro workspace o usa --allow-active.")


def require_manual_confirmation(workspace: str, workspace_path: Path, expected_code: str, allow_active: bool) -> None:
    if not sys.stdin.isatty():
        raise SystemExit(
            "ERROR: ejecucion no interactiva bloqueada. "
            "Un agente debe mostrarte el comando, no ejecutarlo por ti."
        )

    active = active_workspace()
    if workspace == active and not allow_active:
        raise SystemExit(
            f"ERROR: '{workspace}' es el workspace activo. "
            "Activa otro workspace antes de borrarlo o repite con --allow-active."
        )

    actual_code = confirmation_code(workspace, workspace_path)
    if expected_code != actual_code:
        raise SystemExit("ERROR: codigo de confirmacion incorrecto o caducado.")

    print("Vas a eliminar un workspace completo de Hermes.")
    print(f"Workspace: {workspace}")
    print(f"Ruta:      {workspace_path}")
    print()
    typed_name = input(f"Escribe el nombre exacto del workspace ({workspace}): ").strip()
    if typed_name != workspace:
        raise SystemExit("ERROR: nombre incorrecto. Cancelado.")

    phrase = f"DELETE WORKSPACE {workspace}"
    typed_phrase = input(f"Escribe exactamente '{phrase}': ").strip()
    if typed_phrase != phrase:
        raise SystemExit("ERROR: frase incorrecta. Cancelado.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Elimina un workspace de Hermes con backup previo y confirmacion manual. "
            "Los agentes no deben ejecutar --execute; deben mostrar el comando al usuario."
        )
    )
    parser.add_argument("--workspace", required=True, help="Nombre del workspace a eliminar")
    parser.add_argument("--execute", action="store_true", help="Aplicar el borrado; por defecto solo muestra el plan")
    parser.add_argument("--confirm-code", help="Codigo mostrado por el dry-run para permitir --execute")
    parser.add_argument("--allow-active", action="store_true", help="Permitir borrar el workspace activo")
    args = parser.parse_args()

    workspace = args.workspace.strip()
    if not valid_workspace_name(workspace):
        raise SystemExit("ERROR: nombre de workspace invalido.")

    workspace_path = WORKSPACES_DIR / workspace
    if not workspace_path.is_dir():
        raise SystemExit(f"ERROR: workspace no encontrado: {workspace_path}")
    try:
        workspace_path.resolve().relative_to(WORKSPACES_DIR.resolve())
    except ValueError:
        raise SystemExit("ERROR: ruta fuera de workspaces; cancelado.")

    active = active_workspace()
    if not args.execute:
        print_plan(workspace, workspace_path, active=active)
        return

    if not args.confirm_code:
        raise SystemExit("ERROR: --execute requiere --confirm-code.")

    require_manual_confirmation(
        workspace,
        workspace_path,
        expected_code=args.confirm_code.strip().upper(),
        allow_active=args.allow_active,
    )

    backup_path = archive_workspace(workspace_path, workspace)
    shutil.rmtree(workspace_path)

    print()
    print(f"Backup creado: {backup_path}")
    print(f"Workspace eliminado: {workspace_path}")


if __name__ == "__main__":
    main()
