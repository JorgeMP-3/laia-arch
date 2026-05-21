# Atlas — LAIA Path Registry (DNS for files)

> 📅 Actualizado: 2026-05-19

## Concept

Atlas is the "DNS for files" of the LAIA ecosystem. Instead of hardcoding absolute paths in 40+ files, every component looks up paths from a single registry in `~/.laia/config.yaml`. A daemon keeps everything live and self-healing.

## Architecture

```
config.yaml (paths: section)          ← Source of truth (32 paths)
       │
       ▼
laia-pathd (daemon)                   ← Watches config + filesystem
       │
       ├── ~/.laia/.env.paths          ← Bash + systemd consumers
       ├── ~/.laia/atlas/<alias>       ← Symlink farm (any program)
       ├── ~/.laia/pathd.sock          ← Unix socket (Python clients)
       └── ~/.laia/state/path-cache.json ← Persistent state + history
```

## How to use

### Bash (scripts)
```bash
source ~/.laia/.env.paths
echo $LAIA_CORE        # /home/laia-hermes/LAIA/.laia-core
echo $LAIA_WORKSPACES  # /home/laia-hermes/LAIA/workspaces
```

### Python
```python
from laia_paths import get_path, all_paths

get_path("agora")     # Path("/home/.../services/agora-backend")
all_paths()           # {"agora": "/home/...", "workspaces": "/home/...", ...}
```

### Systemd
```ini
[Service]
EnvironmentFile=-/home/laia-hermes/.laia/.env.paths
WorkingDirectory=${LAIA_CORE}
ExecStart=${LAIA_VENV}/bin/laia gateway run
```

### Any program (symlinks)
```bash
ls -la ~/.laia/atlas/agora
# agora -> /home/laia-hermes/LAIA/services/agora-backend
```

## CLI

```bash
laia-path resolve agora           # /home/.../services/agora-backend
laia-path list                    # All 32 aliases
laia-path status                  # Daemon health
laia-path doctor                  # Validate all paths exist
laia-path reload                  # Force re-read config.yaml
laia-path pending-restarts        # Show queued restarts
laia-path apply-restarts --yes    # Apply pending restarts
```

## Adding a new path

1. Edit `~/.laia/config.yaml` → `paths:` section
2. Run `laia-path reload` (or wait 2s for auto-detection)
3. The path is immediately available to all consumers

## Path Registry (32 aliases)

| Alias | Resolves to |
|---|---|
| `laia_root` | `/home/laia-hermes/LAIA` |
| `laia_home` | `~/.laia` |
| `laia_core` | `LAIA/.laia-core` |
| `laia_venv` | `LAIA/.laia-core/venv` |
| `ui_server` | `LAIA/.laia-core/laia-ui-server` |
| `ui_backend` | `LAIA/.laia-core/laia-ui-server/backend` |
| `agora` | `LAIA/services/agora-backend` |
| `agora_venv` | `LAIA/services/agora-backend/.venv` |
| `agora_data` | `~/.laia/agora.db` |
| `runtime` | `LAIA/services/laia-runtime` |
| `workspaces` | `LAIA/workspaces` |
| `plugins` | `~/.laia/plugins` |
| `plugins_src` | `LAIA/plugins` |
| `skills` | `LAIA/skills` |
| `infra` | `LAIA/infra` |
| `infra_bin` | `LAIA/infra/bin` |
| `infra_lxd` | `LAIA/infra/lxd` |
| `infra_scripts` | `LAIA/infra/scripts` |
| `systemd_units` | `LAIA/infra/systemd` |
| `laiactl` | `LAIA/infra/laiactl` |
| `store` | `LAIA/workspace_store` |
| `laia_ui` | `LAIA/laia-ui` |
| `ui_packages` | `LAIA/laia-ui/packages` |
| `services` | `LAIA/services` |
| `laia_scripts` | `LAIA/scripts` |
| `laia_host_logs` | `LAIA/logs` |
| `laia_docs` | `LAIA/docs` |
| `srv_laia` | `/srv/laia` |
| `agora_frontend_dist` | `/srv/laia/agora/frontend/dist` |
| `laia_state_root` | `/srv/laia/state` |
| `laia_backups` | `/srv/laia/backups` |
| `logs` | `~/.laia/logs` |

## Daemon (laia-pathd)

- **Service:** `laia-pathd` (systemd user unit)
- **Socket:** `~/.laia/pathd.sock`
- **Poll interval:** 2s (config.yaml mtime check)
- **Watcher:** inotify (watchdog) on registered parent directories
- **Auto-detection:** Rename a directory → alias updates in <1s
- **Restart markers:** When a path changes, systemd units with `X-LaiaPathDeps=<alias>` get a pending-restart entry

## Automatic Behavior

1. **Config change:** Edit `config.yaml` → daemon detects in <2s → regenerates `.env.paths` + atlas symlinks
2. **Directory rename:** `mv old-dir new-dir` → daemon detects via inotify in <1s → updates alias + writes restart marker
3. **Directory deleted:** Daemon marks alias as "missing" → `laia-path doctor` reports it
4. **Service restarts:** When `X-LaiaPathDeps` aliases change → `laia-path pending-restarts` shows affected units → `laia-path apply-restarts` applies with confirmation
