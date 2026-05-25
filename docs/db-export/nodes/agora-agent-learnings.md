# Agent Learnings — Aprendizaje Persistente

## Metadata

- ID: `215`
- Slug: `agora-agent-learnings`
- Kind: `doc`
- Status: `active`
- Filename: `agora-agent-learnings.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:33:53.509227+00:00`
- Updated at: `2026-05-19T08:33:53.509227+00:00`
- Aliases: `agora-agent-learnings`

## Summary

El agente aprende de conversaciones. Persiste aprendizajes en agent_learnings con titulo, tags, confianza. Decay automatico cada 6h limpia aprendizajes no referenciados.

## Body

# Agent Learnings — Aprendizaje Persistente

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

El agente puede persistir lo que aprende de las conversaciones. Cada aprendizaje tiene
titulo, contenido markdown, tags, confianza y contador de referencias. Un proceso de
decay automatico limpia aprendizajes no usados.

## DB: agent_learnings

```sql
agent_learnings(id, user_id, kind, title, content_md, tags,
    context_json, confidence DEFAULT 0.5, times_referenced DEFAULT 0,
    created_at, updated_at)
```

Indexado por `(user_id, kind, created_at)`.

## Decay

Controlado por `scheduler.py._decay_learnings()`. Corre cada 6 horas.
Configurable via env vars:
- `AGORA_LEARNING_DECAY_DAYS` — dias para considerar "viejo" (default: 30)
- `AGORA_LEARNING_DECAY_FACTOR` — factor de reduccion de confianza
- `AGORA_LEARNING_DECAY_FLOOR` — confianza minima antes de eliminar

Aprendizajes con `confidence < FLOOR` y 0 referencias se eliminan.

## Uso en chat

El agente puede buscar sus aprendizajes previos para contextualizar respuestas.
La tool `agent_search_learnings` busca por texto en `content_md` y `tags`.
La tool `agent_add_learning` crea un nuevo aprendizaje.

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agent Learnings — Aprendizaje Persistente

# Agent Learnings — Aprendizaje Persistente

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

El agente puede persistir lo que aprende de las conversaciones. Cada aprendizaje tiene
titulo, contenido markdown, tags, confianza y contador de referencias. Un proceso de
decay automatico limpia aprendizajes no usados.

## DB: agent_learnings

```sql
agent_learnings(id, user_id, kind, title, content_md, tags,
    context_json, confidence DEFAULT 0.5, times_referenced DEFAULT 0,
    created_at, updated_at)
```

Indexado por `(user_id, kind, created_at)`.

## Decay

Controlado por `scheduler.py._decay_learnings()`. Corre cada 6 horas.
Configurable via env vars:
- `AGORA_LEARNING_DECAY_DAYS` — dias para considerar "viejo" (default: 30)
- `AGORA_LEARNING_DECAY_FACTOR` — factor de reduccion de confianza
- `AGORA_LEARNING_DECAY_FLOOR` — confianza minima antes de eliminar

Aprendizajes con `confidence < FLOOR` y 0 referencias se eliminan.

## Uso en chat

El agente puede buscar sus aprendizajes previos para contextualizar respuestas.
La tool `agent_search_learnings` busca por texto en `content_md` y `tags`.
La tool `agent_add_learning` crea un nuevo aprendizaje.
