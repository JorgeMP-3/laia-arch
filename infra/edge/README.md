# laia-edge — Edge gateway de LAIA (Caddy + Cloudflare Tunnel)

Infra del **edge** del host: el LXC `laia-edge` (Caddy + cloudflared) que enruta todos los
hostnames de `laiajmp.org` a sus backends, y el LXC `laia-uis` (node/npm) que compila las UIs.

- **Plan**: `~/laia-developers/workflow-server/plans/2026-06-02-edge-gateway-uis.md`
- **Bitácora**: `~/laia-developers/workflow-server/` y `workflow-ui/`.

## Contenedores
- `laia-edge` (10.99.0.51): Caddy (HTTP plano) + cloudflared (túnel `doyouwin`). Internet-facing, mínimo.
- `laia-uis`  (10.99.0.52): node/npm. Compila UIs → `dist/` a `/srv/laia/web/sites/<app>/`. Apagable, sin internet entrante.

## Layout en host
`/srv/laia/web/{sites/<app>/, edge/Caddyfile, src/}` — `sites` lo escribe `laia-uis` (RW) y lo sirve `laia-edge` (RO).

## Fases
1. (hecho por el agente) crear LXC + instalar Caddy/cloudflared/node.
2. `sudo bash bin/setup-edge-host.sh` — layout, permisos, binds, Caddyfile. NO toca el túnel.
3. `sudo bash bin/cutover-tunnel.sh` — migra el túnel del host a `laia-edge`. Corte ~nulo.

Despliegue de una UI: compilar en `laia-uis` → su `dist/` aparece en `/srv/laia/web/sites/<app>/` → + bloque en `config/Caddyfile`.

---
> **Procedencia**: nació como repo suelto `~/laia-edge` (2026-06-02, commit e8615cc) e
> integrado aquí el 2026-06-03 (reorg D2: la infra del ecosistema vive en `~/LAIA/infra/`).
> Original archivado con su `.git` en `~/archive/laia-edge-repo-20260603/`.
