# Atlas v2 — services/agora-backend/ (other files)

## Source files examined
- `app/agent_pool.py`
- `app/storage.py`
- `app/orchestrator.py`
- `app/models.py`
- `app/agent_identity.py`
- `app/laia_identity.py`
- `app/laia_chat.py`
- `app/llm_config.py`
- `start.sh`
- `tests/test_agents.py`
- `tests/test_admin_control_center.py`
- `tests/test_agent_profile.py`
- `tests/test_agent_pool.py`

---

## Hardcoded refs found

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? | Comment/Code? |
|---|---|---|---|---|---|---|
| app/admin.py | 716 | `/srv/laia/users` | path | `srv_users` (line 87) | YES | Code — `AGORA_ADMIN_USERS_ROOT` fallback default |
| app/config.py | 14 | `/srv/laia/agora` | path | `srv_agora` (line 82) | YES | Code — `AGORA_DATA_DIR` fallback default |
| app/config.py | 73 | `/srv/laia/state` | path | `srv_laia` only (parent, line 33) | YES | Code — `LAIA_STATE_ROOT` fallback default; no dedicated entry |
| app/storage.py | 366 | `/srv/laia/users/<slug>` | path | `srv_users` (line 87) | N/A | Comment — only mentions the path in passing |
| app/marketplace_storage.py | 8 | `/srv/laia/agora` | path | `srv_agora` (line 82) | N/A | Comment — "typically `/srv/laia/agora`" in docstring |
| app/admin.py | 336 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded in fallback list; env var exists but not checked |
| app/admin.py | 442 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded special-case in `_enrich_container` |
| app/admin.py | 457, 478 | `"agora-backend"`, `"laia-agora"` | service/container | `agora_container` (line 130) | YES | Code — hardcoded journalctl args in `_journal_lines` |
| app/admin.py | 483 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded fallback in `_journal_lines` |
| app/admin.py | 501 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded comparison in `_normalize_container_name` |
| app/admin.py | 1489 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded in `restart_backend` job |
| app/admin.py | 876 | `"laia-agora"` (default) | container | `agora_container` (line 130) | NO | Env-var-only code; already uses `os.environ.get("AGORA_IMAGE_ALIAS", "laia-agora")` — env override is sufficient |
| app/admin.py | 1067, 1526, 1549 | `"laia-agora"` (default) | container | `agora_container` (line 130) | NO | Env-var-only code; `os.environ.get(..., "laia-agora")` — env override is sufficient |
| app/main.py | 901 | `"laia-agora"` | container | `agora_container` (line 130) | YES | Code — hardcoded in status endpoint return dict |
| app/main.py | 1446 | `"laia-agora"` | container | `agora_container` (line 130) | N/A | Comment only — "guaranteed to exist inside the laia-agora image" |
| app/orchestrator.py | 250 | `/opt/laia/agent/src` | path | NO | YES | Code — hardcoded Python path used in `run_agent_script` |
| app/orchestrator.py | 251 | `/opt/laia/runtime/venv/bin/python` | path | NO | YES | Code — hardcoded venv python in `run_agent_script` |
| app/orchestrator.py | 316 | `/opt/laia/healthcheck.sh` | path | NO | YES | Code — hardcoded healthcheck path in `get_agent_status` |
| app/orchestrator.py | 321 | `/opt/laia/data/status.json` | path | NO | YES | Code — hardcoded path in `get_agent_status` |
| app/orchestrator.py | 374 | `/opt/laia/data/tasks/inbox/` | path | NO | YES | Code — hardcoded path in `deliver_task` |
| app/orchestrator.py | 404 | `/opt/laia/data/tasks/{folder}/` | path | NO | YES | Code — hardcoded path in `read_task_result` |
| app/storage.py | 213 | `/opt/laia/workspaces/personal/workspace.db` | path | NO | YES | Code — hardcoded default workspace seed path |
| app/main.py | 695, 1153, 1171 | `/opt/laia/workspaces/personal/workspace.db` | path | NO | YES | Code — hardcoded default workspace path in agent creation |
| app/admin.py | 649 | `/opt/laia/workspaces/personal/workspace.db` | path | NO | YES | Code — hardcoded default in `_provision_user_job` |
| app/admin.py | 1562-1563 | `:8088` | port | `agora_api` (line 112) | N/A | Comment only — "on host :8088 even after kill" in PM2 fix docstring |
| app/admin.py | 427 | `:9091` (health endpoint) | port | `executor_api` (line 120) | YES | Code — uses `{agent.container_ip}:9091/health`; `executor_api` exists in atlas |
| app/admin.py | 430 | `:9091` (profile endpoint) | port | `executor_api` (line 120) | YES | Code — uses `{agent.container_ip}:9091/profile`; `executor_api` exists in atlas |
| app/laia_chat.py | 21, 23, 30 | `"laia-agora"` | container | `agora_container` (line 130) | N/A | Comment/docstring — architectural explanation, not code |
| app/llm_config.py | 13 | `"laia-agora"` | container | `agora_container` (line 130) | N/A | Comment — "inside the laia-agora container" in docstring |
| app/agent_pool.py | 415, 429, 434, 450, 471, 474 | `"laia-agora"` | container | `agora_container` (line 130) | N/A | Comment — docstrings explaining executor/toolset behavior |
| app/agent_identity.py | 10 | `{"laia-agora", "laia-jorge"}` | container-set | `agora_container` (line 130) + `jorge_container` (line 135) | NO | Code but identity constant — define once via atlas is cleaner |
| app/models.py | 23 | `"laia-agora"` | container | `agora_container` (line 130) | NO | Code — reserved slug set; already enforced by platform |
| tests/test_agents.py | 227 | `"laia-agora"`, `"laia-arch"` | container | `agora_container` (line 130) | NO | Test data — test asserting reserved slug rejection |
| tests/test_admin_control_center.py | 50, 73 | `"laia-agora"` | container | `agora_container` | NO | Test data — CSV fixtures and assertions |
| tests/test_agent_profile.py | 25 | `/opt/laia/data/profile` | path | NO | NO | Test fixture — fake profile path, not real infrastructure path |
| tests/test_agent_pool.py | 102 | `~/.laia/config.yaml` | path | `laia_home` (line 23) | NO | Test assertion — verifies fallback behavior |
| start.sh | 5 | Port `8088` | port | `agora_api` (line 112) | NO | Env-var-backed; `LAIA_AGORA` + `exec uvicorn ... --port 8088` are safe defaults |
| app/main.py | 217, 224 | `~/.laia` | path | `laia_home` (line 23) | NO | Comment — explains env override reasoning |

---

## Questions needing answers

1. **Should `opt_laia` sub-paths be added to atlas.yaml?**
   - `/opt/laia/agent/src`, `/opt/laia/runtime/venv/bin/python`, `/opt/laia/healthcheck.sh`, `/opt/laia/data/status.json`, `/opt/laia/data/tasks/{folder}/`, `/opt/laia/workspaces/personal/workspace.db` — all inside the installed product under `/opt/laia`.
   - These could get entries under `opt_laia` as interpolated refs.

2. **`/srv/laia/state` has no dedicated atlas entry** — only the parent `srv_laia` exists. Should a `srv_state` entry be added for completeness?

3. **`agent-jorge` appears in atlas as `jorge_container`** (line 135) but the codebase has zero mentions of `agent-jorge` as a literal string. The only reference is `executor_api.host: agent-jorge` in atlas.yaml. Is the executor host actually "agent-jorge" or should this be verified?

4. **Container name vs slug constants** (`agent_identity.py:10`, `models.py:23`): These are canonical identity constants (not connection references). Is it appropriate to have a set of protected container names in atlas.yaml? Or leave as code constants since they represent identity rather than location?

5. **`laia-agora` hardcoded in `restart_backend` job** (admin.py:1489): Even if other parts use `os.environ.get` with a fallback, the job runner hardcodes the container name. Should the job runner also use the env-var pattern for consistency?

---

## New refs to add

### HIGH priority (connection strings that may change)

```yaml
  # ── Paths inside /opt/laia that are hardcoded in agora-backend ──────────────

  opt_laia_workspace:
    type: path
    value: ${ref.opt_laia}/workspaces/personal/workspace.db
    description: "Default workspace.db path for personal agents"

  opt_laia_agent_src:
    type: path
    value: ${ref.opt_laia}/agent/src
    description: "Python source tree for laia-agent"

  opt_laia_runtime_venv:
    type: path
    value: ${ref.opt_laia}/runtime/venv/bin/python
    description: "Python venv binary for agent runtime"

  opt_laia_healthcheck:
    type: path
    value: ${ref.opt_laia}/healthcheck.sh
    description: "Healthcheck script inside agent containers"

  opt_laia_agent_data:
    type: path
    value: ${ref.opt_laia}/data
    description: "Agent data directory (tasks, status.json)"
```

### MEDIUM priority (documented but no dedicated entry)

```yaml
  srv_state:
    type: path
    value: ${ref.srv_laia}/state
    description: "LXD orchestrator persistent state"
    note: "Only referenced as parent of agents.json; no direct path refs in codebase"
```

### Already covered by atlas.yaml (no action needed)

- `/srv/laia/users` → `srv_users: ${ref.srv_laia}/users`
- `/srv/laia/agora` → `srv_agora: ${ref.srv_laia}/agora`
- `laia-agora` (container) → `agora_container: laia-agora`
- `agora-backend` (service-name in journalctl) → derived from container but not standalone
- `:8088` → `agora_api.port: 8088`
- `:9091` → `executor_api.port: 9091`
- `~/.laia` → `laia_home: ~/.laia`

### Not needed in atlas

- Test fixture paths (e.g., `/opt/laia/data/profile` in test_agent_profile.py — fake data)
- Documented architecture references in docstrings — informational only
- `agent_identity.py`/`models.py` constants — identity definitions, not connection strings
