#!/usr/bin/env python3
"""
LAIA Startup Report
Ejecutado por laia-startup.service al arranque del servidor.

Registra la hora de inicio, calcula tiempo apagado, y escribe
un informe en logs/startup.log y logs/last-startup.json.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

LAIA_ROOT        = Path(os.environ.get("HERMES_HOME") or (Path.home() / "LAIA"))
LOG_FILE         = LAIA_ROOT / "logs" / "startup.log"
LAST_STARTUP     = LAIA_ROOT / "logs" / "last-startup.json"
LAST_SHUTDOWN    = LAIA_ROOT / "logs" / "last-shutdown.json"


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a") as f:
        f.write(line + "\n")


def get_uptime_kernel() -> str:
    try:
        out = subprocess.check_output(["uptime", "-p"], text=True).strip()
        return out
    except Exception:
        return "desconocido"


def get_load() -> str:
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        return f"{parts[0]} {parts[1]} {parts[2]}"
    except Exception:
        return "desconocido"


def calc_downtime(shutdown_ts: str) -> str:
    try:
        from datetime import timedelta
        shutdown = datetime.fromisoformat(shutdown_ts)
        now      = datetime.now(timezone.utc)
        delta    = now - shutdown
        h, rem   = divmod(int(delta.total_seconds()), 3600)
        m        = rem // 60
        return f"{h}h {m}m"
    except Exception:
        return "desconocido"


def main() -> None:
    now = datetime.now(timezone.utc)
    log("=" * 60)
    log(f"Servidor iniciado — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Tiempo apagado
    downtime = "desconocido"
    if LAST_SHUTDOWN.exists():
        try:
            data = json.loads(LAST_SHUTDOWN.read_text())
            downtime = calc_downtime(data["timestamp"])
            log(f"Tiempo apagado: {downtime}")
            last_sync = data.get("sync", {})
            synced = [k for k, v in last_sync.items() if v == "ok"]
            if synced:
                log(f"Repos sincronizados anoche: {', '.join(synced)}")
        except Exception:
            pass

    log(f"Load: {get_load()}")

    report = {
        "timestamp": now.isoformat(),
        "downtime": downtime,
        "load": get_load(),
        "kernel_uptime": get_uptime_kernel(),
    }
    LAST_STARTUP.parent.mkdir(parents=True, exist_ok=True)
    LAST_STARTUP.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log("Informe de arranque guardado.")


if __name__ == "__main__":
    main()
