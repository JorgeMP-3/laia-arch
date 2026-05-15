#!/usr/bin/env python3
"""
LAIA Nightly Shutdown
Ejecutado por laia-nightly.service a las 00:00.

Flujo:
  1. Ventana de cancelación de 5 min (crea /tmp/laia-cancel-shutdown para abortar)
  2. Sync git de todos los workspaces
  3. Programa alarma RTC para las 07:30
  4. Apaga el servidor
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from _laia_runtime_paths import laia_root

LAIA_ROOT   = laia_root()
SCRIPTS_DIR = LAIA_ROOT / "scripts"
CANCEL_FILE = Path("/tmp/laia-cancel-shutdown")
LOG_FILE    = LAIA_ROOT / "logs" / "nightly.log"
WAKE_HOUR   = 7
WAKE_MINUTE = 30
CANCEL_WINDOW = 5 * 60  # segundos

# ── helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a") as f:
        f.write(line + "\n")

def _load_git_manager():
    spec = importlib.util.spec_from_file_location(
        "git_manager", SCRIPTS_DIR / "git-manager.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.WorkspaceGitManager()

# ── pasos ─────────────────────────────────────────────────────────────────────

def wait_cancel_window() -> bool:
    """Espera CANCEL_WINDOW segundos. Devuelve True si se debe abortar."""
    log(f"Apagado programado en {CANCEL_WINDOW // 60} minutos.")
    log(f"Para cancelar: touch {CANCEL_FILE}")

    CANCEL_FILE.unlink(missing_ok=True)
    deadline = time.monotonic() + CANCEL_WINDOW
    while time.monotonic() < deadline:
        if CANCEL_FILE.exists():
            log("Apagado CANCELADO por el usuario.")
            CANCEL_FILE.unlink(missing_ok=True)
            return True
        remaining = int(deadline - time.monotonic())
        if remaining % 60 == 0 and remaining > 0:
            log(f"  {remaining // 60} min para el apagado...")
        time.sleep(5)
    return False


def sync_workspaces() -> dict:
    log("Iniciando sync git de workspaces...")
    try:
        mgr = _load_git_manager()
        results: dict[str, str] = {}
        workspaces = mgr.list_all()
        for ws in workspaces:
            if ws.get("excluded"):
                continue
            name = ws["workspace"]
            repos = ws.get("repos", [])
            if not repos:
                continue
            # Solo sincroniza repos con remote y cambios pendientes (o ahead)
            has_pending = any(
                (not r["git"]["clean"] or r["git"]["ahead"] > 0)
                for r in repos
                if r.get("git", {}).get("has_remote")
            )
            if not has_pending:
                results[name] = "sin cambios"
                log(f"  {name}: sin cambios")
                continue
            result = mgr.push_to_github(
                name, commit_message=f"sync: nightly {datetime.now().strftime('%Y-%m-%d')}"
            )
            status = "ok" if result["ok"] else f"error: {result.get('message','')}"
            results[name] = status
            icon = "✓" if result["ok"] else "✗"
            log(f"  {icon} {name}: {status}")
        return results
    except Exception as e:
        log(f"Error en sync: {e}")
        return {"error": str(e)}


def set_rtc_wake() -> bool:
    """Programa el RTC para despertar a WAKE_HOUR:WAKE_MINUTE mañana."""
    try:
        import math
        now = datetime.now()
        # Calcular timestamp de la próxima ocurrencia de WAKE_HOUR:WAKE_MINUTE
        from datetime import timedelta
        wake = now.replace(hour=WAKE_HOUR, minute=WAKE_MINUTE, second=0, microsecond=0)
        if wake <= now:
            wake += timedelta(days=1)

        wake_utc = wake.astimezone(timezone.utc)
        wake_ts  = int(wake_utc.timestamp())

        # Primero limpiar alarma anterior
        subprocess.run(["bash", "-c", "echo 0 > /sys/class/rtc/rtc0/wakealarm"], check=True)
        subprocess.run(["bash", "-c", f"echo {wake_ts} > /sys/class/rtc/rtc0/wakealarm"], check=True)

        log(f"Alarma RTC configurada: {wake.strftime('%H:%M')} ({wake.strftime('%Y-%m-%d')})")
        return True
    except Exception as e:
        log(f"Error configurando RTC: {e} — intentando con rtcwake...")
        try:
            wake_str = f"tomorrow {WAKE_HOUR:02d}:{WAKE_MINUTE:02d}"
            ts = subprocess.check_output(
                ["date", "-d", wake_str, "+%s"], text=True
            ).strip()
            subprocess.run(
                ["rtcwake", "-m", "no", "-t", ts], check=True
            )
            log(f"Alarma RTC configurada con rtcwake: {wake_str}")
            return True
        except Exception as e2:
            log(f"Error con rtcwake: {e2}")
            return False


def write_shutdown_report(sync_results: dict) -> None:
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wake_scheduled": f"{WAKE_HOUR:02d}:{WAKE_MINUTE:02d}",
        "sync": sync_results,
    }
    report_path = LAIA_ROOT / "logs" / "last-shutdown.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log(f"Informe guardado en {report_path}")


def poweroff() -> None:
    log("Apagando servidor... hasta las 07:30.")
    subprocess.run(["systemctl", "poweroff"])


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log("=" * 60)
    log("LAIA Nightly Shutdown iniciado")

    if wait_cancel_window():
        sys.exit(0)

    sync_results = sync_workspaces()
    rtc_ok       = set_rtc_wake()

    if not rtc_ok:
        log("AVISO: No se pudo configurar la alarma RTC. El servidor NO se encenderá automáticamente.")

    write_shutdown_report(sync_results)
    poweroff()


if __name__ == "__main__":
    main()
