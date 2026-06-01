#!/usr/bin/env python3
"""Publica el estado de salud de LAIA a partir del reporte del runner T1.

Track B · slice B2 (monitor → dashboard). Este helper es la pieza *pura* y
testeable del monitor: NO corre nada del ecosistema. Recibe el reporte JSON que
emite ``tests/integration/run_integrity.sh --json`` y su exit code, calcula un
veredicto (``green`` / ``red`` / ``error``) con su causa, y escribe el estado a
un directorio consultable (por defecto ``/srv/laia/state/health``):

* ``latest.json``    — veredicto + summary + lista de checks fallidos (causa).
* ``latest.txt``     — el mismo veredicto en tabla legible (``cat`` y listo).
* ``report.json``    — el reporte crudo del runner (evidencia completa).
* ``history.jsonl``  — una línea compacta por run, capada a las últimas N.

Diseño (decisiones del PRD B2):
* **Sin email** — sólo estado consultable; Jorge lo mira cuando quiere.
* **Sobrescribe, no acumula ruido** — ``latest.*`` se reescriben atómicamente;
  el histórico es corto (``--history-max``, default 50). No hay canal de alertas
  que pueda spamear: el "cooldown" es la cadencia del timer + el histórico capado.
* **Escritura atómica** — se escribe a un ``.tmp`` y se hace ``os.replace`` para
  que un lector (dashboard) nunca vea un fichero a medias.

Mapeo de veredicto (alineado con los exit codes del runner T1):
* exit 2 / reporte ilegible / sin tests  → ``error`` (el monitor no pudo emitir
  veredicto fiable).
* exit 1 o ``summary.failed > 0``         → ``red`` (algún check de integridad falló).
* exit 0 (``failed == 0`` y ``passed > 0``) → ``green``.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MONITOR_SCHEMA_VERSION = 1
DEFAULT_HISTORY_MAX = 50
STDERR_TAIL_LINES = 15


def _now(args: argparse.Namespace) -> tuple[str, int]:
    """ISO-8601 UTC + epoch. Overridable por flags para tests deterministas."""
    if args.now_epoch is not None:
        epoch = int(args.now_epoch)
        iso = args.now_iso or datetime.fromtimestamp(epoch, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return iso, epoch
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), int(dt.timestamp())


def _tail(text: str, n: int = STDERR_TAIL_LINES) -> str:
    lines = (text or "").rstrip("\n").splitlines()
    return "\n".join(lines[-n:])


def _load_report(path: str) -> tuple[dict[str, Any] | None, str | None]:
    """Devuelve (report, error). report=None si no se pudo leer/parsear."""
    try:
        raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"no se pudo leer el reporte del runner: {exc}"
    if not raw.strip():
        return None, "el runner no emitió reporte (vacío)"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"reporte del runner ilegible (JSON inválido): {exc}"
    if not isinstance(data, dict):
        return None, "reporte del runner con forma inesperada (no es un objeto)"
    return data, None


def _failed_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in report.get("tests", []) or []:
        if t.get("status") == "fail":
            out.append(
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "layers": t.get("layers", []),
                    "exit_code": t.get("exit_code"),
                    "reason": t.get("reason"),
                    "stderr_tail": _tail(t.get("stderr", "")),
                }
            )
    return out


def build_verdict(
    report: dict[str, Any] | None,
    load_error: str | None,
    runner_exit: int,
    *,
    profile: str,
    host: str,
    now_iso: str,
    now_epoch: int,
) -> dict[str, Any]:
    """Construye el dict de veredicto (lo que va a latest.json)."""
    base: dict[str, Any] = {
        "monitor_schema_version": MONITOR_SCHEMA_VERSION,
        "generated_at": now_iso,
        "epoch": now_epoch,
        "host": host,
        "profile_requested": profile,
        "runner_exit_code": runner_exit,
    }

    # Caso error: no hay reporte fiable o el runner reportó error de config (2).
    if report is None or runner_exit == 2:
        cause = load_error or (
            "el runner devolvió exit 2 (error de configuración / ningún test "
            "seleccionado)"
        )
        base.update(
            {
                "status": "error",
                "cause": cause,
                "summary": (report or {}).get("summary"),
                "profile_effective": (report or {}).get("profile"),
                "environment": (report or {}).get("environment"),
                "failed": [],
            }
        )
        return base

    summary = report.get("summary", {}) or {}
    failed_n = int(summary.get("failed", 0) or 0)
    passed_n = int(summary.get("passed", 0) or 0)
    failed = _failed_checks(report)

    if runner_exit == 1 or failed_n > 0:
        status = "red"
        if failed:
            names = ", ".join(f"{f['id']}" for f in failed[:5])
            cause = f"{failed_n} check(s) de integridad fallaron: {names}"
        else:
            cause = f"el runner devolvió exit {runner_exit} (fallo sin detalle por-test)"
    elif passed_n > 0:
        status = "green"
        cause = None
    else:
        # Defensivo: exit 0 sin tests pasados no debería ocurrir (el runner da 2),
        # pero si pasa lo tratamos como error, no como verde falso.
        status = "error"
        cause = "el runner no ejecutó ningún check (0 passed) pese a exit 0"

    base.update(
        {
            "status": status,
            "cause": cause,
            "summary": summary,
            "profile_effective": report.get("profile"),
            "environment": report.get("environment"),
            "failed": failed,
        }
    )
    return base


def render_txt(verdict: dict[str, Any]) -> str:
    s = verdict.get("summary") or {}
    status = verdict["status"].upper()
    lines = [
        f"LAIA health — {status}",
        f"generated: {verdict['generated_at']}  host: {verdict['host']}  "
        f"profile: {verdict.get('profile_effective') or verdict['profile_requested']}",
        "checks: pass={p} fail={f} skip={sk} (total {t})  runner_exit={rc}  duration={d}ms".format(
            p=s.get("passed", "?"),
            f=s.get("failed", "?"),
            sk=s.get("skipped", "?"),
            t=s.get("total", "?"),
            rc=verdict.get("runner_exit_code"),
            d=s.get("duration_ms", "?"),
        ),
    ]
    if verdict.get("cause"):
        lines.append(f"cause: {verdict['cause']}")
    if verdict.get("failed"):
        lines.append("failed checks:")
        for f in verdict["failed"]:
            head = f"  - [{f.get('exit_code')}] {f.get('id')} ({f.get('name')})"
            lines.append(head)
            tail = (f.get("stderr_tail") or "").strip()
            if tail:
                for tl in tail.splitlines()[-3:]:
                    lines.append(f"      {tl}")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _history_line(verdict: dict[str, Any]) -> str:
    s = verdict.get("summary") or {}
    rec = {
        "epoch": verdict["epoch"],
        "at": verdict["generated_at"],
        "status": verdict["status"],
        "pass": s.get("passed"),
        "fail": s.get("failed"),
        "skip": s.get("skipped"),
        "cause": verdict.get("cause"),
    }
    return json.dumps(rec, ensure_ascii=False)


def append_history(state_dir: Path, verdict: dict[str, Any], history_max: int) -> None:
    path = state_dir / "history.jsonl"
    existing: list[str] = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
    existing.append(_history_line(verdict))
    # Sobrescribe, no acumula ruido: nos quedamos con las últimas N.
    trimmed = existing[-history_max:] if history_max > 0 else existing
    _atomic_write(path, "\n".join(trimmed) + "\n")


def publish(
    state_dir: Path,
    verdict: dict[str, Any],
    report: dict[str, Any] | None,
    history_max: int,
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(state_dir / "latest.json", json.dumps(verdict, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(state_dir / "latest.txt", render_txt(verdict))
    if report is not None:
        _atomic_write(state_dir / "report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    append_history(state_dir, verdict, history_max)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Publica estado de salud de LAIA desde el reporte T1")
    p.add_argument("--report", required=True, help="ruta al reporte JSON del runner, o '-' para stdin")
    p.add_argument("--runner-exit", type=int, required=True, help="exit code del runner T1")
    p.add_argument("--state-dir", required=True, help="directorio de estado (p.ej. /srv/laia/state/health)")
    p.add_argument("--profile", default="host", help="perfil solicitado al runner (informativo)")
    p.add_argument("--history-max", type=int, default=DEFAULT_HISTORY_MAX, help="máximo de líneas en history.jsonl")
    p.add_argument("--host", default=None, help="nombre de host (default: hostname)")
    p.add_argument("--now-iso", default=None, help="timestamp ISO fijo (tests)")
    p.add_argument("--now-epoch", type=int, default=None, help="epoch fijo (tests)")
    p.add_argument("--print", action="store_true", help="imprime el veredicto en stdout (txt)")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    now_iso, now_epoch = _now(args)
    host = args.host or socket.gethostname()
    report, load_error = _load_report(args.report)
    verdict = build_verdict(
        report,
        load_error,
        args.runner_exit,
        profile=args.profile,
        host=host,
        now_iso=now_iso,
        now_epoch=now_epoch,
    )
    publish(Path(args.state_dir), verdict, report, args.history_max)
    if args.print:
        sys.stdout.write(render_txt(verdict))
    # El helper SIEMPRE termina 0 cuando logra publicar el estado: la salud se lee
    # del fichero de estado, no del exit code (el monitor no debe "fallar" sólo
    # porque la salud esté roja). Sólo una excepción no capturada daría != 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
