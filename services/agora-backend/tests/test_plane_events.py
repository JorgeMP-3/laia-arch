"""POST /api/plane/events — inbound Plane intake (S6 minimal endpoint).

Router-level TestClient (the router has no app-state dependencies); storage
writes go through the real store fixture env set up by conftest.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


EVENT = {
    "delivery": "dlv-1", "event": "issue", "action": "updated",
    "workspace_id": "ws", "project_id": "proj-1", "work_item_id": "wi-1",
    "title": "SEAT VN León 449,00€ junio 26", "state": "Diseño",
    "actor": "vanessa@x.com",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    token_file = tmp_path / "plane-events-token"
    token_file.write_text("tok-events-1\n", encoding="utf-8")
    monkeypatch.setenv("AGORA_PLANE_EVENTS_TOKEN_FILE", str(token_file))

    from app.plane_events import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _post(client, body=None, token="tok-events-1", raw=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    content = raw if raw is not None else json.dumps(body or EVENT)
    return client.post("/api/plane/events", content=content, headers=headers)


def test_valid_event_is_accepted(client):
    r = _post(client)
    assert r.status_code == 202
    assert r.json() == {"ok": True, "delivery": "dlv-1"}


def test_valid_event_is_recorded_in_store(client):
    # The store boots the workspace layer from LAIA_ROOT (workspace_store
    # package). Live-dependency rule: skip cleanly where it is absent.
    try:
        from app.storage import store
    except ModuleNotFoundError as exc:
        pytest.skip(f"agora store unavailable here: {exc}")

    assert _post(client).status_code == 202
    events = [e for e in store.events() if e.event_type == "plane_event"]
    assert events and events[-1].payload["work_item_id"] == "wi-1"


def test_missing_bearer_is_401(client):
    assert _post(client, token=None).status_code == 401


def test_wrong_token_is_403(client):
    assert _post(client, token="nope").status_code == 403


def test_invalid_json_is_400(client):
    assert _post(client, raw="not json{").status_code == 400


def test_missing_required_fields_is_422(client):
    r = _post(client, body={"event": "issue"})
    assert r.status_code == 422


def test_oversized_body_is_413(client):
    big = dict(EVENT, title="x" * (70 * 1024))
    assert _post(client, body=big).status_code == 413


def test_unprovisioned_token_file_is_503(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_PLANE_EVENTS_TOKEN_FILE", str(tmp_path / "missing"))
    from app.plane_events import router
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post("/api/plane/events", content=json.dumps(EVENT),
               headers={"Authorization": "Bearer tok-events-1"})
    assert r.status_code == 503
