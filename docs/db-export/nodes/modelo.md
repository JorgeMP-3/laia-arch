# Modelo conceptual del ecosistema LAIA

## Metadata

- ID: `124`
- Slug: `modelo`
- Kind: `topic`
- Status: `active`
- Filename: `modelo.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T09:01:47.428856+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `modelo`

## Summary

LAIA como agente padre unico que opera en dos contextos (ARCH, AGORA) y tiene agentes hijos por usuario.

## Body

# Modelo conceptual del ecosistema LAIA

## Vision general

LAIA es un **agente padre unico** que opera en dos contextos de permisos distintos (LAIA-ARCH y LAIA-AGORA) y tiene agentes hijos por cada usuario.

## Conceptos clave

### LAIA (agente padre)
- Agente unico, no se duplica.
- Opera en contexto LAIA-LAIA-ARCH (host, admin total) y contexto AGORA (contenedor `laia-agora`, coordinador).
- LAIA-ARCH es la instancia que ve el admin; LAIA AGORA es la instancia que ven los usuarios.

### Contextos de LAIA

| Contexto | Nombre | Quien lo ve | Donde vive | Privilegios |
|---|---|---|---|---|
| Admin | LAIA-ARCH | Solo admin (Jorge) | Host nativo | Totales: LXD, nginx, sistema, Docker |
| Coordinador | LAIA AGORA | Todos los usuarios | Contenedor `laia-agora` | Monitoriza, asigna tareas, alerta. NO modifica hijos. |

### PA-AGORA (hijos de LAIA)
- Uno por usuario en su propio contenedor LXD (`laia-{usuario}`).
- El usuario elige el nombre de su agente (NO puede llamarse "LAIA").
- El usuario edita ficheros de comportamiento, skills, memories y plugins propios.
- No ven LAIA-ARCH ni los plugins del host.

### Separacion conceptual

| Capa | Significado |
|---|---|
| Agente padre | LAIA: unico, opera en dos contextos |
| Contexto | ARCH (admin) y AGORA (coordinador) |
| Hijos | PA-AGORA editables por usuario |
| Permisos | Capacidades concretas segun contexto |
| Memoria | Workspace.db propio y aislado por agente |

## Reglas fundamentales

1. LAIA no es "un ser que se expresa por medios". Es un agente padre con contextos.
2. LAIA-ARCH y LAIA-AGORA no son "medios" separados. Son contextos de permisos de LAIA.
3. Los PA-AGORA no son "medios de LAIA". Son hijos de LAIA.
4. Solo existe una identidad LAIA; los contextos cambian los permisos, no la identidad.

→ LAIA como agente padre y sus contextos: `modelo-ser-medios.md`
→ Vision general del ecosistema: `vision-general.md`
→ Modelo de aislamiento: `modelo-aislamiento.md`

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- `contains` → `modelo-ser-medios` (LAIA — Agente padre y contextos) [peso=1.00]
- `contains` → `vision-general` (Vision general del ecosistema LAIA) [peso=1.00]

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Modelo conceptual del ecosistema LAIA

# Modelo conceptual del ecosistema LAIA

## Vision general

LAIA es un **agente padre unico** que opera en dos contextos de permisos distintos (LAIA-ARCH y LAIA-AGORA) y tiene agentes hijos por cada usuario.

## Conceptos clave

### LAIA (agente padre)
- Agente unico, no se duplica.
- Opera en contexto LAIA-LAIA-ARCH (host, admin total) y contexto AGORA (contenedor `laia-agora`, coordinador).
- LAIA-ARCH es la instancia que ve el admin; LAIA AGORA es la instancia que ven los usuarios.

### Contextos de LAIA

| Contexto | Nombre | Quien lo ve | Donde vive | Privilegios |
|---|---|---|---|---|
| Admin | LAIA-ARCH | Solo admin (Jorge) | Host nativo | Totales: LXD, nginx, sistema, Docker |
| Coordinador | LAIA AGORA | Todos los usuarios | Contenedor `laia-agora` | Monitoriza, asigna tareas, alerta. NO modifica hijos. |

### PA-AGORA (hijos de LAIA)
- Uno por usuario en su propio contenedor LXD (`laia-{usuario}`).
- El usuario elige el nombre de su agente (NO puede llamarse "LAIA").
- El usuario edita ficheros de comportamiento, skills, memories y plugins propios.
- No ven LAIA-ARCH ni los plugins del host.

### Separacion conceptual

| Capa | Significado |
|---|---|
| Agente padre | LAIA: unico, opera en dos contextos |
| Contexto | ARCH (admin) y AGORA (coordinador) |
| Hijos | PA-AGORA editables por usuario |
| Permisos | Capacidades concretas segun contexto |
| Memoria | Workspace.db propio y aislado por agente |

## Reglas fundamentales

1. LAIA no es "un ser que se expresa por medios". Es un agente padre con contextos.
2. LAIA-ARCH y LAIA-AGORA no son "medios" separados. Son contextos de permisos de LAIA.
3. Los PA-AGORA no son "medios de LAIA". Son hijos de LAIA.
4. Solo existe una identidad LAIA; los contextos cambian los permisos, no la identidad.

→ LAIA como agente padre y sus contextos: `modelo-ser-medios.md`
→ Vision general del ecosistema: `vision-general.md`
→ Modelo de aislamiento: `modelo-aislamiento.md`

> 📅 Documentado: 2026-05-12

→ LAIA — Agente padre y contextos: `modelo-ser-medios.md`
→ Vision general del ecosistema LAIA: `vision-general.md`
