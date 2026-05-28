# Atlas v2 — bin/ and infra/installer/lib/

## Real code/shell hardcodes

| File | Line | Value | Type | In atlas.yaml? | Should atlas? | Context |
|------|------|-------|------|----------------|----------------|---------|
| bin/laia | 126-127 | `/opt/laia/.laia-core/venv/bin/python` | path | `opt_laia` → `/opt/laia` (partial) | YES | Fallback Python interpreter when venv not found at `core_dir`. Real path literal. |
| bin/laia-clone | 334 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | LXD image existence check for laia-agora |
| bin/laia-clone | 367 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | Log message about LXD image presence |
| bin/laia-install | 254 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | JSON event label: "Provision laia-agora container" |
| infra/installer/lib/clone.sh | 41 | `http://127.0.0.1:8088/api/health` | service | `agora_api` → `127.0.0.1:8088` | YES | `LAIA_AGORA_HEALTH_URL` shell default constant |
| infra/installer/lib/clone.sh | 933-934 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | `lxc info laia-agora` and error message |
| infra/installer/lib/clone.sh | 937 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | `lxc config get laia-agora volatile.idmap.base` |
| infra/installer/lib/clone.sh | 939 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | Die message referencing container config |
| infra/installer/lib/clone.sh | 944 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | Verify command in log_warn |
| infra/installer/lib/clone.sh | 818 | `/srv/laia/arch` (in log message) | path | `srv_laia` → `/srv/laia` (partial) | NO | Human-readable log message, not code |
| infra/installer/lib/bootstrap.sh | 145-150 | `laia-agora` | container | `agora_container` → `laia-agora` | YES | `lxc info laia-agora`, `lxc config device show laia-agora`, `lxc config device add laia-agora agora-data` |
| infra/installer/lib/bootstrap.sh | 170 | `http://127.0.0.1:8088/api/health` | service | `agora_api` → `127.0.0.1:8088` | YES | `url="${LAIA_AGORA_HEALTH_URL:-http://127.0.0.1:8088/api/health}"` shell default |
| infra/installer/lib/factory.sh | 132 | `http://127.0.0.1:8088` | service | `agora_api` → `127.0.0.1:8088` | YES | `api="${AGORA_API:-http://127.0.0.1:8088}"` shell default |
| infra/installer/lib/factory.sh | 171 | `/srv/laia/agora/agora.db` (in var) | path | `srv_agora` → `${srv_laia}/agora` | YES | `db="${AGORA_DB_PATH:-${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}/agora.db}"` shell default |
| infra/installer/lib/factory.sh | 270 | `/srv/laia/agora/.env` | env_file | `agora_env` → `/srv/laia/agora/.env` | YES | `env_host_file="${LAIA_AGORA_ENV_FILE_OVERRIDE:-/srv/laia/agora}/.env"` shell default |
| infra/installer/lib/rewrite_config_paths.py | 27-28 | `/opt/laia`, `/srv/laia/agora/agora.db` | path | `opt_laia`, `srv_agora` | PARTIAL | Path rewrite lookup table for config.yaml. Canonical mapping, but could use atlas.get() |

## bin/atlas self-check (does it use atlas.get internally?)

**YES.** `bin/atlas` properly uses `atlas.get()` internally in all relevant commands:

- `cmd_get` (line 142-151): Calls `atlas.get(args.name)` to resolve a single reference
- `cmd_check` (line 154-164): Calls `atlas.health(args.name)` which internally uses atlas
- `cmd_list` (line 180-231): Calls `atlas.get(name)` for each reference when displaying values
- `cmd_doctor` (line 279-343): Calls `atlas.doctor()` to health-check all references
- `cmd_env` (line 346-361): Calls `atlas.get(name)` for each reference when exporting
- `cmd_graph` (line 364-431): Uses `atlas.all_refs()` and `atlas.get()` for dependency resolution
- `cmd_consumers` (line 627-657): Uses `atlas.get()` to detect hardcoded literals vs logical usage

**Conclusion:** `bin/atlas` itself is a proper Atlas v2 consumer. It imports the atlas module (`from .laia-core import atlas`) and uses `atlas.get()` for all reference resolution.

## Shell DEFAULT values (NOT hardcodes — using `${VAR:-default}` pattern)

These are **shell defaults** following the `${VAR:-default}` idiom, NOT hardcoded literals to migrate. They provide override capability via environment variables:

| File | Line | Value | Override env var |
|------|------|-------|------------------|
| infra/installer/lib/clone.sh | 38 | `readonly LAIA_USERS_DIR_DEFAULT="/srv/laia/users"` | `LAIA_USERS_DIR_OVERRIDE` |
| infra/installer/lib/clone.sh | 39 | `readonly LAIA_AGORA_DIR_DEFAULT="/srv/laia/agora"` | `LAIA_AGORA_DIR_OVERRIDE` |
| infra/installer/lib/clone.sh | 40 | `readonly LAIA_ARCH_DIR_DEFAULT="/srv/laia/arch"` | `LAIA_ARCH_DIR_OVERRIDE` |
| infra/installer/lib/bootstrap.sh | 148 | `local data_dir="${LAIA_AGORA_DATA_DIR_OVERRIDE:-/srv/laia/agora}"` | `LAIA_AGORA_DATA_DIR_OVERRIDE` |
| infra/installer/lib/factory.sh | 171 | `db="${AGORA_DB_PATH:-${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}/agora.db}"` | `AGORA_DB_PATH`, `LAIA_AGORA_DIR_OVERRIDE` |
| infra/installer/lib/factory.sh | 270 | `local env_host_file="${LAIA_AGORA_ENV_FILE_OVERRIDE:-/srv/laia/agora}/.env"` | `LAIA_AGORA_ENV_FILE_OVERRIDE` |
| infra/installer/lib/version.sh | 22 | `readonly LAIA_INSTALL_PREFIX="/opt/laia"` | `LAIA_INSTALL_ROOT_OVERRIDE` (via `inst_install_prefix()`) |

## Literal paths in comments (leave as-is)

| File | Line | Context |
|------|------|---------|
| bin/laia | 3, 41 | `laia-rollback — switch /opt/laia symlink` — comment describing the script |
| bin/laia-release | 3, 55 | `promote a dev tree to /opt/laia-vX.Y.Z` — comment describing the script |
| bin/laia-rollback | 65 | `/srv/laia/` in comment about rollback scope |
| infra/installer/lib/clone.sh | 13, 26, 30 | Comments describing Phase 3 layout and overrides |
| infra/installer/lib/clone.sh | 261 | Comment about `/srv/laia/agora` root ownership |
| infra/installer/lib/clone.sh | 270 | Comment referencing SSH test for `/srv/laia` |
| infra/installer/lib/clone.sh | 274, 276, 285 | Error/diagnosis messages mentioning `/srv/laia` |
| infra/installer/lib/clone.sh | 792, 795 | Comments in rewrite_config_paths explaining path mapping |
| infra/installer/lib/version.sh | 12-13 | Comments documenting `LAIA_INSTALL_PREFIX` and `LAIA_INSTALL_VERSIONED` |
| infra/installer/lib/version.sh | 64, 72 | Comments documenting functions |
| infra/installer/lib/release.sh | 10, 14 | Comments about symlink behavior |
| infra/installer/lib/install.sh | 16-17, 459, 488 | Comments about paths and rollback |

## Summary of migration candidates

**High priority (real code with no override mechanism):**

1. **`bin/laia` line 126-127**: `/opt/laia/.laia-core/venv/bin/python` — Could use `atlas.get("laia_core")/venv/bin/python` but requires atlas import in shell
2. **`infra/installer/lib/clone.sh` line 41**: `http://127.0.0.1:8088/api/health` — Should use `atlas.get("agora_api")` + health_path
3. **`infra/installer/lib/clone.sh` lines 933-944**: `laia-agora` container references — Should use `atlas.get("agora_container")`
4. **`infra/installer/lib/bootstrap.sh` line 145-150**: `laia-agora` container references — Should use `atlas.get("agora_container")`
5. **`infra/installer/lib/bootstrap.sh` line 170**: `http://127.0.0.1:8088/api/health` — Should use `atlas.get("agora_api")`
6. **`infra/installer/lib/factory.sh` line 132**: `http://127.0.0.1:8088` — Should use `atlas.get("agora_api")`
7. **`infra/installer/lib/factory.sh` lines 171, 270**: `/srv/laia/agora/...` — Should use `atlas.get("srv_agora")`
8. **`infra/installer/lib/rewrite_config_paths.py` lines 27-28**: Path lookup table — Could use atlas.get() dynamically

**Note:** The shell scripts would need to source atlas or call `atlas get` to resolve these values at runtime, adding complexity. The `${VAR:-default}` pattern already provides override capability via environment variables, which is a reasonable middle ground.
