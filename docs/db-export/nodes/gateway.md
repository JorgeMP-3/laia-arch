# Gateway — Comunicación multi-plataforma

## Metadata

- ID: `57`
- Slug: `gateway`
- Kind: `doc`
- Status: `active`
- Filename: `gateway.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:51.317243+00:00`
- Updated at: `2026-05-08T08:05:51.317243+00:00`
- Aliases: `gateway`

## Summary

Sistema de comunicación con múltiples plataformas

## Body

# Gateway — Comunicación multi-plataforma

## Ubicación
~/LAIA/.laia-arch/gateway/

## Plataformas soportadas
- Telegram
- Discord
- Slack
- WhatsApp
- Signal
- CLI (terminal)

## Características
- Single gateway process
- Voice memo transcription
- Cross-platform conversation continuity
- Streaming tool output

## Arquitectura
```
Plataformas → Gateway → Agent
     ↑                      │
     └──────────────────────┘
```

## Código principal
- gateway/__init__.py: Gestor principal
- gateway/telegram.py: Integración Telegram
- gateway/discord.py: Integración Discord
- gateway/whatsapp.py: Integración WhatsApp


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Gateway — Comunicación multi-plataforma

# Gateway — Comunicación multi-plataforma

## Ubicación
~/LAIA/.laia-arch/gateway/

## Plataformas soportadas
- Telegram
- Discord
- Slack
- WhatsApp
- Signal
- CLI (terminal)

## Características
- Single gateway process
- Voice memo transcription
- Cross-platform conversation continuity
- Streaming tool output

## Arquitectura
```
Plataformas → Gateway → Agent
     ↑                      │
     └──────────────────────┘
```

## Código principal
- gateway/__init__.py: Gestor principal
- gateway/telegram.py: Integración Telegram
- gateway/discord.py: Integración Discord
- gateway/whatsapp.py: Integración WhatsApp
