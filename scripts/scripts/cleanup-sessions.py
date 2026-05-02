#!/usr/bin/env python3
# Archiva y elimina sesiones antiguas de Hermes. Soporta `sessions/` actual y `logs/sessions/` legacy.

from __future__ import annotations

import argparse
import shutil
import os
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
PRIMARY_SESSIONS_DIR = HERMES_HOME / "sessions"
PRIMARY_ARCHIVE_DIR = PRIMARY_SESSIONS_DIR / "archive"
LEGACY_SESSIONS_DIR = HERMES_HOME / "logs" / "sessions"
LEGACY_ARCHIVE_DIR = HERMES_HOME / "logs" / "archive"


def resolve_session_dirs(use_legacy: bool = False) -> tuple[Path, Path]:
    if use_legacy:
        return LEGACY_SESSIONS_DIR, LEGACY_ARCHIVE_DIR
    if PRIMARY_SESSIONS_DIR.exists():
        return PRIMARY_SESSIONS_DIR, PRIMARY_ARCHIVE_DIR
    return LEGACY_SESSIONS_DIR, LEGACY_ARCHIVE_DIR


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def session_mtime(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return datetime.min


def session_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except Exception:
                pass
    return total


def collect_sessions(sessions_dir: Path, archive_dir: Path) -> list[tuple[Path, datetime, int]]:
    if not sessions_dir.exists():
        return []
    entries = []
    for path in sessions_dir.iterdir():
        if path.name.startswith(".") or path == archive_dir:
            continue
        mtime = session_mtime(path)
        size = session_size(path)
        entries.append((path, mtime, size))
    return sorted(entries, key=lambda item: item[1])


def group_by_month(paths: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for path in paths:
        month_key = session_mtime(path).strftime("%Y-%m")
        groups.setdefault(month_key, []).append(path)
    return groups


def archive_group(month_key: str, paths: list[Path], archive_dir: Path, dry_run: bool) -> int:
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"sessions-{month_key}.tar.gz"
    total_size = sum(session_size(path) for path in paths)

    if dry_run:
        return total_size

    if archive_path.exists():
        suffix = datetime.now().strftime("%Y%m%d%H%M%S")
        archive_path = archive_dir / f"sessions-{month_key}-{suffix}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        for path in paths:
            tar.add(path, arcname=path.name)

    for path in paths:
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)

    return total_size


def delete_sessions(paths: list[Path], dry_run: bool) -> int:
    total_size = sum(session_size(path) for path in paths)
    if dry_run:
        return total_size
    for path in paths:
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
    return total_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Archiva y elimina sesiones antiguas de Hermes.")
    parser.add_argument("--execute", action="store_true", help="Aplicar cambios; por defecto solo muestra el plan")
    parser.add_argument("--keep-days", type=int, default=30, metavar="N", help="Conservar sesiones recientes de los últimos N días")
    parser.add_argument("--archive-days", type=int, default=90, metavar="N", help="Archivar sesiones entre keep-days y N días")
    parser.add_argument("--archive-all", action="store_true", help="Nunca eliminar; archivar también las más antiguas")
    parser.add_argument("--legacy", action="store_true", help="Usar rutas legacy logs/sessions y logs/archive")
    args = parser.parse_args()

    sessions_dir, archive_dir = resolve_session_dirs(use_legacy=args.legacy)
    dry_run = not args.execute

    if not sessions_dir.exists():
        print(f"No hay directorio de sesiones: {sessions_dir}")
        sys.exit(0)

    now = datetime.now()
    keep_threshold = now - timedelta(days=args.keep_days)
    archive_threshold = now - timedelta(days=args.archive_days)

    sessions = collect_sessions(sessions_dir, archive_dir)
    if not sessions:
        print("No hay sesiones.")
        sys.exit(0)

    keep = [(path, mt, size) for path, mt, size in sessions if mt >= keep_threshold]
    to_archive = [(path, mt, size) for path, mt, size in sessions if archive_threshold <= mt < keep_threshold]
    to_delete = [(path, mt, size) for path, mt, size in sessions if mt < archive_threshold]

    if args.archive_all:
        to_archive_all = to_archive + to_delete
        to_delete = []
    else:
        to_archive_all = to_archive

    total_size = sum(size for _, _, size in sessions)
    keep_size = sum(size for _, _, size in keep)
    archive_size = sum(size for _, _, size in to_archive_all)
    delete_size = sum(size for _, _, size in to_delete)

    if dry_run:
        print("DRY RUN — usa --execute para aplicar cambios\n")

    print(f"Sesiones: {sessions_dir}")
    print(f"Archivo:  {archive_dir}")
    print(f"Total:    {len(sessions)} sesiones ({human_size(total_size)})")
    print(f"  Conservar (< {args.keep_days} días): {len(keep)} ({human_size(keep_size)})")
    print(f"  Archivar ({args.keep_days}-{args.archive_days} días): {len(to_archive_all)} ({human_size(archive_size)})")
    print(f"  Eliminar (> {args.archive_days} días): {len(to_delete)} ({human_size(delete_size)})")

    if to_archive_all:
        months = sorted(group_by_month([path for path, _, _ in to_archive_all]).keys())
        print(f"  Meses a archivar: {', '.join(months)}")

    if not args.archive_all:
        print(f"\nEspacio a liberar: ~{human_size(delete_size)}")

    if dry_run:
        if to_archive_all or to_delete:
            print("\nNada modificado. Ejecuta con --execute para aplicar.")
        return

    if to_archive_all:
        grouped = group_by_month([path for path, _, _ in to_archive_all])
        for month_key, paths in sorted(grouped.items()):
            archived = archive_group(month_key, paths, archive_dir, dry_run=False)
            print(f"  ✓ Archivado {month_key}: {len(paths)} sesiones ({human_size(archived)})")

    if to_delete:
        deleted = delete_sessions([path for path, _, _ in to_delete], dry_run=False)
        print(f"  ✓ Eliminadas: {len(to_delete)} sesiones ({human_size(deleted)})")

    print("\nLimpieza completada.")


if __name__ == "__main__":
    main()
