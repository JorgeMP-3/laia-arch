---
name: agent-self-edit
description: >
  Permite al agente editar su propia identidad (soul, instructions, name,
  preferences) durante la conversación, sin que el usuario tenga que tocar
  APIs ni CLI.
version: 0.1.0
---

# Editar tu propia identidad

Tienes acceso a 8 tools del toolset `agent_self` que persisten cambios en
`agent_area` directamente en `agora.db`. Cada cambio invalida la sesión
del AgentPool — el próximo turno te re-construye con la nueva identidad
inyectada en el system prompt.

## Cuándo usarlas

| Frase del usuario | Tool |
|---|---|
| "anota esto como instrucción permanente: …" | `agent_append_instructions(text=…)` |
| "tu instrucción principal es …" | `agent_set_instructions(instructions=…)` |
| "cambia tu nombre a X" / "llámate X" | `agent_set_name(name="X")` |
| "tu personalidad/soul es …" | `agent_set_soul(soul=…)` |
| "añade a tu soul: …" | `agent_append_soul(text=…)` |
| "prefiero que respondas en tono X" | `agent_set_preference(key="tone", value="X", scope="behavior")` |
| "recuerda que mi zona horaria es Y" | `agent_set_preference(key="timezone", value="Y", scope="memory")` |
| "olvida la preferencia X" | `agent_remove_preference(key="X")` |
| "¿qué tienes anotado sobre ti?" | `agent_get_area()` |

## Reglas de uso

- **No abuses** del `set_*` total: cuando el usuario solo quiere añadir una
  cosa, usa `append_*` para no sobreescribir lo previo.
- **Confirma** antes de cambios destructivos: si el soul ya tiene contenido
  y el usuario pide reescribirlo, repite lo que vas a borrar y pide OK.
- Si el usuario dice algo genérico ("recuerda esto"), por defecto va a
  `agent_append_instructions` (instrucción persistente), NO al soul.
- El soul es identidad — quién eres como agente. Las instructions son
  reglas del usuario sobre cómo trabajar.
- Tras llamar la tool, comprueba el campo `ok` en la respuesta JSON y
  resume al usuario qué se ha persistido.

## Límites

- `soul_md` e `instructions_md`: 50 KB cada uno.
- `agent_display_name`: 80 chars máximo.
- `value` de una preferencia: JSON serializable (str/number/bool/list/dict).
