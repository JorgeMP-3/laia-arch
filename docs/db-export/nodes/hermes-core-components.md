# Hermes Core Components

## Metadata

- ID: `123`
- Slug: `hermes-core-components`
- Kind: `topic`
- Status: `active`
- Filename: `hermes-core-components.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:49:12.902999+00:00`
- Updated at: `2026-05-08T09:03:49.397452+00:00`
- Aliases: `hermes-core-components`

## Summary

Componentes principales del núcleo de Hermes

## Body

# Hermes Core Components

## Descripción

Documentación técnica de cada componente del núcleo de Hermes Agent. Hermes es el motor base sobre el que se construye LAIA.

## Arquitectura del núcleo

```
┌─────────────────────────────────────┐
│           Hermes Core               │
├─────────────────────────────────────┤
│  Agent (run_agent.py)              │
│  ├── AIAgent class                 │
│  ├── Agent loop                    │
│  ├── Prompt builder                │
│  └── Memory manager                │
├─────────────────────────────────────┤
│  Gateway (gateway/)                │
│  ├── Telegram                      │
│  ├── Discord                       │
│  ├── Slack                         │
│  ├── WhatsApp                      │
│  └── CLI                           │
├─────────────────────────────────────┤
│  Tools (tools/)                    │
│  ├── Terminal                       │
│  ├── Execute code                  │
│  ├── Browser                       │
│  ├── Web search                    │
│  └── ~30 herramientas              │
├─────────────────────────────────────┤
│  Plugins (plugins/)                │
│  ├── workspace-context             │
│  └── Custom plugins                │
└─────────────────────────────────────┘
```

## Documentos incluidos

### Componentes principales
- **agent**: Núcleo de procesamiento del agente
- **gateway**: Comunicación multi-plataforma
- **tools**: Herramientas disponibles
- **plugins**: Extensiones modulares

### Documentación detallada (hermes-core-*)
- **hermes-core-agent-detail**: AIAgent class, agent loop, prompts
- **hermes-core-architecture-detail**: Arquitectura general del sistema
- **hermes-core-commands-detail**: Slash commands (~40 comandos)
- **hermes-core-memory-detail**: Sistema de memoria en capas
- **hermes-core-multi-agent-detail**: Delegación y sub-agentes
- **hermes-core-plugins-detail**: Sistema de plugins
- **hermes-core-tools-detail**: ~30 herramientas nativas
- **hermes-core-vision-detail**: Sistema de visión
- **hermes-core-voice-detail**: Sistema de voz

### Modelo conceptual
- **modelo-ser-medios**: LAIA como ser y sus medios
- **vision-general**: Visión estratégica del ecosistema

### Orquestación
- **command-center**: Orquestación multi-agente
- **tool-context-injection**: Sistema de inyección de contexto

## Creador

**Nous Research** (https://nousresearch.com)
GitHub: https://github.com/NousResearch/hermes-agent
Licencia: MIT
Versión: 0.11.0


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- `contains` → `agent` (Agent — Núcleo de procesamiento) [peso=1.00]
- `contains` → `gateway` (Gateway — Comunicación multi-plataforma) [peso=1.00]
- `contains` → `hermes-core-agent-detail` (Hermes Core — Agent) [peso=1.00]
- `contains` → `hermes-core-architecture-detail` (Hermes Core — Arquitectura General) [peso=1.00]
- `contains` → `hermes-core-commands-detail` (Hermes Core — Commands) [peso=1.00]
- `contains` → `hermes-core-memory-detail` (Hermes Core — Memory System) [peso=1.00]
- `contains` → `hermes-core-multi-agent-detail` (Hermes Core — Multi-Agent System) [peso=1.00]
- `contains` → `hermes-core-plugins-detail` (Hermes Core — Plugin System) [peso=1.00]
- `contains` → `hermes-core-tools-detail` (Hermes Core — Tools) [peso=1.00]
- `contains` → `hermes-core-vision-detail` (Hermes Core — Vision System) [peso=1.00]
- `contains` → `hermes-core-voice-detail` (Hermes Core — Voice System) [peso=1.00]
- `contains` → `plugins` (Plugins — Extensiones modulares) [peso=1.00]
- `contains` → `tools` (Tools — Herramientas disponibles) [peso=1.00]

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core Components

# Hermes Core Components

## Descripción

Documentación técnica de cada componente del núcleo de Hermes Agent. Hermes es el motor base sobre el que se construye LAIA.

## Arquitectura del núcleo

```
┌─────────────────────────────────────┐
│           Hermes Core               │
├─────────────────────────────────────┤
│  Agent (run_agent.py)              │
│  ├── AIAgent class                 │
│  ├── Agent loop                    │
│  ├── Prompt builder                │
│  └── Memory manager                │
├─────────────────────────────────────┤
│  Gateway (gateway/)                │
│  ├── Telegram                      │
│  ├── Discord                       │
│  ├── Slack                         │
│  ├── WhatsApp                      │
│  └── CLI                           │
├─────────────────────────────────────┤
│  Tools (tools/)                    │
│  ├── Terminal                       │
│  ├── Execute code                  │
│  ├── Browser                       │
│  ├── Web search                    │
│  └── ~30 herramientas              │
├─────────────────────────────────────┤
│  Plugins (plugins/)                │
│  ├── workspace-context             │
│  └── Custom plugins                │
└─────────────────────────────────────┘
```

## Documentos incluidos

### Componentes principales
- **agent**: Núcleo de procesamiento del agente
- **gateway**: Comunicación multi-plataforma
- **tools**: Herramientas disponibles
- **plugins**: Extensiones modulares

### Documentación detallada (hermes-core-*)
- **hermes-core-agent-detail**: AIAgent class, agent loop, prompts
- **hermes-core-architecture-detail**: Arquitectura general del sistema
- **hermes-core-commands-detail**: Slash commands (~40 comandos)
- **hermes-core-memory-detail**: Sistema de memoria en capas
- **hermes-core-multi-agent-detail**: Delegación y sub-agentes
- **hermes-core-plugins-detail**: Sistema de plugins
- **hermes-core-tools-detail**: ~30 herramientas nativas
- **hermes-core-vision-detail**: Sistema de visión
- **hermes-core-voice-detail**: Sistema de voz

### Modelo conceptual
- **modelo-ser-medios**: LAIA como ser y sus medios
- **vision-general**: Visión estratégica del ecosistema

### Orquestación
- **command-center**: Orquestación multi-agente
- **tool-context-injection**: Sistema de inyección de contexto

## Creador

**Nous Research** (https://nousresearch.com)
GitHub: https://github.com/NousResearch/hermes-agent
Licencia: MIT
Versión: 0.11.0


> 📅 Documentado: 2026-05-08

→ Agent — Núcleo de procesamiento: `agent.md`
→ Gateway — Comunicación multi-plataforma: `gateway.md`
→ Hermes Core — Agent: `hermes-core-agent-detail.md`
→ Hermes Core — Arquitectura General: `hermes-core-architecture-detail.md`
→ Hermes Core — Commands: `hermes-core-commands-detail.md`
→ Hermes Core — Memory System: `hermes-core-memory-detail.md`
→ Hermes Core — Multi-Agent System: `hermes-core-multi-agent-detail.md`
→ Hermes Core — Plugin System: `hermes-core-plugins-detail.md`
→ Hermes Core — Tools: `hermes-core-tools-detail.md`
→ Hermes Core — Vision System: `hermes-core-vision-detail.md`
→ Hermes Core — Voice System: `hermes-core-voice-detail.md`
→ Plugins — Extensiones modulares: `plugins.md`
→ Tools — Herramientas disponibles: `tools.md`
