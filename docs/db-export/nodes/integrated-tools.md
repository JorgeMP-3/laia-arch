# Integrated Tools — Overview

## Metadata

- ID: `91`
- Slug: `integrated-tools`
- Kind: `doc`
- Status: `active`
- Filename: `integrated-tools.md`
- Parent: `integrated-tools-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:00.815695+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `integrated-tools`

## Summary

Este nodo es el indice maestro de todas las herramientas integradas en Hermes. Consulta los nodos hi

## Body

# Integrated Tools — Herramientas Integradas

# Integrated Tools — Herramientas Integradas

## Resumen

Este nodo es el indice maestro de todas las herramientas integradas en Hermes. Consulta los nodos hijos para cada categoria:

| Nodo hijo | Contenido |
|---|---|
| `integrated-workspace-tools` | Skills workspace-read y workspace-write |
| `integrated-openclaw` | OpenClaw gateway y migracion |
| `integrated-usageai` | UsageAI: reporting Codex/Claude Code |

## Categorias de herramientas integradas

### Skills (~/.laia/skills/)

| Skill | Ruta | Descripcion |
|---|---|---|
| `workspace-read` | `skills/workspace/workspace-read/` | Solo lectura DB-first |
| `workspace-write` | `skills/workspace/workspace-write/` | Escritura DB + code/ |
| `agent-coordination` | `skills/workspace/agent-coordination/` | Coordinacion multi-agente |
| `dogfood` | `skills/dogfood/` | QA testing sistemico de web apps |
| `usageai` | `skills/devops/usageai/` | Reporting de consumo AI |
| `apple-notes` | `skills/apple/apple-notes/` | Apple Notes via memo CLI |
| `apple-reminders` | `skills/apple/apple-reminders/` | Apple Reminders via remindctl |
| `findmy` | `skills/apple/findmy/` | FindMy app via AppleScript |
| `imessage` | `skills/apple/imessage/` | iMessage via imsg CLI |
| `workhard` | `skills/openclaw-imports/workhard/` | Trabajos largos por fases |

## Gateway (OpenClaw)

El gateway de Hermes procesa mensajes de multiples plataformas:

| Plataforma | Archivo | Tamanio |
|---|---|---|
| Telegram | `gateway/platforms/telegram.py` | ~132KB |
| Discord | `gateway/platforms/discord.py` | ~162KB |
| Slack | `gateway/platforms/slack.py` | ~69KB |
| WhatsApp | `gateway/platforms/whatsapp.py` | ~41KB |
| Signal | `gateway/platforms/signal.py` | ~38KB |
| WeChat/Weixin | `gateway/platforms/weixin.py` | ~77KB |
| Feishu | `gateway/platforms/feishu.py` | ~182KB |
| Wecom | `gateway/platforms/wecom.py` | ~59KB |
| Dingtalk | `gateway/platforms/dingtalk.py` | ~55KB |
| Matrix | `gateway/platforms/matrix.py` | ~85KB |
| Mattermost | `gateway/platforms/mattermost.py` | ~27KB |
| Email | `gateway/platforms/email.py` | ~23KB |
| SMS | `gateway/platforms/sms.py` | ~14KB |
| HomeAssistant | `gateway/platforms/homeassistant.py` | ~16KB |
| Webhook | `gateway/platforms/webhook.py` | ~30KB |

## Skills Apple (macOS only)

Estas skills solo cargan en sistemas macOS:

| Skill | Herramienta CLI | Funcionalidad |
|---|---|---|
| `apple-notes` | `memo` | CRUD de Apple Notes |
| `apple-reminders` | `remindctl` | Tareas en Apple Reminders |
| `findmy` | AppleScript + screencapture | Localizacion de dispositivos/AirTags |
| `imessage` | `imsg` | Enviar/recibir iMessages |

### Instalacion de herramientas Apple

```bash
# Notes
brew tap antoniorodr/memo && brew install antoniorodr/memo/memo

# Reminders
brew install steipete/tap/remindctl

# iMessage
brew install steipete/tap/imsg

# FindMy (opcional, mejor UI automation)
brew install steipete/tap/peekaboo
```

## Dogfood QA Skill

Skill de testing sistemico de aplicaciones web. Ubicacion: `skills/dogfood/SKILL.md`

### Herramientas usadas
- `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`
- `browser_scroll`, `browser_back`, `browser_press`, `browser_vision`, `browser_console`

### Flujo de 5 fases
1. **Plan** — crear estructura de directorios, sitemap
2. **Explore** — navegar, snapshot, console, vision annotate
3. **Collect Evidence** — screenshots + detalles del bug
4. **Categorize** — deduplicar, severidad, categoria
5. **Report** — plantilla en `templates/dogfood-report-template.md`

## Workhard (OpenClaw imports)

Trabajos largos con fases, TODO.md como contrato, checkpoints git. Ubicacion: `skills/openclaw-imports/workhard/SKILL.md`

```bash
/workhard [objetivo]     # modo normal
/workhard super [obj]    # modo super (investigacion + cuestionario)
/workhard resume        # reanudar sesion
/workhard status        # ver estado
/workhard abort         # abortar
/workhard log           # ver log
```

## OpenClaw Migration

Hermes incluye comandos de migracion desde OpenClaw:

```bash
hermes claw migrate              # Preview y migrate
hermes claw migrate --dry-run    # Solo preview
hermes claw migrate --yes       # Skip confirmacion
hermes claw cleanup             # Archivar leftovers de OpenClaw
```

Script: `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`

## Nodos relacionados

- `hermes-core-tools` — catalogo completo de herramientas core de Hermes
- `hermes-core-plugins` — sistema de plugins
- `agent-team` — equipo de agentes
- `agent-log` — log de actividad de agentes

→ Apple Skills: `apple-skills.md`
→ Dogfood QA Skill: `dogfood-skill.md`
→ Integrated Tools — OpenClaw Gateway: `integrated-openclaw.md`
→ Integrated Tools — UsageAI: `integrated-usageai.md`
→ Integrated Tools — Workspace Skills: `integrated-workspace-tools.md`
→ Workhard Skill: `workhard-skill.md`


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `integrated-tools-area` (Integrated Tools) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Integrated Tools — Overview

# Integrated Tools — Herramientas Integradas

# Integrated Tools — Herramientas Integradas

## Resumen

Este nodo es el indice maestro de todas las herramientas integradas en Hermes. Consulta los nodos hijos para cada categoria:

| Nodo hijo | Contenido |
|---|---|
| `integrated-workspace-tools` | Skills workspace-read y workspace-write |
| `integrated-openclaw` | OpenClaw gateway y migracion |
| `integrated-usageai` | UsageAI: reporting Codex/Claude Code |

## Categorias de herramientas integradas

### Skills (~/.laia/skills/)

| Skill | Ruta | Descripcion |
|---|---|---|
| `workspace-read` | `skills/workspace/workspace-read/` | Solo lectura DB-first |
| `workspace-write` | `skills/workspace/workspace-write/` | Escritura DB + code/ |
| `agent-coordination` | `skills/workspace/agent-coordination/` | Coordinacion multi-agente |
| `dogfood` | `skills/dogfood/` | QA testing sistemico de web apps |
| `usageai` | `skills/devops/usageai/` | Reporting de consumo AI |
| `apple-notes` | `skills/apple/apple-notes/` | Apple Notes via memo CLI |
| `apple-reminders` | `skills/apple/apple-reminders/` | Apple Reminders via remindctl |
| `findmy` | `skills/apple/findmy/` | FindMy app via AppleScript |
| `imessage` | `skills/apple/imessage/` | iMessage via imsg CLI |
| `workhard` | `skills/openclaw-imports/workhard/` | Trabajos largos por fases |

## Gateway (OpenClaw)

El gateway de Hermes procesa mensajes de multiples plataformas:

| Plataforma | Archivo | Tamanio |
|---|---|---|
| Telegram | `gateway/platforms/telegram.py` | ~132KB |
| Discord | `gateway/platforms/discord.py` | ~162KB |
| Slack | `gateway/platforms/slack.py` | ~69KB |
| WhatsApp | `gateway/platforms/whatsapp.py` | ~41KB |
| Signal | `gateway/platforms/signal.py` | ~38KB |
| WeChat/Weixin | `gateway/platforms/weixin.py` | ~77KB |
| Feishu | `gateway/platforms/feishu.py` | ~182KB |
| Wecom | `gateway/platforms/wecom.py` | ~59KB |
| Dingtalk | `gateway/platforms/dingtalk.py` | ~55KB |
| Matrix | `gateway/platforms/matrix.py` | ~85KB |
| Mattermost | `gateway/platforms/mattermost.py` | ~27KB |
| Email | `gateway/platforms/email.py` | ~23KB |
| SMS | `gateway/platforms/sms.py` | ~14KB |
| HomeAssistant | `gateway/platforms/homeassistant.py` | ~16KB |
| Webhook | `gateway/platforms/webhook.py` | ~30KB |

## Skills Apple (macOS only)

Estas skills solo cargan en sistemas macOS:

| Skill | Herramienta CLI | Funcionalidad |
|---|---|---|
| `apple-notes` | `memo` | CRUD de Apple Notes |
| `apple-reminders` | `remindctl` | Tareas en Apple Reminders |
| `findmy` | AppleScript + screencapture | Localizacion de dispositivos/AirTags |
| `imessage` | `imsg` | Enviar/recibir iMessages |

### Instalacion de herramientas Apple

```bash
# Notes
brew tap antoniorodr/memo && brew install antoniorodr/memo/memo

# Reminders
brew install steipete/tap/remindctl

# iMessage
brew install steipete/tap/imsg

# FindMy (opcional, mejor UI automation)
brew install steipete/tap/peekaboo
```

## Dogfood QA Skill

Skill de testing sistemico de aplicaciones web. Ubicacion: `skills/dogfood/SKILL.md`

### Herramientas usadas
- `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`
- `browser_scroll`, `browser_back`, `browser_press`, `browser_vision`, `browser_console`

### Flujo de 5 fases
1. **Plan** — crear estructura de directorios, sitemap
2. **Explore** — navegar, snapshot, console, vision annotate
3. **Collect Evidence** — screenshots + detalles del bug
4. **Categorize** — deduplicar, severidad, categoria
5. **Report** — plantilla en `templates/dogfood-report-template.md`

## Workhard (OpenClaw imports)

Trabajos largos con fases, TODO.md como contrato, checkpoints git. Ubicacion: `skills/openclaw-imports/workhard/SKILL.md`

```bash
/workhard [objetivo]     # modo normal
/workhard super [obj]    # modo super (investigacion + cuestionario)
/workhard resume        # reanudar sesion
/workhard status        # ver estado
/workhard abort         # abortar
/workhard log           # ver log
```

## OpenClaw Migration

Hermes incluye comandos de migracion desde OpenClaw:

```bash
hermes claw migrate              # Preview y migrate
hermes claw migrate --dry-run    # Solo preview
hermes claw migrate --yes       # Skip confirmacion
hermes claw cleanup             # Archivar leftovers de OpenClaw
```

Script: `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`

## Nodos relacionados

- `hermes-core-tools` — catalogo completo de herramientas core de Hermes
- `hermes-core-plugins` — sistema de plugins
- `agent-team` — equipo de agentes
- `agent-log` — log de actividad de agentes

→ Apple Skills: `apple-skills.md`
→ Dogfood QA Skill: `dogfood-skill.md`
→ Integrated Tools — OpenClaw Gateway: `integrated-openclaw.md`
→ Integrated Tools — UsageAI: `integrated-usageai.md`
→ Integrated Tools — Workspace Skills: `integrated-workspace-tools.md`
→ Workhard Skill: `workhard-skill.md`


> 📅 Documentado: 2026-05-08
