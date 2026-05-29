# Atlas v2 — services/laia-executor/

## Hardcoded refs found

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? | Comment/Code? |
|---|---|---|---|---|---|---|
| `config.py` | 10 | `/etc/laia/executor-token` | path | NO | YES | Code — DEFAULT_TOKEN_FILE constant |
| `config.py` | 11 | `/etc/laia/agent.json` | path | NO | YES | Code — DEFAULT_PROFILE_FILE constant |
| `config.py` | 37 | `/var/lib/laia/workspace` | path | NO (srv_laia=/srv/laia) | YES | Code — default workspace_root |
| `config.py` | 38 | `/opt/laia/plugins` | path | NO (opt_laia=/opt/laia) | YES | Code — default plugins_root |
| `auth.py` | 4 | `/etc/laia/executor-token` | path | NO | YES | Comment — token mounted path |
| `private_workspace.py` | 53 | `/opt/laia/lib/` | path | NO (opt_laia=/opt/laia) | YES | Comment — production install path for workspace_store |
| `private_workspace.py` | 60 | `/opt/laia/lib` | path | NO (opt_laia=/opt/laia) | YES | Code — candidate workspace_store path |
| `private_workspace.py` | 104 | `/var/lib/laia/workspace` | path | NO (srv_laia=/srv/laia) | YES | Code — fallback LAIA_EXECUTOR_WORKSPACE_ROOT |
| `process_tools.py` | 10 | `/var/log/laia-processes/` | path | NO | YES | Comment — background process log location |
| `process_tools.py` | 37 | `/var/log/` | path | NO | YES | Comment — why logs go here vs /home/user |
| `process_tools.py` | 40 | `/var/log/laia-processes` | path | NO | YES | Code — PROCESS_LOG_DIR constant |
| `bash_tool.py` | 26 | `/bin/bash` | path | NO | NO | Code — hardcoded shell executable (inherently static, container-specific) |
| `cron_tools.py` | 100 | `/bin/bash -c` | path | NO | NO | Comment — how command is executed |
| `cron_tools.py` | 130 | `/bin/bash -lc` | path | NO | NO | Code — ExecStart in systemd unit |
| `process_tools.py` | 128 | `/bin/bash -c` | path | NO | NO | Comment — how command is executed |
| `process_tools.py` | 168 | `/bin/bash -c` | path | NO | NO | Code — subprocess.Popen call |

## New refs needed for atlas.yaml

```yaml
refs:

  # ── laia-executor paths ───────────────────────────────────────────────────

  executor_token_file:
    type: path
    value: /etc/laia/executor-token
    description: "Bearer token for executor HTTP API (mode 0600, mounted in container)"
    in_code: config.py DEFAULT_TOKEN_FILE, auth.py comment

  executor_profile_file:
    type: path
    value: /etc/laia/agent.json
    description: "Agent profile JSON (read for slug)"
    in_code: config.py DEFAULT_PROFILE_FILE

  executor_workspace_root:
    type: path
    value: /var/lib/laia/workspace
    description: "Base directory for per-user private workspaces"
    in_code: config.py default, private_workspace.py _workspace_root_dir()

  executor_plugins_root:
    type: path
    value: ${ref.opt_laia}/plugins
    description: "Plugins root for laia-executor"
    in_code: config.py default (LAIA_EXECUTOR_PLUGINS_ROOT env var)

  workspace_store_lib:
    type: path
    value: ${ref.opt_laia}/lib
    description: "Production path for workspace_store package"
    in_code: private_workspace.py _candidate_workspace_store_paths()

  laia_process_log_dir:
    type: path
    value: /var/log/laia-processes
    description: "Background process stdout/stderr logs"
    in_code: process_tools.py PROCESS_LOG_DIR
```

## Notes

- **/bin/bash** references are hardcoded shell executables. These are **NOT** candidates for atlas.get() because:
  - They are container-runtime constants ( bash is always at /bin/bash inside LXD containers )
  - They are not configurable paths — changing them would break subprocess invocation
  - Related: `cron_tools.py` also hardcodes `systemd` unit dir as `/etc/systemd/system` (line 36) — not currently in grepable patterns but worth noting as a system path

- **Existing atlas.yaml refs** that partially cover some paths:
  - `opt_laia: /opt/laia` exists but `/opt/laia/lib` and `/opt/laia/plugins` are sub-paths not listed
  - `srv_laia: /srv/laia` exists but `/var/lib/laia` is a different mount point ( not covered )
