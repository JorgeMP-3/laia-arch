# LAIA — Mapa del proyecto

> Plano de **todo el repositorio**: las carpetas más importantes, su objetivo, y sus
> archivos y subcarpetas clave. Es el índice estructural del código. Para la **idea** del
> proyecto ver [`../LAIA_ECOSYSTEM.md`](../LAIA_ECOSYSTEM.md); para el **layout en disco /
> migración** ver [`arch-layout.md`](arch-layout.md).
>
> Última revisión: 2026-05-27. (Listados representativos, no exhaustivos: se omiten
> `__pycache__`, `venv`, `node_modules`, `*.egg-info`.)

---

## Vista de pájaro

```
LAIA/
├── AGENTS.md  CLAUDE.md  LAIA_ECOSYSTEM.md   ← documentos de entrada y visión
├── Makefile  install.sh                      ← build y bootstrap
├── bin/                ← CLIs de cara al operador (laia, atlas, install, clone…)
├── .laia-core/         ← EL MOTOR del agente (cerebro). Regla ⑦: solo host + laia-agora
├── services/           ← los dos microservicios del producto
│   ├── agora-backend/  ← el cerebro/API multi-usuario (LAIA-AGORA)
│   └── laia-executor/  ← el ejecutor que corre en el container del usuario
├── infra/              ← infraestructura: instalador, LXD, orquestador, pathd, nginx
├── skills/             ← catálogo de skills (capacidades del agente)
├── plugins/            ← plugins del ecosistema
├── workspace_store/    ← librería compartida de workspaces (SQLite + FTS5)
├── laia-ui/            ← interfaz web (en reconstrucción)
├── scripts/            ← utilidades operacionales del host
├── tests/              ← suites de integración y e2e (raíz del repo)
├── workflow/           ← documentación operativa, bitácoras y planes
├── docs/               ← documentación y diagramas del proyecto
├── examples/  archived/← ejemplos y material archivado
```

---

## Raíz — documentos y bootstrap

| Archivo | Objetivo |
|---|---|
| `AGENTS.md` | Punto de entrada canónico para cualquier IA que trabaje en el repo. **Léelo primero.** |
| `CLAUDE.md` | Reglas operativas específicas para Claude Code. |
| `LAIA_ECOSYSTEM.md` | Documento de visión: qué es LAIA, entidades, reglas duras, roadmap. |
| `Makefile` | Targets de build/dev. |
| `install.sh` | Bootstrap de instalación (entrada de `laia-install`). |
| `.gitignore` | Importante: ignora `.laia-core/` entero (lo necesario se hace `git add -f`). |

---

## `bin/` — CLIs de cara al operador

Wrappers que el operador (LAIA-ARCH/Jorge) invoca desde el PATH.

| Archivo | Objetivo |
|---|---|
| `laia` | Dispatcher unificado. Sin args → chat con el agente; subcomandos → install/clone/wizard/release/… o se reenvían al CLI Python del agente. |
| `atlas` | CLI del registro Atlas v2 (`get`, `doctor`, `check`, `list`, `validate`, `env`, `graph`…). |
| `laia-install` | Instala LAIA en un host limpio. |
| `laia-clone` | Migra estado (datos + containers) desde otro servidor (patrón pull). |
| `laia-release` | Promueve un árbol dev a `/opt/laia-vX.Y.Z` y reinicia. |
| `laia-rollback` | Vuelve el symlink `/opt/laia` a una versión anterior. |

---

## `.laia-core/` — El motor del agente (el cerebro)

El núcleo que razona y usa herramientas. **Regla ⑦:** solo vive en el host (LAIA-ARCH) y
en el container `laia-agora` (LAIA-AGORA); NUNCA en containers de usuario. En dev está en
la raíz del repo. Gran parte está gitignored (se hace `git add -f` de lo necesario).

| Subcarpeta / archivo | Objetivo |
|---|---|
| `cli.py` | Monolito histórico del agente (loop de chat, herramientas, sesión). |
| `laia_cli/` | CLI modular (Phase 3): `main.py` (entrypoint), `oneshot.py`, `auth.py`, `cron.py`, `web_server.py`, `commands.py`, `config.py`, `banner.py`, `curator.py`… |
| `agent/` | Adaptadores de proveedores LLM (`anthropic_adapter`, `gemini_*`, `codex_*`, `bedrock_*`), motor de contexto (`context_engine`, `context_compressor`), pool de credenciales, seguridad de ficheros. |
| `tools/` | Implementación de las herramientas del agente: ficheros, bash, código, browser, cron (`cronjob_tools.py`), delegación, entornos, etc. |
| `cron/` | Sistema de tareas programadas: `jobs.py` (`get_job`, `create_job`, `parse_schedule`…), `scheduler.py`, `__init__.py`. **Recuperado de la VM (gitignored).** |
| `gateway/` `tui_gateway/` | Gateway multi-plataforma (mensajería) y su TUI. |
| `plugins/` | Plugins internos del motor. |
| `acp_adapter/` `acp_registry/` | Soporte ACP (Agent Client Protocol). |
| `skills/` `SOUL.md` `ai-agents.json` | Skills internas, persona por defecto e índice de agentes. **Recuperados de la VM.** |
| `run_agent.py` `toolsets.py` `model_tools.py` `atlas.py` | Loop de ejecución, definición de toolsets, selección de modelo, librería Atlas v2. |
| `tests/` | Tests del motor (`test_atlas`, `test_timezone`, `laia_cli/`, `tools/`…). |
| `pyproject.toml` | Empaquetado (`laia-agent`); declara los paquetes incluidos (incl. `cron`). |

---

## `services/` — Los dos microservicios del producto

### `services/agora-backend/` — El cerebro/API (LAIA-AGORA)

API REST multi-usuario que vive en el container `laia-agora`.

| Ruta | Objetivo |
|---|---|
| `app/main.py` | App FastAPI y rutas principales. |
| `app/admin.py` | Control Center: administración, deploy, auditoría. |
| `app/auth.py` | Autenticación JWT. |
| `app/chat_engine.py` | Motor de chat con el PA-AGORA. |
| `app/laia_chat.py` `app/coordinator.py` `app/laia_identity.py` | Modo coordinador "LAIA". |
| `app/agent_pool.py` | Pool de instancias de IA (una por sesión). |
| `app/agent_client.py` | Cliente HTTP hacia el executor (Tool Forwarder). |
| `app/marketplace*.py` | Marketplace de plugins y skills. |
| `app/database.py` `app/models.py` | Acceso a `agora.db` y modelos. |
| `app/auto_import/` | Importación automática de recursos. |
| `tests/` | Suite del backend. |
| `start.sh` `requirements.txt` | Arranque y dependencias. |

### `services/laia-executor/` — El ejecutor (despacho del usuario)

Microservicio que corre dentro del container del usuario y ejecuta las tool calls que le
envía el cerebro, como root y sin restricciones.

| Ruta | Objetivo |
|---|---|
| `src/` | Código del executor: config, herramientas (`tools/`), workspace privado. |
| `systemd/` | Unit para arrancarlo como servicio en el container. |
| `pyproject.toml` | Empaquetado. |
| `tests/` | Suite del executor. |

---

## `infra/` — Infraestructura del host

| Subcarpeta | Objetivo |
|---|---|
| `installer/lib/` | Librerías del instalador/clonador: `clone.sh`, `bootstrap.sh`, `shell_rc.sh`, `factory.sh`, `sudo.sh`, `common.sh`, `rewrite_config_paths.py`… |
| `installer/systemd/` | Units systemd que instala el producto. |
| `lxd/` | Gestión de contenedores: `image-build/` (construcción de imágenes), `profiles/` (perfiles LXD), `scripts/` (rebuild/create/provision). |
| `orchestrator/` | Orquestador Python de containers: `lxd.py`, `config.py`, `state.py`, `cli.py`. |
| `pathd/` | Daemon de resolución de paths (`server.py`, `cli.py`, `notifier.py`, `watcher.py`) + `atlas.yaml.example`. |
| `nginx/` | Configs de proxy inverso. |
| `dev/` | Herramientas de desarrollo (marketplace, seed de skills…). |
| `bin/` `scripts/` `laiactl` | Binarios y scripts auxiliares de infra. |
| `PORTS.md` `README.md` `docs/` | Documentación de infra (puertos, etc.). |

---

## `skills/` — Catálogo de skills

Capacidades empaquetadas que el agente puede cargar. Organizadas por dominio:
`devops/`, `data-science/`, `documentation/`, `github/`, `email/`, `media/`, `mcp/`,
`note-taking/`, `creative/`, `gaming/`, `domain/`, `autonomous-ai-agents/`… Más
`.hub/` (caché del hub), `.bundled_manifest` y `README.md`.

## `plugins/` — Plugins del ecosistema

Plugins instalables. Ver `README.md` para el contrato de plugin.

## `workspace_store/` — Librería de workspaces

`__init__.py`: librería compartida (SQLite + FTS5) que usan backend, executor y LAIA-ARCH
para leer/escribir/buscar en workspaces.

## `laia-ui/` — Interfaz web

UI de LAIA-AGORA. En **reconstrucción** (la v1 se archivó; ver roadmap en la visión).

---

## `scripts/` — Utilidades operacionales del host

Scripts de LAIA-ARCH para operar el host: `ai-orchestrator.py`, `health-check.py`,
`create-workspace.py` / `delete-workspace.py`, `git-manager*.py`, `cleanup-sessions.py`,
`startup-report.py`, `nightly-shutdown.py`, `_doc_context_engine.py`,
`_laia_runtime_paths.py` (puente a Atlas), `datasette-start.sh`… `INDEX.md` los indexa.

## `tests/` — Suites de integración y e2e (raíz)

Pruebas a nivel de producto: `test_atlas.py`, `test_clone_config_rewrite.py`,
`test_marketplace_cli.sh`, `test_laia_init*.sh`, `test_preflight.sh`,
`test_rebuild*.sh`, `test_seed_base_skills.sh`, más `installer/` (incl.
`test_shell_rc.sh`), `e2e/` y `wizard/`.

## `workflow/` — Documentación operativa y bitácoras

| Archivo | Objetivo |
|---|---|
| `00-start-here.md` | Reglas operativas — el primer sitio al que ir. |
| `01-canonical-sources.md` | Qué fuente gana en cada conflicto. |
| `02-how-to-work.md` `03-multi-ai-coordination.md` | Cómo trabajar y coordinarse entre IAs. |
| `changelog.md` | Bitácora de cambios materiales (se actualiza al cierre de turno). |
| `problems.md` | Bugs descubiertos (se anotan al descubrirlos). |
| `security.md` | Hallazgos y acciones de seguridad. |
| `arch-layout.md` | Layout en disco y contrato `laia-clone` (doc técnico). |
| `project-map.md` | **Este documento** — mapa del repo. |
| `release-flow.md` `arch-data-layout.md` | Flujo de release y layout de datos ARCH. |
| `plans/` | Planes de trabajo por fechas (incl. los de Atlas v2). |
| `evidence/` | Evidencias de verificación. |

## `docs/` · `examples/` · `archived/`

`docs/` documentación y diagramas (`map.drawio`, `map.svg`, `db-export/`); `examples/`
ejemplos de uso; `archived/` material retirado pero conservado.
