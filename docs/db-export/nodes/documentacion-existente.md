# Documentación existente del sistema

## Metadata

- ID: `69`
- Slug: `documentacion-existente`
- Kind: `doc`
- Status: `active`
- Filename: `documentacion-existente.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T08:18:36.123256+00:00`
- Updated at: `2026-05-19T11:13:52.675564`
- Aliases: `documentacion-existente`

## Summary

Inventario de toda la documentación disponible en docs/docs y laia_arch/context

## Body

# Documentación existente del sistema

## Ubicaciones de documentación

### 1. ~/LAIA/docs/docs/ (Documentación del servidor)
Documentación técnica del servidor Dell OptiPlex 9020.

| Archivo | Contenido |
|---|---|
| arquitectura.md | Diagrama y visión general del stack |
| servicios.md | Todos los servicios, puertos y comandos de gestión |
| nginx.md | Configuración del reverse proxy |
| cloudflare.md | Tunnel y dominios |
| laia-arch.md | Hermes, workspace-ui y estructura git |
| docker.md | WordPress y contenedores |
| arranque.md | Cómo arranca todo al encender el servidor |
| mantenimiento.md | Guía de operaciones del día a día |
| samba.md | Acceso desde Mac por SMB (Finder) |
| migracion-familiamp.md | Registro de migración de usuario |
| command-center.md | Command Center: orquestación multi-agente |
| tool-context-injection.md | ToolContextInjector: guía técnica |
| tool-ui-architecture.md | Arquitectura UI profesional |

### 2. ~/LAIA/docs/context-engine/ (Documentación Context Engine)
Documentación del sistema de memoria DB-first.

| Archivo | Contenido |
|---|---|
| 00-index.md | Índice general |
| 01-workspace-store.md | WorkspaceStore: schema SQLite, API Python, FTS5 |
| 02-plugin.md | Plugin: 20 tools, prefetch, inject modes |
| 03-web-ui.md | Workspace UI: FastAPI + React, tema amber |
| 04-migration.md | Migración legacy a DB, backups, exports |
| 05-scripts.md | Scripts: create, health-check, show-injected, sync |

### 3. ~/LAIA/workspaces/laia_arch/context/ (41 archivos)
Documentación completa del workspace laia_arch.

**Hermes Core:**
- hermes-core-agent.md
- hermes-core-architecture.md
- hermes-core-commands.md
- hermes-core-memory.md
- hermes-core-multi-agent.md
- hermes-core-plugins.md
- hermes-core-tools.md
- hermes-core-vision.md
- hermes-core-voice.md
- hermes-core.md

**Workspace UI:**
- workspace-ui-backend.md
- workspace-ui-frontend.md
- workspace-ui-overview.md
- workspace-ui.md

**Context Engine:**
- context-engine-docs-01-workspace-store.md
- context-engine-docs-02-plugin.md
- context-engine-docs-03-web-ui.md
- context-engine-docs-04-migration.md
- context-engine.md

**Herramientas integradas:**
- integrated-openclaw.md
- integrated-tools.md
- integrated-usageai.md
- integrated-workspace-tools.md

**Skills:**
- apple-skills.md
- dogfood-skill.md
- workhard-skill.md

**Agentes:**
- agent-behavior.md
- agent-log.md
- agent-team.md
- hermes-master-plan.md

### 4. ~/LAIA/docs/problemas-command-center/
- README.md — Problemas conocidos del Command Center

## Próximos pasos

1. Leer toda la documentación existente
2. Clasificar por proyecto (AGORA, ARCH, HERMES)
3. Crear nodos en laia-ecosystem
4. Establecer relaciones


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Documentación existente del sistema

# Documentación existente del sistema

## Ubicaciones de documentación

### 1. ~/LAIA/docs/docs/ (Documentación del servidor)
Documentación técnica del servidor Dell OptiPlex 9020.

| Archivo | Contenido |
|---|---|
| arquitectura.md | Diagrama y visión general del stack |
| servicios.md | Todos los servicios, puertos y comandos de gestión |
| nginx.md | Configuración del reverse proxy |
| cloudflare.md | Tunnel y dominios |
| laia-arch.md | Hermes, workspace-ui y estructura git |
| docker.md | WordPress y contenedores |
| arranque.md | Cómo arranca todo al encender el servidor |
| mantenimiento.md | Guía de operaciones del día a día |
| samba.md | Acceso desde Mac por SMB (Finder) |
| migracion-familiamp.md | Registro de migración de usuario |
| command-center.md | Command Center: orquestación multi-agente |
| tool-context-injection.md | ToolContextInjector: guía técnica |
| tool-ui-architecture.md | Arquitectura UI profesional |

### 2. ~/LAIA/docs/context-engine/ (Documentación Context Engine)
Documentación del sistema de memoria DB-first.

| Archivo | Contenido |
|---|---|
| 00-index.md | Índice general |
| 01-workspace-store.md | WorkspaceStore: schema SQLite, API Python, FTS5 |
| 02-plugin.md | Plugin: 20 tools, prefetch, inject modes |
| 03-web-ui.md | Workspace UI: FastAPI + React, tema amber |
| 04-migration.md | Migración legacy a DB, backups, exports |
| 05-scripts.md | Scripts: create, health-check, show-injected, sync |

### 3. ~/LAIA/workspaces/laia_arch/context/ (41 archivos)
Documentación completa del workspace laia_arch.

**Hermes Core:**
- hermes-core-agent.md
- hermes-core-architecture.md
- hermes-core-commands.md
- hermes-core-memory.md
- hermes-core-multi-agent.md
- hermes-core-plugins.md
- hermes-core-tools.md
- hermes-core-vision.md
- hermes-core-voice.md
- hermes-core.md

**Workspace UI:**
- workspace-ui-backend.md
- workspace-ui-frontend.md
- workspace-ui-overview.md
- workspace-ui.md

**Context Engine:**
- context-engine-docs-01-workspace-store.md
- context-engine-docs-02-plugin.md
- context-engine-docs-03-web-ui.md
- context-engine-docs-04-migration.md
- context-engine.md

**Herramientas integradas:**
- integrated-openclaw.md
- integrated-tools.md
- integrated-usageai.md
- integrated-workspace-tools.md

**Skills:**
- apple-skills.md
- dogfood-skill.md
- workhard-skill.md

**Agentes:**
- agent-behavior.md
- agent-log.md
- agent-team.md
- hermes-master-plan.md

### 4. ~/LAIA/docs/problemas-command-center/
- README.md — Problemas conocidos del Command Center

## Próximos pasos

1. Leer toda la documentación existente
2. Clasificar por proyecto (AGORA, ARCH, HERMES)
3. Crear nodos en laia-ecosystem
4. Establecer relaciones


> 📅 Documentado: 2026-05-08
