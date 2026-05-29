# Atlas v2 — .laia-core/ entry points

## Summary

Investigated 7 key entry-point files in `/home/laia-arch/LAIA/.laia-core/` for hardcoded references to:
- `/srv/laia`
- `/opt/laia`
- `laia-agora`
- `agent-jorge`
- `~/.laia`

**Scope rule applied:** `.laia-core/tools/` (the tools directory) is NOT in scope per agent instructions — it belongs to agent 4.

---

## Hardcoded refs found

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? | Comment/Code? |
|---|---|---|---|---|---|---|
| `run_agent.py` | 86 | `~/.laia/.env` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring explaining env loading behavior |
| `run_agent.py` | 981 | `~/.laia/SOUL.md` | path | YES (`laia_home`) | N/A | **COMMENT** — parameter docstring |
| `run_agent.py` | 1233 | `~/.laia/logs/` | path | YES (`laia_home`) | N/A | **COMMENT** — comment describing log location |
| `run_agent.py` | 1581 | `~/.laia/sessions/` | path | YES (`laia_home`) | N/A | **COMMENT** — comment describing session log location |
| `cli.py` | 80 | `~/.laia/.env` | path | YES (`laia_home`) | N/A | **COMMENT** — module-level doc comment |
| `cli.py` | 206 | `~/.laia/` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring for `_load_prefill_messages` |
| `cli.py` | 253 | `~/.laia/config.yaml` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring for `load_cli_config` |
| `cli.py` | 260 | `~/.laia/config.yaml` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring continuation |
| `cli.py` | 603 | `~/.laia/logs/` | path | YES (`laia_home`) | N/A | **COMMENT** — comment for logging setup |
| `cli.py` | 1779 | `~/.laia/config.yaml` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring for `save_config_value` |
| `cli.py` | 1795 | `~/.laia/config.yaml` | path | YES (`laia_home`) | N/A | **COMMENT** — comment re: first-use dir creation |
| `cli.py` | 2094 | `~/.laia/checkpoints/` | path | YES (`laia_home`) | N/A | **COMMENT** — comment for checkpoint auto-maintenance |
| `cli.py` | 3832 | `~/.laia/images/` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring for `_try_attach_clipboard_image` |
| `cli.py` | 5080 | `~/.laia/sessions/saved/` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring for `save_conversation` |
| `laia_constants.py` | 102 | `/opt/laia-custom` | path | YES (`opt_laia`) | N/A | **COMMENT** — docstring example only |
| `laia_paths.py` | 3 | `~/.laia/config.yaml` | path | YES (`laia_home`) | N/A | **COMMENT** — module docstring describing what it reads |
| `laia_paths.py` | 30 | `~/.laia/` | path | YES (`laia_home`) | N/A | **COMMENT** — docstring comment |
| `laia_state.py` | (none) | — | — | — | — | No refs found |
| `laia_logging.py` | (none) | — | — | — | — | No refs found (uses `get_laia_home()` properly) |
| `mcp_serve.py` | (none) | — | — | — | — | No refs found |

### Out-of-scope files with refs (listed for completeness, NOT in scope per agent mandate):

| File | Ref | Type | Notes |
|---|---|---|---|
| `laia_cli/install_wizard/flows/reset.py` | `/srv/laia`, `/opt/laia` | path | Installer script — entire purpose is to operate on these paths. Should NOT use atlas.get() (must work even if atlas unavailable during disaster recovery) |
| `laia_cli/install_wizard/flows/clone.py` | `/opt/laia` | path | Installer script — mentions path in docstring |
| `laia_cli/gateway.py` | `/opt/laia` | path | **CODE** line 1483 — remapping logic, keeps `/opt/laia` as-is. This is intentional (non-home path preserved). NOT an atlas ref candidate |
| `Dockerfile` | `/opt/laia` | path | Container build — CANNOT use atlas.get() (builds the container itself) |
| `toolset_distributions.py` | `laia-agora` | container | **COMMENT** — architectural description in toolset profile docstring |
| `plugins/agent-scheduler/__init__.py` | `laia-agora` | container | **COMMENT** — module docstring describing where scheduler runs |
| `plugins/agent-self-edit/__init__.py` | `laia-agora` | container | **COMMENT** — module docstring |
| `plugins/agora-executor-forwarder/__init__.py` | `laia-agora` | container | **COMMENT** — plugin docstring |

---

## Findings by category

### 1. `~/.laia` references — ALL are comments/docstrings (NOT hardcoded code)

All appearances of `~/.laia` in the 7 key entry points are in:
- Module-level doc comments
- Function/method docstrings
- Inline explanatory comments

The **actual code** uses `get_laia_home()` from `laia_constants.py`, which reads the `LAIA_HOME` env var and falls back to `Path.home() / ".laia"`. This is profile-aware and correct.

**Verdict:** Not hardcodes in the code sense — these are documentation. The code path is already correct.

### 2. `/opt/laia` references — All are installer/Dockerfile context

- `reset.py` (lines 5, 58, 262): Installer script that **deliberately wipes** `/opt/laia`. The entire purpose is to handle this path in a disaster-recovery flow. `atlas.get()` would be circular (atlas itself lives in `~/.laia/atlas.yaml` which is under threat).
- `clone.py` (lines 230, 469): Installer mentions path in confirmation dialog text.
- `Dockerfile` (lines 10, 26, 60, 69, 73): Container build context. The WORKDIR and runtime env vars are set **inside the container being built**, which cannot self-reference via atlas.
- `laia_constants.py` (line 102): **COMMENT** — docstring example: "profile: `~/.laia/profiles/coder` / custom: `/opt/laia-custom`" — just a display example.
- `laia_cli/gateway.py` (line 1483): **CODE** — `_remap_path_for_user()` explicitly keeps `/opt/laia` unchanged (not a home-subtree path). This is correct by design; system-wide installs don't belong in a user's home directory.

**Verdict:** No action needed. These are in installer/build contexts where atlas.get() is inappropriate.

### 3. `/srv/laia` references — All are in installer reset script

- `reset.py` (lines 6, 59, 262): Same reasoning as `/opt/laia` — disaster recovery installer script that wipes this path. Cannot depend on atlas being available.

**Verdict:** No action needed. This is correct by design for disaster-recovery scripts.

### 4. `laia-agora` references — All are comments describing system architecture

All 19 references across `toolset_distributions.py`, `plugins/agent-scheduler/`, `plugins/agent-self-edit/`, `plugins/agora-executor-forwarder/`, and `reset.py` are in **docstrings and comments** describing the architecture:

- "the AIAgent running INSIDE the laia-agora container"
- "All run locally in laia-agora"
- "This plugin lives inside the laia-agora orchestrator container"

These describe a runtime architecture, not path references that need resolution. The **actual code paths** that interact with `laia-agora` (e.g., the executor-forwarder plugin) use the container name via configuration, not hardcoded strings.

**Verdict:** Documentation/architecture comments only. If the system needs to reference `laia-agora` container in executable code, it should use `atlas.get("agora_container")` — but no such usage found in the 7 key files.

### 5. `agent-jorge` references — NOT FOUND in key entry points

Zero matches in `run_agent.py`, `cli.py`, `laia_constants.py`, `laia_paths.py`, `laia_state.py`, `laia_logging.py`, or `mcp_serve.py`.

`~/.laia/atlas.yaml` defines it as `jorge_container` (line 133-138) with type `container`, value `agent-jorge`. The reference exists in atlas but not in the entry-point code.

---

## atlas.yaml coverage check

| Atlas ref | Type | In key entry files? |
|---|---|---|
| `laia_home` (`~/.laia`) | path | Used via `get_laia_home()` — correct |
| `srv_laia` (`/srv/laia`) | path | Only in reset.py installer — correct |
| `opt_laia` (`/opt/laia`) | path | Only in Dockerfile + installer — correct |
| `agora_container` (`laia-agora`) | container | Only in docstrings — COMMENT only |
| `jorge_container` (`agent-jorge`) | container | Not found in entry files |

All paths that **should** be atlas-referenced (`laia_home`) are already properly accessed via `get_laia_home()` in real code. Comments that mention paths are documentation, not hardcodes.

---

## Conclusion

**No hardcoded executable references requiring atlas.get() replacement found in the 7 key entry-point files.**

The `~/.laia` references in comments are documentation (docstrings and inline comments), not functional code. The `/srv/laia`, `/opt/laia`, and `laia-agora` references live in:
1. **Installer scripts** (reset, clone) — where atlas independence is intentional for disaster recovery
2. **Dockerfile** — container build context where self-reference is impossible
3. **Docstrings/comments** — architectural descriptions, not code paths
4. **Gateway remapping logic** — intentionally preserves non-home paths like `/opt/laia`

**Code that reads `~/.laia` paths in real execution** (`cli.py`, `run_agent.py`, `laia_state.py`, `laia_logging.py`) already uses `get_laia_home()` from `laia_constants.py`, which is the profile-aware mechanism and does NOT hardcode `~/.laia`.

---

## Questions

1. Should the **architecture docstrings** in `toolset_distributions.py` and plugin `__init__.py` files be converted to use `atlas.get("agora_container")` dynamically? Currently they are static comments describing an architecture that IS in atlas.yaml.

2. The installer scripts (`reset.py`, `clone.py`) explicitly cannot use atlas (they are the disaster-recovery path when atlas itself may be corrupt or unavailable). Is this an explicit architectural decision that should be documented?

---

## New refs needed

No new atlas refs identified as needed. The existing `agora_container` (laia-agora) and `jorge_container` (agent-jorge) in atlas.yaml are correctly defined.

If the architecture docstring references were to be converted to runtime resolution, it would require adding a way for docstrings to resolve atlas refs at documentation-generation time, which is likely out of scope.

