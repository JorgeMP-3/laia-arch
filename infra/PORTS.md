# LAIA ports

Puertos oficiales propuestos para el servidor.

| Servicio | Puerto | Bind | Estado |
|---|---:|---|---|
| ARCH / workspace-ui | 8077 | `127.0.0.1` o LAN/VPN | Existente |
| AGORA backend | 8088 | `127.0.0.1` | Nuevo |
| AGORA frontend preview | 5174 | desarrollo | Dev only |
| ARCH frontend dev | 5173 | desarrollo | Dev only |
| Agentes personales LXD | interno por IP LXD | red LXD | Pendiente |

## Dominios previstos

| Dominio | Destino |
|---|---|
| `arch.laiajmp.org` | ARCH UI/API, solo admin/VPN o Cloudflare Access |
| `agora.laiajmp.org` | AGORA frontend |
| `api.laiajmp.org` | AGORA backend `/api/*` |

## Regla

AGORA backend debe escuchar en localhost. nginx/cloudflared exponen solo lo necesario.

