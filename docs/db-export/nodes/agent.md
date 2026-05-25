# Agent — Núcleo de procesamiento

## Metadata

- ID: `56`
- Slug: `agent`
- Kind: `doc`
- Status: `active`
- Filename: `agent.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:51.076335+00:00`
- Updated at: `2026-05-08T08:05:51.076335+00:00`
- Aliases: `agent`

## Summary

Lógica del agente, modelos de lenguaje y prompts

## Body

# Agent — Núcleo de procesamiento

## Ubicación
~/LAIA/.laia-arch/agent/

## Función
El agente es el cerebro de Hermes. Procesa entradas del usuario, decide qué herramientas usar y genera respuestas.

## Modelos soportados
- OpenRouter (200+ modelos)
- Nous Portal
- NVIDIA NIM
- OpenAI
- Anthropic
- Xiaomi MiMo
- Kimi/Moonshot
- MiniMax
- Hugging Face
- Endpoint personalizado

## Características
- Multi-modelo: cambiar con `hermes model`
- Contexto persistente entre sesiones
- Memoria a largo plazo
- Skills autónomos
- Delegación a sub-agentes

## Código principal
- agent/__init__.py: Clase principal del agente
- agent/models.py: Gestión de modelos
- agent/prompts.py: Templates de prompts


> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agent — Núcleo de procesamiento

# Agent — Núcleo de procesamiento

## Ubicación
~/LAIA/.laia-arch/agent/

## Función
El agente es el cerebro de Hermes. Procesa entradas del usuario, decide qué herramientas usar y genera respuestas.

## Modelos soportados
- OpenRouter (200+ modelos)
- Nous Portal
- NVIDIA NIM
- OpenAI
- Anthropic
- Xiaomi MiMo
- Kimi/Moonshot
- MiniMax
- Hugging Face
- Endpoint personalizado

## Características
- Multi-modelo: cambiar con `hermes model`
- Contexto persistente entre sesiones
- Memoria a largo plazo
- Skills autónomos
- Delegación a sub-agentes

## Código principal
- agent/__init__.py: Clase principal del agente
- agent/models.py: Gestión de modelos
- agent/prompts.py: Templates de prompts


> 📅 Documentado: 2026-05-12
