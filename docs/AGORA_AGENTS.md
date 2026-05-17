# AGORA Agents — Cerebro Centralizado + Executors Libres

> **Estado**: rediseño en curso (branch `feat/agora-redesign-centralized-brain`).
> Reemplaza al sprint 2 (commit `36f7263`), cuya documentación se conserva
> en `archived/sprint2-agora-agents-20260516/AGORA_AGENTS.sprint2.md`.

## Resumen ejecutivo

AGORA Agents es el sistema multiusuario de LAIA: cada empleado tiene un agente
personal con su propia memoria privada, acceso a una memoria colectiva
compartida, y libertad total dentro de un contenedor LXD aislado del host.

El rediseño resuelve la incoherencia del sprint 2 — donde el código del cerebro
(`.laia-core`) vivía DENTRO del contenedor del usuario y se le quitaban permisos
al propio usuario para protegerlo — moviendo el cerebro a un contenedor
dedicado (`laia-agora`) y dejando el contenedor del usuario como un **executor
fino** (`laia-executor`) donde el usuario es root y manda él.

## Arquitectura

```
┌─────────────── HOST (Linux, dev ARM aarch64 7.2 GB) ──────────────────────┐
│                                                                            │
│  ARCH (en host)         /srv/laia/                                         │
│  ~/.laia-core/          ├── agora/                                         │
│  (intacto)              │   ├── agora.db          (users, agents, ...)     │
│                         │   └── workspaces/                                │
│                         │       └── collective/workspace.db                │
│                         │                                                  │
│                         └── users/{slug}/         (bind sources)           │
│                             ├── home/             → /home/user            │
│                             ├── plugins/          → /opt/laia/plugins     │
│                             └── workspace/        → /var/lib/laia/...     │
│                                                                            │
│  ┌── LXD container: laia-agora ────────────────────────────────────┐       │
│  │  /opt/agora/app/.laia-core/      cerebro AIAgent                │       │
│  │  /opt/agora/app/services/agora-backend/  FastAPI :8000          │       │
│  │  /opt/agora/data/               (bind /srv/laia/agora)          │       │
│  │      agora.db + workspaces/collective/workspace.db              │       │
│  │  AgentPool (1 AIAgent por sesión, TTL 60 min, LRU evict)        │       │
│  │  Per-user LLM keys en agora.db                                  │       │
│  │  Plugin agora-executor-forwarder ── HTTP → executors            │       │
│  │  Telegram gateway multi-tenant                                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                              ↕ HTTP/bridge LXD                             │
│  ┌── laia-{slug} ────────┐  ┌── laia-{slug2} ─────┐  (1 por usuario)       │
│  │  laia-executor :9091  │  │  laia-executor :9091│                        │
│  │  FastAPI fino         │  │  FastAPI fino        │                       │
│  │  root sin sandbox     │  │  root sin sandbox    │                       │
│  │  bind /home/user      │  │  bind /home/user     │                       │
│  │  bind workspace/      │  │  bind workspace/     │                       │
│  └───────────────────────┘  └──────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Componentes

| Componente | Ubicación | Función |
|------------|-----------|---------|
| AGORA Backend | `services/agora-backend/`, corre en container `laia-agora` :8000 | API FastAPI: auth, users, agents, chat, LLM config, Telegram |
| AIAgent pool | `services/agora-backend/app/agent_pool.py` | Una instancia de AIAgent por sesión activa, TTL 60 min, LRU evict |
| LLM config | `services/agora-backend/app/llm_config.py` | Catálogo de 30+ providers (paridad con LAIA ARCH) |
| Tool forwarder | `.laia-core/plugins/agora-executor-forwarder/` | Plugin pre_tool_call que redirige filesystem/bash a HTTP |
| laia-executor | `services/laia-executor/` | FastAPI fino dentro de cada container de usuario |
| Workspace colectivo | en `laia-agora`: `/opt/agora/data/workspaces/collective/workspace.db` | Memoria compartida entre todos los agentes |
| Workspace privado | en `laia-{slug}`: `/var/lib/laia/workspace/private/workspace.db` | Memoria personal de cada usuario |

## Flujo end-to-end

```
Usuario → AGORA UI → POST /api/agents/me/chat {message, session_id}
  → agora-backend (en container laia-agora)
    → AgentPool.get_or_create(user_id, session_id, agent_slug)
       ├─ if new: AIAgent(api_key=user.llm_api_key, provider=user.llm_provider, ...)
       └─ else: reuse + touch last_active
    → forwarder.configure_session(slug, container_ip, api_token)   # thread-local
    → AIAgent.run_conversation(message, callbacks)
       └─ LLM API call (provider configurado por user)
       └─ LLM responde: tool_call write_file("/home/user/x.py", "...")
       └─ pre_tool_call hook (agora-executor-forwarder)
            tool ∈ EXECUTOR_TOOLS → HTTP POST http://10.x.x.x:9091/exec
            ↓
            ┌── laia-executor (en container laia-{slug}) ──┐
            │  valida bearer token                          │
            │  ejecuta write_file como root                 │
            │    → /home/user/x.py (bind → /srv/laia/...) │
            │  → {"ok": true, "result": "..."}              │
            └───────────────────────────────────────────────┘
            ↓
       └─ hook retorna directive {"action":"replace","message":result}
       └─ AIAgent inyecta result en el loop, LLM continúa
    → SSE stream → AGORA UI muestra respuesta
  → Session persiste 60 min más, evict eventual por TTL/LRU
```

**Si el tool es `web_search`, `vision`, etc.** (no en `EXECUTOR_TOOLS`):
- El hook devuelve `None` → AIAgent ejecuta el handler local en AGORA
- Usa credenciales globales de AGORA (no las del user)
- Resultado vuelve al loop normal

## Decisiones de diseño

| Tema | Decisión | Por qué |
|------|----------|---------|
| AIAgent strategy | 1 instancia por sesión activa, TTL 60 min, LRU evict bajo presión | Aislamiento per-user + per-user LLM key limpio |
| Tool split | Filesystem/bash → executor; web/vision/image_gen/browser/workspace colectivo → AGORA | Evita duplicar API keys en N containers; tools locales más rápidas |
| Workspace dual | Colectivo en AGORA (acceso directo), privado en executor (forwardeado vía `private_workspace_*`) | Una fuente de verdad por workspace, namespacing claro para el LLM |
| Persistencia | Bind mounts host `/srv/laia/users/{slug}/` → container | Si el container muere, los datos sobreviven; backup simple |
| Sandbox | Eliminado en el executor (usuario root); auth solo a nivel API bearer token | El usuario es dueño de su container, no se le quita libertad |
| LLM providers | Paridad con LAIA ARCH (30+ providers) | UX consistente; el usuario elige (DeepSeek, Anthropic, OpenAI, Bedrock, ...) |
| Telegram | Aprovechar gateway existente de `.laia-core/`, multi-tenant via `telegram_links` table | El motor ya soporta multi-tenancy via session keys |

## API del executor (interfaz HTTP)

| Método | Path | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | — | Liveness probe |
| GET | `/profile` | Bearer | slug, version, uptime, tools registrados |
| POST | `/exec` | Bearer | `{tool, args, request_id}` → `{ok, result\|error, request_id}` |
| GET | `/workspace/files?path=` | Bearer | Lista archivos en un directorio |

Tools registradas en el executor (10 nativas + 4 de workspace privado):

- **Filesystem**: `read_file`, `write_file`, `apply_patch`, `list_dir`, `glob`, `grep`, `delete_file`, `move_file`, `make_dir`
- **Shell**: `bash` (subprocess directo, sin blacklist)
- **Private workspace**: `private_workspace_search`, `private_workspace_read_node`, `private_workspace_add_node`, `private_workspace_find_related`

## API del backend AGORA (selección)

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/api/login` | Auth |
| GET | `/api/me` | Usuario actual |
| GET | `/api/llm/providers` | Catálogo de los 30+ providers soportados |
| GET | `/api/llm/providers/{id}/models` | Modelos por defecto del provider |
| GET | `/api/user/llm-config` | Config LLM actual (key enmascarada) |
| PATCH | `/api/user/llm-config` | Actualizar config LLM |
| POST | `/api/agents/me/chat` | Chat con tu agente (SSE) |
| POST | `/api/agents/{slug}/chat` | Chat como admin con cualquier agente |
| GET | `/api/agents` | Listar agentes (admin) |
| POST | `/api/agents/register` | Registrar agente provisionado |
| POST | `/api/user/telegram/link-token` | Generar token de vinculación Telegram |

### Convención de respuestas

| Forma | Cuándo se usa | Ejemplo |
|-------|---------------|---------|
| `{plural_key: [...]}`  | Endpoints que devuelven colecciones | `GET /api/users` → `{"users":[…]}` |
| `{singular_key: {...}}` | Endpoints que devuelven un objeto creado/registrado | `POST /api/agents/register` → `{"ok":true,"agent":{…}}` |
| `[...]` directo | Endpoints tipados con `response_model=list[...]` (catálogos estables) | `GET /api/llm/providers` |
| `{...}` directo | Endpoints de salud / estado puntual | `GET /api/health`, `GET /api/me` |

Frontend / clientes nuevos deben asumir el primer formato salvo que el endpoint esté en las dos últimas filas. Cualquier desviación es bug y va contra esta convención — abrir issue.

### auth.json: writer ↔ reader

- **Writer canónico**: ARCH (`~/.laia/auth.json`). El comando `laia auth` y los refresh OAuth son los únicos que lo escriben.
- **Reader**: AGORA. Al arrancar, `agent_pool._ensure_collective_workspace_env` simlinkea `$LAIA_HOME/auth.json` → `~/.laia/auth.json` (override con `AGORA_ARCH_AUTH_JSON`).
- Si tu default provider es OAuth (`openai-codex`, `qwen-oauth`, `google-gemini-cli`, `copilot-acp`, `nous`) y `~/.laia/auth.json` no existe, `/api/health` reportará `"auth_json_ready": false`. Soluciona corriendo `laia auth` antes del primer chat.
- AGORA NO refresca tokens. Esa decisión evita carreras con ARCH; si hay que cambiarla, hay que añadir `flock` en el wrapper.

### Notas operativas

- **PM2 / supervisors externos**: si tienes PM2 corriendo `agora-backend`, sus restarts seguirán al código viejo aunque tú actualices el repo. Para iterar en dev usa `pm2 stop agora-backend` (o `pm2 delete agora-backend` permanente) antes de lanzar `infra/dev/chat-with-agent.sh`. El script ya elige un puerto aleatorio (18000-18999) para no chocar con un backend huérfano en :8088, pero los datos los lee/escribe en el mismo `/srv/laia/agora/agora.db` así que dos backends activos sí pueden interferir.

## Provisioning operativo

### Crear el container AGORA (una sola vez)

```bash
# 1. Construir la imagen
sudo bash infra/lxd/image-build/build-agora-image.sh

# 2. Provisionar el container con bind mount
sudo bash infra/lxd/scripts/create-agora.sh

# 3. Verificar
curl http://127.0.0.1:8088/health
```

### Crear un container de usuario (por cada empleado)

```bash
# 1. Construir la imagen base (una vez)
sudo bash infra/lxd/image-build/build-base-image.sh

# 2. Provisionar el container del usuario `jorge`
sudo bash infra/lxd/scripts/create-agent.sh jorge

# La salida JSON es lo que se pega en POST /api/agents/register
```

Los bind mounts en `/srv/laia/users/jorge/` ya están creados por el script
con `chown 100000:100000` (mapeo LXD unprivileged → uid root inside).

## Migración desde sprint 2

El sprint 2 metía `.laia-core/` dentro de cada container del usuario (con
permisos restrictivos) y aplicaba un sandbox a tools y comandos. El código
del sprint 2 **no se ha borrado** — se ha movido a
`archived/sprint2-agora-agents-20260516/` para auditoría y posible reúso:

- `archived/.../laia-runtime/` — el daemon viejo (api.py, agent_wrapper.py, tasks.py, profile.py, ...)
- `archived/.../agora_sandbox.py` — path whitelist + command blacklist
- `archived/.../AGORA_AGENTS.sprint2.md` — doc original del sprint 2

Restaurar es posible:

```bash
# Volver al estado completo del sprint 2:
git checkout sprint2-snapshot

# Restaurar un módulo concreto:
git mv archived/sprint2-agora-agents-20260516/laia-runtime services/laia-runtime
```

## Telegram (multi-tenant)

Un único bot de Telegram sirve a todos los usuarios AGORA. La identidad se
mapea con la tabla `telegram_links(telegram_user_id PK, agora_user_id FK)`:

```
Usuario en la web  ──►  POST /api/user/telegram/link-token
                        ↓ {"token": "abc...", "deep_link": "https://t.me/<bot>?start=link_abc..."}
Usuario en Telegram ──► envía  /link abc...   (o abre el deep-link, equivalente)
Bot AGORA          ──►  consume token + escribe telegram_links
                        ↓
A partir de aquí, cada mensaje del Telegram user_id se enruta contra el
agente del agora_user_id vinculado: misma AgentPool, misma LLM config,
mismo agent_slug. Web + Telegram comparten contexto por usuario.
```

Bot:
- Long-polling vía `getUpdates` (sin webhooks, no requiere URL pública).
- Implementado in-process en `services/agora-backend/app/telegram_gateway.py`
  como tarea asyncio bajo el lifespan de FastAPI. Solo se arranca si
  `AGORA_TELEGRAM_TOKEN` está en el entorno.
- Comandos: `/start` (onboarding), `/help`, `/link <token>`, `/unlink`.
- Cualquier otro texto se procesa con `AgentPool.get_or_create()` + el
  AIAgent ya cacheado para ese usuario.

Limitación documentada: si se necesita rebrand per-tenant (un bot distinto
por usuario) habrá que volver a multi-bot — ver `[PENDIENTE]` en
`.claude2/plans/contexto-lo-snuggly-scott.md` sección Fase 7.

## Tests

| Suite | Cobertura | Ubicación |
|-------|-----------|-----------|
| Executor | 19 tests (endpoints, tools, auth, private_workspace_*) | `services/laia-executor/tests/` |
| AGORA backend | 140 tests (auth, storage, agents, LLM, pool, workspace bootstrap, telegram links + gateway) | `services/agora-backend/tests/` |
| Plugin forwarder | 11 tests (passthrough, forward, errors, thread isolation, private_workspace_* schemas + routing) | `.laia-core/plugins/agora-executor-forwarder/tests/` |
| Hook system (.laia-core) | Tests de pre_tool_call directive (block + replace) | `.laia-core/tests/` |

**Total automatizado:** 170 tests verde a 16 de mayo de 2026.

## Tags y branches

- `sprint2-snapshot` → commit `36f7263` (estado funcional del sprint 2)
- `pre-redesign-backup` → mismo commit (alias semántico)
- `sprint2-final` → mismo commit (marca el fin del sprint 2, post-rediseño)
- `feat/agora-redesign-centralized-brain` → branch del rediseño

## Smoke test E2E

Cuando exista LXD en la máquina destino, ejecutar:

```bash
sudo bash infra/lxd/scripts/smoke-e2e.sh
```

Cubre los 13 pasos del plan: health, login, llm-config, create agent,
write+read forwardado, persistencia post-recreate, key inválida, Telegram
link, aislamiento multi-usuario, concurrencia, TTL del pool.

## Notas para mantenedores

- **No tocar la UI `laia-ui/packages/agora-app/`** — el usuario la rehará desde cero. Los nuevos endpoints backend que la UI futura necesita ya están listos (LLM config, Telegram link, etc.) — solo falta el frontend.
- **No borrar código** — cualquier módulo retirado va a `archived/sprint2-agora-agents-20260516/` con `git mv` (no `git rm`), preservando historia.
- **Paridad LLM con ARCH** — cualquier nuevo agente debe soportar los mismos providers que `.laia-core/laia_cli/providers.py:LAIA_OVERLAYS`.
