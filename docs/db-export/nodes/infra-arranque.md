# Proceso de Arranque

## Metadata

- ID: `111`
- Slug: `infra-arranque`
- Kind: `doc`
- Status: `active`
- Filename: `infra-arranque.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:12.698720+00:00`
- Updated at: `2026-05-08T08:35:12.698720+00:00`
- Aliases: `infra-arranque`

## Summary

systemd gestiona todo. El orden es:

## Body

# Arranque automático del servidor

## Orden de arranque al encender la máquina

systemd gestiona todo. El orden es:

```
1. postgresql          (systemd — after network.target)
2. nginx               (systemd — after network.target)
3. cloudflared         (systemd — after network.target)
4. hermes              (systemd — after network.target)
5. workspace-ui        (systemd — after hermes.service)
6. pm2-laia-arch       (systemd — after network.target)
   └── arete-backend   (PM2 resurrect desde ~/.pm2/dump.pm2)
7. Docker daemon       (systemd)
   └── tienda_*        (restart: unless-stopped)
```

## Verificar que todo arrancó correctamente

```bash
# Estado de servicios systemd
systemctl is-active nginx postgresql cloudflared hermes workspace-ui pm2-laia-arch

# Estado PM2
source ~/.nvm/nvm.sh && pm2 list

# Estado Docker
docker ps

# Test de puertos
curl -s -o /dev/null -w "workspace-ui  :8077 → %{http_code}\n" http://localhost:8077/
curl -s -o /dev/null -w "arete backend :8000 → %{http_code}\n" http://localhost:8000/health
curl -s -o /dev/null -w "wordpress     :9000 → %{http_code}\n" http://localhost:9000/
curl -s -o /dev/null -w "nginx laiajmp :80   → %{http_code}\n" -H "Host: laiajmp.org" http://localhost/
```

## Archivos de servicio systemd

| Servicio | Archivo |
|---|---|
| hermes | `/etc/systemd/system/hermes.service` |
| workspace-ui | `/etc/systemd/system/workspace-ui.service` |
| pm2 | `/etc/systemd/system/pm2-laia-arch.service` |
| nginx | `/lib/systemd/system/nginx.service` (apt) |
| postgresql | `/lib/systemd/system/postgresql.service` (apt) |
| cloudflared | `/etc/systemd/system/cloudflared.service` (cloudflared installer) |

Las copias fuente (para modificar) de hermes y workspace-ui están en `~/servidor/`.  
Tras editar, copiar y recargar:
```bash
sudo cp ~/servidor/hermes.service /etc/systemd/system/
sudo cp ~/servidor/workspace-ui.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart hermes workspace-ui
```

## Si PM2 no arranca arete-backend

```bash
source ~/.nvm/nvm.sh
pm2 list                          # ver si está en la lista
pm2 resurrect                     # cargar el dump guardado
# o bien:
cd ~/servidor/arete/backend
pm2 start dist/server.js --name arete-backend
pm2 save
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Proceso de Arranque

# Arranque automático del servidor

## Orden de arranque al encender la máquina

systemd gestiona todo. El orden es:

```
1. postgresql          (systemd — after network.target)
2. nginx               (systemd — after network.target)
3. cloudflared         (systemd — after network.target)
4. hermes              (systemd — after network.target)
5. workspace-ui        (systemd — after hermes.service)
6. pm2-laia-arch       (systemd — after network.target)
   └── arete-backend   (PM2 resurrect desde ~/.pm2/dump.pm2)
7. Docker daemon       (systemd)
   └── tienda_*        (restart: unless-stopped)
```

## Verificar que todo arrancó correctamente

```bash
# Estado de servicios systemd
systemctl is-active nginx postgresql cloudflared hermes workspace-ui pm2-laia-arch

# Estado PM2
source ~/.nvm/nvm.sh && pm2 list

# Estado Docker
docker ps

# Test de puertos
curl -s -o /dev/null -w "workspace-ui  :8077 → %{http_code}\n" http://localhost:8077/
curl -s -o /dev/null -w "arete backend :8000 → %{http_code}\n" http://localhost:8000/health
curl -s -o /dev/null -w "wordpress     :9000 → %{http_code}\n" http://localhost:9000/
curl -s -o /dev/null -w "nginx laiajmp :80   → %{http_code}\n" -H "Host: laiajmp.org" http://localhost/
```

## Archivos de servicio systemd

| Servicio | Archivo |
|---|---|
| hermes | `/etc/systemd/system/hermes.service` |
| workspace-ui | `/etc/systemd/system/workspace-ui.service` |
| pm2 | `/etc/systemd/system/pm2-laia-arch.service` |
| nginx | `/lib/systemd/system/nginx.service` (apt) |
| postgresql | `/lib/systemd/system/postgresql.service` (apt) |
| cloudflared | `/etc/systemd/system/cloudflared.service` (cloudflared installer) |

Las copias fuente (para modificar) de hermes y workspace-ui están en `~/servidor/`.  
Tras editar, copiar y recargar:
```bash
sudo cp ~/servidor/hermes.service /etc/systemd/system/
sudo cp ~/servidor/workspace-ui.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart hermes workspace-ui
```

## Si PM2 no arranca arete-backend

```bash
source ~/.nvm/nvm.sh
pm2 list                          # ver si está en la lista
pm2 resurrect                     # cargar el dump guardado
# o bien:
cd ~/servidor/arete/backend
pm2 start dist/server.js --name arete-backend
pm2 save
```


> 📅 Documentado: 2026-05-08
