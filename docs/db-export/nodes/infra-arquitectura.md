# Arquitectura del Servidor

## Metadata

- ID: `106`
- Slug: `infra-arquitectura`
- Kind: `doc`
- Status: `active`
- Filename: `infra-arquitectura.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:11.212761+00:00`
- Updated at: `2026-05-08T08:35:11.212761+00:00`
- Aliases: `infra-arquitectura`

## Summary

Internet

## Body

# Arquitectura del servidor

## Diagrama de flujo

```
Internet
   │
   ▼
Cloudflare (DNS + SSL)
   │  túnel cifrado HTTPS
   ▼
cloudflared (servicio nativo)
   │  reenvía a localhost:80
   ▼
nginx 1.24 (reverse proxy nativo)
   │
   ├── laiajmp.org / www.laiajmp.org
   │       │  archivos estáticos (React/Vite)
   │       ├── /api/*  ──────────────► arete-backend :8000  (PM2/Node.js)
   │       ├── /auth/* ──────────────► arete-backend :8000
   │       └── /*      ──────────────► dist/ (SPA, index.html fallback)
   │
   ├── app.laiajmp.org
   │       └── /*      ──────────────► arete-backend :8000  (API para app escritorio)
   │
   ├── tienda.laiajmp.org
   │       └── /*      ──────────────► WordPress Docker :9000
   │
   └── presentaciones.laiajmp.org
           └── 404 (pendiente de configurar)

Servicios internos (no expuestos por nginx):
   workspace-ui  :8077   (FastAPI/uvicorn — acceso interno)
   hermes gateway        (host network)
   adminer (phpMyAdmin para WordPress) :9001
   phpmyadmin  :9001
   postgresql  :5432
```

## Filosofía de despliegue

- **Todo nativo excepto WordPress.** Arete (backend + frontend), Hermes, workspace-ui y nginx corren directamente en el sistema operativo sin Docker.
- **Docker solo para WordPress** porque requiere MySQL + phpMyAdmin + WordPress juntos y no vale la pena instalarlos de forma nativa.
- **Cloudflare Tunnel** en lugar de abrir puertos en el router. El servidor no expone nada directamente a internet — todo el tráfico entra cifrado por el túnel.
- **nginx como único punto de entrada** en :80. Cloudflare envía todo a localhost:80 y nginx decide a qué servicio enrutar según el dominio (Host header).

## Stack de software

| Componente | Tecnología | Versión |
|---|---|---|
| OS | Linux Mint / Ubuntu 24.04 | Noble |
| Node.js | nvm | v22.22.2 |
| Python | sistema | 3.12.3 |
| Nginx | apt | 1.24.0 |
| PostgreSQL | apt | 16.13 |
| Docker | apt | 29.4.2 |
| PM2 | npm global | 6.0.14 |
| cloudflared | apt (Cloudflare repo) | 2026.3.0 |
| Hermes | venv pip | v0.11.0 (2026.4.23) |


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Arquitectura del Servidor

# Arquitectura del servidor

## Diagrama de flujo

```
Internet
   │
   ▼
Cloudflare (DNS + SSL)
   │  túnel cifrado HTTPS
   ▼
cloudflared (servicio nativo)
   │  reenvía a localhost:80
   ▼
nginx 1.24 (reverse proxy nativo)
   │
   ├── laiajmp.org / www.laiajmp.org
   │       │  archivos estáticos (React/Vite)
   │       ├── /api/*  ──────────────► arete-backend :8000  (PM2/Node.js)
   │       ├── /auth/* ──────────────► arete-backend :8000
   │       └── /*      ──────────────► dist/ (SPA, index.html fallback)
   │
   ├── app.laiajmp.org
   │       └── /*      ──────────────► arete-backend :8000  (API para app escritorio)
   │
   ├── tienda.laiajmp.org
   │       └── /*      ──────────────► WordPress Docker :9000
   │
   └── presentaciones.laiajmp.org
           └── 404 (pendiente de configurar)

Servicios internos (no expuestos por nginx):
   workspace-ui  :8077   (FastAPI/uvicorn — acceso interno)
   hermes gateway        (host network)
   adminer (phpMyAdmin para WordPress) :9001
   phpmyadmin  :9001
   postgresql  :5432
```

## Filosofía de despliegue

- **Todo nativo excepto WordPress.** Arete (backend + frontend), Hermes, workspace-ui y nginx corren directamente en el sistema operativo sin Docker.
- **Docker solo para WordPress** porque requiere MySQL + phpMyAdmin + WordPress juntos y no vale la pena instalarlos de forma nativa.
- **Cloudflare Tunnel** en lugar de abrir puertos en el router. El servidor no expone nada directamente a internet — todo el tráfico entra cifrado por el túnel.
- **nginx como único punto de entrada** en :80. Cloudflare envía todo a localhost:80 y nginx decide a qué servicio enrutar según el dominio (Host header).

## Stack de software

| Componente | Tecnología | Versión |
|---|---|---|
| OS | Linux Mint / Ubuntu 24.04 | Noble |
| Node.js | nvm | v22.22.2 |
| Python | sistema | 3.12.3 |
| Nginx | apt | 1.24.0 |
| PostgreSQL | apt | 16.13 |
| Docker | apt | 29.4.2 |
| PM2 | npm global | 6.0.14 |
| cloudflared | apt (Cloudflare repo) | 2026.3.0 |
| Hermes | venv pip | v0.11.0 (2026.4.23) |


> 📅 Documentado: 2026-05-08
