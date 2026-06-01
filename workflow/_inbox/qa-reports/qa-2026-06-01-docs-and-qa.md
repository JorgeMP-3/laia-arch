# QA Report — 2026-06-01

## Mission 1: Documentation (EN translation)
### Files edited (comment-only changes)
| File | Changes |
|------|---------|
| `services/agora-backend/app/storage.py:217-221` | Translated Spanish comment block to English |
| `services/agora-backend/app/models.py:18-20` | Translated Spanish comment to English |
| `scripts/show-injected.py:2` | Translated shebang comment to English |
| `scripts/create-workspace.py:462,540` | Translated comments + fixed typo "Guia"→"Guide" |
| `scripts/nightly-shutdown.py:109,113` | Translated docstring and comment |
| `scripts/index-scripts.py:2,98` | Translated shebang comment and table header |
| `scripts/git-manager.py:39` | Translated comment |
| `scripts/hermes-backup.py:2` | Translated shebang comment |
| `scripts/workspace-daily-diagnostic.py:2` | Translated docstring |

### Files identified for future translation (NOT touched - user output text)
- `scripts/git-manager.py:716` — "Volver al dashboard" — user-facing output text, not comment

---

## Mission 2: QA Sweep Findings

### BLOCKERS (registered in problems.md)

| File:line | Severity | Category | Description |
|-----------|----------|----------|-------------|
| `services/agora-backend/app/monitor.py:74` | **blocker** | bug | `if not True: continue` — dead code that skips ALL agent checks in every iteration. The entire for-loop body is unreachable, making the monitor completely ineffective. |
| `services/agora-backend/app/main.py:1601-1603` | **blocker** | bug | WebSocket `_push()` task has bare `except Exception: pass` and `except WebSocketDisconnect: pass` — all exceptions are silently swallowed. |
| `services/agora-backend/app/main.py:226-232` | **blocker** | bug | Empty `try` blocks with `pass` on lines 229 and 232 — silently swallows any exception when clearing `_LOAD_CONFIG_CACHE`. |

### MAJOR

| File:line | Severity | Category | Description |
|-----------|----------|----------|-------------|
| `services/agora-backend/app/coordinator.py:61,79,97` | **major** | bug | Bare `except Exception: pass` in `_loop()` — coordinator silently ignores all exceptions during check cycles. |
| `services/agora-backend/app/storage.py:137,152,167,184` | **major** | bug | Empty `except Exception: pass` in `_migrate_from_json()` — migration failures silently ignored. |
| `services/agora-backend/app/admin.py:148-149` | **major** | bug | `_warn_host_op_via_agora_admin()` silently swallows exceptions — audit trail for rule-6 violations is lost. |
| `infra/pathd/ipc.py:73-79` | **major** | bug | `_handle_client` catches `ConnectionResetError, BrokenPipeError` with `pass` — errors during client handling are completely invisible. |
| `infra/pathd/server.py:221-222` | **major** | bug | `_fs_callback()` catches `RuntimeError: pass` — catches all RuntimeErrors including unrelated ones. |
| `services/agora-backend/app/atlas_paths.py:4` | **major** | deuda | Module docstring documents v1 path `~/.laia/atlas.yaml` — outdated, should be `/srv/laia/arch/atlas.yaml` |
| `services/agora-backend/app/main.py:224` | **major** | deuda | Comment references `~/.laia/config.yaml` — v1 path |
| `services/agora-backend/app/main.py:336` | **major** | deuda | Comment references `~/.laia/auth.json` — v1 path |
| `services/agora-backend/app/admin.py:1519,1523,1582,1589` | **major** | deuda | Comments reference `~/.laia/auth.json` and `~/.laia/` — v1 paths |
| `services/agora-backend/app/agent_pool.py:185` | **major** | deuda | Comment references `~/.laia/auth.json` — v1 path |
| `infra/pathd/server.py:4-8` | **major** | deuda | Module docstring documents v1 paths throughout |
| `infra/pathd/notifier.py:4,49` | **major** | deuda | References `~/.laia/.env.paths` and `~/.laia/atlas/<alias>` — v1 paths |
| `infra/pathd/restarts.py:5` | **major** | deuda | Module docstring: `~/.laia/state/pending-restarts.json` — v1 path |
| `infra/pathd/__init__.py:3-6` | **major** | deuda | Package docstring documents ALL v1 paths |
| `scripts/_laia_runtime_paths.py:54` | **major** | deuda | `laia_home()` defaults to `Path.home() / ".laia"` — v1 layout default |
| `scripts/_doc_context_engine.py:82-85` | **minor** | deuda | Extensive v1 path references in docstring examples |
| `services/agora-backend/app/chat_engine.py:292` | **major** | estándar-prod | Tool call audit log at INFO level but operators may not know to look for it |
| `services/agora-backend/app/telegram_gateway.py:336` | **minor** | estándar-prod | `str.removeprefix()` is Python 3.9+ — may fail on Python 3.8 |
| `scripts/create-workspace.py:267-268` | **minor** | estándar-prod | macOS-specific `launchctl` command in `restart_gateway()` will fail silently on Linux |

### MINOR / NIT

| File:line | Severity | Category | Description |
|-----------|----------|----------|-------------|
| `services/agora-backend/app/admin.py:1504,1509` | **minor** | sintaxis | Empty comment lines (only `#`) — likely accidental formatting issue |
| `services/agora-backend/app/agent_pool.py:50,437,449` | **minor** | sintaxis | Empty comment lines |
| `infra/pathd/cli.py:229` | **minor** | estándar-prod | `input()` blocks forever in automated runs — should check `sys.stdin.isatty()` |
| `infra/pathd/restarts.py:10` | **minor** | TODO | Docstring states "No automatic restarts ever happen" — indicates deferred enhancement |
| `services/agora-backend/app/config.py:13,76` | **major** | smell | `Path.home()` fallback in `resolved_path()` may not match actual user in containers |
| `services/agora-backend/app/telegram_gateway.py:177-190` | **minor** | smell | Broad exception catching when calling `run()` and recording usage |
| `infra/pathd/cli.py:42,106` | **minor** | doc-EN-faltante | `_laia_home()` and `_via_demon_or_local()` lack docstrings |
| `infra/pathd/restarts.py:24,86,174` | **minor** | doc-EN-faltante | `_repo_systemd_dir()`, `scan_units()`, `apply_restart()` lack docstrings |
| `scripts/cleanup-sessions.py:22-105` | **minor** | doc-EN-faltante | Multiple functions lack docstrings |
| `scripts/create-workspace.py:35,49` | **minor** | doc-EN-faltante | `append_agent_log()`, `run_index_scripts()` lack docstrings |
| `scripts/sync-workspace-markdown.py:22-71` | **minor** | doc-EN-faltante | Multiple functions lack docstrings |

---

## Files NOT modified (project documentation, not code)

Per my mandate, the following were NOT touched:
- `LAIA_ECOSYSTEM.md` — project canonical doc (ES)
- `workflow/*` — project docs (ES)
- `workflow/_inbox/*` — project drafts (ES)
- `workflow/problems.md` — project tracker (ES)
- Any `.md` in root or `workflow/` directories

---

## Summary

| Severity | Count |
|----------|-------|
| blocker | 3 |
| major | 18 |
| minor | 14 |
| nit | 1 |

### Suggested Priority Fix Order
1. `monitor.py:74` — dead code `if not True: continue`
2. `main.py:226-232` — silent exception swallowing
3. `main.py:1601-1603` — WebSocket silent failures
4. All v1 path references → v2 layout (`/srv/laia/arch/...`)
5. Silent `except: pass` patterns in coordinator, storage, admin