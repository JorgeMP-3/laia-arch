# OpenClaw Gateway

## Metadata

- ID: `92`
- Slug: `integrated-openclaw`
- Kind: `doc`
- Status: `active`
- Filename: `integrated-openclaw.md`
- Parent: `integrated-tools-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:01.147514+00:00`
- Updated at: `2026-05-08T08:34:01.147514+00:00`
- Aliases: `integrated-openclaw`

## Summary

OpenClaw es el gateway de mensajeria de Hermes. Procesa mensajes de multiples plataformas (Telegram,

## Body

# Integrated Tools — OpenClaw Gateway

# Integrated Tools — OpenClaw Gateway

## Que es OpenClaw

OpenClaw es el gateway de mensajeria de Hermes. Procesa mensajes de multiples plataformas (Telegram, Discord, Slack, WhatsApp, etc.) y los normaliza en un formato comun para que el agente Hermes los procese de forma unificada.

## Arquitectura

```
Plataforma (Telegram/Discord/etc.)
    │
    ▼
gateway/platforms/{platform}.py   # Adaptador especifico
    │
    ▼
gateway/run.py                    # Loop principal + slash commands
    │
    ▼
gateway/session.py                # SessionStore (persistencia)
    │
    ▼
hermes_agent (run_agent.py)       # Agente IA
```

## Plataformas soportadas

| Plataforma | Tamanio | Notas |
|---|---|---|
| Telegram | ~132KB | Principal, mas desarrollada |
| Discord | ~162KB | Guilds, roles, canales |
| Slack | ~69KB | Workspaces, canales |
| WhatsApp | ~41KB | Audio, video, imagenes |
| Signal | ~38KB | E2E encryption |
| Weixin/WeChat | ~77KB | Mini programs |
| Feishu/Lark | ~182KB | Apps, comments |
| Wecom | ~59KB | Enterprise WeChat |
| Dingtalk | ~55KB | Alibaba enterprise |
| Matrix | ~85KB | Protocolo abierto |
| Mattermost | ~27KB | Self-hosted |
| Email | ~23KB | IMAP/SMTP |
| SMS | ~14KB | Twilio compatible |
| HomeAssistant | ~16KB | Smart home events |
| Webhook | ~30KB | HTTP callbacks |
| BlueBubbles | ~33KB | iMessage en Mac |

## Ficheros clave del gateway

| Archivo | Proposito |
|---|---|
| `gateway/run.py` | Loop principal, 508KB — dispatch de mensajes, slash commands |
| `gateway/session.py` | SessionStore — persistencia de conversaciones |
| `gateway/config.py` | Configuracion de plataformas (58KB) |
| `gateway/stream_consumer.py` | Consumo de streams (messages, edits, deletions) |
| `gateway/status.py` | Gestion de status/presence |
| `gateway/channel_directory.py` | Directorio de canales activos |
| `gateway/hooks.py` | Sistema de hooks |
| `gateway/delivery.py` | Entrega de mensajes |
| `gateway/display_config.py` | Configuracion visual por canal |
| `gateway/pairing.py` | Emparejamiento de dispositivos |
| `gateway/mirror.py` | Modo mirror |
| `gateway/platforms/base.py` | BaseAdapter — interfaz comun |

## Slash commands del gateway

Los slash commands se registran via `COMMAND_REGISTRY` en `hermes_cli/commands.py`:

```
/help              — ayuda general
/model             — cambiar modelo
/skills            — gestionar skills
/tools             — gestionar tools
/agents            — agentes externos
/usageai           — reporting de consumo
/status            — estado del sistema
/tg                — comandos Telegram especificos
```

## Migracion desde OpenClaw

Hermes incluye un script de migracion para mover workspaces de OpenClaw a Hermes:

```bash
# Preview
hermes claw migrate --dry-run

# Migrar
hermes claw migrate

# Full con overwrite
hermes claw migrate --preset full --overwrite

# Cleanup de leftovers
hermes claw cleanup
```

Script: `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`

## Anadir una nueva plataforma

Ver `gateway/platforms/ADDING_A_PLATFORM.md` para guias detalladas.

Pasos generales:
1. Crear `gateway/platforms/{platform}.py` heredando de `BaseAdapter`
2. Implementar `send_message()`, `edit_message()`, `delete_message()`, `upload_file()`
3. Implementar `register_webhook()` si usa webhook
4. Anadir a `PLATFORM_ADAPTERS` en `base.py`
5. Configurar credenciales en `config.yaml`

## Hooks del gateway

Sistema de hooks en `gateway/builtin_hooks/`:

| Hook | Cuando |
|---|---|
| `on_message` | Cada mensaje recibido |
| `on_edit` | Mensaje editado |
| `on_delete` | Mensaje eliminado |
| `on_command` | Slash command ejecutado |
| `on_delivery` | Mensaje entregado |
| `on_error` | Error de plataforma |

## Skills de OpenClaw imports

Ubicadas en `skills/openclaw-imports/`:

### Workhard

Trabajos largos y estructurados con fases. Ver `skills/openclaw-imports/workhard/SKILL.md`

```bash
/workhard [objetivo]     # modo normal
/workhard super [obj]    # investigacion + cuestionario
/workhard resume         # reanudar
/workhard status         # ver estado
/workhard abort          # abortar
```

### Estructura de archivos workhard

```
workspace/workhard/WORK/[proyecto]/
├── CONTEXTO.md
├── TODO.md               # contrato de pasos
├── LOG.md                # historial de ejecucion
├── NOTES.md
├── SESSION.md            # fuente de verdad para reanudar
├── INVESTIGATION.md      # modo super
└── QUESTIONNAIRE.md     # modo super
```

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-usageai` — reporting de consumo
- `hermes-core-tools` — catalogo de herramientas core
- `hermes-core-plugins` — sistema de plugins


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `integrated-tools-area` (Integrated Tools) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# OpenClaw Gateway

# Integrated Tools — OpenClaw Gateway

# Integrated Tools — OpenClaw Gateway

## Que es OpenClaw

OpenClaw es el gateway de mensajeria de Hermes. Procesa mensajes de multiples plataformas (Telegram, Discord, Slack, WhatsApp, etc.) y los normaliza en un formato comun para que el agente Hermes los procese de forma unificada.

## Arquitectura

```
Plataforma (Telegram/Discord/etc.)
    │
    ▼
gateway/platforms/{platform}.py   # Adaptador especifico
    │
    ▼
gateway/run.py                    # Loop principal + slash commands
    │
    ▼
gateway/session.py                # SessionStore (persistencia)
    │
    ▼
hermes_agent (run_agent.py)       # Agente IA
```

## Plataformas soportadas

| Plataforma | Tamanio | Notas |
|---|---|---|
| Telegram | ~132KB | Principal, mas desarrollada |
| Discord | ~162KB | Guilds, roles, canales |
| Slack | ~69KB | Workspaces, canales |
| WhatsApp | ~41KB | Audio, video, imagenes |
| Signal | ~38KB | E2E encryption |
| Weixin/WeChat | ~77KB | Mini programs |
| Feishu/Lark | ~182KB | Apps, comments |
| Wecom | ~59KB | Enterprise WeChat |
| Dingtalk | ~55KB | Alibaba enterprise |
| Matrix | ~85KB | Protocolo abierto |
| Mattermost | ~27KB | Self-hosted |
| Email | ~23KB | IMAP/SMTP |
| SMS | ~14KB | Twilio compatible |
| HomeAssistant | ~16KB | Smart home events |
| Webhook | ~30KB | HTTP callbacks |
| BlueBubbles | ~33KB | iMessage en Mac |

## Ficheros clave del gateway

| Archivo | Proposito |
|---|---|
| `gateway/run.py` | Loop principal, 508KB — dispatch de mensajes, slash commands |
| `gateway/session.py` | SessionStore — persistencia de conversaciones |
| `gateway/config.py` | Configuracion de plataformas (58KB) |
| `gateway/stream_consumer.py` | Consumo de streams (messages, edits, deletions) |
| `gateway/status.py` | Gestion de status/presence |
| `gateway/channel_directory.py` | Directorio de canales activos |
| `gateway/hooks.py` | Sistema de hooks |
| `gateway/delivery.py` | Entrega de mensajes |
| `gateway/display_config.py` | Configuracion visual por canal |
| `gateway/pairing.py` | Emparejamiento de dispositivos |
| `gateway/mirror.py` | Modo mirror |
| `gateway/platforms/base.py` | BaseAdapter — interfaz comun |

## Slash commands del gateway

Los slash commands se registran via `COMMAND_REGISTRY` en `hermes_cli/commands.py`:

```
/help              — ayuda general
/model             — cambiar modelo
/skills            — gestionar skills
/tools             — gestionar tools
/agents            — agentes externos
/usageai           — reporting de consumo
/status            — estado del sistema
/tg                — comandos Telegram especificos
```

## Migracion desde OpenClaw

Hermes incluye un script de migracion para mover workspaces de OpenClaw a Hermes:

```bash
# Preview
hermes claw migrate --dry-run

# Migrar
hermes claw migrate

# Full con overwrite
hermes claw migrate --preset full --overwrite

# Cleanup de leftovers
hermes claw cleanup
```

Script: `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`

## Anadir una nueva plataforma

Ver `gateway/platforms/ADDING_A_PLATFORM.md` para guias detalladas.

Pasos generales:
1. Crear `gateway/platforms/{platform}.py` heredando de `BaseAdapter`
2. Implementar `send_message()`, `edit_message()`, `delete_message()`, `upload_file()`
3. Implementar `register_webhook()` si usa webhook
4. Anadir a `PLATFORM_ADAPTERS` en `base.py`
5. Configurar credenciales en `config.yaml`

## Hooks del gateway

Sistema de hooks en `gateway/builtin_hooks/`:

| Hook | Cuando |
|---|---|
| `on_message` | Cada mensaje recibido |
| `on_edit` | Mensaje editado |
| `on_delete` | Mensaje eliminado |
| `on_command` | Slash command ejecutado |
| `on_delivery` | Mensaje entregado |
| `on_error` | Error de plataforma |

## Skills de OpenClaw imports

Ubicadas en `skills/openclaw-imports/`:

### Workhard

Trabajos largos y estructurados con fases. Ver `skills/openclaw-imports/workhard/SKILL.md`

```bash
/workhard [objetivo]     # modo normal
/workhard super [obj]    # investigacion + cuestionario
/workhard resume         # reanudar
/workhard status         # ver estado
/workhard abort          # abortar
```

### Estructura de archivos workhard

```
workspace/workhard/WORK/[proyecto]/
├── CONTEXTO.md
├── TODO.md               # contrato de pasos
├── LOG.md                # historial de ejecucion
├── NOTES.md
├── SESSION.md            # fuente de verdad para reanudar
├── INVESTIGATION.md      # modo super
└── QUESTIONNAIRE.md     # modo super
```

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-usageai` — reporting de consumo
- `hermes-core-tools` — catalogo de herramientas core
- `hermes-core-plugins` — sistema de plugins
