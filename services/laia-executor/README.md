# laia-executor

Thin tool executor service that runs **inside each user's LXD container** in the AGORA Agents architecture.

## Role

AGORA (in container `laia-agora`) runs the AIAgent / LLM. When the LLM decides to call a filesystem/bash tool, AGORA forwards the call here via HTTP. The executor runs the tool as `root` inside the user's container (full freedom, no sandbox) and returns the result.

```
AGORA AIAgent → HTTP POST /exec → laia-executor → tool handler → result → AGORA
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/exec` | Execute a single tool: `{tool, args, request_id}` → `{ok, result \| error}` |
| GET    | `/health` | Liveness probe |
| GET    | `/profile` | Container identity: slug, ip, uptime, version |
| GET    | `/workspace/files` | List files under `?path=` (utility) |

All endpoints (except `/health`) require `Authorization: Bearer <token>`. Token is read from `/etc/laia/executor-token` (mode 0600). AGORA holds the same token in its database (`agents.api_token`) and sends it in every request.

## Supported tools (native, no `.laia-core` dependency)

- `read_file(path, offset=1, limit=500)`
- `write_file(path, content)`
- `apply_patch(path, old_string, new_string, replace_all=False)`
- `list_dir(path)`
- `glob(pattern, path=".")`
- `grep(pattern, path=".", include=None)` (uses `rg` if available, falls back to Python)
- `bash(command, cwd=None, timeout=120, env=None)`
- `delete_file(path)`
- `move_file(src, dst)`
- `make_dir(path, parents=True)`

## Run locally (dev)

```bash
cd services/laia-executor
python -m venv .venv && source .venv/bin/activate
pip install -e .
echo "dev-token-123" | sudo tee /etc/laia/executor-token >/dev/null
sudo chmod 600 /etc/laia/executor-token
laia-executor  # listens on 0.0.0.0:9091
```

Test:
```bash
curl http://localhost:9091/health
curl -H "Authorization: Bearer dev-token-123" \
     -X POST http://localhost:9091/exec \
     -H "Content-Type: application/json" \
     -d '{"tool":"read_file","args":{"path":"/etc/hostname"},"request_id":"t1"}'
```

## Production (inside LXD container)

Systemd unit at `systemd/laia-executor.service` starts the executor on container boot, listening on `0.0.0.0:9091`. The container's IP is registered in AGORA DB (`agents.container_ip`) so AGORA knows where to forward.

## Architecture decisions

1. **Native tool handlers** (not imported from `.laia-core/tools/`). Reason: `.laia-core/tools/file_tools.py:12` imports `agora_sandbox` at module level — that sandbox is being archived in Fase 4. Implementing native handlers here keeps the executor standalone and lightweight, no `.laia-core` install required in the container.
2. **No internal state / no DB**. Persistence lives on bind-mounted host volumes (`/srv/laia/users/{slug}/`).
3. **Root inside container**. The user is root, the executor runs as root. The container itself is LXD unprivileged, so root inside = uid 100000 on host.
4. **One service, one binary**. Replaces `laia-agent.service` + `laia-agent-api.service` from sprint 2.
