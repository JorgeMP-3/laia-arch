# Cloudflare Tunnel

## Datos del túnel

| Campo | Valor |
|---|---|
| Nombre | arete-home |
| Tunnel ID | 739382f9-f44b-42db-8a9a-2ed3abc5fc3d |
| Estado | HEALTHY |
| Conector | familiamp-OptiPlex-9020 (nombre histórico en dashboard Cloudflare) |
| Data center | mad (Madrid) |
| IP pública | 89.29.161.221 |
| Versión cloudflared | 2026.3.0 |

## Cómo funciona

1. `cloudflared` corre como servicio systemd en el servidor
2. Establece una conexión saliente cifrada hacia Cloudflare (sin abrir puertos)
3. Cloudflare recibe tráfico HTTPS en los dominios y lo reenvía por el túnel
4. cloudflared entrega el tráfico a `http://localhost:80` (nginx)
5. nginx enruta al servicio correcto según el dominio

**El router NO necesita port-forwarding.** El servidor puede estar detrás de NAT.

## Rutas configuradas (Published Application Routes)

| # | Dominio | Path | Destino |
|---|---|---|---|
| 1 | laiajmp.org | * | http://localhost:80 |
| 2 | tienda.laiajmp.org | * | http://localhost:80 |
| 3 | presentaciones.laiajmp.org | * | http://localhost:80 |
| 4 | app.laiajmp.org | * | http://localhost:80 |
| — | catch-all | — | http_status:404 |

## Gestión del servicio

```bash
sudo systemctl status cloudflared
sudo systemctl restart cloudflared
journalctl -u cloudflared -f        # logs en tiempo real
```

## Dashboard

https://one.dash.cloudflare.com → Networks → Tunnels → arete-home

## Token

El token del túnel está en `~/servidor/arete/.env` como `CLOUDFLARE_TUNNEL_TOKEN`.  
**No compartir ni subir a GitHub.**

## Reinstalar el servicio (si hace falta)

```bash
sudo cloudflared service uninstall
TOKEN=$(grep CLOUDFLARE_TUNNEL_TOKEN ~/servidor/arete/.env | cut -d= -f2)
sudo cloudflared service install "$TOKEN"
sudo systemctl enable --now cloudflared
```
