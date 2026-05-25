# LAIA AGORA — Protocolo de comunicacion

## Metadata

- ID: `65`
- Slug: `coordinador-protocolo`
- Kind: `doc`
- Status: `active`
- Filename: `coordinador-protocolo.md`
- Parent: `coordinador`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:53.173120+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `coordinador-protocolo`

## Summary

Protocolo de comunicacion entre LAIA AGORA, LAIA ARCH y la plataforma AGORA.

## Body

# LAIA AGORA — Protocolo de comunicacion

## Canales de comunicacion

| Origen | Destino | Metodo | Proposito |
|---|---|---|---|
| LAIA AGORA | LAIA-ARCH | Alertas internas | Supervison, alertas criticas |
| LAIA-ARCH | LAIA AGORA | Instrucciones directas | Cambios de configuracion, prioridades |
| LAIA AGORA | AGORA (plataforma) | API REST | Publicar tareas, actualizar marketplace |
| AGORA (usuarios) | LAIA AGORA | API REST | Reportar estado de tareas, actividad |
| Usuarios | Agentes hijos | Via AGORA | Gestionar su PA-AGORA |

## Lo que NO existe

LAIA AGORA NO se comunica directamente con los contenedores de los usuarios. No hay canal:
- LAIA AGORA → contenedor `laia-maria` (NO EXISTE)
- LAIA AGORA → ejecutar comandos en agentes (NO EXISTE)

## Formato de mensajes

### Alerta (LAIA AGORA → LAIA-ARCH)
```json
{
    "type": "alert",
    "severity": "warning|critical",
    "agent": "laia-maria",
    "message": "Agente inactivo por mas de 3 horas",
    "timestamp": "2026-05-12T10:00:00Z"
}
```

### Tarea publicada (LAIA AGORA → AGORA)
```json
{
    "type": "task_published",
    "task_id": "task_abc123",
    "title": "Actualizar documentacion del proyecto X",
    "priority": "medium",
    "assignee": null,
    "visible_to": "all"
}
```

### Reporte de estado (AGORA → LAIA AGORA)
```json
{
    "type": "task_update",
    "task_id": "task_abc123",
    "user_id": "maria",
    "status": "done",
    "timestamp": "2026-05-12T11:00:00Z"
}
```

## Reglas

1. LAIA AGORA nunca expone informacion de LAIA-ARCH a los usuarios.
2. LAIA AGORA filtra y anonimiza antes de compartir datos entre usuarios.
3. Toda comunicacion con contenedores de usuarios es mediada por AGORA (plataforma), nunca directa.

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `coordinador` (LAIA AGORA — Coordinador) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA AGORA — Protocolo de comunicacion

# LAIA AGORA — Protocolo de comunicacion

## Canales de comunicacion

| Origen | Destino | Metodo | Proposito |
|---|---|---|---|
| LAIA AGORA | LAIA-ARCH | Alertas internas | Supervison, alertas criticas |
| LAIA-ARCH | LAIA AGORA | Instrucciones directas | Cambios de configuracion, prioridades |
| LAIA AGORA | AGORA (plataforma) | API REST | Publicar tareas, actualizar marketplace |
| AGORA (usuarios) | LAIA AGORA | API REST | Reportar estado de tareas, actividad |
| Usuarios | Agentes hijos | Via AGORA | Gestionar su PA-AGORA |

## Lo que NO existe

LAIA AGORA NO se comunica directamente con los contenedores de los usuarios. No hay canal:
- LAIA AGORA → contenedor `laia-maria` (NO EXISTE)
- LAIA AGORA → ejecutar comandos en agentes (NO EXISTE)

## Formato de mensajes

### Alerta (LAIA AGORA → LAIA-ARCH)
```json
{
    "type": "alert",
    "severity": "warning|critical",
    "agent": "laia-maria",
    "message": "Agente inactivo por mas de 3 horas",
    "timestamp": "2026-05-12T10:00:00Z"
}
```

### Tarea publicada (LAIA AGORA → AGORA)
```json
{
    "type": "task_published",
    "task_id": "task_abc123",
    "title": "Actualizar documentacion del proyecto X",
    "priority": "medium",
    "assignee": null,
    "visible_to": "all"
}
```

### Reporte de estado (AGORA → LAIA AGORA)
```json
{
    "type": "task_update",
    "task_id": "task_abc123",
    "user_id": "maria",
    "status": "done",
    "timestamp": "2026-05-12T11:00:00Z"
}
```

## Reglas

1. LAIA AGORA nunca expone informacion de LAIA-ARCH a los usuarios.
2. LAIA AGORA filtra y anonimiza antes de compartir datos entre usuarios.
3. Toda comunicacion con contenedores de usuarios es mediada por AGORA (plataforma), nunca directa.

> 📅 Documentado: 2026-05-12
