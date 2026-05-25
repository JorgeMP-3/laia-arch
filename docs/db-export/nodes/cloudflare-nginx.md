# Cloudflare Tunnel + nginx

## Metadata

- ID: `48`
- Slug: `cloudflare-nginx`
- Kind: `doc`
- Status: `active`
- Filename: `cloudflare-nginx.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:27.843407+00:00`
- Updated at: `2026-05-08T08:04:27.843407+00:00`
- Aliases: `cloudflare-nginx`

## Summary

Configuración de acceso externo seguro

## Body

# Cloudflare Tunnel + nginx

## Arquitectura
```
Internet → Cloudflare → Tunnel → nginx → Servicios locales
```

## Cloudflare Tunnel
- Acceso seguro sin exponer puertos
- Autenticación en Cloudflare
- SSL automático

## nginx
- Proxy inverso para servicios locales
- Configuración en ~/LAIA/nginx/
- Endpoints:
  - / → Workspace UI (8077)
  - /api → Backend API
  - /ws → WebSockets

## Dominios
- laiajmp.org → App principal (AGORA)
- Configuración en Cloudflare DNS


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Cloudflare Tunnel + nginx

# Cloudflare Tunnel + nginx

## Arquitectura
```
Internet → Cloudflare → Tunnel → nginx → Servicios locales
```

## Cloudflare Tunnel
- Acceso seguro sin exponer puertos
- Autenticación en Cloudflare
- SSL automático

## nginx
- Proxy inverso para servicios locales
- Configuración en ~/LAIA/nginx/
- Endpoints:
  - / → Workspace UI (8077)
  - /api → Backend API
  - /ws → WebSockets

## Dominios
- laiajmp.org → App principal (AGORA)
- Configuración en Cloudflare DNS


> 📅 Documentado: 2026-05-08
