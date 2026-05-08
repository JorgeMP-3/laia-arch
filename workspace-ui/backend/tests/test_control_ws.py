from __future__ import annotations

import importlib
import sys
import textwrap

from fastapi.testclient import TestClient


def _write_fake_gateway(path):
    path.write_text(
        textwrap.dedent(
            """
            import json
            import sys


            def send(obj):
                sys.stdout.write(json.dumps(obj) + "\\n")
                sys.stdout.flush()


            send({
                "jsonrpc": "2.0",
                "method": "event",
                "params": {"type": "gateway.ready", "payload": {"skin": {"branding": {"agent": "Laia"}}}},
            })

            created = []

            for raw in sys.stdin:
                req = json.loads(raw)
                rid = req.get("id")
                method = req.get("method")
                params = req.get("params") or {}

                if method == "session.create":
                    created.append(params.get("app_context", ""))
                    sid = f"fake-session-{len(created)}"
                    send({"jsonrpc": "2.0", "id": rid, "result": {"session_id": sid, "info": {"model": "fake"}}})
                    send({
                        "jsonrpc": "2.0",
                        "method": "event",
                        "params": {"type": "session.info", "session_id": sid, "payload": {"model": "fake"}},
                    })
                    continue

                if method == "prompt.submit":
                    sid = params.get("session_id", "fake-session")
                    send({"jsonrpc": "2.0", "id": rid, "result": {"status": "streaming"}})
                    send({"jsonrpc": "2.0", "method": "event", "params": {"type": "message.start", "session_id": sid}})
                    send({
                        "jsonrpc": "2.0",
                        "method": "event",
                        "params": {"type": "tool.complete", "session_id": sid, "payload": {
                            "tool_id": "t1",
                            "name": "apply_patch",
                            "inline_diff": "--- a/app.py\\n+++ b/app.py\\n@@\\n-old\\n+new",
                        }},
                    })
                    send({
                        "jsonrpc": "2.0",
                        "method": "event",
                        "params": {"type": "message.complete", "session_id": sid, "payload": {"text": "done"}},
                    })
                    continue

                if method == "approval.respond":
                    send({"jsonrpc": "2.0", "id": rid, "result": {"resolved": True}})
                    continue

                send({"jsonrpc": "2.0", "id": rid, "error": {"code": 404, "message": f"unknown {method}"}})
            """
        ),
        encoding="utf-8",
    )


def test_control_ws_forwards_gateway_events_and_inline_diff(tmp_path, monkeypatch):
    fake_gateway = tmp_path / "fake_gateway.py"
    _write_fake_gateway(fake_gateway)

    monkeypatch.setenv("HERMES_WEB_GATEWAY_CMD", f"{sys.executable} -u {fake_gateway}")
    monkeypatch.setenv("HERMES_WEB_IDLE_CLOSE_SECONDS", "0.01")

    import main

    importlib.reload(main)

    with TestClient(main.app) as client:
        with client.websocket_connect("/api/control/ws") as ws:
            seen = [ws.receive_json(), ws.receive_json(), ws.receive_json()]
            assert any(msg["type"] == "event" and msg["event"] == "gateway.ready" for msg in seen)
            assert any(msg["type"] == "event" and msg["event"] == "control.ready" for msg in seen)
            assert any(msg["type"] == "event" and msg["event"] == "session.info" for msg in seen)

            ws.send_json({
                "type": "request",
                "id": "submit-1",
                "method": "prompt.submit",
                "params": {"text": "haz un cambio"},
            })

            messages = [ws.receive_json() for _ in range(4)]
            assert {"type": "response", "id": "submit-1", "ok": True, "result": {"status": "streaming"}} in messages
            diff_events = [
                msg for msg in messages
                if msg["type"] == "event" and msg["event"] == "tool.complete"
            ]
            assert diff_events
            assert diff_events[0]["payload"]["inline_diff"] == "--- a/app.py\n+++ b/app.py\n@@\n-old\n+new"

            ws.send_json({
                "type": "request",
                "id": "approval-1",
                "method": "approval.respond",
                "params": {"choice": "once"},
            })
            assert ws.receive_json() == {
                "type": "response",
                "id": "approval-1",
                "ok": True,
                "result": {"resolved": True},
            }


def test_control_ws_isolates_sessions_by_area_and_context(tmp_path, monkeypatch):
    fake_gateway = tmp_path / "fake_gateway.py"
    _write_fake_gateway(fake_gateway)

    monkeypatch.setenv("HERMES_WEB_GATEWAY_CMD", f"{sys.executable} -u {fake_gateway}")
    monkeypatch.setenv("HERMES_WEB_IDLE_CLOSE_SECONDS", "0.01")

    import main

    importlib.reload(main)

    def recv_ready(ws):
        for _ in range(5):
            msg = ws.receive_json()
            if msg["type"] == "event" and msg["event"] == "control.ready":
                return msg
        raise AssertionError("control.ready not received")

    with TestClient(main.app) as client:
        with client.websocket_connect("/api/control/ws?area_id=workspace&app_context=WORKSPACE") as ws:
            workspace_ready = recv_ready(ws)
        with client.websocket_connect("/api/control/ws?area_id=command-center&app_context=COMMAND") as ws:
            command_ready = recv_ready(ws)
        with client.websocket_connect("/api/control/ws?area_id=workspace&app_context=WORKSPACE") as ws:
            workspace_again = recv_ready(ws)
        with client.websocket_connect("/api/control/ws?area_id=workspace&app_context=WORKSPACE_V2") as ws:
            workspace_changed = recv_ready(ws)

        assert workspace_ready["payload"]["area_id"] == "workspace"
        assert command_ready["payload"]["area_id"] == "command-center"
        assert workspace_ready["session_id"] != command_ready["session_id"]
        assert workspace_again["session_id"] == workspace_ready["session_id"]
        assert workspace_changed["session_id"] != workspace_ready["session_id"]
