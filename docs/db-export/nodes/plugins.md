# Plugins — Extensiones modulares

## Metadata

- ID: `59`
- Slug: `plugins`
- Kind: `doc`
- Status: `active`
- Filename: `plugins.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:51.799750+00:00`
- Updated at: `2026-05-08T08:05:51.799750+00:00`
- Aliases: `plugins`

## Summary

Sistema de plugins para extender funcionalidad

## Body

# Plugins — Extensiones modulares

## Ubicación
~/LAIA/.laia-arch/plugins/ (internos)
~/LAIA/plugins/ (externos)

## Plugins principales

| Plugin | Directorio | Función |
|---|---|---|
| workspace-context | plugins/workspace-context/ | Sistema de memoria DB-first |
| doyouwin | plugins/doyouwin/ | Plugin personalizado |

## Plugin: workspace-context
- Sistema de memoria basado en SQLite
- 20 herramientas para gestión de nodos
- 3 modos de inyección (index, all-indexes, full)
- Búsqueda FTS5 con ranking BM25

## Crear un plugin
1. Crear directorio en plugins/
2. Crear __init__.py con register(ctx)
3. Crear plugin.yaml con configuración
4. Registrar en config.yaml


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Plugins — Extensiones modulares

# Plugins — Extensiones modulares

## Ubicación
~/LAIA/.laia-arch/plugins/ (internos)
~/LAIA/plugins/ (externos)

## Plugins principales

| Plugin | Directorio | Función |
|---|---|---|
| workspace-context | plugins/workspace-context/ | Sistema de memoria DB-first |
| doyouwin | plugins/doyouwin/ | Plugin personalizado |

## Plugin: workspace-context
- Sistema de memoria basado en SQLite
- 20 herramientas para gestión de nodos
- 3 modos de inyección (index, all-indexes, full)
- Búsqueda FTS5 con ranking BM25

## Crear un plugin
1. Crear directorio en plugins/
2. Crear __init__.py con register(ctx)
3. Crear plugin.yaml con configuración
4. Registrar en config.yaml


> 📅 Documentado: 2026-05-08
