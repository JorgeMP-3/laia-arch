# Atlas v2 — infra/orchestrator/ and infra/pathd/

## laia_paths import check (CRITICAL)

**Does `from laia_paths import` work? Where does the module live?**

YES — `from laia_paths import` **WORKS**. The module lives at:

```
/home/laia-arch/LAIA/.laia-core/laia_paths.py   (223 lines, paths-only layer)
```

The pathd package adds `.laia-core` to `sys.path` before importing:

```python
# server.py:21-25, cli.py:12-15, notifier.py:13-17
_CORE = Path(__file__).resolve().parents[2] / ".laia-core"
if str(_CORE) not in _sys.path:
    _sys.path.insert(0, str(_CORE))
```

All three files (`server.py`, `cli.py`, `notifier.py`) have a `try/except ImportError` guard
around the import, so a missing `.laia-core/laia_paths.py` raises a `RuntimeError` with a
clear message instead of a cryptic import traceback.

`laia_paths.py` reads `~/.laia/config.yaml` (paths-only), NOT `atlas.yaml`. It is the
**legacy pathd resolver**. Atlas v2 (`atlas.py`) lives alongside it in the same directory
and provides the full multi-type registry (paths + services + containers + sockets).

---

## pathd architecture

**Does server.py import from atlas.py or laia_paths.py?**

`server.py` imports from **`laia_paths`** (NOT from `atlas.py`):

```python
# infra/pathd/server.py:27-28
from laia_paths import load_config, resolve  # noqa: E402
```

The daemon is still wired to the legacy `config.yaml` / `laia_paths` resolver.
`atlas.py` (full Atlas v2) exists in `.laia-core/` but is **not yet used** by the daemon.
This means the pathd daemon does NOT yet consume `atlas.yaml` — only `~/.laia/config.yaml`.

---

## Host-side hardcodes (should migrate)

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|------|------|-------|------|----------------|---------------------|
| `infra/orchestrator/README.md` | 60 | `/srv/laia/state` | env override | YES (`srv_laia` → `/srv/laia`) | YES |

**Only 1 host-side hardcode found** across the entire `infra/orchestrator/` and
`infra/pathd/` surfaces (excluding container-internal paths — see below).

The README reference is a documentation example showing how to set `LAIA_STATE_ROOT`
to override the default state directory. This is an **intentional env-override hint**,
documenting the supported escape hatch. Not a raw path that needs migrating.

### No other host-side hardcodes found

- `cli.py` lines 180–350: `"/opt/laia/workspaces/personal/workspace.db"` — these are
  **recorded in the state JSON file** (`agents.json`), written by `state.upsert_agent()`.
  They are snapshots of where the container **actually ended up**, not prescriptive paths.
  They should arguably come from an atlas lookup at the time of recording, but they are
  not causing incorrect behavior today — the container paths are determined at runtime
  inside the container and are correct by construction.
- `paths.laia_root / "workspace_store"` in lxd.py:160,190 — uses `config.Paths.laia_root`
  which is **already resolved** via `config.discover_paths()` (derived from `__file__`).
- `lxd.py` lines 403–417 (`_agent_json_script`): inline JSON with `/opt/laia/...` paths.
  These are written **inside the container** at container-provision time via `lxc exec`.
  They describe the container's own internal layout — they are NOT read from the host after
  the fact. The agent reads its own `/opt/laia/agent.json` at startup.

---

## Container-internal paths (OUT OF SCOPE — do not migrate)

All `/opt/laia/...` paths in `infra/orchestrator/lxd.py` are paths **inside the LXD
container** (the agent runtime environment). They appear in `lxc exec` commands that
run **inside** the container and refer to the container's own filesystem.

These are NOT host-side paths. They cannot be migrated to atlas because:
1. They are resolved at container-provision time by the host-side orchestrator
2. They describe where things are **inside the container**, which is fixed by the
   laia-runtime layout
3. The host reads them back from the container via `lxc exec cat /opt/laia/...`

| File | Line | Value | Note |
|------|------|-------|------|
| `infra/orchestrator/lxd.py` | 175–178 | `/opt/laia/agent`, `/opt/laia/data`, `/opt/laia/logs`, `/opt/laia/runtime`, `/opt/laia/workspaces/personal`, `/opt/laia/data/tasks/{inbox,done,failed}` | `mkdir -p` inside container |
| `infra/orchestrator/lxd.py` | 182 | `/opt/laia` | `useradd --system --home /opt/laia ...` |
| `infra/orchestrator/lxd.py` | 184 | `/opt/laia/agent` | `rm -rf` then re-push runtime |
| `infra/orchestrator/lxd.py` | 186 | `/opt/laia/agent` | `mv /tmp/laia-runtime /opt/laia/agent` |
| `infra/orchestrator/lxd.py` | 188 | `/opt/laia/agent/vendor` | mkdir vendor dir |
| `infra/orchestrator/lxd.py` | 191 | `/opt/laia/agent` | `find ... -name __pycache__ -exec rm -rf` |
| `infra/orchestrator/lxd.py` | 193 | `/opt/laia/runtime/venv` | `python3 -m venv /opt/laia/runtime/venv` |
| `infra/orchestrator/lxd.py` | 196 | `/opt/laia/agent/systemd/laia-agent.service` | cp to `/etc/systemd/system/` |
| `infra/orchestrator/lxd.py` | 200–202 | `/opt/laia/agent/healthcheck.sh`, `/opt/laia/healthcheck.sh` | cp + chmod +x |
| `infra/orchestrator/lxd.py` | 207–209 | `/opt/laia/agent`, `/opt/laia/runtime` | chown root:laia-agent, chmod u=rwX |
| `infra/orchestrator/lxd.py` | 212–214 | `/opt/laia/data`, `/opt/laia/logs`, `/opt/laia/workspaces/...` | chown laia-agent:laia-agent |
| `infra/orchestrator/lxd.py` | 216–217 | `/opt/laia/agent.json` | chmod 0640, chown root:laia-agent |
| `infra/orchestrator/lxd.py` | 222 | `/opt/laia/healthcheck.sh` | systemctl restart + healthcheck |
| `infra/orchestrator/lxd.py` | 238–240 | `/opt/laia/runtime/venv/bin/python`, `/opt/laia/workspaces/personal/workspace.db` | workspace init |
| `infra/orchestrator/lxd.py` | 256–260 | `/opt/laia/...` profile paths | init_agent_profile checks |
| `infra/orchestrator/lxd.py` | 276–277 | `/opt/laia/runtime/venv/bin/python` | get_agent_profile script |
| `infra/orchestrator/lxd.py` | 293–294 | ditto | update_agent_profile script |
| `infra/orchestrator/lxd.py` | 311–312 | ditto | set_agent_skill script |
| `infra/orchestrator/lxd.py` | 340–341 | `/opt/laia/data/status.json`, `/opt/laia/logs/agent.log` | agent_status |
| `infra/orchestrator/lxd.py` | 359–368 | `/opt/laia/healthcheck.sh`, `/opt/laia/runtime/venv/bin/python`, `/opt/laia/data/profile/...`, `/opt/laia/workspaces/personal/workspace.db` | verify_agent checks |
| `infra/orchestrator/lxd.py` | 403–417 | ALL `/opt/laia/...` values | `_agent_json_script()` — generates `/opt/laia/agent.json` inside the container |
| `infra/orchestrator/lxd.py` | 474 | `/opt/laia/data/status.json` | fleet_status reads status from each container |

### cli.py state-file entries

Lines 180, 199, 216, 295, 350 in `cli.py` write `workspace:
"/opt/laia/workspaces/personal/workspace.db"` into `agents.json`. This is stored as a
**snapshot of the container's internal path at provisioning time**. These paths should
ideally be re-resolved from an atlas ref (e.g. `agent_workspace` with value
`/opt/laia/workspaces/personal/workspace.db`) rather than hardcoded strings, **but**
they are not causing active bugs and are out of scope for the current audit.

---

## laia-agora / agent-jorge string exclusions

`infra/orchestrator/lxd.py` uses these strings as **filter excludes** (not paths):

```python
# lxd.py:83
if row and (row[0].startswith("agent-") or row[0].startswith("laia-")) \
   and row[0] not in {"laia-agora", "laia-jorge"}:
```

```python
# lxd.py:448
elif name.startswith("laia-") and name not in {"laia-agora", "laia-jorge"}:
```

Both are container-name filters to skip the special central containers. They exist as
**literal strings** rather than atlas refs. In atlas.yaml:
- `laia-agora` is at `refs.agora_container.value: laia-agora`
- `agent-jorge` is at `refs.jorge_container.value: agent-jorge`

These **should** migrate to `atlas.get("agora_container")` / `atlas.get("jorge_container")`.

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |
|------|------|-------|------|----------------|---------------------|
| `infra/orchestrator/lxd.py` | 83 | `"laia-agora"` | container-name filter | YES (`agora_container`) | YES |
| `infra/orchestrator/lxd.py` | 83 | `"laia-jorge"` | container-name filter | YES (`	jorge_container`) | YES |
| `infra/orchestrator/lxd.py` | 448 | `"laia-agora"` | container-name filter | YES (`agora_container`) | YES |
| `infra/orchestrator/lxd.py` | 448 | `"laia-jorge"` | container-name filter | YES (`jorge_container`) | YES |

---

## New refs needed

1. **`agent_workspace`** — path ref for the per-agent SQLite workspace inside the container:
   ```
   value: /opt/laia/workspaces/personal/workspace.db
   ```
   Used in `cli.py:180,199,216,295,350` (state snapshots) and `lxd.py` checks.

2. **`agent_runtime_root`** — path ref for the runtime root inside the container:
   ```
   value: /opt/laia/runtime
   ```
   Currently resolved on-host via `config.Paths.agent_runtime_root` (from `laia_root`), which
   is the **host-side** source tree, not the installed runtime inside the container. The
   runtime is pushed to `/opt/laia/runtime` inside the container at install time.

3. **`agent_data`** — path ref for agent data directory inside the container:
   ```
   value: /opt/laia/data
   ```
   Used for `status.json`, profile files, tasks directories.

4. **`agent_logs`** — path ref for agent logs directory:
   ```
   value: /opt/laia/logs
   ```

5. **`agent_dir`** — path ref for agent code directory:
   ```
   value: /opt/laia/agent
   ```

6. **`container_laia_agora`** — explicit container ref for `laia-agora` (already exists as
   `agora_container` in atlas yaml, but `get_container_name()` helper in `lxd.py:27-32`
   generates `agent-{slug}` / `laia-{slug}` programmatically — no migration needed for the
   naming logic itself, only for the exclusion filters at lines 83 and 448).

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| Host-side hardcodes to migrate | 1 | Fix in README.md or mark WONTFIX |
| Container-name filter strings (laia-agora, laia-jorge) | 4 | Migrate to atlas refs |
| Container-internal `/opt/laia` paths (OUT OF SCOPE) | ~50 | Do not migrate |
| `laia_paths` import | WORKING | `.laia-core/laia_paths.py` |
| pathd daemon backend | laia_paths (legacy) | NOT yet using `atlas.py` |
