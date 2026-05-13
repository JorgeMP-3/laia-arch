from __future__ import annotations

import json
import threading
import time
from typing import Any

from .config import settings
from .models import Agent, Event, Task, now_iso

_pending_broadcasts: list[dict[str, Any]] = []
_broadcast_lock = threading.Lock()


def queue_broadcast(event_type: str, payload: dict[str, Any]) -> None:
    with _broadcast_lock:
        _pending_broadcasts.append({"type": event_type, "payload": payload})
        if len(_pending_broadcasts) > 200:
            _pending_broadcasts[:] = _pending_broadcasts[-100:]


def drain_broadcasts() -> list[dict[str, Any]]:
    with _broadcast_lock:
        items = list(_pending_broadcasts)
        _pending_broadcasts.clear()
    return items


class Coordinator:
    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_check: str = ""
        self._check_interval = 30

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="coordinator")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        from .storage import store

        while self._running:
            try:
                self.run_check(store)
            except Exception:
                pass
            time.sleep(self._check_interval)

    def run_check(self, store=None) -> dict[str, Any]:
        from .storage import store as s

        if store is None:
            store = s

        alerts: list[dict] = []
        tasks = store.tasks()
        agents_list = store.agents()
        lxd_agents: list[dict] = []
        try:
            from .orchestrator import orchestrator

            lxd_agents = orchestrator.list_agents()
        except Exception:
            pass

        agent_map = {a.container_name: a for a in agents_list}

        for lxd in lxd_agents:
            slug = lxd.get("slug", "")
            container = f"laia-{slug}"
            state = (lxd.get("lxd_state") or "").upper()
            registered_agent = agent_map.get(container)

            if state == "STOPPED":
                alerts.append({
                    "level": "warning",
                    "message": f"Agente {container} esta parado",
                    "agent": container,
                    "state": state,
                })
            elif state in ("", "unknown") and registered_agent is None:
                pass
            elif registered_agent and registered_agent.status not in ("running", "stopped"):
                alerts.append({
                    "level": "info",
                    "message": f"Agente {container} registrado como '{registered_agent.status}' pero LXD dice '{state}'",
                    "agent": container,
                    "state": state,
                    "registered_status": registered_agent.status,
                })

        for agent in agents_list:
            if agent.container_name not in agent_map:
                agent_map[agent.container_name] = agent
            found = any(
                a for a in lxd_agents
                if a.get("slug") == agent.container_name.removeprefix("laia-")
            )
            if not found and agent.status == "running":
                alerts.append({
                    "level": "warning",
                    "message": f"Agente {agent.container_name} registrado como running pero no aparece en LXD",
                    "agent": agent.container_name,
                })

        stale_hours = 24
        for t in tasks:
            if t.status == "blocked":
                try:
                    created = t.created_at
                    from datetime import datetime, timezone, timedelta

                    dt = datetime.fromisoformat(created)
                    if datetime.now(timezone.utc) - dt > timedelta(hours=stale_hours):
                        alerts.append({
                            "level": "warning",
                            "message": f"Tarea '{t.title}' bloqueada mas de {stale_hours}h",
                            "task_id": t.id,
                            "task_title": t.title,
                        })
                except (ValueError, TypeError):
                    pass

        for alert in alerts:
            store.record_event(Event(
                id=f"alert_{now_iso().replace(':','-').replace('.','-')}_{alert['level']}",
                event_type="coordinator_alert",
                actor_id="coordinator",
                summary=alert["message"],
                payload=alert,
            ))
            queue_broadcast("coordinator_alert", alert)

        self._last_check = now_iso()
        return {
            "ok": True,
            "checked_at": self._last_check,
            "agents_scanned": len(lxd_agents),
            "alerts_generated": len(alerts),
            "alerts": alerts,
        }

    def get_alerts(self, store=None, limit: int = 50) -> list[dict]:
        from .storage import store as s

        if store is None:
            store = s
        events = store.events()
        alerts = []
        for e in reversed(events):
            if e.event_type == "coordinator_alert":
                alerts.append({
                    "id": e.id,
                    "created_at": e.created_at,
                    "summary": e.summary,
                    "payload": e.payload if isinstance(e.payload, dict) else {},
                })
            if len(alerts) >= limit:
                break
        return alerts


coordinator = Coordinator()
