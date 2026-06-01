# QA Master Report — 2026-06-01 (Actualizado)
**Orquestador:** Minimax (QA/Reviewer)
**Fecha:** 2026-06-01
**Auditorías:** 10-agent original + re-auditoría 3-agent (B + C)

---

## Resumen ejecutivo

| Auditoría | Bloqueantes | Mayores | Menores | Nits |
|-----------|-------------|---------|---------|------|
| Original (10 agentes) | 5 | 23 | 11 | 13 |
| Re-auditoría B (executor+agent) | 0 | 2 | 11 | 6 |
| Re-auditoría C (infra+scripts) | 12 | 7 | 6 | 3 |
| **TOTAL** | **17** | **32** | **28** | **22** |

---

## BLOQUEANTES (17 total — requieren fix inmediato)

### De auditoría original (5) — YA en problems.md

| # | Fichero:línea | Issue |
|---|---------------|-------|
| 1 | `monitor.py:74` | `if not True: continue` — FleetMonitor inútil |
| 2 | `auth.py:27` | `elif pw == password:` — plaintext password comparison |
| 3 | `storage.py:207` | seed password `"dev-admin"` en texto plano |
| 4 | `main.py:1601-1603` | WebSocket silent `except: pass` |
| 5 | `main.py:226-232` | config cache silent `except: pass` |

### De re-auditoría C (12 bloqueantes nuevos)

| # | Fichero:línea | Issue |
|---|---------------|-------|
| 6 | `infra/bin/laia` | Sin shebang + sin `set -euo pipefail` |
| 7 | `infra/bin/laia-watch` | Sin shebang + sin `set -euo pipefail` |
| 8 | `infra/dev/preflight.sh` | `set -uo pipefail` (falta `e`) |
| 9 | `infra/dev/smoke-test.sh` | `set -uo pipefail` (falta `e`) + `ADMIN_PASSWORD=dev-admin` hardcoded |
| 10 | `infra/dev/add-test-user.sh:140-146` | Credenciales `"jorge"/"dev-admin"` hardcoded en curl |
| 11 | `infra/dev/chat-with-agent.sh:195-196` | Credenciales `"jorge"/"dev-admin"` hardcoded |
| 12 | `scripts/ai-orchestrator.py:34-67` | `DEFAULT_CONFIG` con tokens y paths de producción hardcoded |
| 13 | `scripts/hermes-backup.py:22` | `DEFAULT_DEST = /Volumes/PortableSSD/` — path macOS-only |
| 14 | `scripts/check-hardcoded-paths.py:48` | Nombres de workspaces reales embebidos en regex |
| 15 | `infra/scripts/deploy-agora.sh:28-29` | Referencia dirs archivados (ya no existen) |
| 16 | `scripts/cleanup-sessions.py:96-100` | `shutil.rmtree` sin validar symlink — puede borrar cualquier cosa |
| 17 | `scripts/delete-workspace.py:170` | `shutil.rmtree` sin symlink guard |

---

## TOP 10 más graves (bloqueantes + mayores combinados)

| # | Fichero:línea | Severidad | Categoría | Issue |
|---|---------------|-----------|-----------|-------|
| 1 | `monitor.py:74` | BLOCKER | bug | `if not True: continue` — monitor dead |
| 2 | `auth.py:27` | BLOCKER | security | plaintext password comparison |
| 3 | `storage.py:207` | BLOCKER | security | seed password plaintext |
| 4 | `main.py:1601-1603` | BLOCKER | bug | WebSocket silent pass |
| 5 | `main.py:226-232` | BLOCKER | bug | config cache silent pass |
| 6 | `scripts/cleanup-sessions.py:96-100` | BLOCKER | security | rmtree sin symlink guard |
| 7 | `infra/bin/laia` | BLOCKER | bash | sin shebang ni pipefail |
| 8 | `scripts/ai-orchestrator.py:34-67` | BLOCKER | security | tokens hardcoded |
| 9 | `infra/dev/add-test-user.sh:140` | BLOCKER | security | credenciales hardcoded |
| 10 | `database.py:319` | MAJOR | robustness | SQLite check_same_thread=False |

---

## ÁREAS limpios (sin acción requerida)

| Área | Veredicto |
|------|-----------|
| Agent Orchestration (02) | ✅ Limpio |
| Infra LXD/Installer (09) | ✅ Limpio |
| Pathd/Orchestrator/Tests (10) | ✅ Limpio |
| `infra/pathd/` | ✅ Limpio |
| `infra/orchestrator/` | ✅ Limpio |
| `infra/scripts/setup-prod-dirs.sh` | ✅ Limpio |
| `infra/scripts/backup-state.sh` | ✅ Limpio |
| `scripts/nightly-shutdown.py` | ✅ Limpio |
| `scripts/startup-report.py` | ✅ Limpio |

---

## Acciones por Owner

### Codex (backend)

| Prioridad | Issue |
|-----------|-------|
| BLOCKER | `monitor.py:74` — remove dead code |
| BLOCKER | `auth.py:27` — eliminar plaintext comparison |
| BLOCKER | `storage.py:207` — hashear seed password |
| BLOCKER | `main.py:1601-1603` — logging en WebSocket |
| BLOCKER | `main.py:226-232` — logging en config cache |
| MAJOR | `database.py:319` — SQLite thread-safety |
| MAJOR | `storage.py:122-186` — logging en migraciones |
| MAJOR | `security.py:89-97` — thread-lock rate store |
| MAJOR | `admin.py:1128-1131` — optimizar O(n²) |
| MAJOR | `config.py:86-97` — manejo OSError |

### Claude-b (scripts/tests)

| Prioridad | Issue |
|-----------|-------|
| BLOCKER | `infra/bin/laia` — añadir shebang + pipefail |
| BLOCKER | `infra/bin/laia-watch` — añadir shebang + pipefail |
| BLOCKER | `infra/dev/preflight.sh` — añadir `e` a pipefail |
| BLOCKER | `infra/dev/smoke-test.sh` — añadir `e` + externalizar creds |
| BLOCKER | `infra/dev/add-test-user.sh` — credenciales a env |
| BLOCKER | `infra/dev/chat-with-agent.sh` — credenciales a env |
| BLOCKER | `scripts/cleanup-sessions.py:96-100` — symlink guard |
| BLOCKER | `scripts/delete-workspace.py:170` — symlink guard |
| BLOCKER | `scripts/hermes-backup.py:22` — path multi-plataforma |
| MAJOR | `infra/scripts/deploy-agora.sh:28-29` — fix paths archivados |

---

## Informes parciales

| Agente | Fichero |
|--------|---------|
| 01 | `qa-2026-06-01-AGENTE-01-security-data.md` |
| 02 | `qa-2026-06-01-AGENTE-02-agent-orchestration.md` |
| 03 | `qa-2026-06-01-AGENTE-03-chat-llm.md` |
| 04 | `qa-2026-06-01-AGENTE-04-api-channels.md` |
| 05 | `qa-2026-06-01-AGENTE-05-executor.md` |
| 06 | `qa-2026-06-01-AGENTE-06-laia-cli-1.md` |
| 07 | `qa-2026-06-01-AGENTE-07-laia-cli-2.md` |
| 08 | `qa-2026-06-01-AGENTE-08-agent-acp.md` |
| 09 | `qa-2026-06-01-AGENTE-09-infra-lxd.md` |
| 10 | `qa-2026-06-01-AGENTE-10-pathd-orchestrator-tests.md` |
| B (re-audit) | `qa-2026-06-01-AGENTE-B.md` |
| C (re-audit) | `qa-2026-06-01-AGENTE-C.md` |

---

**Generado por:** Minimax (QA/Reviewer)
**Branch:** `wip/minimax/docs-and-qa`
**Fecha:** 2026-06-01