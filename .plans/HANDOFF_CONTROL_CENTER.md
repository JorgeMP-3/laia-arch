# Handoff — Construir el Centro de Control de AGORA

> **Para**: el siguiente agente (Codex) que arranque desde un git limpio en esta máquina.
> **De**: Claude Code Opus 4.7 1M, tras la sesión que dejó la arquitectura desplegada
> (tag `redesign-v2.0-deployed`, commit `2878dad`).
> **Fecha**: 2026-05-17.

Lee este documento de cabo a rabo antes de tocar código. Tiene 3 partes:

1. **Contexto** — qué es AGORA, qué se hizo en esta sesión, dónde está todo.
2. **Estado actual** — qué corre, qué tags hay, qué bugs/gotchas conocidos.
3. **Lo que toca hacer** — la especificación del **Centro de Control** que el
   operador pidió.

---

## 1. Contexto

### 1.1 Qué es AGORA Agents

Sistema multi-usuario de LAIA. Cada empleado tiene un agente personal con:

- Su propio container LXD (`laia-<slug>`) donde es **root** sin sandbox.
- Su propia memoria privada (SQLite workspace dentro del container).
- Acceso a una memoria colectiva compartida con otros usuarios (workspace
  en el cerebro `laia-agora`).
- Su propia config LLM (provider, key, model) — guardada en `agora.db`.

El cerebro AIAgent vive en un container LXD dedicado (`laia-agora`).
Cuando el LLM emite un tool_call que toca filesystem/bash, un plugin
(`agora-executor-forwarder`) lo intercepta y lo envía por HTTP al
`laia-executor` del container del usuario. Tool calls "inocuas" (web
search, vision) se ejecutan localmente en el cerebro.

### 1.2 Esta sesión — resumen ejecutivo

Empezamos con commit `36f7263` (sprint 2) que tenía un problema
fundamental: el motor LAIA vivía DENTRO del container del usuario con
permisos restrictivos. Resultado: el usuario era prisionero de su
propio container.

Se completaron en cascada (cada commit es un tag):

| Tag | Commit | Qué |
|---|---|---|
| `sprint2-snapshot` | `36f7263` | Estado de partida (sprint 2) — funcional pero arquitectura incoherente. |
| `redesign-v1-functional` | `64ba0c2` | Rediseño base: cerebro centralizado en `laia-agora`, executors finos por usuario, forwarder plugin. **210 tests verde.** |
| `redesign-v1.1-functional` | `0e6eb34` | Fix cross-thread: el AIAgent ejecuta tools en `ThreadPoolExecutor` interno; el plugin pasó de `threading.local` a registry por `task_id`. |
| `redesign-v1.2-secure` | `ec2140f` | **Bloque A — Security hardening**: toolset whitelist (quita `execute_code`/`process`/`cronjob`/`skill_manage`/`delegate_task`/`moa`), `AGORA_LOCAL_DENY` en forwarder, systemd hardening (User=agora, ProtectSystem=strict, etc.), read denylist de paths sensibles, audit log de tool calls. |
| `redesign-v1.3-user-runtime` | `53e9072` | **E1 — Safe equivalents** de las tools removidas, ejecutándose en el container del USUARIO: `python_exec`, `process_start/list/status/kill`, `cron_create/list/delete` (systemd timers). |
| `redesign-v2.0-deployed` | `2878dad` | Scripts de rebuild end-to-end. Arquitectura desplegada y validada: `laia-agora` corriendo el backend con OAuth ChatGPT Teams, `laia-jorge-dev` como primer user con tools forwardeadas. |

### 1.3 Arquitectura desplegada

```
HOST
└── LXD containers
    ├── laia-agora      (RUNNING)  cerebro AIAgent + plugin forwarder
    │   ├── FastAPI :8000 → host :8088 vía proxy device
    │   ├── User=agora (uid 999, no root) — ProtectSystem=strict, etc.
    │   ├── /opt/agora/data ← bind mount /srv/laia/agora
    │   ├── /opt/agora/data/auth.json ← lxc file push de ~/.laia/auth.json
    │   └── .laia-core/ + agora-backend/ + workspace_store/
    │
    ├── laia-<slug>    (1 por usuario)  executor fino
    │   ├── FastAPI :9091 — bearer token único por agente
    │   ├── root sin sandbox (libertad total dentro del container)
    │   ├── /home/user ← bind /srv/laia/users/<slug>/home
    │   └── 22 tools: read/write_file, terminal, patch, search_files,
    │                glob, grep, private_workspace_*, python_exec,
    │                process_*, cron_*
    │
    └── laia-jorge     (STOPPED)  sprint 2 viejo — preservar siempre
```

### 1.4 Archivos críticos por área

```
services/agora-backend/                  cerebro — FastAPI
  app/main.py                            endpoints (auth, users, agents, chat, telegram, llm_config)
  app/agent_pool.py                      AgentPool, AGORA_ENABLED_TOOLSETS, seed_agora_config_yaml
  app/chat_engine.py                     SSE streaming, forwarder lifecycle (register/unregister_context)
  app/storage.py                         CRUD: users, agents, events, telegram_links, conversations
  app/llm_config.py                      catalog 32 providers (paridad ARCH)
  app/models.py                          Pydantic — User, Agent, ChatProxyRequest, TelegramLinkTokenResponse...
  app/telegram_gateway.py                bot multi-tenant
  app/database.py                        schema SQLite + migrations

services/laia-executor/                  executor fino (1 por container de usuario)
  src/laia_executor/api.py               FastAPI :9091 + middleware body limit
  src/laia_executor/tools/registry.py    22 tools registradas
  src/laia_executor/tools/python_exec.py E1
  src/laia_executor/tools/process_tools.py  E1 — registry en memoria
  src/laia_executor/tools/cron_tools.py  E1 — systemd timers
  src/laia_executor/tools/private_workspace.py

.laia-core/plugins/agora-executor-forwarder/
  __init__.py                            EXECUTOR_TOOLS, AGORA_LOCAL_DENY, register_context, _on_pre_tool_call,
                                         SAFE_EXEC_TOOL_SCHEMAS, PRIVATE_WORKSPACE_TOOL_SCHEMAS

infra/lxd/
  image-build/build-base-image.sh        construye imagen laia-agent (executor)
  image-build/build-agora-image.sh       construye imagen laia-agora (cerebro)
  scripts/create-agent.sh                provisiona container de usuario
  scripts/create-agora.sh                provisiona container laia-agora
  scripts/rebuild-1..4-*.sh              4 scripts de rebuild total
  scripts/smoke-e2e.sh                   13 pasos E2E
  scripts/deploy-redesign.sh             el provision usado en dev local

infra/dev/
  chat-with-agent.sh                     dev (backend en host)
  chat-with-deployed.sh                  prod (backend en laia-agora)
  add-test-user.sh                       crear users adicionales
  verify-redesign.sh                     suite verde + boot test + round-trip

docs/
  AGORA_AGENTS.md                        arquitectura post-rediseño
  HANDOFF_CONTROL_CENTER.md              este documento
```

---

## 2. Estado actual de la máquina

### 2.1 Containers vivos

```
$ lxc list
laia-agora        RUNNING  10.99.0.219  (cerebro)
laia-jorge        STOPPED  -            (sprint 2 viejo — NO TOCAR)
laia-jorge-dev    RUNNING  10.99.0.92   (executor del primer user)
```

### 2.2 Endpoints y credenciales conocidas

- **AGORA backend** http://10.99.0.219:8000 — bind directo a la IP del container.
- **Proxy host** http://127.0.0.1:8088 → mismo backend.
- **Admin seed**: username=`jorge`, password=`dev-admin`. Verificable con
  `curl -fsS http://10.99.0.219:8000/api/health`.
- **Primer user test**: username=`jorge-dev`, password=`chattest`, slug
  `jorge-dev`, container `laia-jorge-dev`. State guardado en
  `/tmp/laia-state-jorge-dev.json`.

### 2.3 Tests automáticos

Estado al cierre de la sesión (vivos en CI):

| Suite | Pass | Skip | Path |
|---|---|---|---|
| agora-backend | 168 | 0 | `services/agora-backend/tests/` |
| laia-executor | 53 | 1* | `services/laia-executor/tests/` |
| forwarder plugin | 25 | 0 | `.laia-core/plugins/agora-executor-forwarder/tests/` |
| **Total** | **246** | 1 | |

*El skip es de `test_file_ops_truncate` porque `ripgrep` no está
instalado en el venv de tests; el handler real lo detecta y falla a un
fallback Python. No es regresión.

Para correrlos:

```bash
# Backend
cd ~/LAIA/services/agora-backend
PYTHONPATH=/home/laia-hermes/LAIA/.laia-core .venv/bin/pytest tests/ -q

# Executor
cd ~/LAIA/services/laia-executor
.venv/bin/pytest tests/ -q

# Forwarder
cd ~/LAIA
/home/laia-hermes/LAIA/services/agora-backend/.venv/bin/python \
  -m pytest .laia-core/plugins/agora-executor-forwarder/tests/ \
  --override-ini="addopts=" -q
```

### 2.4 Gotchas conocidos (lee esto ANTES de tocar nada)

#### G1. `auth.json` se distribuye por copy, NO por bind mount

ARCH refresca tokens OAuth ChatGPT en `~/.laia/auth.json`. Intentamos
bind-mountearlo al container `laia-agora` y NO funcionó por varias capas:
- Bind mount **FILE** sobre paths anidados en otro bind mount → falla
  silenciosamente en LXD unprivileged ARM.
- Bind mount **DIR** sí monta pero `~/.laia/` es 700 → container ve
  `nobody:nogroup` y no puede leer.
- `raw.idmap "uid 1000 999"` REEMPLAZA el idmap default en vez de añadir
  override → todos los uids caen a nobody, hasta root container.

**Workaround actual**: `sudo lxc file push ~/.laia/auth.json laia-agora/opt/agora/data/auth.json --uid 999 --gid 988 --mode 644`
en el momento del provisioning. Cuando ARCH refresca tokens (~mensual con
ChatGPT Teams), hay que re-pushear manualmente. **Esto es candidato a
fix permanente en el Centro de Control** (un endpoint admin que dispare
el `lxc file push`).

#### G2. `auth_json_status` queda `"unknown"` aunque el chat funcione

Cosmético. El bootstrap en `agent_pool._ensure_collective_workspace_env`
intenta symlinkear `~/.laia/auth.json` (resuelto desde dentro del
container = `/opt/agora/.laia/auth.json` o `/home/agora/.laia/auth.json`,
inexistente) → reporta `"missing"` o se queda `"unknown"`. PERO el
AIAgent lee `LAIA_HOME/auth.json` = `/opt/agora/data/auth.json` (que SÍ
existe gracias al `file push`), así que el chat funciona. El status
miente.

**Fix recomendado**: cuando el path candidato `~/.laia/auth.json` no
existe, mirar `LAIA_HOME/auth.json` ANTES de marcar `"missing"`. Una
docena de líneas en `agent_pool._ensure_collective_workspace_env`.

#### G3. `.laia-core` se instala con pyproject.toml, no requirements.txt

ARCH migró. El `build-agora-image.sh` viejo buscaba `requirements.txt`,
no estaba, salía silencioso → la imagen quedaba sin `fire`, `openai`,
`anthropic`, etc. → el backend caía al `_PlaceholderAgent`. Ya está
parcheado en `build-agora-image.sh:166-172`: si hay `pyproject.toml`,
hace `pip install /opt/agora/app/.laia-core` (modo no-editable porque
el bind mount no monta `.laia-core/` en runtime — solo agora-backend).

#### G4. PM2 puede respawnear backends huérfanos en :8088

Si el operador tenía PM2 configurado para `agora-backend` (legado de
otro intento), va a respawnear y tu container se ignora porque PM2
escucha en el mismo puerto. `rebuild-1-cleanup.sh` ya hace
`pm2 delete agora-backend && pm2 save`. Si vuelves a ver:

```
ps aux | grep "uvicorn app.main:app"
```

con un PID que renace tras `kill`, mira `pm2 list`.

#### G5. Forwarder rompe entre versions de LXD

El hook `pre_tool_call` del plugin se registra en el plugin manager
singleton del .laia-core. Si por algún motivo se cargan DOS instances
del PluginManager (p.ej. tests que importan el plugin file-by-path Y
también vía discover_plugins), el hook se duplica. Tests del plugin
hacen `_load_plugin()` por path; producción carga vía `discover_plugins`.
Si quieres testear con plugin manager real, importa `laia_cli.plugins`,
no por file path.

#### G6. Tools cargadas: 22 en executor, 27 en cerebro

Verificable:
```bash
# Cerebro (debe NO incluir execute_code/process/cronjob/skill_manage/delegate_task/moa)
lxc exec laia-agora -- journalctl -u agora-backend --no-pager | grep "Loaded.*tools" | tail -1

# Executor
curl -fsS -H "Authorization: Bearer $TOKEN" http://<container-ip>:9091/profile | jq '.tools | length'
```

#### G7. slug regex se relajó para aceptar underscores

El `create-agent.sh` aceptaba solo `^[a-z0-9][a-z0-9-]{1,30}$` (con
guion). Ahora `^[a-z0-9][a-z0-9_-]{1,30}$` (acepta `_` y `-`). Pero el
LXD subyacente NO admite underscores en `lxc launch`. Si pasas
`jorge_dev`, el script aborta. Usa `jorge-dev` con guion. Esto está
documentado en el script pero el agente y la UI tienen que enforcearlo.

#### G8. `chat-with-agent.sh` vs `chat-with-deployed.sh`

- `chat-with-agent.sh` levanta `uvicorn app.main:app` en HOST con
  puerto random — para iterar el código del backend rápido (Ctrl+C +
  relanzar = 5s). Útil cuando cambias `app/*.py`.
- `chat-with-deployed.sh` asume backend YA corriendo en `laia-agora` y
  hace curl contra el container. Para validar producción.

NO mezclar — cada uno usa un state file distinto
(`/tmp/laia-redesign-state.json` vs `/tmp/laia-state-<slug>.json`).

---

## 3. Lo que toca hacer — Centro de Control

El operador pidió un **Centro de Control backend-only** para administrar
todo el ecosistema y resolver errores como los de esta sesión sin tener
que entrar en SSH. Es una API REST que un panel admin futuro consumirá.

### 3.1 Capacidades requeridas

| Categoría | Operación | Hoy se hace así | Qué tiene que ofrecer el centro |
|---|---|---|---|
| **Diagnostico** | Verificar health de toda la pila | `curl …/api/health` + `lxc list` + `journalctl` | `GET /api/admin/status` agregado con: containers, /health de cada uno, tokens OAuth, suite tests, errors recientes |
| | Ver logs del backend | `lxc exec laia-agora -- journalctl -u agora-backend` | `GET /api/admin/logs/agora-backend?lines=N&since=...` |
| | Ver logs del executor | `lxc exec laia-<slug> -- journalctl -u laia-executor` | `GET /api/admin/logs/<slug>?lines=N` |
| | Inspeccionar tool calls audit | `grep tool_call /tmp/agora-backend-chat.log` | `GET /api/admin/audit/tools?user_id=&from=&to=` (lee del logger `agora.tool_call`) |
| **Lifecycle de usuario** | Crear user + container + register | `sudo bash rebuild-4-first-user.sh --slug X` | `POST /api/admin/users/provision {slug, display_name, role?}` → orquesta los 3 pasos atómicamente |
| | Listar users + estado | curl + cruzar con `lxc list` | `GET /api/admin/users` con datos enriquecidos: container_state, last_chat, llm_provider, agent_id |
| | Eliminar user (soft + container) | curl DELETE + `lxc delete` | `DELETE /api/admin/users/{slug}` → soft-delete user, lxc delete container, rm bind mount |
| | Recrear container del user | `lxc delete + create-agent.sh + PATCH /api/users` | `POST /api/admin/users/{slug}/rebuild` |
| | Refresh OAuth tokens en `laia-agora` | `laia auth` + `lxc file push` | `POST /api/admin/system/refresh-oauth` → re-push del `~/.laia/auth.json` actual al container |
| **Lifecycle de container** | Snapshot/restore | `lxc snapshot` + `lxc restore` | `POST /api/admin/containers/{name}/snapshot` + `POST /api/admin/containers/{name}/restore` |
| | Restart container | `lxc restart` | `POST /api/admin/containers/{name}/restart` |
| | Restart agora-backend | `lxc exec laia-agora -- systemctl restart` | `POST /api/admin/system/restart-backend` |
| **Lifecycle de imágenes** | Rebuild imagen | `sudo bash rebuild-2-images.sh` | `POST /api/admin/system/rebuild-image {kind}` (long-running → background job + status endpoint) |
| **Plugins** | Listar plugins cargados | `discover_plugins().keys()` | `GET /api/admin/plugins` |
| | Habilitar/deshabilitar plugin | editar `config.yaml` + restart | `PATCH /api/admin/plugins/{key} {enabled}` |
| **Telegram** | Ver vinculaciones | sqlite directo | `GET /api/admin/telegram/links` |
| **Errores** | Ver errores recientes | `grep ERROR /tmp/agora-backend-chat.log` | `GET /api/admin/errors?since=...` (parsea logs JSON) |
| | Health-fix conocidos | manual | `POST /api/admin/fix/{name}` con scripts curados (ej. `auth-json-push`, `pip-install-laia-core`, `pm2-stop-respawner`) |

### 3.2 Patrones que DEBE respetar

1. **Endpoints `/api/admin/*`** — requieren rol `agora_admin`. Reusa el
   decorator `require_roles("agora_admin")` que ya existe en
   `services/agora-backend/app/main.py`.
2. **Convención de shapes** — ya documentada en `docs/AGORA_AGENTS.md`:
   colecciones devuelven `{plural_key: [...]}`, objetos creados
   devuelven `{singular_key: {...}}`.
3. **Long-running ops** — los rebuilds tardan 5-15 min. NO hacer SSE
   streaming síncrono. Patrón: `POST /api/admin/.../start` devuelve
   `{job_id}`, `GET /api/admin/jobs/{job_id}` devuelve estado +
   tail de logs. Job ID es UUID, estado persistido en `agora.db`
   (nueva tabla `admin_jobs`).
4. **Tests primero** — cada endpoint nuevo trae su test en
   `services/agora-backend/tests/test_admin_*.py`. La suite actual
   tiene una fixture `_reset_login_rate_limit` autouse que limpia
   `security._rate_store` entre tests (resuelve flakes pre-existentes
   de integración).
5. **No tocar `.laia-core/`** salvo lo ESTRICTAMENTE necesario (extender
   schemas del forwarder si añades tools). El sub-repo es de ARCH; los
   merges deben ser limpios.
6. **No tocar `laia-ui/`** — el operador rehará la UI desde cero,
   feedback persistente en memoria
   (`feedback_skip_agora_ui.md`).
7. **No `git rm` jamás** — código retirado va a `archived/`
   (feedback `feedback_no_delete_code.md`).
8. **Paridad LLM** — cualquier nueva LLM config debe soportar los 32
   providers que `app/llm_config.py:list_providers` expone
   (feedback `feedback_llm_provider_parity.md`).

### 3.3 Tabla nueva en SQLite: `admin_jobs`

Para tracking de operaciones largas:

```sql
CREATE TABLE admin_jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                  -- 'rebuild-image', 'provision-user', 'snapshot', ...
    status TEXT NOT NULL,                -- 'pending', 'running', 'done', 'failed'
    actor_id TEXT NOT NULL,              -- user_id del admin
    params_json TEXT NOT NULL,           -- args originales
    result_json TEXT,                    -- result on success
    error TEXT,                          -- error message on failure
    log_path TEXT,                       -- path a /tmp/admin-job-<id>.log
    progress INTEGER DEFAULT 0,          -- 0-100
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (actor_id) REFERENCES users(id)
);
CREATE INDEX idx_admin_jobs_status ON admin_jobs(status);
CREATE INDEX idx_admin_jobs_actor ON admin_jobs(actor_id);
```

Migración: añade el bloque a `services/agora-backend/app/database.py:SCHEMA`.

### 3.4 Endpoint mínimo viable (sugerencia de fase 1)

Empieza con esto — 4 endpoints de diagnóstico + 1 acción:

```
GET  /api/admin/status                   estado global (cubre G1, G2, G4, G6)
GET  /api/admin/containers               lxc list + cruzar con agents table
GET  /api/admin/logs/{name}              tail de journalctl o /tmp/*.log
GET  /api/admin/audit/tools              tool_call audit (Bloque A5 ya lo emite)
POST /api/admin/system/refresh-oauth     fix conocido del auth.json (G1)
```

Con eso ya solucionas la mayoría de los problemas que vimos en esta
sesión. Las operaciones de provisioning vienen después.

### 3.5 Plan de implementación recomendado

```
Sprint AC-1 (4-6h): diagnostics read-only
  AC-1.1  admin_jobs table + helpers (BaseJob, run_in_background)
  AC-1.2  /api/admin/status
  AC-1.3  /api/admin/containers, /api/admin/logs
  AC-1.4  /api/admin/audit/tools (lee del logger agora.tool_call)
  AC-1.5  Tests + autodiscovery del agent admin role

Sprint AC-2 (6-8h): actions con jobs
  AC-2.1  /api/admin/system/refresh-oauth (resuelve G1)
  AC-2.2  /api/admin/users/provision (orquesta create-agent + register)
  AC-2.3  /api/admin/users/{slug}/rebuild
  AC-2.4  /api/admin/containers/{name}/restart, /snapshot, /restore
  AC-2.5  Tests con jobs mockeados

Sprint AC-3 (4-6h): rebuild imágenes + plugins
  AC-3.1  /api/admin/system/rebuild-image (long job)
  AC-3.2  /api/admin/plugins listar/toggle
  AC-3.3  /api/admin/fix/{name} con scripts curados (G1, G3, G4)

Sprint AC-4 (3-4h): polish + telegram + docs
  AC-4.1  /api/admin/telegram/links
  AC-4.2  /api/admin/errors paginado
  AC-4.3  Documentación en docs/CONTROL_CENTER.md
  AC-4.4  Smoke test E2E del admin flow
```

Total estimado: 17-24h.

### 3.6 NO hacer en este trabajo

- **NO** rehacer el rediseño actual. Lo desplegado funciona; el centro
  de control SOLO añade endpoints `/api/admin/*` y la lógica para
  orquestar.
- **NO** modificar el flujo de chat existente (`/api/agents/me/chat` +
  forwarder). Si encuentras un bug de chat, abre issue, NO patchees.
- **NO** tocar `laia-ui/` ni intentar crear frontend. El operador
  rehará la UI completa.
- **NO** romper la suite existente (246 tests). Cualquier cambio en
  `agent_pool.py`, `chat_engine.py`, `main.py` o el plugin del
  forwarder debe pasar la suite antes de commit.

### 3.7 Validación final del centro de control

Cuando termines, este flujo debe funcionar end-to-end como admin:

1. `curl -X POST /api/login -d '{username:jorge, password:dev-admin}'`
2. `curl /api/admin/status` → muestra `laia-agora UP, 1 user, 0 errors`.
3. `curl -X POST /api/admin/users/provision -d '{slug:maria}'` → job_id.
4. `curl /api/admin/jobs/<job_id>` → estado `running` → `done`.
5. `curl /api/admin/users` → ahora muestra `jorge-dev` y `maria`.
6. Llega Telegram para maria: `curl -X POST /api/user/telegram/link-token`
   (admin actuando en nombre de maria) → token.
7. Después de un mes, los tokens OAuth caducan. Admin corre:
   `curl -X POST /api/admin/system/refresh-oauth` → re-push del
   auth.json. Chat funciona otra vez sin intervención SSH.

---

## 4. Cómo arrancar (literal)

Cuando el operador inicie tu sesión, pega esto:

```
Continúo trabajo en feat/agora-redesign-centralized-brain. Arquitectura
desplegada en tag redesign-v2.0-deployed. Lee docs/HANDOFF_CONTROL_CENTER.md
completo antes de tocar nada. Tu trabajo: implementar el centro de
control admin descrito en la sección 3. Sprint AC-1 primero.
```

Y verifica que parte limpio:

```bash
cd ~/LAIA
git log --oneline -1                             # debe ser 2878dad o más reciente
git tag | grep redesign                          # debe incluir redesign-v2.0-deployed
lxc list                                         # laia-agora RUNNING, laia-jorge-dev RUNNING
curl -fsS http://10.99.0.219:8000/api/health     # {"ok": true, ...}
```

Si alguno falla, NO empieces a codear. Avisa al operador.

---

## 5. Última cosa — créditos OAuth

El admin (`jorge`) y todos los users (default) consumen créditos de la
cuenta ChatGPT Teams pegada a `~/.laia/auth.json` (operador
`info@myhelpcar.com`). Esto es **intencional** — el operador quiere que
sus empleados usen su suscripción y no API tokens individuales. Si un
admin quiere cambiar a un provider distinto solo para algunos users:

```bash
curl -X PATCH /api/user/llm-config -H 'Auth: Bearer $USER_TOKEN' \
     -d '{"provider":"anthropic", "api_key":"sk-ant-..."}'
```

Y ese user consumirá tokens propios en vez de OAuth. No requiere
cambios en el centro de control salvo exponerlo en UI.

---

Fin del handoff. Cuando termines AC-1+AC-2 mínimo, deja todo en un tag
`control-center-v0.1` y vuelve a notificar al operador.
