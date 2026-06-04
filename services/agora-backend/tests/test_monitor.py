"""Tests del FleetMonitor (monitor.py).

Contexto (auditoría 2026-06-02): el bloque `if not True: continue` del bucle
de run_check se reportó (erróneamente) como si hiciera inalcanzable el cuerpo
del bucle. En realidad era un no-op (el `continue` era lo inalcanzable) y el
monitor siempre funcionó. El dead code ya se eliminó; estos tests fijan el
contrato real para que ninguna "limpieza" futura lo rompa de verdad:

- los agentes del store se trackean en cada check,
- una transición RUNNING → STOPPED de un agente "running" emite alerta
  y registra un Event en el store.
"""

from app.models import Agent
from app.monitor import FleetMonitor


class _FakeStore:
    def __init__(self, agents):
        self._agents = agents
        self.events = []

    def agents(self):
        return self._agents

    def record_event(self, event):
        self.events.append(event)


def _agent(slug: str, status: str = "running") -> Agent:
    return Agent(
        id=f"agent_{slug}",
        user_id=f"user_{slug}",
        container_name=f"agent-{slug}",
        status=status,
        workspace_path=f"/tmp/{slug}/workspace.db",
    )


def _patch_lxd(monkeypatch, agents: list[dict]) -> None:
    from app import orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.orchestrator, "list_agents", lambda: agents)


def test_run_check_tracks_every_agent(monkeypatch):
    """El cuerpo del bucle corre para cada agente: todos quedan trackeados."""
    _patch_lxd(monkeypatch, [
        {"slug": "bob", "lxd_state": "RUNNING"},
        {"slug": "carol", "lxd_state": "RUNNING"},
    ])
    store = _FakeStore([_agent("bob"), _agent("carol")])

    result = FleetMonitor().run_check(store)

    assert result["ok"] is True
    assert result["agents_tracked"] == 2


def test_run_check_alerts_on_stop_and_records_event(monkeypatch):
    """RUNNING → STOPPED con agent.status == running ⇒ alerta + Event."""
    store = _FakeStore([_agent("bob", status="running")])
    mon = FleetMonitor()

    _patch_lxd(monkeypatch, [{"slug": "bob", "lxd_state": "RUNNING"}])
    mon.run_check(store)

    _patch_lxd(monkeypatch, [{"slug": "bob", "lxd_state": "STOPPED"}])
    result = mon.run_check(store)

    down = [a for a in result["alerts"] if a["current"] == "STOPPED"]
    assert len(down) == 1
    assert down[0]["agent"] == "bob"
    assert any(e.event_type == "monitor_alert" for e in store.events)


def test_run_check_survives_lxd_failure(monkeypatch):
    """Si LXD no responde, el check completa (agentes como NOT_FOUND)."""
    from app import orchestrator as orch_mod

    def _boom():
        raise RuntimeError("lxc unreachable")

    monkeypatch.setattr(orch_mod.orchestrator, "list_agents", _boom)
    store = _FakeStore([_agent("bob")])

    result = FleetMonitor().run_check(store)

    assert result["ok"] is True
    assert result["agents_tracked"] == 1
