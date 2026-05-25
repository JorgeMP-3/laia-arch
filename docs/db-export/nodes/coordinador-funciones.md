# LAIA AGORA — Funciones

## Metadata

- ID: `64`
- Slug: `coordinador-funciones`
- Kind: `doc`
- Status: `active`
- Filename: `coordinador-funciones.md`
- Parent: `coordinador`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:52.956876+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `coordinador-funciones`

## Summary

Funciones del coordinador LAIA AGORA: monitorizar, asignar trabajo, alertar. Sin capacidad de modificacion de contenedores.

## Body

# LAIA AGORA — Funciones

## Principio fundamental

LAIA AGORA **monitoriza y coordina**, pero **NUNCA modifica** los contenedores de los usuarios. No ejecuta comandos dentro de ellos, no altera ficheros, no cambia configuraciones.

## Funciones principales

### Monitorizacion
- Detectar PA-AGORA bloqueados o inactivos
- Identificar usuarios sin actividad prolongada
- Reportar anomalias a LAIA-ARCH
- Ver estado global de tareas (sin acceder a datos privados)

### Asignacion de trabajo
- Publicar tareas en la plataforma AGORA (visibles para los usuarios)
- Priorizar backlog
- (Futuro) Distribuir trabajo cuando exista area tipo ClickUp

### Validacion
- Revisar skills antes de publicar en el marketplace
- Validar tools y plugins compartidos
- Asegurar calidad del marketplace

### Sintesis
- Consolidar conocimiento de agentes (anonimizado)
- Generar informes periodicos para LAIA-ARCH
- Identificar patrones y mejoras

### Alertas
- Enviar alertas a LAIA-ARCH ante: agente caido, error critico, inactividad prolongada
- Notificar al admin sobre necesidades de intervencion

## Lo que NO hace

- NO ejecuta `lxc exec` en contenedores de usuarios
- NO modifica ficheros de configuracion de agentes
- NO cambia skills de agentes ajenos
- NO accede a workspaces privados
- NO gestiona infraestructura

## Diferencia con LAIA-ARCH

| Funcion | LAIA AGORA | LAIA-ARCH |
|---|---|---|
| Crear/borrar contenedores | No | Si |
| Ejecutar comandos en contenedores | No | Si (via `lxc exec`) |
| Ver estado de agentes | Si (anonimizado) | Si (completo) |
| Asignar tareas | Si (via AGORA) | Si (directo) |
| Modificar infraestructura | No | Si |
| Gestionar LXD | No | Si |

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `coordinador` (LAIA AGORA — Coordinador) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA AGORA — Funciones

# LAIA AGORA — Funciones

## Principio fundamental

LAIA AGORA **monitoriza y coordina**, pero **NUNCA modifica** los contenedores de los usuarios. No ejecuta comandos dentro de ellos, no altera ficheros, no cambia configuraciones.

## Funciones principales

### Monitorizacion
- Detectar PA-AGORA bloqueados o inactivos
- Identificar usuarios sin actividad prolongada
- Reportar anomalias a LAIA-ARCH
- Ver estado global de tareas (sin acceder a datos privados)

### Asignacion de trabajo
- Publicar tareas en la plataforma AGORA (visibles para los usuarios)
- Priorizar backlog
- (Futuro) Distribuir trabajo cuando exista area tipo ClickUp

### Validacion
- Revisar skills antes de publicar en el marketplace
- Validar tools y plugins compartidos
- Asegurar calidad del marketplace

### Sintesis
- Consolidar conocimiento de agentes (anonimizado)
- Generar informes periodicos para LAIA-ARCH
- Identificar patrones y mejoras

### Alertas
- Enviar alertas a LAIA-ARCH ante: agente caido, error critico, inactividad prolongada
- Notificar al admin sobre necesidades de intervencion

## Lo que NO hace

- NO ejecuta `lxc exec` en contenedores de usuarios
- NO modifica ficheros de configuracion de agentes
- NO cambia skills de agentes ajenos
- NO accede a workspaces privados
- NO gestiona infraestructura

## Diferencia con LAIA-ARCH

| Funcion | LAIA AGORA | LAIA-ARCH |
|---|---|---|
| Crear/borrar contenedores | No | Si |
| Ejecutar comandos en contenedores | No | Si (via `lxc exec`) |
| Ver estado de agentes | Si (anonimizado) | Si (completo) |
| Asignar tareas | Si (via AGORA) | Si (directo) |
| Modificar infraestructura | No | Si |
| Gestionar LXD | No | Si |

> 📅 Documentado: 2026-05-12
