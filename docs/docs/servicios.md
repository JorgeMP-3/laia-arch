# Servicios del servidor

## Resumen de puertos

| Puerto | Servicio | Acceso |
|---|---|---|
| 80 | nginx (reverse proxy) | interno (Cloudflare tunnel) |
| 443 | — | no usado (SSL en Cloudflare) |
| 8000 | arete-backend (Node.js) | interno |
| 8077 | workspace-ui (FastAPI) | interno |
| 9000 | WordPress (Docker) | interno |
| 9001 | phpMyAdmin (Docker) | interno |
| 5432 | PostgreSQL | interno |
| 3306 | MySQL/tienda (Docker) | interno |

---

## Servicios systemd (nativos)

### nginx
```bash
sudo systemctl start|stop|restart|reload nginx
sudo systemctl status nginx
sudo nginx -t                    # validar config antes de recargar
```

### postgresql
```bash
sudo systemctl start|stop|restart postgresql
sudo systemctl status postgresql
sudo -u postgres psql            # consola SQL
sudo -u postgres psql arete      # BD de arete
```

### cloudflared
```bash
sudo systemctl start|stop|restart cloudflared
sudo systemctl status cloudflared
journalctl -u cloudflared -f     # logs en tiempo real
```

### hermes
```bash
sudo systemctl start|stop|restart hermes
sudo systemctl status hermes
journalctl -u hermes -f          # logs
```
Config en: `~/.hermes/config.yaml`  
Auth en: `~/.hermes/auth.json`

### workspace-ui
```bash
sudo systemctl start|stop|restart workspace-ui
sudo systemctl status workspace-ui
journalctl -u workspace-ui -f    # logs
```
Acceso: `http://localhost:8077`

---

## PM2 — arete-backend

```bash
source ~/.nvm/nvm.sh             # cargar node si hace falta

pm2 list                         # ver procesos
pm2 status                       # resumen
pm2 restart arete-backend        # reiniciar
pm2 stop arete-backend           # parar
pm2 logs arete-backend           # logs en tiempo real
pm2 logs arete-backend --lines 50 --nostream  # últimas 50 líneas
pm2 save                         # guardar lista (para arranque automático)
```

El arranque automático está configurado vía `pm2-laia-arch.service` en systemd.  
En cada reinicio del sistema: systemd → pm2-laia-arch → `pm2 resurrect` → arete-backend.

---

## Docker — WordPress (tienda)

```bash
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml up -d"
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml down"
sg docker -c "docker compose -f ~/servidor/tienda/docker-compose.yml restart"
sg docker -c "docker ps"
sg docker -c "docker logs tienda_db"
sg docker -c "docker logs tienda_wordpress"
```

> **Nota:** usar `sg docker -c "..."` mientras la sesión no haya recargado el grupo docker.  
> Tras cerrar y abrir sesión, `docker` funciona directamente sin `sg docker`.

Contenedores:
- `tienda_db` — MySQL 8.0 (datos en volumen `tienda_db_data`)
- `tienda_wordpress` — WordPress latest (datos en volumen `tienda_wordpress_data`)
- `tienda_phpmyadmin` — phpMyAdmin en http://localhost:9001
