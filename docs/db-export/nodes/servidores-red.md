# Servidores y Red

## Metadata

- ID: `117`
- Slug: `servidores-red`
- Kind: `topic`
- Status: `active`
- Filename: `servidores-red.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T08:49:11.075854+00:00`
- Updated at: `2026-05-08T09:03:49.018736+00:00`
- Aliases: `servidores-red`

## Summary

Configuración de servidores, red, nginx, cloudflare, docker

## Body

# Servidores y Red

## Descripción

Configuración completa de la infraestructura de servidores y red del ecosistema LAIA. Incluye nginx, cloudflare, docker y todos los servicios del sistema.

## Arquitectura de red

```
Internet
   │
   ▼
Cloudflare (DNS + SSL)
   │
   ▼
cloudflared (túnel cifrado)
   │
   ▼
nginx (reverse proxy)
   │
   ├── laiajmp.org → Arete backend
   ├── app.laiajmp.org → API
   ├── tienda.laiajmp.org → WordPress
   └── workspace-ui → :8077
```

## Servicios principales

| Servicio | Puerto | Descripción |
|---|---|---|
| nginx | 80/443 | Reverse proxy |
| Workspace UI | 8077 | Interfaz web |
| PostgreSQL | 5432 | Base de datos |
| Docker | - | Contenedores |
| cloudflared | - | Túnel Cloudflare |

## Documentos incluidos

### Infraestructura base
- **infra-arquitectura**: Diagrama y visión general del stack
- **infra-servicios**: Todos los servicios, puertos y comandos
- **infra-nginx**: Configuración del reverse proxy
- **infra-cloudflare**: Tunnel y dominios
- **cloudflare-nginx**: Configuración combinada

### Docker y contenedores
- **infra-docker**: WordPress y contenedores
- **docker-host**: Configuración del servidor Dell 9020

### Operaciones
- **infra-arranque**: Cómo arranca todo al encender
- **infra-mantenimiento**: Guía de operaciones del día a día
- **infra-samba**: Acceso desde Mac por SMB

### Configuración
- **infra-laia-arch**: Hermes, workspace-ui y estructura git
- **infra-migracion**: Registro de migración de usuario
- **infraestructura-puertos-recursos**: Mapa de puertos y recursos
- **infra-tool-ui-architecture**: Arquitectura UI profesional

### Herramientas
- **laia-tools**: Suite de herramientas CLI
- **laia-tools-plan**: Plan de mejora y nuevas herramientas


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- `contains` → `infra-samba` (Acceso SMB/Samba) [peso=1.00]
- `contains` → `infra-arquitectura` (Arquitectura del Servidor) [peso=1.00]
- `contains` → `infra-cloudflare` (Cloudflare Tunnel) [peso=1.00]
- `contains` → `cloudflare-nginx` (Cloudflare Tunnel + nginx) [peso=1.00]
- `contains` → `infra-nginx` (Configuración nginx) [peso=1.00]
- `contains` → `docker-host` (Docker Host — Dell 9020) [peso=1.00]
- `contains` → `infra-docker` (Docker y Contenedores) [peso=1.00]
- `contains` → `infra-mantenimiento` (Guía de Mantenimiento) [peso=1.00]
- `contains` → `infraestructura-puertos-recursos` (Infraestructura, puertos y recursos) [peso=1.00]
- `contains` → `infra-laia-arch` (LAIA-ARCH Configuración) [peso=1.00]
- `contains` → `infra-migracion` (Migración familiamp) [peso=1.00]
- `contains` → `infra-arranque` (Proceso de Arranque) [peso=1.00]
- `contains` → `infra-servicios` (Servicios y Puertos) [peso=1.00]
- `contains` → `infra-tool-ui-architecture` (Tool UI Architecture) [peso=1.00]

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Servidores y Red

# Servidores y Red

## Descripción

Configuración completa de la infraestructura de servidores y red del ecosistema LAIA. Incluye nginx, cloudflare, docker y todos los servicios del sistema.

## Arquitectura de red

```
Internet
   │
   ▼
Cloudflare (DNS + SSL)
   │
   ▼
cloudflared (túnel cifrado)
   │
   ▼
nginx (reverse proxy)
   │
   ├── laiajmp.org → Arete backend
   ├── app.laiajmp.org → API
   ├── tienda.laiajmp.org → WordPress
   └── workspace-ui → :8077
```

## Servicios principales

| Servicio | Puerto | Descripción |
|---|---|---|
| nginx | 80/443 | Reverse proxy |
| Workspace UI | 8077 | Interfaz web |
| PostgreSQL | 5432 | Base de datos |
| Docker | - | Contenedores |
| cloudflared | - | Túnel Cloudflare |

## Documentos incluidos

### Infraestructura base
- **infra-arquitectura**: Diagrama y visión general del stack
- **infra-servicios**: Todos los servicios, puertos y comandos
- **infra-nginx**: Configuración del reverse proxy
- **infra-cloudflare**: Tunnel y dominios
- **cloudflare-nginx**: Configuración combinada

### Docker y contenedores
- **infra-docker**: WordPress y contenedores
- **docker-host**: Configuración del servidor Dell 9020

### Operaciones
- **infra-arranque**: Cómo arranca todo al encender
- **infra-mantenimiento**: Guía de operaciones del día a día
- **infra-samba**: Acceso desde Mac por SMB

### Configuración
- **infra-laia-arch**: Hermes, workspace-ui y estructura git
- **infra-migracion**: Registro de migración de usuario
- **infraestructura-puertos-recursos**: Mapa de puertos y recursos
- **infra-tool-ui-architecture**: Arquitectura UI profesional

### Herramientas
- **laia-tools**: Suite de herramientas CLI
- **laia-tools-plan**: Plan de mejora y nuevas herramientas


> 📅 Documentado: 2026-05-08

→ Acceso SMB/Samba: `infra-samba.md`
→ Arquitectura del Servidor: `infra-arquitectura.md`
→ Cloudflare Tunnel: `infra-cloudflare.md`
→ Cloudflare Tunnel + nginx: `cloudflare-nginx.md`
→ Configuración nginx: `infra-nginx.md`
→ Docker Host — Dell 9020: `docker-host.md`
→ Docker y Contenedores: `infra-docker.md`
→ Guía de Mantenimiento: `infra-mantenimiento.md`
→ Infraestructura, puertos y recursos: `infraestructura-puertos-recursos.md`
→ LAIA-ARCH Configuración: `infra-laia-arch.md`
→ Migración familiamp: `infra-migracion.md`
→ Proceso de Arranque: `infra-arranque.md`
→ Servicios y Puertos: `infra-servicios.md`
→ Tool UI Architecture: `infra-tool-ui-architecture.md`
