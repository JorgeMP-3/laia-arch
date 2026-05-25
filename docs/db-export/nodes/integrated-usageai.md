# UsageAI Reporting

## Metadata

- ID: `93`
- Slug: `integrated-usageai`
- Kind: `doc`
- Status: `active`
- Filename: `integrated-usageai.md`
- Parent: `integrated-tools-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:01.456228+00:00`
- Updated at: `2026-05-08T08:34:01.456228+00:00`
- Aliases: `integrated-usageai`

## Summary

UsageAI es un skill de reporting de consumo de sistemas AI: Codex y Claude Code. Muestra estado de a

## Body

# Integrated Tools — UsageAI

# Integrated Tools — UsageAI

## Resumen

UsageAI es un skill de reporting de consumo de sistemas AI: Codex y Claude Code. Muestra estado de autenticacion, usage summaries, y metricas del gateway OpenClaw.

**Trigger:** `/usageai` o cualquier variante (`usageai`, `usage ai`, `codex usage`, `claude usage`)

## Comando

```bash
~/.local/bin/usageai
```

Este comando es la unica interfaz de uso. No hace llamadas directas a APIs de providers.

## Que muestra

| Seccion | Contenido |
|---|---|
| Codex usage | Resumen de uso de Codex/OpenAI |
| Claude Code (Jorge) | Auth status en el host |
| Claude Code (Maribel) | Auth status en Docker |
| OpenClaw gateway | Usage del gateway si RPC disponible |
| Nota de no disponibilidad | Cuando no se puede obtener detalle |

## Cuentas monitoreadas

| Cuenta | Entorno | Notas |
|---|---|---|
| Jorge | Host (macOS) | Cuenta principal |
| Maribel | Docker container | Compartida, usar con cuidado |

## Reglas de interpretacion

### Lenguaje apropiado

- Usar: *usage*, *consumption*, *status*
- No usar: *billing*, *charges* a menos que el provider exponga billing explícito

### Disponibilidad

- **Auth status** confirma cual cuenta esta activa
- **Usage summaries** son senales de consumo, no totales de facturacion
- **Provider-level usage** puede ser compartido entre cuentas
- Si el gateway OpenClaw esta down, no habra usage detail disponible

### Cuentas compartidas

- Maribel es cuenta compartida — monitorizar uso conservadoramente
- No asumir que usage == facturacion directa

## Output esperado

Formato similar a `/status` de CLI: rapido, factual, sin framing de billing.

```
CODEX USAGE
  Plan: ...
  Last 30 days: ...
  Latest day: ...

CLAUDE CODE STATUS (Jorge - host)
  Auth: active
  Account: jorge@...

CLAUDE CODE STATUS (Maribel - Docker)
  Auth: active
  Account: ...

OPENCLAW GATEWAY USAGE
  [detalles si RPC disponible]

[NOTA] Detailed usage not available — gateway down
```

## Telegram / Gateway note

**Importante:** Un skill trigger como `/usageai` no crea automaticamente un slash command de Telegram.

Si Telegram responde `Unknown command /usageai`, el comando debe registrarse en la capa OpenClaw/gateway/plugin.

Skill trigger y Telegram slash command son superficies relacionadas pero separadas.

## Archivo del skill

- Ubicacion: `skills/devops/usageai/SKILL.md`
- Sin dependencias de APIs externas
- Solo invoca `~/.local/bin/usageai` (script local)

## Nodos relacionados

- `integrated-tools` — indice maestro
- `hermes-core-tools` — catalogo de herramientas core
- `hermes-core-agent` — agente principal


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `integrated-tools-area` (Integrated Tools) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# UsageAI Reporting

# Integrated Tools — UsageAI

# Integrated Tools — UsageAI

## Resumen

UsageAI es un skill de reporting de consumo de sistemas AI: Codex y Claude Code. Muestra estado de autenticacion, usage summaries, y metricas del gateway OpenClaw.

**Trigger:** `/usageai` o cualquier variante (`usageai`, `usage ai`, `codex usage`, `claude usage`)

## Comando

```bash
~/.local/bin/usageai
```

Este comando es la unica interfaz de uso. No hace llamadas directas a APIs de providers.

## Que muestra

| Seccion | Contenido |
|---|---|
| Codex usage | Resumen de uso de Codex/OpenAI |
| Claude Code (Jorge) | Auth status en el host |
| Claude Code (Maribel) | Auth status en Docker |
| OpenClaw gateway | Usage del gateway si RPC disponible |
| Nota de no disponibilidad | Cuando no se puede obtener detalle |

## Cuentas monitoreadas

| Cuenta | Entorno | Notas |
|---|---|---|
| Jorge | Host (macOS) | Cuenta principal |
| Maribel | Docker container | Compartida, usar con cuidado |

## Reglas de interpretacion

### Lenguaje apropiado

- Usar: *usage*, *consumption*, *status*
- No usar: *billing*, *charges* a menos que el provider exponga billing explícito

### Disponibilidad

- **Auth status** confirma cual cuenta esta activa
- **Usage summaries** son senales de consumo, no totales de facturacion
- **Provider-level usage** puede ser compartido entre cuentas
- Si el gateway OpenClaw esta down, no habra usage detail disponible

### Cuentas compartidas

- Maribel es cuenta compartida — monitorizar uso conservadoramente
- No asumir que usage == facturacion directa

## Output esperado

Formato similar a `/status` de CLI: rapido, factual, sin framing de billing.

```
CODEX USAGE
  Plan: ...
  Last 30 days: ...
  Latest day: ...

CLAUDE CODE STATUS (Jorge - host)
  Auth: active
  Account: jorge@...

CLAUDE CODE STATUS (Maribel - Docker)
  Auth: active
  Account: ...

OPENCLAW GATEWAY USAGE
  [detalles si RPC disponible]

[NOTA] Detailed usage not available — gateway down
```

## Telegram / Gateway note

**Importante:** Un skill trigger como `/usageai` no crea automaticamente un slash command de Telegram.

Si Telegram responde `Unknown command /usageai`, el comando debe registrarse en la capa OpenClaw/gateway/plugin.

Skill trigger y Telegram slash command son superficies relacionadas pero separadas.

## Archivo del skill

- Ubicacion: `skills/devops/usageai/SKILL.md`
- Sin dependencias de APIs externas
- Solo invoca `~/.local/bin/usageai` (script local)

## Nodos relacionados

- `integrated-tools` — indice maestro
- `hermes-core-tools` — catalogo de herramientas core
- `hermes-core-agent` — agente principal
