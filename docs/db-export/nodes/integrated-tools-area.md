# Integrated Tools

## Metadata

- ID: `121`
- Slug: `integrated-tools-area`
- Kind: `topic`
- Status: `active`
- Filename: `integrated-tools-area.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:49:12.340507+00:00`
- Updated at: `2026-05-08T09:03:49.550066+00:00`
- Aliases: `integrated-tools-area`

## Summary

OpenClaw, UsageAI, Workspace Skills y otras herramientas

## Body

# Integrated Tools

## Descripción

Herramientas integradas en el ecosistema Hermes que extienden las capacidades del agente.

## Herramientas principales

### OpenClaw Gateway
Gateway de Telegram con plugins y slash commands.
- Integración con Telegram
- Sistema de plugins
- Slash commands personalizados
- Configuración flexible

### UsageAI
Skill de reporting de consumo para Codex y Claude Code.
- Monitoreo de uso de modelos
- Estado de consumo
- Reportes periódicos
- Optimización de costes

### Workspace Skills
Skills para gestión de workspaces DB-first.
- **workspace-read**: Lectura y búsqueda en workspaces
- **workspace-write**: Escritura y estructura de workspaces
- Coordinación multi-agente
- Flujos de trabajo diarios

## Documentos incluidos

- **integrated-tools**: Visión general de herramientas integradas
- **integrated-openclaw**: OpenClaw Gateway (Telegram)
- **integrated-usageai**: UsageAI reporting
- **integrated-workspace-tools**: Workspace Skills (read/write)

## Estado actual

- OpenClaw: ACTIVO
- UsageAI: ACTIVO
- Workspace Skills: ACTIVO
- Código: ~/LAIA/.laia-arch/plugins/

## Uso típico

```bash
# Usar OpenClaw
hermes telegram

# Ver uso de modelos
hermes usage

# Trabajar con workspaces
workspace_search_nodes(query)
workspace_get_node(ref)
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- `contains` → `integrated-tools` (Integrated Tools — Overview) [peso=1.00]
- `contains` → `integrated-openclaw` (OpenClaw Gateway) [peso=1.00]
- `contains` → `integrated-usageai` (UsageAI Reporting) [peso=1.00]
- `contains` → `integrated-workspace-tools` (Workspace Skills) [peso=1.00]

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Integrated Tools

# Integrated Tools

## Descripción

Herramientas integradas en el ecosistema Hermes que extienden las capacidades del agente.

## Herramientas principales

### OpenClaw Gateway
Gateway de Telegram con plugins y slash commands.
- Integración con Telegram
- Sistema de plugins
- Slash commands personalizados
- Configuración flexible

### UsageAI
Skill de reporting de consumo para Codex y Claude Code.
- Monitoreo de uso de modelos
- Estado de consumo
- Reportes periódicos
- Optimización de costes

### Workspace Skills
Skills para gestión de workspaces DB-first.
- **workspace-read**: Lectura y búsqueda en workspaces
- **workspace-write**: Escritura y estructura de workspaces
- Coordinación multi-agente
- Flujos de trabajo diarios

## Documentos incluidos

- **integrated-tools**: Visión general de herramientas integradas
- **integrated-openclaw**: OpenClaw Gateway (Telegram)
- **integrated-usageai**: UsageAI reporting
- **integrated-workspace-tools**: Workspace Skills (read/write)

## Estado actual

- OpenClaw: ACTIVO
- UsageAI: ACTIVO
- Workspace Skills: ACTIVO
- Código: ~/LAIA/.laia-arch/plugins/

## Uso típico

```bash
# Usar OpenClaw
hermes telegram

# Ver uso de modelos
hermes usage

# Trabajar con workspaces
workspace_search_nodes(query)
workspace_get_node(ref)
```


> 📅 Documentado: 2026-05-08

→ Integrated Tools — Overview: `integrated-tools.md`
→ OpenClaw Gateway: `integrated-openclaw.md`
→ UsageAI Reporting: `integrated-usageai.md`
→ Workspace Skills: `integrated-workspace-tools.md`
