"""Tests for WebSocket (Fase 6)."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.security import create_access_token
from app.config import settings

client = TestClient(app)


def get_token(user_id: str = "user_jorge", role: str = "agora_admin") -> str:
    return create_access_token(user_id, role, settings.jwt_secret)


def test_ws_missing_token():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            pass


def test_ws_invalid_token():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=bad-token") as ws:
            pass


def test_ws_connect_valid_token():
    token = get_token()
    with client.websocket_connect(f"/ws?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "connected"
        assert data["user_id"] == "user_jorge"
        assert data["role"] == "agora_admin"
        ws.close()


def test_ws_ping_pong():
    token = get_token()
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.receive_json()  # connected message
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        ws.close()
