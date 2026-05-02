#!/usr/bin/env python3
# Crea backups rotativos de ~/.hermes en un SSD externo.
"""hermes-backup.py — backup periódico con retención configurable."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
DEFAULT_DEST = Path("/Volumes/PortableSSD/HermesBackups")
DEFAULT_RETENTION_DAYS = 6
DEFAULT_MIN_FREE_GB = 3.0
LOCK_PATH = HERMES_HOME / "locks" / "periodic-backup.lock"

EXCLUDE_PARTS = {
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDE_NAMES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def should_exclude(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES:
        return True
    try:
        rel_parts = path.relative_to(HERMES_HOME.parent).parts
    except ValueError:
        rel_parts = path.parts
    return any(part in EXCLUDE_PARTS for part in rel_parts)


def free_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.free


def ensure_external_destination(dest_root: Path) -> None:
    parts = dest_root.resolve().parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        volume = Path("/", "Volumes", parts[2])
        if not volume.exists() or not os.path.ismount(volume):
            raise SystemExit(f"ERROR: el volumen externo no está montado: {volume}")


def backup_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    path = Path(tarinfo.name)
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return None
    if path.name in EXCLUDE_NAMES or any(path.name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return None
    return tarinfo


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum = sha256_file(path)
    checksum_path.write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
    return checksum_path


def verify_checksum(path: Path, checksum_path: Path) -> bool:
    expected = checksum_path.read_text(encoding="utf-8").split()[0]
    return sha256_file(path) == expected


def sqlite_dbs() -> list[Path]:
    return sorted(path for path in HERMES_HOME.rglob("*.db") if path.is_file() and not should_exclude(path))


def snapshot_sqlite_dbs(target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    checksums: list[str] = []
    for db_path in sqlite_dbs():
        rel = db_path.relative_to(HERMES_HOME)
        out = target_dir / str(rel).replace("/", "__")
        try:
            src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            dst = sqlite3.connect(out)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
        except Exception:
            shutil.copy2(db_path, out)
        checksums.append(f"{sha256_file(out)}  {out.name}")
        count += 1
    (target_dir.parent / "sqlite-db-snapshots.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return count


def create_backup(dest_root: Path, *, dry_run: bool = False, min_free_gb: float = DEFAULT_MIN_FREE_GB) -> Path | None:
    if not HERMES_HOME.exists():
        raise SystemExit(f"ERROR: no existe {HERMES_HOME}")
    ensure_external_destination(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    if free_bytes(dest_root) < int(min_free_gb * 1024**3):
        raise SystemExit(f"ERROR: espacio libre insuficiente en {dest_root}; mínimo {min_free_gb:.1f} GB")

    backup_dir = dest_root / f"hermes-backup-{now_stamp()}"
    archive = backup_dir / "hermes-state.tar.gz"
    if dry_run:
        print(f"DRY RUN: crearía {backup_dir}")
        print(f"DRY RUN: destino libre {human_size(free_bytes(dest_root))}")
        return None

    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest = backup_dir / "MANIFEST.txt"
    manifest.write_text(
        "\n".join(
            [
                "Hermes backup",
                f"Created: {utc_now().isoformat()}",
                f"Source: {HERMES_HOME}",
                "Strategy: full Hermes state excluding regenerable dependencies/caches.",
                "Excluded: node_modules, venv/.venv, __pycache__, test caches, .DS_Store, bytecode.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(HERMES_HOME, arcname=".hermes", filter=backup_filter)

    checksum_path = write_checksum(archive)
    if not verify_checksum(archive, checksum_path):
        raise SystemExit("ERROR: checksum verification failed")
    db_count = snapshot_sqlite_dbs(backup_dir / "sqlite-db-snapshots")
    print(f"Backup creado: {backup_dir}")
    print(f"Archivo: {archive} ({human_size(archive.stat().st_size)})")
    print(f"Checksum: OK")
    print(f"SQLite snapshots: {db_count}")
    return backup_dir


def acquire_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"Backup ya en marcha; lock activo: {LOCK_PATH}")
        raise SystemExit(0)
    handle.write(f"pid={os.getpid()} started={utc_now().isoformat()}\n")
    handle.flush()
    return handle


def prune_backups(dest_root: Path, retention_days: int, *, dry_run: bool = False) -> list[Path]:
    if not dest_root.exists():
        return []
    threshold = datetime.now() - timedelta(days=retention_days)
    removed: list[Path] = []
    for path in sorted(dest_root.glob("hermes-backup-*")):
        if not path.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            continue
        if mtime >= threshold:
            continue
        removed.append(path)
        if not dry_run:
            shutil.rmtree(path)
    if removed:
        action = "Eliminaría" if dry_run else "Eliminado"
        for path in removed:
            print(f"{action}: {path}")
    return removed


def install_launch_agent(dest_root: Path, retention_days: int, interval_seconds: int) -> Path:
    label = "local.hermes.periodic-backup"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    log_dir = HERMES_HOME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    script_path = Path(__file__).resolve()
    python_path = sys.executable
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_path}</string>
    <string>{script_path}</string>
    <string>run</string>
    <string>--dest</string>
    <string>{dest_root}</string>
    <string>--retention-days</string>
    <string>{retention_days}</string>
  </array>
  <key>StartInterval</key>
  <integer>{interval_seconds}</integer>
  <key>StandardOutPath</key>
  <string>{log_dir / "periodic-backup.log"}</string>
  <key>StandardErrorPath</key>
  <string>{log_dir / "periodic-backup.error.log"}</string>
</dict>
</plist>
"""
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist, encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, text=True)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    print(f"LaunchAgent instalado: {plist_path}")
    return plist_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup periódico rotativo de Hermes.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Crear backup y aplicar retención")
    run.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    run.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    run.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    run.add_argument("--dry-run", action="store_true")

    prune = sub.add_parser("prune", help="Eliminar backups más antiguos que la retención")
    prune.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    prune.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    prune.add_argument("--dry-run", action="store_true")

    install = sub.add_parser("install-launchd", help="Instalar programación cada 2 días en macOS")
    install.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    install.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    install.add_argument("--interval-seconds", type=int, default=2 * 24 * 60 * 60)

    args = parser.parse_args()
    if args.command == "run":
        with acquire_lock():
            create_backup(args.dest, dry_run=args.dry_run, min_free_gb=args.min_free_gb)
            prune_backups(args.dest, args.retention_days, dry_run=args.dry_run)
    elif args.command == "prune":
        prune_backups(args.dest, args.retention_days, dry_run=args.dry_run)
    elif args.command == "install-launchd":
        install_launch_agent(args.dest, args.retention_days, args.interval_seconds)


if __name__ == "__main__":
    main()
