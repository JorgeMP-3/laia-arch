# LAIA — Agente padre y contextos

## Metadata

- ID: `61`
- Slug: `modelo-ser-medios`
- Kind: `doc`
- Status: `active`
- Filename: `modelo-ser-medios.md`
- Parent: `modelo`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:52.276318+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `modelo-ser-medios`

## Summary

Definicion conceptual de LAIA como agente padre unico con dos contextos de permisos y agentes hijos por usuario.

## Body

# LAIA — Agente padre y contextos

## Tesis

LAIA es el agente padre del ecosistema. Opera en dos contextos de permisos: ARCH (admin total en host) y AGORA (coordinador en contenedor `laia-agora`). Los PA-AGORA son hijos de LAIA, uno por usuario.

## Separacion conceptual

| Capa | Significado |
|---|---|
| LAIA | Agente padre unico, identidad del ecosistema |
| Contexto LAIA-ARCH | Permisos totales: host, LXD, infraestructura. Solo admin. |
| Contexto AGORA | Permisos limitados: monitorizar, asignar tareas. Todos los usuarios. |
| Hijos | PA-AGORA editables en contenedores LXD |

## Los contextos de LAIA

### LAIA-ARCH — Contexto admin
- LAIA vive en el host nativo.
- Solo el administrador (Jorge) interactua con LAIA en este contexto.
- Control total: LXD, nginx, systemd, Docker, todos los contenedores.
- Desde aqui se gobierna `laia-agora` y los contenedores de usuarios.
- Herramientas sin restricciones.

### AGORA — Contexto coordinador
- LAIA vive en su propio contenedor LXD (`laia-agora`).
- Todos los usuarios interactuan con LAIA en este contexto a traves de la plataforma AGORA.
- Menos privilegios que en ARCH.
- Funciones: monitorizar el trabajo de los usuarios, asignar tareas, alertar a ARCH.
- **NO puede** modificar nada dentro de los contenedores de los usuarios.
- **NO puede** ejecutar comandos en los contenedores de los usuarios.
- **NO puede** acceder a herramientas de ARCH.

## Los agentes hijos

Cada usuario tiene un PA-AGORA (hijo de LAIA) en su propio contenedor LXD:
- El usuario le pone **nombre** (NO puede llamarse "LAIA", nombre reservado).
- El usuario puede editar: skills, comportamiento, memories, plugins propios.
- Los plugins del host (`/home/laia-hermes/LAIA/plugins/`) son **invisibles** para los hijos.
- Cada hijo tiene su propio `workspace.db` aislado.

## Lo que los usuarios NO ven
- LAIA-ARCH (no saben que existe)
- Los agentes de otros usuarios
- Los plugins del host
- La infraestructura (LXD, nginx, etc.)

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `modelo` (Modelo conceptual del ecosistema LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA — Agente padre y contextos

# LAIA — Agente padre y contextos

## Tesis

LAIA es el agente padre del ecosistema. Opera en dos contextos de permisos: ARCH (admin total en host) y AGORA (coordinador en contenedor `laia-agora`). Los PA-AGORA son hijos de LAIA, uno por usuario.

## Separacion conceptual

| Capa | Significado |
|---|---|
| LAIA | Agente padre unico, identidad del ecosistema |
| Contexto LAIA-ARCH | Permisos totales: host, LXD, infraestructura. Solo admin. |
| Contexto AGORA | Permisos limitados: monitorizar, asignar tareas. Todos los usuarios. |
| Hijos | PA-AGORA editables en contenedores LXD |

## Los contextos de LAIA

### LAIA-ARCH — Contexto admin
- LAIA vive en el host nativo.
- Solo el administrador (Jorge) interactua con LAIA en este contexto.
- Control total: LXD, nginx, systemd, Docker, todos los contenedores.
- Desde aqui se gobierna `laia-agora` y los contenedores de usuarios.
- Herramientas sin restricciones.

### AGORA — Contexto coordinador
- LAIA vive en su propio contenedor LXD (`laia-agora`).
- Todos los usuarios interactuan con LAIA en este contexto a traves de la plataforma AGORA.
- Menos privilegios que en ARCH.
- Funciones: monitorizar el trabajo de los usuarios, asignar tareas, alertar a ARCH.
- **NO puede** modificar nada dentro de los contenedores de los usuarios.
- **NO puede** ejecutar comandos en los contenedores de los usuarios.
- **NO puede** acceder a herramientas de ARCH.

## Los agentes hijos

Cada usuario tiene un PA-AGORA (hijo de LAIA) en su propio contenedor LXD:
- El usuario le pone **nombre** (NO puede llamarse "LAIA", nombre reservado).
- El usuario puede editar: skills, comportamiento, memories, plugins propios.
- Los plugins del host (`/home/laia-hermes/LAIA/plugins/`) son **invisibles** para los hijos.
- Cada hijo tiene su propio `workspace.db` aislado.

## Lo que los usuarios NO ven
- LAIA-ARCH (no saben que existe)
- Los agentes de otros usuarios
- Los plugins del host
- La infraestructura (LXD, nginx, etc.)

> 📅 Documentado: 2026-05-12
