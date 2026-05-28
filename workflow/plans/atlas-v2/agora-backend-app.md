# Atlas v2 — services/agora-backend/app/

## Hardcoded refs found

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? | Comment/Code? |
|---|---|---|---|---|---|---|
| config.py | 14 | `/srv/laia/agora` | path | ✅ `srv_agora` | YES | CODE — `self.prod_data_dir = Path(os.environ.get("AGORA_DATA_DIR", "/srv/laia/agora"))` |
| config.py | 73 | `/srv/laia/state` | path | ✅ `srv_laia` (parent) | YES | CODE — `_prod_state = Path(os.environ.get("LAIA_STATE_ROOT", "/srv/laia/state"))` |
| admin.py | 716 | `/srv/laia/users` | path | ✅ `srv_users` | YES | CODE — `user_dir = Path(os.environ.get("AGORA_ADMIN_USERS_ROOT", "/srv/laia/users")) / slug` |
| admin.py | 48 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — `CONTAINER_RE = re.compile(r"...")` hardcoded fallback |
| admin.py | 308 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — skip condition in `_parse_lxc_csv` |
| admin.py | 336 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — hardcoded fallback container dict in `_fallback_containers_from_store` |
| admin.py | 442 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — health check special case for agora container |
| admin.py | 457 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — journalctl service name |
| admin.py | 478 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — journalctl fallback container |
| admin.py | 483 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — lxc exec fallback |
| admin.py | 501 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — `_normalize_container_name` special case |
| admin.py | 876 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — default image alias: `os.environ.get("AGORA_IMAGE_ALIAS", "laia-agora")` |
| admin.py | 1067 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — default auth container: `os.environ.get("AGORA_ADMIN_AUTH_CONTAINER", "laia-agora")` |
| admin.py | 1489 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — `lxc exec laia-agora -- systemctl restart agora-backend` |
| admin.py | 1518 | `~/.laia` | path | ✅ `laia_home` | YES | CODE — Path.home() / ".laia" in `_fix_auth_json_push` |
| admin.py | 1526 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — default auth container var |
| admin.py | 1549 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — default agora container var |
| admin.py | 1563 | `:8088` | port | ✅ `agora_api` (port 8088) | YES | COMMENT — `"a stray PM2 daemon respawns an old uvicorn on host :8088"` (doc comment only) |
| admin.py | 1605 | `~/.laia` | path | ✅ `laia_home` | YES | CODE — `~/.laia/auth.json` in fix description |
| admin.py | 1620 | `~/.laia` | path | ✅ `laia_home` | YES | CODE — `~/.laia` in fix description |
| main.py | 217 | `~/.laia` | path | ✅ `laia_home` | YES | COMMENT — `"Force the env var even if something already set ~/.laia as default"` (comment only) |
| main.py | 224 | `~/.laia` | path | ✅ `laia_home` | YES | COMMENT — `"already invoked load_config before this point, which cached ~/.laia/config.yaml"` (comment only) |
| main.py | 336 | `~/.laia` | path | ✅ `laia_home` | YES | COMMENT — `"~/.laia/auth.json isn't linked yet"` (comment only) |
| main.py | 625 | `~/.laia` | path | ✅ `laia_home` | YES | COMMENT — `"~/.laia/auth.json) and the operator does not have to paste an API key"` (comment only) |
| main.py | 695 | `/opt/laia/workspaces/personal/workspace.db` | path | ✅ `opt_laia` (parent) | YES | CODE — `workspace_path="/opt/laia/workspaces/personal/workspace.db"` in Agent creation |
| main.py | 901 | `laia-agora` | container | ✅ `agora_container` | YES | CODE — coordinator report dict: `"container": "laia-agora"` |
| main.py | 1060 | `/opt/laia/data/tasks/` | path | ✅ `opt_laia` (parent) | YES | CODE — lxc exec command with hardcoded path inside container |
| main.py | 1153 | `/opt/laia/workspaces/personal/workspace.db` | path | ✅ `opt_laia` (parent) | YES | CODE — `existing.workspace_path = "/opt/laia/workspaces/personal/workspace.db"` |
| main.py | 1171 | `/opt/laia/workspaces/personal/workspace.db` | path | ✅ `opt_laia` (parent) | YES | CODE — `workspace_path="/opt/laia/workspaces/personal/workspace.db"` in Agent creation |
| main.py | 1446 | `laia-agora` | container | ✅ `agora_container` | YES | COMMENT — `"laia-agora image"` (doc comment only) |
| orchestrator.py | 250 | `/opt/laia/agent/src` | path | ✅ `opt_laia` (parent) | YES | CODE — `PYTHONPATH=/opt/laia/agent/src` in lxc exec |
| orchestrator.py | 251 | `/opt/laia/runtime/venv/bin/python` | path | ✅ `opt_laia` (parent) | YES | CODE — python path inside container |
| orchestrator.py | 316 | `/opt/laia/healthcheck.sh` | path | ✅ `opt_laia` (parent) | YES | CODE — healthcheck script path |
| orchestrator.py | 321 | `/opt/laia/data/status.json` | path | ✅ `opt_laia` (parent) | YES | CODE — status JSON path inside container |
| orchestrator.py | 374 | `/opt/laia/data/tasks/inbox` | path | ✅ `opt_laia` (parent) | YES | CODE — task inbox path |
| orchestrator.py | 375 | `/opt/laia/data/tasks/inbox/{task_id}.json` | path | ✅ `opt_laia` (parent) | YES | CODE — task file injection path |
| orchestrator.py | 404 | `/opt/laia/data/tasks/{folder}/{task_id}.json` | path | ✅ `opt_laia` (parent) | YES | CODE — task result read path |
| storage.py | 213 | `/opt/laia/workspaces/personal/workspace.db` | path | ✅ `opt_laia` (parent) | YES | CODE — default workspace_path in seed data |
| storage.py | 366 | `/srv/laia/users` | path | ✅ `srv_users` | NO | COMMENT — docstring only: `"bind-mount under /srv/laia/users/<slug>"` |
| marketplace_storage.py | 8 | `/srv/laia/agora` | path | ✅ `srv_agora` | NO | COMMENT — docstring: `"typically /srv/laia/agora"` |

**Total: 38 hardcoded references across 6 files.**

---

## Questions needing answers before migration

1. **`/opt/laia` inside containers vs `/opt/laia` on host**: The paths like `/opt/laia/healthcheck.sh`, `/opt/laia/runtime/venv/bin/python`, `/opt/laia/data/tasks/` exist INSIDE the LXD containers (they are the product installation inside the container). The atlas.yaml `opt_laia` currently points to the HOST's `/opt/laia`. Is there a separate "container-internal product path" concept needed, or should the container paths be derived as container-internal equivalents?

2. **`laia-agora` is both container AND host-level service**: Multiple refs use `laia-agora` as the container name AND as the backend service identifier (e.g., journalctl `-u agora-backend` inside that container). The atlas has `agora_container` for the container but the service itself (`agora-backend`) isn't yet in atlas — should `agora_api` (already in atlas at port 8088) be linked to this container?

3. **`/srv/laia/state` vs `laia_state_root`**: `config.py:73` uses `/srv/laia/state` for LXD agent state (agents.json). The `srv_laia` ref exists but there's no `srv_state` sub-entry. Should we add one or is `srv_laia` sufficient (state is a subdir of srv_laia)?

4. **`~/.laia` references include runtime data dir**: In `main.py:217-224`, `LAIA_HOME` is set to `settings.data_dir` (which is `/srv/laia/agora`) NOT to `~/.laia`. The comments reference `~/.laia` but the actual code sets `LAIA_HOME` to the agora data dir. This appears intentional (plugin discovery must scan agora's config.yaml). Are these `~/.laia` comments still valid as-is, or do they need updating to reflect the dual-LAIA_HOME pattern?

5. **Port 9091 (`executor_api` in atlas) vs hardcoded `:9091`**: The health check at `admin.py:427` uses `:9091` dynamically constructed from `agent.container_ip` (from DB). This is NOT a static hardcode of `agent-jorge:9091` — it's a per-agent runtime value. The atlas `executor_api` entry uses `host: agent-jorge` which may be the default for Jorge's specific container. Should the health check use a service name from atlas instead of constructing the URL dynamically?

6. **Image alias `laia-agora` vs `laia-agent`**: `admin.py:876` defaults to `laia-agora` for `AGORA_IMAGE_ALIAS`. But the `_ALLOWED_IMAGE_ALIASES` defaults to `laia-agent`. This seems like a real discrepancy — the create-agent.sh script produces `laia-agent` images but the code defaults to `laia-agora` for the agora container itself. Is `laia-agora` also a valid image alias for the backend container image?

---

## New refs to add to atlas.yaml

```yaml
# Container-internal product paths (inside LXD containers)
opt_laia_internal:
  type: path
  value: /opt/laia
  description: "Product installation path INSIDE executor containers (healthcheck.sh, runtime, tasks)"

opt_laia_data:
  type: path
  value: /opt/laia/data
  description: "Runtime data dir inside executor containers (tasks, status.json)"

opt_laia_runtime:
  type: path
  value: /opt/laia/runtime
  description: "Python venv inside executor containers"

opt_laia_agent_src:
  type: path
  value: /opt/laia/agent/src
  description: "Agent source code inside executor containers (PYTHONPATH)"

# State subdir of srv_laia
srv_state:
  type: path
  value: /srv/laia/state
  description: "LXD agent state (agents.json)"

# Auth target inside container
agora_auth_target:
  type: path
  value: /opt/agora/data/auth.json
  description: "Path where auth.json is pushed inside laia-agora container"

# PM2 process name
agora_pm2_process:
  type: service
  name: agora-backend
  description: "PM2 process name for agora-backend respawner fix"
```

---

## Summary

- **All 38 hardcoded refs point to values already in atlas.yaml** (or to parent paths that exist there).
- **Most urgent migration candidates**: `config.py` (lines 14, 73) and `admin.py` (line 716) — these are production data paths that should be centralized.
- **Container path (`/opt/laia/*`)**: These live INSIDE containers; the host's `/opt/laia` may be a different thing (product installation). Clarification needed before migration.
- **Comments vs code**: ~8 of the 38 are docstrings/comments only (e.g., `marketplace_storage.py:8`, `admin.py:1563`, `main.py` comments referencing `~/.laia`). Comments don't need migration but should be kept consistent.
- **Dynamic values** (e.g., `agent.container_ip:9091` at `admin.py:427`) are NOT static hardcodes — they use runtime DB data and are acceptable as-is.
