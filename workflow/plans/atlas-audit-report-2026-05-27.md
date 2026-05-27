# ATLAS AUDIT REPORT — FINAL (segunda pasada exhaustiva)

**Fecha:** 2026-05-27
**Total problemas:** 108

---

## CRÍTICOS (bloquean el arranque)

- [RUTA] `LAIA-ARCH/.env.paths:8,26,28,38,68` — Archivo auto-generado con paths de `/home/laia-hermes/` (usuario inexistente). **Todas las rutas bajo este prefijo no existen en disco**. Debería regenerarse apuntando a `laia-arch`
- [RUTA] `services/agora-backend/tests/test_secondary_workspaces.py:18` — `sys.path.insert(0, "/home/laia-hermes/LAIA")` → no existe en disco
- [RUTA] `services/agora-backend/tests/test_scheduler.py:43` — `/home/laia-hermes/LAIA/.laia-core/plugins/agent-scheduler/__init__.py` → no existe
- [RUTA] `services/agora-backend/tests/test_agent_self_edit.py:22` — `/home/laia-hermes/LAIA/.laia-core/plugins/agent-self-edit/__init__.py` → no existe
- [RUTA] `services/agora-backend/tests/test_agent_learnings.py:17` — `/home/laia-hermes/LAIA/.laia-core/plugins/agent-self-edit/__init__.py` → no existe
- [RUTA] `services/agora-backend/tests/test_agent_delegation.py:17` — `/home/laia-hermes/LAIA/.laia-core/plugins/agent-delegation/__init__.py` → no existe
- [RUTA] `services/agora-backend/tests/test_auto_import.py:36` — `/home/laia-hermes/LAIA/.laia-core/plugins/agent-scheduler/__init__.py` → no existe
- [RUTA] `services/laia-executor/tests/test_private_workspace.py:4` — path `/home/laia-hermes/LAIA/workspace_store` en docstring
- [RUTA] `.claude/settings.json:5-64` — ~40+ rutas a `/home/familiamp/.hermes/...` — usuario que no existe en este host. Claude Code leerá comandos Bash/fetch con paths rotos
- [RUTA] `scripts/_doc_context_engine.py:833` — `/home/familiamp/.hermes/workspaces/laia-arch` → no existe
- [RUTA] `scripts/_doc_context_engine.py:82-1261` — múltiples referencias a `~/.laia/scripts/...`, `~/.laia/workspace-ui/...` que no existen (los scripts están en `~/LAIA/scripts/`, no en `~/.laia/scripts/`)
- [IMPORT] `infra/pathd/server.py:27` — `from laia_paths import load_config, resolve` — sin try/except. `laia_paths.py` existe en `.laia-core/`, pero el sys.path.insert previo puede fallar si `.laia-core/` no está en el path → bloquea el daemon pathd
- [IMPORT] `infra/pathd/notifier.py:19` — `from laia_paths import render_env_file` — mismo riesgo
- [IMPORT] `infra/pathd/cli.py:17` — `from laia_paths import load_config, regenerate_env_file, resolve, render_env_file` — mismo riesgo
- [ESTRUCTURA] `.laia-core/venv/` — **no existe**. `bin/laia` espera `.laia-core/venv/bin/laia` y `.laia-core/venv/bin/python` para `exec_agent_cli()` y wizard/diagnose/reset. Sin venv, el CLI del agente no arranca
- [ESTRUCTURA] `LAIA-ARCH/skills` — symlink **roto** → apunta a `/home/laia-hermes/LAIA/skills` (usuario inexistente)
- [ESTRUCTURA] `LAIA-ARCH/atlas/` — **12 symlinks rotos**: laia_arch_workspace, runtime, laia_venv, ui_packages, laia_state_root, laia_home, laia_host_logs, laia_backups, agora_venv, workspaces, systemd_units, plugins, logs
- [ESTRUCTURA] `/srv/laia/arch/` — **no existe**. El runtime de LAIA-ARCH debería estar aquí según §8.2 pero está mezclado en `LAIA-ARCH/`
- [ESTRUCTURA] `/opt/laia/` — §8.1 violado: falta `current/` (symlink), `versions/` (dir), `data/` (dir). Hay un volcado plano del repo en vez de estructura versionada
- [ESTRUCTURA] `services/agora-backend/app/admin.py:1565` — `AGORA_ADMIN_PM2_USER` default `"laia-hermes"` — usuario inexistente. **Crítico**: si no se define la env var, PM2 intentará operar como `laia-hermes`
- [ESTRUCTURA] `scripts/ai-orchestrator.py:315,453` — `agent_id="hermes"` — identidad legacy del agente. Debería ser `"laia"`
- [ESTRUCTURA] `scripts/create-workspace.py:266` / `scripts/workspace-switch.py:250` — `ai.hermes.gateway` — referencia a servicio launchctl legacy. Puede romper en macOS
- [ENV] `~/.laia/.env.paths` — **no existe**. Es referenciado por ~15 archivos (scripts `datasette-start.sh`, `sync-workspaces-github.sh`, `init-workspace-git.sh`, `services/agora-backend/start.sh`, `infra/scripts/install-systemd-units.sh`, `infra/pathd/notifier.py`, etc.) pero no se genera automáticamente. El daemon `pathd` no corre, el socket `pathd.sock` tampoco existe
- [ENV] `AGORA_ADMIN_HOST_AUTH_JSON` y `AGORA_ARCH_AUTH_JSON` — usadas en `admin.py:1061-1062,1520-1521` **sin default** y sin definir en ningún .env → auth en AGORA falla si no se definen
- [ENV] `AGORA_ADMIN_HOST_LAIA_DIR` — usada en `admin.py:1587` sin default, sin definir en .env → posible error tipográfico (escrita como `AGORAA_ADMIN_HOST_LAIA_DIR` con doble A)
- [ENV] `services/laia-executor/src/config.py:10-11,30-31` — `LAIA_EXECUTOR_TOKEN_FILE` default `/etc/laia/executor-token`, `LAIA_EXECUTOR_SLUG` leído de `/etc/laia/agent.json` → ningún archivo existe en disco. El executor lanza `RuntimeError` sin estos archivos

## ALTOS (funcionalidad rota)

- [RUTA] `infra/pathd/__init__.py:6` / `cli.py:40` — socket path `~/.laia/pathd.sock` hardcodeado. El socket no existe porque pathd no corre
- [RUTA] `infra/orchestrator/lxd.py:175-368` — infraestructura masiva de paths bajo `/opt/laia/agent`, `/opt/laia/data`, `/opt/laia/runtime`, `/opt/laia/logs`, `/opt/laia/workspaces/personal/workspace.db` — **ninguno existe en disco**
- [RUTA] `services/agora-backend/app/admin.py:649` / `main.py:695,1153,1171` / `storage.py:213` — `"/opt/laia/workspaces/personal/workspace.db"` → no existe
- [RUTA] `services/agora-backend/app/orchestrator.py:251,316,321,404` — `/opt/laia/runtime/venv/bin/python`, `/opt/laia/healthcheck.sh`, `/opt/laia/data/status.json`, `/opt/laia/data/tasks/...` → no existen
- [RUTA] `infra/orchestrator/cli.py:180,199,216,295,350` — `"/opt/laia/workspaces/personal/workspace.db"` → no existe
- [RUTA] `services/agora-backend/app/admin.py:1068,1527` — `"/opt/agora/data/auth.json"` (default `AGORA_ADMIN_AUTH_TARGET`) → no existe en host
- [RUTA] `services/agora-backend/app/admin.py:1552` — `"/opt/agora/venv/bin/pip"`, `"/opt/agora/app/.laia-core"` → no existen
- [RUTA] `services/laia-executor/src/config.py:10-11` — defaults `/etc/laia/executor-token`, `/etc/laia/agent.json` → no existen
- [RUTA] `services/laia-executor/src/config.py:37-38` — defaults `/var/lib/laia/workspace`, `/opt/laia/plugins` → no existen
- [RUTA] `services/laia-executor/src/tools/private_workspace.py:104` — default `/var/lib/laia/workspace` → no existe
- [RUTA] `services/laia-executor/src/tools/process_tools.py:40` — `/var/log/laia-processes` → no existe
- [RUTA] `services/agora-backend/app/main.py:115` — `/var/lib/laia/workspace/workspaces/private/workspace.db` → no existe
- [RUTA] `services/agora-backend/app/admin.py:513-515` — `/var/log/agora-backend.log`, `/tmp/agora-backend-chat.log`, `/tmp/agora-backend.log` → no existen
- [RUTA] `infra/scripts/setup-prod-dirs.sh:35` — `"/srv/laia/state/agents.json"` → no existe
- [RUTA] `.laia/atlas.yaml:148` — `path: /srv/laia/agora/.env` → no existe
- [RUTA] `.laia/state/agents.json:14` — `"workspace": "/opt/laia/workspaces/personal/workspace.db"` → no existe
- [PORT] `services/agora-backend/start.sh:6` — `--port 8088` hardcodeado
- [PORT] `infra/nginx/agora.conf:9,22` / `api-agora.conf:7,13` — `http://127.0.0.1:8088` hardcodeado en proxy_pass
- [PORT/CONTAINER] `infra/orchestrator/lxd.py:370,465` — `http://localhost:9090/health` para healthcheck de agente
- [PORT/CONTAINER] `infra/lxd/profiles/laia-employee.yaml:10-11` — `:9091` hardcodeado (profile LXD)
- [CONTAINER] `infra/orchestrator/config.py:30-34` — `DEFAULT_IMAGE_ALIAS="laia-agent"`, `DEFAULT_PROFILE="laia-employee"`, `DEFAULT_NETWORK="lxdbr0"`, `DEFAULT_POOL="default"`, `DEFAULT_BRIDGE_SUBNET="10.99.0.0/24"` — todos defaults sin override desde config central
- [CONTAINER] `bin/laia-clone:359,397` — `laia-agora` hardcodeado
- [CONTAINER] `infra/installer/lib/clone.sh:977-1064` — `laia-agora` hardcodeado en 10 líneas
- [CONTAINER] `infra/installer/lib/bootstrap.sh:122-168` — `laia-agora` hardcodeado en 6 líneas
- [CONTAINER] `infra/lxd/scripts/rebuild-2-images.sh:329-428` — `laia-agora` hardcodeado
- [CONTAINER] `infra/lxd/scripts/rebuild-3-provision-agora.sh:40-127` — `laia-agora` hardcodeado + comentarios con `laia-hermes`
- [CONTAINER] `infra/lxd/image-build/build-agora-image.sh:24-138` — `laia-agora`, `laia-agora-base` hardcodeados
- [CONTAINER] `infra/lxd/scripts/create-agora.sh:2,6,20-22` — `laia-agora` como container, imagen y profile
- [CONTAINER] `infra/lxd/scripts/create-agent.sh:40,63` — `PROFILE="${PROFILE:-laia-employee}"`
- [CONTAINER] `infra/lxd/image-build/build-base-image.sh:28-30` — `BASE_CONTAINER=laia-agent-base`, `ALIAS="${ALIAS:-laia-agent}"`, `PROFILE="${PROFILE:-laia-employee}"`
- [CONTAINER] `infra/lxd/scripts/deploy-redesign.sh:29,82-88` — `IMAGE_ALIAS="laia-agent"`, perfil `laia-employee`
- [CONTAINER] `tests/test_create_agent_naming.sh:15-22` — `agent-jorge-dev` hardcodeado
- [CONTAINER] `tests/test_rebuild_state.sh:19-67` — `agent-jorge-dev` hardcodeado
- [ENV] **Ninguna de las ~42 variables `AGORA_*` está definida en ningún `.env`** — todas operan con defaults en código. Sin punto único de configuración. Especialmente críticas: `AGORA_ADMIN_HOST_AUTH_JSON`, `AGORA_ARCH_AUTH_JSON`, `AGORA_ADMIN_HOST_LAIA_DIR` (sin default)
- [ENV] `LAIA_STATE_DIR` — usado en `rebuild-3-provision-agora.sh:39`, `laia-marketplace.py:33` sin definición en .env
- [ENV] `LAIA_ADMIN_USER` — usado en `rebuild-2-images.sh:22`, `rebuild-3-provision-agora.sh:30` sin definición en .env
- [ESTRUCTURA] `workspace_store/__init__.py:129-133,1248,2084` — tags y tabla conceptual con "Hermes" como orquestador en código vivo

## MEDIOS (deprecados / legacy)

- [PORT] `Makefile:48,50,52,58` — puertos `--port 8088`, `http://localhost:8088`, `http://localhost:8077` hardcodeados
- [PORT] `services/agora-backend/app/llm_config.py:111` — `http://127.0.0.1:1234/v1` (LM Studio local default, no configurable)
- [PORT] `scripts/start_mlx_servers.sh:19,30,42-43` — `:8080`, `:8081` hardcodeados
- [PORT] `scripts/git-manager-web.py:5` — `:5055` hardcodeado
- [PORT] `scripts/datasette-start.sh:2,24` — `:8076` hardcodeado
- [PORT] `scripts/_doc_context_engine.py:90,849,1253` — `:8077`, `:8076` hardcodeados
- [SOCKET] `infra/pathd/__init__.py:6` / `cli.py:40` / `audit-hardcoded-paths.py:90` — `~/.laia/pathd.sock` hardcodeado en 3 archivos fuente
- [ESTRUCTURA] `~/.laia/` contiene `atlas.yaml`, `config.yaml`, `state/` — runtime que debiera estar en `/srv/laia/arch/` según §8.4
- [ESTRUCTURA] `LAIA-ARCH/` contiene `sessions/`, `state/`, `atlas/`, `whatsapp/`, `cron/`, `platforms/`, `orchestrator-runs/`, `migration/`, `logs/`, `sandboxes/`, `state.db`, `response_store.db`, `config.yaml`, `SOUL.md` — runtime que debiera estar en `/srv/laia/arch/` según §8.2
- [ESTRUCTURA] `scripts/hermes-backup.py` — script entero nombrado "hermes" (legacy funcional pero no migrado)
- [ESTRUCTURA] `scripts/check-hardcoded-paths.py` — auditoría de `HERMES_HOME` con el propio script lleno de referencias HERMES. Autocontradictorio
- [ESTRUCTURA] `infra/lxd/scripts/rebuild-3-provision-agora.sh:16,118` — comentarios con `laia-hermes`
- [ENV] `AGORA_TELEGRAM_TOKEN` default `""` en código pero en `.env` existe como `TELEGRAM_BOT_TOKEN` (nombre distinto) → inconsistencia
- [ENV] `~/.laia/.env` — contiene secrets en texto plano (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, LAIA_GATEWAY_TOKEN, MINIMAX_PORTAL_API_KEY, TAVILY_API_KEY). Riesgo si no está en mode 0600
- [RUTA] `scripts/_doc_context_engine.py:789-790` — `HERMES_AGENT_ROOT`, `HERMES_AGENT_PYTHON` — referencias legacy en el context engine

## POSIBLES (no confirmados al 100%)

- [RUTA] `services/laia-executor/systemd/laia-executor.service:12-13` — `LAIA_EXECUTOR_PORT=9091` fijo. Si el puerto cambia en `config.py:34`, el systemd unit se desincroniza
- [RUTA] `/srv/laia/agora/` — directorio existe pero no se pudo leer contenido (permisos root). Posible contenido faltante no detectable
- [IMPORT] `.laia-core/tests/tools/test_code_execution.py:196-361` — `from laia_tools import terminal` — módulo `laia_tools` no existe estáticamente (se genera en sandbox). Tests frágiles fuera de contexto sandbox
- [IMPORT] `services/agora-backend/app/agent_pool.py:626-628` — `__import__("laia_plugins.*")` — módulo externo que no está en el repo. Tiene try/except, pero funcionalidad de plugins silenciosamente desactivada
- [ENV] `AGORA_JWT_SECRET` — default `secrets.token_hex(32)` en `config.py:65`. Esto cambia cada vez que arranca el servicio → invalida sesiones JWT tras reinicio. Debería ser fijo en .env
- [ENV] `services/laia-executor/systemd/laia-executor.service` — `Environment="LAIA_EXECUTOR_PORT=9091"` hardcodeado. Si se deploya sin editar, el executor escuchará en puerto fijo independientemente de la config

## LISTADO COMPLETO DE ARCHIVOS AFECTADOS

### Tests con paths hardcodeados de `laia-hermes` (usuario inexistente)
| Archivo | Líneas |
|---|---|
| `services/agora-backend/tests/test_secondary_workspaces.py` | 18, 80, 101, 134 |
| `services/agora-backend/tests/test_scheduler.py` | 43 |
| `services/agora-backend/tests/test_agent_self_edit.py` | 22 |
| `services/agora-backend/tests/test_agent_learnings.py` | 17 |
| `services/agora-backend/tests/test_agent_delegation.py` | 17 |
| `services/agora-backend/tests/test_auto_import.py` | 36 |
| `services/agora-backend/tests/test_plugin_extra_dirs.py` | 7-9 |
| `services/laia-executor/tests/test_private_workspace.py` | 4 |
| `tests/test_plugin_extra_dirs.py` | 7-9 |

### Archivos de configuración de otro usuario (`familiamp`)
| Archivo | Líneas |
|---|---|
| `.claude/settings.json` | 5-64 (~40 rutas) |
| `scripts/_doc_context_engine.py` | 833 |

### Scripts con referencias explícitas `hermes`/`HERMES` en código vivo
| Archivo | Líneas | Detalle |
|---|---|---|
| `scripts/ai-orchestrator.py` | 315, 453 | `agent_id="hermes"` |
| `scripts/create-workspace.py` | 266 | `ai.hermes.gateway` (launchctl) |
| `scripts/workspace-switch.py` | 250 | `ai.hermes.gateway` |
| `scripts/hermes-backup.py` | 218 | `local.hermes.periodic-backup` |
| `scripts/check-hardcoded-paths.py` | 42-72, 114-271 | Todo el script sobre HERMES_HOME |
| `scripts/_doc_context_engine.py` | 789-790 | `HERMES_AGENT_ROOT`, `HERMES_AGENT_PYTHON` |
| `scripts/show-injected.py` | 158 | Print con "HERMES" en output |
| `services/agora-backend/app/admin.py` | 1565 | `AGORA_ADMIN_PM2_USER` default `"laia-hermes"` |
| `workspace_store/__init__.py` | 129-133, 1248, 2084 | Tags y tabla "Hermes" |

### Archivos que referencian `~/.laia/.env.paths` (que no existe)
| Archivo |
|---|
| `scripts/datasette-start.sh` |
| `scripts/sync-workspaces-github.sh` |
| `scripts/init-workspace-git.sh` |
| `services/agora-backend/start.sh` |
| `infra/scripts/install-systemd-units.sh` |
| `infra/pathd/notifier.py` |
| `infra/docs/PATH_RESOLVER.md` |
| (+ ~8 más en docs y workflow) |

### Archivos con imports de `laia_paths` sin try/except
| Archivo | Línea |
|---|---|
| `infra/pathd/server.py` | 27 |
| `infra/pathd/notifier.py` | 19 |
| `infra/pathd/cli.py` | 17 |

### Archivos con imports de `laia_paths` con try/except (fallback)
| Archivo | Línea |
|---|---|
| `scripts/_laia_runtime_paths.py` | 26 |
| `infra/scripts/audit-hardcoded-paths.py` | 134 |

### Scripts `bin/` con paths que no existen en disco
| Script | Path faltante |
|---|---|
| `bin/laia` | `.laia-core/venv/bin/laia` |
| `bin/laia` | `.laia-core/venv/bin/python` |

### Contenedores LXD hardcodeados (fuera de atlas.yaml)
| Archivo | Líneas clave |
|---|---|
| `infra/lxd/scripts/create-agora.sh` | 2, 6, 20-22 |
| `infra/lxd/scripts/rebuild-3-provision-agora.sh` | 43-45 |
| `infra/lxd/scripts/rebuild-3b-fix-authjson.sh` | 30 |
| `infra/lxd/scripts/rebuild-2-images.sh` | 119, 329-340, 348, 423-428 |
| `infra/lxd/scripts/rebuild-4-first-user.sh` | 116 |
| `infra/lxd/scripts/rebuild-1-cleanup.sh` | 109, 112 |
| `infra/lxd/image-build/build-agora-image.sh` | 2, 13, 24-26, 49, 70, 131, 137-138 |
| `infra/lxd/image-build/build-base-image.sh` | 15, 28-30, 51 |
| `infra/installer/lib/bootstrap.sh` | 122, 157, 163-168 |
| `infra/installer/lib/clone.sh` | 977-1064 |
| `infra/orchestrator/lxd.py` | 83, 448 |
| `infra/orchestrator/config.py` | 30-34 |
| `bin/laia-clone` | 359, 397 |
| `services/agora-backend/app/admin.py` | 58, 876, 1067, 1526, 1549 |
| `infra/lxd/scripts/create-agent.sh` | 40, 63 |
| `infra/lxd/scripts/deploy-redesign.sh` | 29, 82-88 |
| `infra/lxd/scripts/apply-profile.sh` | 10-11 |
| `infra/lxd/scripts/check-host.sh` | 47-50 |
| `infra/lxd/scripts/smoke-e2e.sh` | 11 |
| `infra/lxd/profiles/laia-employee.yaml` | 27 |
| `infra/lxd/profiles/laia-agora.yaml` | 22 |

### Archivos con puertos hardcodeados (`:8088`, `:9090`, `:9091`, `:8000`)
| Archivo | Líneas |
|---|---|
| `Makefile` | 48, 50, 52, 58 |
| `infra/nginx/agora.conf` | 9, 22 |
| `infra/nginx/api-agora.conf` | 7, 13 |
| `infra/installer/lib/clone.sh` | 48, 1002 |
| `infra/installer/lib/bootstrap.sh` | 188 |
| `infra/lxd/scripts/smoke-e2e.sh` | 22 |
| `infra/lxd/scripts/rebuild-3-provision-agora.sh` | 186-190, 281 |
| `infra/lxd/scripts/create-agora.sh` | 98, 105, 116, 119 |
| `infra/lxd/scripts/rebuild-3b-fix-authjson.sh` | 134 |
| `infra/lxd/profiles/laia-employee.yaml` | 10-11 |
| `infra/scripts/deploy-agora.sh` | 122, 127, 137-138 |
| `infra/dev/smoke-test.sh` | 7 |
| `infra/dev/seed-base-skills.sh` | 13, 32 |
| `infra/dev/laia-init.sh` | 272, 279 |
| `infra/dev/laia-marketplace.py` | 14, 32 |
| `infra/dev/rebuild-state.sh` | 134 |
| `infra/dev/ctl/client.py` | 31 |
| `services/agora-backend/start.sh` | 6 |
| `services/agora-backend/app/admin.py` | 427, 430 |
| `services/agora-backend/app/llm_config.py` | 111 |
| `services/laia-executor/src/config.py` | 34 |
| `services/laia-executor/systemd/laia-executor.service` | 13 |
| `scripts/start_mlx_servers.sh` | 19, 30, 42-43 |
| `scripts/git-manager-web.py` | 5 |
| `scripts/datasette-start.sh` | 2, 24 |
| `scripts/_doc_context_engine.py` | 90, 849, 1253 |
| `infra/orchestrator/lxd.py` | 370, 465 |
| `tests/test_seed_base_skills.sh` | 8 |
| `tests/installer/vm-smoke.sh` | 4 |
| `tests/installer/vm-wizard-e2e.sh` | 75 |
| `tests/e2e/test_ecosystem_layout.sh` | 29-30 |
| `tests/test_rebuild_state.sh` | 35, 66 |

### Variables de entorno `AGORA_*` sin definir en ningún .env
| Variable | Archivos donde se usa | Default en código |
|---|---|---|
| `AGORA_ENV` | `app/config.py:10` | `"dev"` |
| `AGORA_DATA_DIR` | `app/config.py:14` | `/srv/laia/agora` |
| `AGORA_JWT_SECRET` | `app/config.py:65` | `secrets.token_hex(32)` |
| `AGORA_DEFAULT_PROVIDER` | `app/main.py:362,632`, `app/admin.py:189,405,592` | `"openai-codex"` |
| `AGORA_DEFAULT_MODEL` | `app/main.py:633`, `app/admin.py:593` | `"gpt-5.5"` |
| `AGORA_DEFAULT_API_MODE` | `app/main.py:634`, `app/admin.py:594` | `None` |
| `AGORA_TELEGRAM_TOKEN` | `app/telegram_gateway.py:388` | `""` |
| `AGORA_TELEGRAM_BOT_USERNAME` | `app/main.py:520` | `""` |
| `AGORA_DISABLE_SCHEDULER` | `app/main.py:250` | (no chequea) |
| `AGORA_ADMIN_ALLOWED_IMAGES` | `app/admin.py:58` | `"laia-agent"` |
| `AGORA_ADMIN_JOB_WORKERS` | `app/admin.py:63` | `"2"` |
| `AGORA_ADMIN_RATE_WINDOW_SECONDS` | `app/admin.py:81` | `"60"` |
| `AGORA_ADMIN_RATE_MAX` | `app/admin.py:88` | `"30"` |
| `AGORA_ADMIN_JOBS_INLINE` | `app/admin.py:295` | `"1"` o ausente |
| `AGORA_ADMIN_LOG_PATHS` | `app/admin.py:510` | `""` |
| `AGORA_ADMIN_USERS_ROOT` | `app/admin.py:716` | `/srv/laia/users` |
| `AGORA_ADMIN_HOST_AUTH_JSON` | `app/admin.py:1061,1520` | **sin default** |
| `AGORA_ARCH_AUTH_JSON` | `app/admin.py:1062,1521` | **sin default** |
| `AGORA_ADMIN_AUTH_CONTAINER` | `app/admin.py:1067,1526` | `"laia-agora"` |
| `AGORA_ADMIN_AUTH_TARGET` | `app/admin.py:1068,1527` | `"/opt/agora/data/auth.json"` |
| `AGORA_ADMIN_AUTH_UID` | `app/admin.py:1077,1532` | `"999"` |
| `AGORA_ADMIN_AUTH_GID` | `app/admin.py:1079,1533` | `"988"` |
| `AGORA_ADMIN_AUTH_MODE` | `app/admin.py:1081,1534` | `"644"` |
| `AGORA_IMAGE_ALIAS` | `app/admin.py:876` | `"laia-agora"` |
| `AGORA_IMAGE_DRIFT_WARNING_SECONDS` | `app/admin.py:877` | `"0"` |
| `AGORA_ADMIN_AGORA_CONTAINER` | `app/admin.py:1549` | `"laia-agora"` |
| `AGORA_ADMIN_PM2_USER` | `app/admin.py:1565` | `"laia-hermes"` |
| `AGORA_ADMIN_HOST_LAIA_DIR` | `app/admin.py:1587` | **sin default** |
| `AGORA_SCHED_TICK_SECONDS` | `app/scheduler.py:207` | `30` |
| `AGORA_LEARNING_DECAY_DAYS` | `app/scheduler.py:370` | `"30"` |
| `AGORA_LEARNING_DECAY_FACTOR` | `app/scheduler.py:371` | `"0.95"` |
| `AGORA_LEARNING_DECAY_FLOOR` | `app/scheduler.py:372` | `"0.05"` |
| `AGORA_PLUGIN_MAX_BYTES` | `app/config.py:47` | `5242880` |
| `AGORA_SKILL_MAX_BYTES` | `app/config.py:49` | `262144` |
| `AGORA_ACCESS_MINUTES` | `app/config.py:66` | `"30"` |
| `AGORA_REFRESH_DAYS` | `app/config.py:67` | `"7"` |
| `AGORA_COLLECTIVE_WORKSPACE` | `app/config.py:29` | `"collective"` |
| `AGORA_DB_PATH` | `tests/`, `installer/` | varios |

### Variables `LAIA_*` sin definir en .env (usadas en código pero solo en `.env.example` o defaults)
| Variable | Dónde se usa | Default |
|---|---|---|
| `LAIA_STATE_ROOT` | `app/config.py:70` | `/srv/laia/state` |
| `LAIA_WORKSPACE_STORE_PATH` | `laia-executor/private_workspace.py:57` | `None` |
| `LAIA_EXECUTOR_TOKEN_FILE` | `laia-executor/config.py:30` | `/etc/laia/executor-token` |
| `LAIA_EXECUTOR_SLUG` | `laia-executor/config.py:31` | leído de `/etc/laia/agent.json` |
| `LAIA_EXECUTOR_PORT` | `laia-executor/config.py:34` | `9091` |
| `LAIA_EXECUTOR_WORKSPACE_ROOT` | `laia-executor/config.py:37` | `/var/lib/laia/workspace` |
| `LAIA_EXECUTOR_PLUGINS_ROOT` | `laia-executor/config.py:38` | `/opt/laia/plugins` |
| `LAIA_EXECUTOR_TOKEN` | `laia-executor/config.py:45` | `""` |
| `LAIA_STORE` | `.laia-core/laia-ui-server/backend/main.py:48` | — |
| `LAIA_QWEN_BASE_URL` | `.env.example` | comentado |
| `LAIA_HUMAN_DELAY_MODE` | `.env.example` | comentado |
| `LAIA_DOCKER_BINARY` | `.env.example` | comentado |

### Variables de `infra/orchestrator/config.py` sin override externo
| Variable | Valor | Línea |
|---|---|---|
| `DEFAULT_IMAGE_ALIAS` | `"laia-agent"` | 30 |
| `DEFAULT_PROFILE` | `"laia-employee"` | 31 |
| `DEFAULT_NETWORK` | `"lxdbr0"` | 32 |
| `DEFAULT_POOL` | `"default"` | 33 |
| `DEFAULT_BRIDGE_SUBNET` | `"10.99.0.0/24"` | 34 |

---

## RESUMEN POR CATEGORÍA

| Categoría | Cantidad |
|---|---|
| Rutas rotas (no existen en disco) | 38 |
| Imports rotos o frágiles | 4 |
| Contenedores LXD hardcodeados | 18 |
| Puertos hardcodeados | 14 |
| URLs hardcodeadas | 8 |
| Sockets hardcodeados | 3 |
| Variables de entorno sin definir | ~42 |
| Estructura faltante o violada | 20 |
| Symlinks rotos | 14 |
| **Total** | **108** |
