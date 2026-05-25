# Aislamiento de agentes personales

## Metadata

- ID: `68`
- Slug: `agentes-aislamiento`
- Kind: `doc`
- Status: `active`
- Filename: `agentes-aislamiento.md`
- Parent: `agentes-personales`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:53.916469+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `agentes-aislamiento`

## Summary

Modelo de restricciones para agentes hijos: filesystem, red, tools, plugins y memoria aislados del host y de otros agentes.

## Body

# Aislamiento de PA-AGORA

## Principio
Cada PA-AGORA (hijo de LAIA) opera en su propio contenedor LXD con permisos minimos. No hereda herramientas ni plugins del host.

## Restricciones

### Filesystem
- Solo puede escribir en `/opt/laia/data/` y `/opt/laia/workspaces/`
- Lectura limitada a su workspace y runtime
- Sin acceso a directorios del sistema del host
- Sin acceso a `/home/laia-hermes/LAIA/`

### Red
- Sin acceso a puertos internos del host
- Solo acceso web externo (via NAT)
- Sin acceso a otros contenedores
- Subred privada 10.0.0.x

### Tools
- Sin terminal_tool con sudo
- Sin execute_code con subprocess
- Sin workspace tools de escritura global
- Sin herramientas de administracion
- Solo tools de lectura y productividad (ver `herramientas-bloqueadas.md`)

### Plugins
- **Plugins propios**: SI, el usuario puede instalar plugins dentro de su contenedor.
- **Plugins del host**: NO. Los plugins en `/home/laia-hermes/LAIA/plugins/` son **invisibles**.
- **workspace-context**: NO heredado. Cada agente tiene su propio workspace.db.

### Memoria
- Workspace.db propio y aislado en `/opt/laia/workspaces/personal/`
- Sin acceso a workspaces de otros usuarios
- Sin acceso a la memoria global de LAIA

### Entidades no visibles
- LAIA-ARCH (no saben que existe)
- Agentes de otros usuarios
- Plugins del host
- Infraestructura (LXD, nginx, etc.)

## Auditoria
Todas las acciones se registran en el workspace.db del agente y en events del sistema para revision por LAIA-ARCH si es necesario.

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Aislamiento de agentes personales

# Aislamiento de PA-AGORA

## Principio
Cada PA-AGORA (hijo de LAIA) opera en su propio contenedor LXD con permisos minimos. No hereda herramientas ni plugins del host.

## Restricciones

### Filesystem
- Solo puede escribir en `/opt/laia/data/` y `/opt/laia/workspaces/`
- Lectura limitada a su workspace y runtime
- Sin acceso a directorios del sistema del host
- Sin acceso a `/home/laia-hermes/LAIA/`

### Red
- Sin acceso a puertos internos del host
- Solo acceso web externo (via NAT)
- Sin acceso a otros contenedores
- Subred privada 10.0.0.x

### Tools
- Sin terminal_tool con sudo
- Sin execute_code con subprocess
- Sin workspace tools de escritura global
- Sin herramientas de administracion
- Solo tools de lectura y productividad (ver `herramientas-bloqueadas.md`)

### Plugins
- **Plugins propios**: SI, el usuario puede instalar plugins dentro de su contenedor.
- **Plugins del host**: NO. Los plugins en `/home/laia-hermes/LAIA/plugins/` son **invisibles**.
- **workspace-context**: NO heredado. Cada agente tiene su propio workspace.db.

### Memoria
- Workspace.db propio y aislado en `/opt/laia/workspaces/personal/`
- Sin acceso a workspaces de otros usuarios
- Sin acceso a la memoria global de LAIA

### Entidades no visibles
- LAIA-ARCH (no saben que existe)
- Agentes de otros usuarios
- Plugins del host
- Infraestructura (LXD, nginx, etc.)

## Auditoria
Todas las acciones se registran en el workspace.db del agente y en events del sistema para revision por LAIA-ARCH si es necesario.

> 📅 Documentado: 2026-05-12
