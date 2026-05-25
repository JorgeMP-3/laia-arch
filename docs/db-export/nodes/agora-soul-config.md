# AGORA Soul Config — Personalidad como System Prompt

## Metadata

- ID: `212`
- Slug: `agora-soul-config`
- Kind: `doc`
- Status: `active`
- Filename: `agora-soul-config.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T16:10:02.420155+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `agora-soul-config`

## Summary

El soul (soul_md) y las instrucciones (instructions_md) del agente se inyectan como ephemeral_system_prompt en el AIAgent. El LLM las ve como su personalidad. Cambios toman efecto en la siguiente sesion.

## Body

# AGORA Soul Config

## Como funciona

1. El usuario (o admin) edita el area del agente via `PATCH /api/me/agent-area`
2. Los campos `soul_md`, `instructions_md`, `behavior_preferences_json` se guardan en `agent_areas`
3. AgentPool los lee al crear un AIAgent
4. Los concatena en un `ephemeral_system_prompt`:
   ```
   [Soul]
   Soy Nombrix, el PA-AGORA de Jorge.
   
   [Instructions]
   Responde en espanol claro y directo.
   
   [Preferences]
   tone: directo
   language: es
   ```
5. El LLM (DeepSeek/Anthropic/OpenAI) recibe esto como prompt del sistema
6. Si el usuario cambia su soul → AgentPool invalida la sesion → siguiente chat usa el nuevo soul

## Campos de agent_areas

| Campo | Tipo | Uso |
|-------|------|-----|
| agent_display_name | TEXT | Nombre visible: "Nombrix", "MariaBot" |
| soul_md | TEXT | Personalidad del agente (markdown) |
| instructions_md | TEXT | Instrucciones operativas (markdown) |
| memory_preferences_json | TEXT | Preferencias de memoria (JSON) |
| behavior_preferences_json | TEXT | Comportamiento: tone, language, etc (JSON) |

## Diferencia con el viejo /api/agent/profile

| Viejo | Nuevo |
|-------|-------|
| Leia del container (lxc exec) | Lee de agent_areas en DB |
| Archivos sueltos en /opt/laia/data/profile/ | Centralizado en agora.db |
| Sin impacto en AIAgent | Inyectado como system prompt |
| Requeria container corriendo | Funciona aunque el container este parado |

> 📅 Documentado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Soul Config — Personalidad como System Prompt

# AGORA Soul Config

## Como funciona

1. El usuario (o admin) edita el area del agente via `PATCH /api/me/agent-area`
2. Los campos `soul_md`, `instructions_md`, `behavior_preferences_json` se guardan en `agent_areas`
3. AgentPool los lee al crear un AIAgent
4. Los concatena en un `ephemeral_system_prompt`:
   ```
   [Soul]
   Soy Nombrix, el PA-AGORA de Jorge.
   
   [Instructions]
   Responde en espanol claro y directo.
   
   [Preferences]
   tone: directo
   language: es
   ```
5. El LLM (DeepSeek/Anthropic/OpenAI) recibe esto como prompt del sistema
6. Si el usuario cambia su soul → AgentPool invalida la sesion → siguiente chat usa el nuevo soul

## Campos de agent_areas

| Campo | Tipo | Uso |
|-------|------|-----|
| agent_display_name | TEXT | Nombre visible: "Nombrix", "MariaBot" |
| soul_md | TEXT | Personalidad del agente (markdown) |
| instructions_md | TEXT | Instrucciones operativas (markdown) |
| memory_preferences_json | TEXT | Preferencias de memoria (JSON) |
| behavior_preferences_json | TEXT | Comportamiento: tone, language, etc (JSON) |

## Diferencia con el viejo /api/agent/profile

| Viejo | Nuevo |
|-------|-------|
| Leia del container (lxc exec) | Lee de agent_areas en DB |
| Archivos sueltos en /opt/laia/data/profile/ | Centralizado en agora.db |
| Sin impacto en AIAgent | Inyectado como system prompt |
| Requeria container corriendo | Funciona aunque el container este parado |

> 📅 Documentado: 2026-05-18
