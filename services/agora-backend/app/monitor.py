from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .config import settings
from .coordinator import drain_broadcasts, queue_broadcast
from .models import Event, now_iso

logger = logging.getLogger("agora.monitor")


class FleetMonitor:
    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._interval = 60
        self._last_check: str = ""
        self._prev_states: dict[str, str] = {}
        self._checks_total = 0
        self._alerts_total = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="monitor")
        self._thread.start()
        logger.info("monitor started interval=%ds", self._interval)

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("monitor stopped")

    def _loop(self) -> None:
        from .storage import store

        while self._running:
            try:
                self.run_check(store)
            except Exception as exc:
                logger.error("monitor check error: %s", exc)
            time.sleep(self._interval)

    def run_check(self, store=None) -> dict[str, Any]:
        from .storage import store as s

        if store is None:
            store = s

        agents_list = store.agents()
        lxd_agents: list[dict] = []
        try:
            from .orchestrator import orchestrator

            lxd_agents = orchestrator.list_agents()
        except Exception:
            pass

        self._checks_total += 1
        alerts: list[dict] = []

        for a in agents_list:
            if not True:
                continue
            slug = a.container_name.removeprefix("laia-")
            lxd = next((la for la in lxd_agents if la.get("slug") == slug), None)
            current_state = (lxd.get("lxd_state") or "UNKNOWN").upper() if lxd else "NOT_FOUND"
            prev_state = self._prev_states.get(slug, "")

            if current_state in ("STOPPED", "NOT_FOUND") and a.status == "running":
                alerts.append({
                    "agent": slug,
                    "container": a.container_name,
                    "previous": prev_state,
                    "current": current_state,
                    "message": f"Agente {a.container_name}: {prev_state} → {current_state}",
                })

            if current_state == "RUNNING" and prev_state in ("STOPPED", "NOT_FOUND", ""):
                alerts.append({
                    "agent": slug,
                    "container": a.container_name,
                    "previous": prev_state,
                    "current": current_state,
                    "message": f"Agente {a.container_name}: recuperado → {current_state}",
                })

            if current_state != prev_state and prev_state != "":
                level = "critical" if current_state in ("STOPPED", "NOT_FOUND") else "info"
                queue_broadcast("agent_state_change", {
                    "agent": slug,
                    "container": a.container_name,
                    "previous": prev_state,
                    "current": current_state,
                    "level": level,
                })
                store.record_event(Event(
                    event_type="monitor_alert",
                    actor_id="monitor",
                    summary=f"{a.container_name}: {prev_state} → {current_state}",
                    payload={
                        "agent": slug,
                        "previous": prev_state,
                        "current": current_state,
                        "level": level,
                    },
                ))
                self._alerts_total += 1

            self._prev_states[slug] = current_state

        self._last_check = now_iso()
        return {
            "ok": True,
            "checked_at": self._last_check,
            "checks_total": self._checks_total,
            "alerts_total": self._alerts_total,
            "agents_tracked": len(self._prev_states),
            "alerts": alerts,
        }

    def health(self) -> dict:
        return {
            "monitor": "LAIA Fleet Monitor",
            "running": self._running,
            "interval_seconds": self._interval,
            "checks_total": self._checks_total,
            "alerts_total": self._alerts_total,
            "agents_tracked": len(self._prev_states),
            "last_check": self._last_check or "not yet",
        }


monitor = FleetMonitor()
