---
name: agent-learning
description: >
  Patrón disciplinado para que el agente registre errores, hallazgos y
  patrones aprendidos, y los recuerde en sesiones futuras.
version: 0.1.0
---

# Aprendizaje orgánico

Tienes 4 tools del toolset `agent_self` para gestionar aprendizajes
persistentes (tabla `agent_learnings` en `agora.db`):

| Tool | Propósito |
|---|---|
| `learning_record(kind, title, content, tags?, context?)` | Crear |
| `learning_recall(kind?, query?, limit?)` | Buscar |
| `learning_list_recent(limit?)` | Las N más recientes/relevantes |
| `learning_forget(learning_id)` | Borrar (solo owner) |

Los 8 aprendizajes más relevantes se inyectan automáticamente en tu
system prompt al iniciar cada sesión, así que **no necesitas llamar
`learning_recall` para recordarlos** — ya están en tu contexto.

## Cinco categorías (`kind`)

- **`error`** — un fallo tuyo + causa raíz aprendida. Ej: "asumí que el usuario tenía permisos sudo pero no los tenía".
- **`insight`** — un descubrimiento útil. Ej: "el campo `mcp_servers_json` no se serializa si está vacío".
- **`pattern`** — comportamiento recurrente del usuario o del sistema. Ej: "el usuario prefiere bullets para resúmenes largos".
- **`preference`** — el usuario corrigió una asunción tuya. Ej: "no escribo en mayúsculas las siglas técnicas".
- **`skill_observation`** — una skill/tool que has descubierto. Ej: "agent-now es útil cuando necesitas timestamp sin invocar bash".

## Cuándo registrar

- Cuando cometes un error y descubres la causa → `kind="error"`.
- Cuando el usuario te corrige → `kind="preference"`.
- Cuando notas un patrón que se repite → `kind="pattern"`.
- Cuando descubres algo que ahorraría tiempo en el futuro → `kind="insight"`.

## Reglas de calidad

1. **Sé conciso**: el `content` viaja en tu system prompt en futuras
   sesiones (~240 chars de cada uno). Si no cabe en 2 frases, es
   probable que sea documentación, no un learning.
2. **Indexa por título buscable**: el `title` se usa para `learning_recall`.
   "Error con SSH" es malo, "ssh-agent no propaga las claves cuando lanzo desde tmux" es bueno.
3. **No duplicar**: antes de registrar, llama `learning_recall(query=...)` para ver si ya existe uno similar. Si lo hay, considera actualizar (forget+record) en vez de duplicar.
4. **Tags ayudan**: incluye 2-4 tags coma-separados para clustering.
5. **`context`**: opcional, JSON pequeño con `{session_id, tool, error_message}` para auditoría.

## Cuándo borrar

- Si el aprendizaje resulta erróneo y descubres la versión correcta:
  registra el nuevo learning + `learning_forget` el viejo.
- Si el user pide explícitamente "olvida que aprendiste X".
- Auto-decay: aprendizajes con confidence baja sin referenciar durante 30+ días se podan automáticamente (no implementado todavía, P1).
