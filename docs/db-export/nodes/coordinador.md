# LAIA AGORA — Coordinador

## Metadata

- ID: `63`
- Slug: `coordinador`
- Kind: `topic`
- Status: `active`
- Filename: `coordinador.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:52.760405+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `coordinador`

## Summary

LAIA en su contexto AGORA: coordinador que monitoriza, asigna trabajo y alerta a ARCH. Vive en el contenedor laia-agora.

## Body

# LAIA AGORA — Coordinador

## Estado
EN DESARROLLO — Backend con endpoint `/api/coordinator/report` funcional. Logica completa pendiente de area de trabajo tipo ClickUp.

## Que es LAIA AGORA

LAIA AGORA es el mismo agente LAIA pero ejecutandose en su propio contenedor LXD (`laia-agora`) con un conjunto reducido de permisos. Es el coordinador del ecosistema: el agente con el que interactuan todos los usuarios a traves de la plataforma AGORA.

## Donde vive

- **Contenedor LXD**: `laia-agora`
- **NO vive en el host** como LAIA-ARCH. Es una instancia separada.
- Los usuarios normales solo conocen a LAIA AGORA. No saben que existe LAIA-ARCH.

## Funciones

### Monitorizacion
- Detectar PA-AGORA bloqueados o inactivos
- Ver el estado global de todas las tareas
- Identificar patrones y anomalias

### Asignacion de trabajo
- Publicar tareas en la plataforma AGORA
- Priorizar backlog visible para los usuarios
- (Futuro: integracion con area de trabajo tipo ClickUp)

### Alertas
- Enviar alertas a LAIA-ARCH cuando algo requiere atencion
- Notificar al admin sobre agentes caidos o errores

### Marketplace
- Gestionar el marketplace de skills
- Validar skills antes de publicarlas

## Lo que LAIA AGORA NO puede hacer

- **NO** ejecutar comandos dentro del contenedor de ningun usuario
- **NO** modificar ficheros de los PA-AGORA
- **NO** acceder a herramientas de ARCH
- **NO** gestionar infraestructura (LXD, nginx, etc.)
- **NO** crear ni borrar contenedores
- **NO** ver los workspaces privados de los usuarios

## Delegacion

El admin (desde LAIA-ARCH) puede delegar el acceso a LAIA AGORA a otros usuarios con rol `agora_admin` para que puedan ver el panel de coordinacion.

## Comunicacion

LAIA AGORA se comunica con:
- **LAIA-ARCH**: alertas y reportes (unidireccional: AGORA → ARCH)
- **AGORA (plataforma)**: publica tareas, recibe estado de usuarios (bidireccional via API)

LAIA AGORA NUNCA se comunica directamente con los contenedores de los usuarios. Toda interaccion pasa por la plataforma AGORA.

→ Funciones detalladas: `coordinador-funciones.md`
→ Protocolo de comunicacion: `coordinador-protocolo.md`

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- `contains` → `agent-behavior` (Agent Behavior — General) [peso=1.00]
- `contains` → `agent-team` (Agent Team — doyouwin) [peso=1.00]
- `contains` → `coordinador-funciones` (LAIA AGORA — Funciones) [peso=1.00]
- `contains` → `coordinador-protocolo` (LAIA AGORA — Protocolo de comunicacion) [peso=1.00]
- `contains` → `coordinador-agentes` (Plan de documentacion multi-agente) [peso=1.00]

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA AGORA — Coordinador

# LAIA AGORA — Coordinador

## Estado
EN DESARROLLO — Backend con endpoint `/api/coordinator/report` funcional. Logica completa pendiente de area de trabajo tipo ClickUp.

## Que es LAIA AGORA

LAIA AGORA es el mismo agente LAIA pero ejecutandose en su propio contenedor LXD (`laia-agora`) con un conjunto reducido de permisos. Es el coordinador del ecosistema: el agente con el que interactuan todos los usuarios a traves de la plataforma AGORA.

## Donde vive

- **Contenedor LXD**: `laia-agora`
- **NO vive en el host** como LAIA-ARCH. Es una instancia separada.
- Los usuarios normales solo conocen a LAIA AGORA. No saben que existe LAIA-ARCH.

## Funciones

### Monitorizacion
- Detectar PA-AGORA bloqueados o inactivos
- Ver el estado global de todas las tareas
- Identificar patrones y anomalias

### Asignacion de trabajo
- Publicar tareas en la plataforma AGORA
- Priorizar backlog visible para los usuarios
- (Futuro: integracion con area de trabajo tipo ClickUp)

### Alertas
- Enviar alertas a LAIA-ARCH cuando algo requiere atencion
- Notificar al admin sobre agentes caidos o errores

### Marketplace
- Gestionar el marketplace de skills
- Validar skills antes de publicarlas

## Lo que LAIA AGORA NO puede hacer

- **NO** ejecutar comandos dentro del contenedor de ningun usuario
- **NO** modificar ficheros de los PA-AGORA
- **NO** acceder a herramientas de ARCH
- **NO** gestionar infraestructura (LXD, nginx, etc.)
- **NO** crear ni borrar contenedores
- **NO** ver los workspaces privados de los usuarios

## Delegacion

El admin (desde LAIA-ARCH) puede delegar el acceso a LAIA AGORA a otros usuarios con rol `agora_admin` para que puedan ver el panel de coordinacion.

## Comunicacion

LAIA AGORA se comunica con:
- **LAIA-ARCH**: alertas y reportes (unidireccional: AGORA → ARCH)
- **AGORA (plataforma)**: publica tareas, recibe estado de usuarios (bidireccional via API)

LAIA AGORA NUNCA se comunica directamente con los contenedores de los usuarios. Toda interaccion pasa por la plataforma AGORA.

→ Funciones detalladas: `coordinador-funciones.md`
→ Protocolo de comunicacion: `coordinador-protocolo.md`

> 📅 Documentado: 2026-05-12

→ Agent Behavior — General: `agent-behavior.md`
→ Agent Team — doyouwin: `agent-team.md`
→ LAIA AGORA — Funciones: `coordinador-funciones.md`
→ LAIA AGORA — Protocolo de comunicacion: `coordinador-protocolo.md`
→ Plan de documentacion multi-agente: `coordinador-agentes.md`
