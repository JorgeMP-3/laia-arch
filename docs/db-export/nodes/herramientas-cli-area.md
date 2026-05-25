# Herramientas CLI y Scripts

## Metadata

- ID: `126`
- Slug: `herramientas-cli-area`
- Kind: `topic`
- Status: `active`
- Filename: `herramientas-cli-area.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T09:01:47.995507+00:00`
- Updated at: `2026-05-08T09:01:47.995507+00:00`
- Aliases: `herramientas-cli-area`

## Summary

Scripts de mantenimiento y herramientas de línea de comandos

## Body

# Herramientas CLI y Scripts

## Descripción

Conjunto de herramientas de línea de comandos y scripts para el mantenimiento y operación del sistema LAIA.

## Herramientas principales

### LAIA Tools
Suite de herramientas CLI que orquestan el sistema:
- **laia-restart**: Reiniciar servicios
- **gsave**: Guardado guiado (commit + push)
- **clone-laia**: Instalador multi-OS
- **sclaude**: Proxy Docker para Claude Code
- **pack-laia-secrets**: Backup cifrado

### Scripts de mantenimiento
Scripts Python para operaciones del sistema:
- **health-check.py**: Verificación de salud del sistema
- **workspace-daily-diagnostic.py**: Diagnóstico diario
- **sync-workspace-markdown.py**: Sincronización de exports
- **show-injected.py**: Mostrar contexto inyectado

## Estado actual

- Herramientas existentes: 9 scripts en ~/LAIA/bin/
- Scripts de mantenimiento: 29 en ~/LAIA/scripts/
- Plan de mejora: 8 nuevas herramientas planificadas

## Documentos incluidos

- **laia-tools**: Inventario de herramientas actuales
- **laia-tools-plan**: Plan de mejora y nuevas herramientas

## Uso típico

```bash
# Verificar salud del sistema
python3 ~/LAIA/scripts/health-check.py

# Reiniciar servicios
~/LAIA/bin/laia-restart

# Guardar cambios
~/LAIA/bin/gsave
```


> 📅 Documentado: 2026-05-12

## Relaciones salientes

- `contains` → `laia-tools` (LAIA Tools) [peso=1.00]
- `contains` → `laia-tools-plan` (LAIA Tools Plan) [peso=1.00]

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Herramientas CLI y Scripts

# Herramientas CLI y Scripts

## Descripción

Conjunto de herramientas de línea de comandos y scripts para el mantenimiento y operación del sistema LAIA.

## Herramientas principales

### LAIA Tools
Suite de herramientas CLI que orquestan el sistema:
- **laia-restart**: Reiniciar servicios
- **gsave**: Guardado guiado (commit + push)
- **clone-laia**: Instalador multi-OS
- **sclaude**: Proxy Docker para Claude Code
- **pack-laia-secrets**: Backup cifrado

### Scripts de mantenimiento
Scripts Python para operaciones del sistema:
- **health-check.py**: Verificación de salud del sistema
- **workspace-daily-diagnostic.py**: Diagnóstico diario
- **sync-workspace-markdown.py**: Sincronización de exports
- **show-injected.py**: Mostrar contexto inyectado

## Estado actual

- Herramientas existentes: 9 scripts en ~/LAIA/bin/
- Scripts de mantenimiento: 29 en ~/LAIA/scripts/
- Plan de mejora: 8 nuevas herramientas planificadas

## Documentos incluidos

- **laia-tools**: Inventario de herramientas actuales
- **laia-tools-plan**: Plan de mejora y nuevas herramientas

## Uso típico

```bash
# Verificar salud del sistema
python3 ~/LAIA/scripts/health-check.py

# Reiniciar servicios
~/LAIA/bin/laia-restart

# Guardar cambios
~/LAIA/bin/gsave
```


> 📅 Documentado: 2026-05-12

→ LAIA Tools: `laia-tools.md`
→ LAIA Tools Plan: `laia-tools-plan.md`
