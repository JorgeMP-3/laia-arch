# Vision general del ecosistema LAIA

## Metadata

- ID: `62`
- Slug: `vision-general`
- Kind: `doc`
- Status: `active`
- Filename: `vision-general.md`
- Parent: `modelo`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:52.537417+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `vision-general`

## Summary

Vision estrategica del ecosistema: agente padre unico, contextos ARCH/AGORA y agentes hijos por usuario.

## Body

# Vision general del ecosistema LAIA

## Concepto

LAIA es un ecosistema de agentes con un agente padre unico que opera en dos contextos de permisos (LAIA-ARCH y LAIA-AGORA) y tiene agentes hijos personales por cada usuario.

## Arquitectura

```
LAIA (agente padre)
├── Contexto LAIA-ARCH: host nativo, admin total, solo Jorge
└── Contexto AGORA: contenedor laia-agora, coordinador, todos los usuarios
    │
    ├── Agente hijo "Nombrix" (laia-jorge)
    ├── Agente hijo "MariaBot" (laia-maria)
    └── Agente hijo "CarlosAI" (laia-carlos)
```

## Entidades

| Entidad | Descripcion | Acceso |
|---|---|---|
| LAIA-ARCH | Agente padre en contexto admin. Host nativo, todas las herramientas. | Solo admin |
| LAIA AGORA | Agente padre en contexto coordinador. Contenedor `laia-agora`. Monitoriza, no modifica. | Todos los usuarios |
| Agentes hijos | Uno por usuario, en contenedor LXD. Nombre editable, skills/comportamiento/memories/plugins propios. | Su propio usuario |
| AGORA | Plataforma web donde los usuarios gestionan su agente y ven tareas de LAIA AGORA. | Todos los usuarios |

## Nucleo tecnico

**Hermes Agent** es el motor base creado por Nous Research. Es la tecnologia comun que comparten todos los agentes del ecosistema.

## Reglas

1. LAIA es el unico agente padre. No se duplica.
2. Ningun PA-AGORA puede llamarse "LAIA".
3. LAIA AGORA monitoriza pero NO modifica los contenedores de los usuarios.
4. Los agentes hijos NO ven los plugins del host.
5. Los agentes hijos NO ven LAIA-ARCH.

## Vision a futuro

1. **LAIA-ARCH**: Mantener como contexto admin seguro y estable.
2. **LAIA AGORA**: Evolucionar como coordinador autonomo de equipos.
3. **Agentes hijos**: Permitir personalizacion profunda (skills, comportamiento, plugins propios).
4. **AGORA**: Completar la plataforma web con marketplace de skills y gestion de tareas.

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `modelo` (Modelo conceptual del ecosistema LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Vision general del ecosistema LAIA

# Vision general del ecosistema LAIA

## Concepto

LAIA es un ecosistema de agentes con un agente padre unico que opera en dos contextos de permisos (LAIA-ARCH y LAIA-AGORA) y tiene agentes hijos personales por cada usuario.

## Arquitectura

```
LAIA (agente padre)
├── Contexto LAIA-ARCH: host nativo, admin total, solo Jorge
└── Contexto AGORA: contenedor laia-agora, coordinador, todos los usuarios
    │
    ├── Agente hijo "Nombrix" (laia-jorge)
    ├── Agente hijo "MariaBot" (laia-maria)
    └── Agente hijo "CarlosAI" (laia-carlos)
```

## Entidades

| Entidad | Descripcion | Acceso |
|---|---|---|
| LAIA-ARCH | Agente padre en contexto admin. Host nativo, todas las herramientas. | Solo admin |
| LAIA AGORA | Agente padre en contexto coordinador. Contenedor `laia-agora`. Monitoriza, no modifica. | Todos los usuarios |
| Agentes hijos | Uno por usuario, en contenedor LXD. Nombre editable, skills/comportamiento/memories/plugins propios. | Su propio usuario |
| AGORA | Plataforma web donde los usuarios gestionan su agente y ven tareas de LAIA AGORA. | Todos los usuarios |

## Nucleo tecnico

**Hermes Agent** es el motor base creado por Nous Research. Es la tecnologia comun que comparten todos los agentes del ecosistema.

## Reglas

1. LAIA es el unico agente padre. No se duplica.
2. Ningun PA-AGORA puede llamarse "LAIA".
3. LAIA AGORA monitoriza pero NO modifica los contenedores de los usuarios.
4. Los agentes hijos NO ven los plugins del host.
5. Los agentes hijos NO ven LAIA-ARCH.

## Vision a futuro

1. **LAIA-ARCH**: Mantener como contexto admin seguro y estable.
2. **LAIA AGORA**: Evolucionar como coordinador autonomo de equipos.
3. **Agentes hijos**: Permitir personalizacion profunda (skills, comportamiento, plugins propios).
4. **AGORA**: Completar la plataforma web con marketplace de skills y gestion de tareas.

> 📅 Documentado: 2026-05-12
