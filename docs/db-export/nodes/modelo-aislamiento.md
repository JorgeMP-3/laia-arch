# Modelo de aislamiento — Contextos de LAIA

## Metadata

- ID: `51`
- Slug: `modelo-aislamiento`
- Kind: `doc`
- Status: `active`
- Filename: `modelo-aislamiento.md`
- Parent: `seguridad`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:28.533091+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `modelo-aislamiento`

## Summary

Comparativa detallada de permisos y aislamiento entre los contextos de LAIA y los agentes hijos.

## Body

# Modelo de aislamiento — Contextos de LAIA

## Principio
LAIA mantiene una identidad unica como agente padre, pero cada contexto de operacion (ARCH, AGORA) y cada agente hijo tiene permisos distintos.

## Tabla comparativa

| Capacidad | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Host nativo | Si | No | No |
| Docker socket | Si | No | No |
| Codigo base visible | Si | No | No |
| Plugins del host | Si | No | No |
| Servicios internos host | Si | No | No |
| Workspaces de todos | Si | Lectura anonimizada | No |
| Workspace propio | Si | Si | Si |
| Tools admin | Si | No | No |
| Tools productividad | Si | Si | Limitadas |
| Crear/borrar contenedores | Si | No | No |
| Ejecutar comandos en otros contenedores | Si | No | No |
| Modificar agentes ajenos | Si | No | No |
| Marketplace skills | Si | Gestiona | Consume |
| Acceso publico | No (VPN) | Si (via AGORA) | Via AGORA |
| Ver LAIA-ARCH | Si | Si | No |

## Aislamiento de plugins

| Plugins | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Plugins del host (`/home/laia-hermes/LAIA/plugins/`) | Si | No | No |
| Plugins propios del contenedor | N/A (host) | Si | Si |

## Reglas de propiedad

- `usuario jorge` → contenedor `laia-jorge` → PA-AGORA de Jorge
- `usuario maria` → contenedor `laia-maria` → PA-AGORA de Maria
- `laia-agora` → contenedor del coordinador → gestionado por LAIA-ARCH
- AGORA siempre debe validar la relacion usuario-contenedor antes de cualquier operacion.

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `seguridad` (Seguridad y aislamiento) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Modelo de aislamiento — Contextos de LAIA

# Modelo de aislamiento — Contextos de LAIA

## Principio
LAIA mantiene una identidad unica como agente padre, pero cada contexto de operacion (ARCH, AGORA) y cada agente hijo tiene permisos distintos.

## Tabla comparativa

| Capacidad | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Host nativo | Si | No | No |
| Docker socket | Si | No | No |
| Codigo base visible | Si | No | No |
| Plugins del host | Si | No | No |
| Servicios internos host | Si | No | No |
| Workspaces de todos | Si | Lectura anonimizada | No |
| Workspace propio | Si | Si | Si |
| Tools admin | Si | No | No |
| Tools productividad | Si | Si | Limitadas |
| Crear/borrar contenedores | Si | No | No |
| Ejecutar comandos en otros contenedores | Si | No | No |
| Modificar agentes ajenos | Si | No | No |
| Marketplace skills | Si | Gestiona | Consume |
| Acceso publico | No (VPN) | Si (via AGORA) | Via AGORA |
| Ver LAIA-ARCH | Si | Si | No |

## Aislamiento de plugins

| Plugins | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Plugins del host (`/home/laia-hermes/LAIA/plugins/`) | Si | No | No |
| Plugins propios del contenedor | N/A (host) | Si | Si |

## Reglas de propiedad

- `usuario jorge` → contenedor `laia-jorge` → PA-AGORA de Jorge
- `usuario maria` → contenedor `laia-maria` → PA-AGORA de Maria
- `laia-agora` → contenedor del coordinador → gestionado por LAIA-ARCH
- AGORA siempre debe validar la relacion usuario-contenedor antes de cualquier operacion.

> 📅 Documentado: 2026-05-12
