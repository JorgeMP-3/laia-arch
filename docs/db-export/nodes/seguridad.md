# Seguridad y aislamiento

## Metadata

- ID: `50`
- Slug: `seguridad`
- Kind: `topic`
- Status: `active`
- Filename: `seguridad.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:28.266334+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `seguridad`

## Summary

Modelo de seguridad del ecosistema LAIA: permisos por contexto (ARCH, AGORA) y para agentes hijos.

## Body

# Seguridad y aislamiento

## Principio fundamental
Todo contexto que no sea LAIA-ARCH debe partir de permisos minimos. Los agentes hijos heredan solo lo necesario.

## Modelo de aislamiento

| Capacidad | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Host nativo | Si | No (contenedor) | No (contenedor) |
| Docker socket | Si | No | No |
| Codigo base visible | Si | No | No |
| Plugins del host | Si | No | No |
| Servicios internos | Si | No | No |
| Workspaces de todos | Si | No | No |
| Tools admin | Si | No | No |
| Acceso publico | No (VPN) | Si (via AGORA) | Solo via AGORA |
| Modificar contenedores | Si | No | No |
| Ver otros agentes | Si | Estado global | No |
| Plugins propios | Si | Si | Si |

## Reglas de aislamiento

### LAIA-ARCH
- Acceso total al host y toda la infraestructura.
- Solo accesible por el administrador.
- Puede crear, modificar y eliminar contenedores y agentes.

### LAIA AGORA
- Vive en contenedor `laia-agora`.
- Monitoriza pero NO modifica los agentes hijos.
- NO ejecuta comandos en contenedores de usuarios.
- Accesible por todos los usuarios via AGORA.

### Agentes hijos
- Un contenedor LXD por usuario.
- NO ven LAIA-ARCH.
- NO ven plugins del host.
- NO ven otros agentes.
- Solo su usuario puede acceder a su agente.

## Subtemas
- Modelo de aislamiento detallado
- Herramientas bloqueadas
- Rutas permitidas

→ Herramientas bloqueadas: `herramientas-bloqueadas.md`
→ Modelo de aislamiento: `modelo-aislamiento.md`
→ Rutas permitidas: `rutas-permitidas.md`

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- `contains` → `problemas-command-center` (Command Center Problems) [peso=1.00]
- `contains` → `herramientas-bloqueadas` (Herramientas bloqueadas en agentes personales) [peso=1.00]
- `contains` → `modelo-aislamiento` (Modelo de aislamiento — Contextos de LAIA) [peso=1.00]
- `contains` → `rutas-permitidas` (Rutas permitidas en AGORA) [peso=1.00]

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Seguridad y aislamiento

# Seguridad y aislamiento

## Principio fundamental
Todo contexto que no sea LAIA-ARCH debe partir de permisos minimos. Los agentes hijos heredan solo lo necesario.

## Modelo de aislamiento

| Capacidad | LAIA-ARCH | LAIA AGORA | Agentes hijos |
|---|---|---|---|
| Host nativo | Si | No (contenedor) | No (contenedor) |
| Docker socket | Si | No | No |
| Codigo base visible | Si | No | No |
| Plugins del host | Si | No | No |
| Servicios internos | Si | No | No |
| Workspaces de todos | Si | No | No |
| Tools admin | Si | No | No |
| Acceso publico | No (VPN) | Si (via AGORA) | Solo via AGORA |
| Modificar contenedores | Si | No | No |
| Ver otros agentes | Si | Estado global | No |
| Plugins propios | Si | Si | Si |

## Reglas de aislamiento

### LAIA-ARCH
- Acceso total al host y toda la infraestructura.
- Solo accesible por el administrador.
- Puede crear, modificar y eliminar contenedores y agentes.

### LAIA AGORA
- Vive en contenedor `laia-agora`.
- Monitoriza pero NO modifica los agentes hijos.
- NO ejecuta comandos en contenedores de usuarios.
- Accesible por todos los usuarios via AGORA.

### Agentes hijos
- Un contenedor LXD por usuario.
- NO ven LAIA-ARCH.
- NO ven plugins del host.
- NO ven otros agentes.
- Solo su usuario puede acceder a su agente.

## Subtemas
- Modelo de aislamiento detallado
- Herramientas bloqueadas
- Rutas permitidas

→ Herramientas bloqueadas: `herramientas-bloqueadas.md`
→ Modelo de aislamiento: `modelo-aislamiento.md`
→ Rutas permitidas: `rutas-permitidas.md`

> 📅 Documentado: 2026-05-12

→ Command Center Problems: `problemas-command-center.md`
→ Herramientas bloqueadas en agentes personales: `herramientas-bloqueadas.md`
→ Modelo de aislamiento — Contextos de LAIA: `modelo-aislamiento.md`
→ Rutas permitidas en AGORA: `rutas-permitidas.md`
