# Atlas v2 — scripts/ and infra/scripts/

## _laia_runtime_paths.py analysis (the bridge)

**How it works:**
- `_get_path(alias, default)` (lines 23-50) is the core resolver.
- Resolution order: **(1) Atlas** → **(2) Legacy laia_paths** → **(3) caller-supplied default**
- Atlas is tried FIRST (primary), not as fallback. Line 40: `atlas.get(alias)` is called directly; only if it throws does it fall through to legacy.
- The critical design note on line 36: "only accept a value it actually resolves (no default passthrough, so a miss falls through to the legacy layer rather than masking it)."

**Atlas as primary or fallback?**
- Atlas is **primary** in `_get_path()`, but the function is resilient: any exception (missing atlas, missing key) degrades gracefully to legacy, then to default.
- This means scripts that use `_get_path("laia_root", ...)` or `_get_path("workspaces", ...)` already benefit from atlas when available.

**Hardcoded fallbacks that should use atlas:**
- `laia_home()` (line 53-54): Uses `os.environ.get("LAIA_HOME") or (Path.home() / ".laia")` — **bypasses atlas entirely**. Does NOT go through `_get_path`. This is the only function in the module that bypasses the atlas bridge.
  - atlas.yaml has `laia_home: ~/.laia` — but `laia_home()` ignores it.
- `laia_root()`, `workspaces_dir()`, `workspace_store_parent()` all correctly use `_get_path()` and thus get atlas as primary.

**Summary:** The bridge design is correct. The only gap is `laia_home()` which hardcodes its fallback instead of going through atlas.

---

## Other scripts hardcodes

> "Should atlas.get()?" = does the value exist in `~/.laia/atlas.yaml` and should the script use `atlas.get()` to resolve it?

### infra/scripts/

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|---|---|---|---|---|---|
| `deploy-agora.sh` | 18 | `${AGORA_FRONTEND_DIST:-/srv/laia/agora/frontend/dist}` | path | `srv_laia` + interpolated path | YES — use `atlas.get("srv_agora")/frontend/dist` |
| `deploy-agora.sh` | 19 | `${AGORA_DATA_DIR:-/srv/laia/agora}` | path | `srv_agora` (value: `${ref.srv_laia}/agora`) | YES — use `atlas.get("srv_agora")` |
| `deploy-agora.sh` | 20 | `${LAIA_STATE_ROOT:-/srv/laia/state}` | path | `srv_laia` + `state` subdir | YES — use `atlas.get("srv_laia")/state` |
| `deploy-agora.sh` | 122 | `http://127.0.0.1:8088/api/health` | service | `agora_api` (host: 127.0.0.1, port: 8088) | YES — use `atlas.get("agora_api")` url |
| `deploy-agora.sh` | 137 | `http://127.0.0.1:8088/api/health` (echo) | service | same as above | YES — use `atlas.get("agora_api")` |
| `backup-state.sh` | 11 | `${BACKUP_ROOT:-/srv/laia/backups}` | path | `srv_laia` | PARTIAL — `srv_laia` exists but no `backups` sub-entry; could use `atlas.get("srv_laia") + "/backups"` |
| `backup-state.sh` | 14 | `${AGORA_DATA_DIR:-/srv/laia/agora}` | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `backup-state.sh` | 34-36 | `/opt/laia/workspaces/personal/workspace.db` | path | No `/opt/laia` in atlas (it's in-container) | NO — in-container path, not host-accessible |
| `setup-prod-dirs.sh` | 17-25 | hardcoded `/srv/laia` subdirs array | path | `srv_laia` | PARTIAL — dirs like `state`, `agora`, `backups` should use atlas-derived paths |

### infra/dev/

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|---|---|---|---|---|---|
| `preflight.sh` | 32 | `HOST_DATA_DIR=${HOST_DATA_DIR:-/srv/laia/agora}` | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `laia-init-checks.sh` | 39 | `HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"` | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `laia-init.sh` | 190 | `HOST_DATA_DIR_DEFAULT="/srv/laia/agora"` | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `laia-init.sh` | 272 | `http://127.0.0.1:8088` (echo) | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `laia-init.sh` | 279 | `http://127.0.0.1:8088/api/laia/chat` (curl example) | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `rebuild-state.sh` | 89 | `data_dir="/srv/laia/agora"` (fallback) | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `rebuild-state.sh` | 108 | `/opt/agora/data/agora.db` (lxc exec sqlite query) | path | No — in-container path | NO — inside LXD, not host atlas |
| `rebuild-state.sh` | 134 | `agora_api="http://127.0.0.1:8088"` (fallback) | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `smoke-test.sh` | 7 | `API_URL="${AGORA_API_URL:-http://127.0.0.1:8088}"` | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `seed-base-skills.sh` | 32 | `API="${AGORA_API:-http://127.0.0.1:8088}"` | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `seed-base-skills.sh` | 59 | "laia-agora" (error message) | container name | `agora_container` (value: laia-agora) | YES — use `atlas.get("agora_container")` |
| `laia-marketplace.py` | 32 | `DEFAULT_API = "http://127.0.0.1:8088"` | service | `agora_api` | YES — use `atlas.get("agora_api")` |
| `chat-with-agent.sh` | 105 | `"agora_data_dir": "/srv/laia/agora"` (JSON) | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `chat-with-agent.sh` | 143 | `AGORA_DATA_DIR="${AGORA_DATA_DIR:-/srv/laia/agora}"` | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `add-test-user.sh` | 97 | `"agora_data_dir":"/srv/laia/agora"` (JSON) | path | `srv_agora` | YES — use `atlas.get("srv_agora")` |
| `verify-redesign.sh` | 185 | `/tmp/laia-verify/agora-data/workspaces/collective/workspace.db` | path | No — temp test path | NO — ephemeral test artifact |

### scripts/ (clean — all use _laia_runtime_paths correctly)

| File | Line | Value | Type | Notes |
|---|---|---|---|---|
| `workspace-switch.py` | 183, 244, 269, 309, 345 | `workspace.db` (filename) | filename | Not a path hardcode — local filename within WORKSPACES_DIR, already through `_get_path("workspaces")` |
| `create-workspace.py` | 326, 336, 378, etc. | `workspace.db` (string literal) | filename | Same — file name, not path |
| `sync-workspace-markdown.py` | 34 | `workspace.db` (error message) | filename | Same |
| `health-check.py` | 48 | `workspace.db` (filename) | filename | Same |
| `ai-orchestrator.py` | various | `workspace.db` (comments/docstrings) | filename | Doc references only |
| `datasette-start.sh` | 15 | `workspace.db` (glob pattern) | filename | `for db in "$WORKSPACES_DIR"/*/workspace.db` — uses env-var-default path, not hardcoded |

**scripts/ verdict:** No hardcoded paths to `/srv/laia`, `/opt/laia`, `127.0.0.1:8088`, or container names found. All Python scripts go through `_laia_runtime_paths`. Shell scripts use `${VAR:-default}` patterns relative to `LAIA_HOME`/`WORKSPACES_DIR` env vars.

---

## Shell script defaults (`${VAR:-default}` patterns — assess if these should change)

All evaluated against the question: **Should this use `atlas.get()` instead of a static default?**

### Already environment-variable driven (acceptable pattern):
- `scripts/start_mlx_servers.sh:7` — `LAIA_HOME="${LAIA_HOME:-$HOME/.laia}"` — OK, uses home-relative fallback
- `scripts/datasette-start.sh:5` — `LAIA_HOME="${LAIA_HOME:-$HOME/.laia}"` — OK
- `scripts/init-workspace-git.sh:7` — `LAIA_HOME="${LAIA_HOME:-$HOME/.laia}"` — OK
- `scripts/sync-workspaces-github.sh:11` — `LAIA_HOME="${LAIA_HOME:-$HOME/.laia}"` — OK

### Should migrate to atlas:

| Script | Default | Why should change |
|---|---|---|
| `infra/scripts/deploy-agora.sh:18-20` | `/srv/laia/agora/...` | Production paths should come from atlas, not hardcoded |
| `infra/scripts/backup-state.sh:11,14` | `/srv/laia/...` | Same |
| `infra/dev/preflight.sh:32` | `/srv/laia/agora` | Should use `atlas.get("srv_agora")` |
| `infra/dev/laia-init-checks.sh:39` | `/srv/laia/agora` | Same |
| `infra/dev/laia-init.sh:190` | `/srv/laia/agora` | Same |
| `infra/dev/smoke-test.sh:7` | `http://127.0.0.1:8088` | Should use `atlas.get("agora_api")` |
| `infra/dev/seed-base-skills.sh:32` | `http://127.0.0.1:8088` | Same |
| `infra/dev/rebuild-state.sh:89,134` | `/srv/laia/agora`, `http://127.0.0.1:8088` | Both should use atlas |
| `infra/dev/chat-with-agent.sh:105,143` | `/srv/laia/agora` | Should use atlas |

### Acceptable as-is (atlas doesn't own these yet):

| Script | Default | Why acceptable |
|---|---|---|
| `infra/dev/laia-init.sh:48` | ORIG_USER computed via `getent` | User detection, not a fixed path |
| `infra/dev/preflight.sh:36` | `${LAIA_EXPECTED_OWNER:-${ORIG_USER}:${ORIG_GROUP}}` | Dynamic ownership detection |
| `infra/scripts/setup-prod-dirs.sh:16-25` | `/srv/laia/...` dirs array | Pure production bootstrap; these ARE the canonical production dirs. Atlas owns `srv_laia` but the subdirs (state, backups, etc.) aren't registered separately. Acceptable as-is for now, but could benefit from atlas subdir entries. |

---

## Summary

| Category | Count | Notes |
|---|---|---|
| Hardcoded `/srv/laia` paths (infra/scripts + infra/dev) | ~18 | Should use `atlas.get("srv_laia")` or sub-path refs |
| Hardcoded `127.0.0.1:8088` (infra/dev) | ~6 | Should use `atlas.get("agora_api")` |
| Hardcoded `laia-agora` container name (infra/dev) | ~4 | Should use `atlas.get("agora_container")` |
| In-container paths `/opt/laia` (infra/scripts/backup-state.sh) | 1 | NOT actionable — inside LXD, not host-accessible |
| Hardcoded `agent-jorge` hostname | 0 | Not found in scripts or infra/scripts |
| scripts/ cleanliness | CLEAN | All Python scripts use `_laia_runtime_paths`; no hardcoded production paths found |

**Priority actions:**
1. `infra/dev/smoke-test.sh`, `seed-base-skills.sh`, `laia-marketplace.py`, `rebuild-state.sh`, `chat-with-agent.sh` — migrate `127.0.0.1:8088` to `atlas.get("agora_api")`
2. `infra/dev/preflight.sh`, `laia-init-checks.sh`, `laia-init.sh`, `rebuild-state.sh`, `chat-with-agent.sh` — migrate `/srv/laia/agora` to `atlas.get("srv_agora")`
3. `infra/scripts/deploy-agora.sh`, `backup-state.sh` — same migrations
4. `_laia_runtime_paths.py:laia_home()` — consider bridging through `_get_path` for consistency, though current behavior is intentional (always-available bootstrap)
