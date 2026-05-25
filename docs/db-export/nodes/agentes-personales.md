# Agentes personales — Hijos de LAIA (v2.1)

## Metadata

- ID: `127`
- Slug: `agentes-personales`
- Kind: `topic`
- Status: `active`
- Filename: `agentes-personales.md`
- Parent: `index`
- Source kind: `manual`
- Created at: `2026-05-08T09:01:48.290651+00:00`
- Updated at: `2026-05-19T11:13:52.676742`
- Aliases: `agentes-personales`

## Summary

Arquitectura v2.1: executors finos (root libre) en containers LXD. El cerebro (AIAgent) corre en laia-agora y forwardea tool calls a los executors.

## Body

# PA-AGORA v2.1

## Modelo actual: cada usuario tiene container LXD con laia-executor (FastAPI :9091, 22 tools, root). El cerebro corre en laia-agora. LLM forwardea tools al executor.

## vs Sprint 2: .laia-core/ solo en laia-agora (no en cada container). Sandbox eliminado. Usuario root. Per-user LLM config.

## Nodos relacionados: agora-rediseno, agora-executor, agora-forwarder

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- `contains` → `agentes-docker-alternativa` (Agentes personales — Docker (Alternativa documentada)) [peso=1.00]
- `contains` → `agentes-lxd` (Agentes personales — LXD (v2.2)) [peso=1.00]
- `contains` → `agentes-aislamiento` (Aislamiento de agentes personales) [peso=1.00]
- `contains` → `agentes-base` (Base de agentes personales) [peso=1.00]
- `contains` → `decision-lxd-vs-docker` (Decisión — LXD vs Docker para agentes personales) [peso=1.00]
- `contains` → `agentes-imagen-base` (Imagen base de agentes — Sistema de aprovisionamiento) [peso=1.00]

## Relaciones entrantes

- `contains` ← `index` (LAIA — Ecosistema v2.6) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agentes personales — Hijos de LAIA (v2.1)

# PA-AGORA v2.1

## Modelo actual: cada usuario tiene container LXD con laia-executor (FastAPI :9091, 22 tools, root). El cerebro corre en laia-agora. LLM forwardea tools al executor.

## vs Sprint 2: .laia-core/ solo en laia-agora (no en cada container). Sandbox eliminado. Usuario root. Per-user LLM config.

## Nodos relacionados: agora-rediseno, agora-executor, agora-forwarder

> 📅 Documentado: 2026-05-12

→ Agentes personales — Docker (Alternativa documentada): `agentes-docker-alternativa.md`
→ Agentes personales — LXD (v2.2): `agentes-lxd.md`
→ Aislamiento de agentes personales: `agentes-aislamiento.md`
→ Base de agentes personales: `agentes-base.md`
→ Decisión — LXD vs Docker para agentes personales: `decision-lxd-vs-docker.md`
→ Imagen base de agentes — Sistema de aprovisionamiento: `agentes-imagen-base.md`
