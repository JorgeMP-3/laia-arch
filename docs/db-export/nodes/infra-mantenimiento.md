# Guía de Mantenimiento

## Metadata

- ID: `112`
- Slug: `infra-mantenimiento`
- Kind: `doc`
- Status: `active`
- Filename: `infra-mantenimiento.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:12.992596+00:00`
- Updated at: `2026-05-08T08:35:12.992596+00:00`
- Aliases: `infra-mantenimiento`

## Summary

gsave   # menú interactivo — elige 3 para guardar todo

## Body

# Guía de mantenimiento

## Operaciones del día a día

### Guardar cambios en GitHub
```bash
gsave   # menú interactivo — elige 3 para guardar todo
```

### Actualizar Arete frontend (tras cambios en el código)
```bash
cd ~/servidor/arete/frontend
npm run build
# nginx sirve directamente dist/ — no hace falta reiniciar nada
```

### Actualizar Arete backend (tras cambios en el código)
```bash
cd ~/servidor/arete/backend
npm run build                     # recompila TypeScript → dist/
source ~/.nvm/nvm.sh && pm2 restart arete-backend
```

### Reiniciar todos los servicios
```bash
sudo systemctl restart nginx hermes workspace-ui
source ~/.nvm/nvm.sh && pm2 restart arete-backend
docker compose -f ~/servidor/tienda/docker-compose.yml restart
```

---

## Actualizar Hermes desde NousResearch

```bash
cd ~/laia-arch/hermes-agent
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
git checkout local-customizations
git rebase main
git push origin local-customizations --force-with-lease

# Reinstalar el paquete con los cambios
source venv/bin/activate
pip install -e . --quiet
sudo systemctl restart hermes workspace-ui
```

---

## Cambiar configuración de nginx

1. Editar `~/servidor/nginx/laia.conf`
2. Aplicar:
```bash
sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia
sudo nginx -t && sudo systemctl reload nginx
```

---

## Logs

```bash
# Hermes
journalctl -u hermes -f

# Workspace-UI
journalctl -u workspace-ui -f

# Nginx (errores)
sudo tail -f /var/log/nginx/error.log

# Nginx (accesos)
sudo tail -f /var/log/nginx/access.log

# Cloudflare Tunnel
journalctl -u cloudflared -f

# Arete backend
source ~/.nvm/nvm.sh && pm2 logs arete-backend

# WordPress
docker logs tienda_wordpress -f
docker logs tienda_db -f
```

---

## Backup de WordPress

```bash
# Backup de la BD MySQL
docker exec tienda_db mysqldump -u wpuser -pwp123456 tienda_smr > ~/backups/tienda_$(date +%Y%m%d).sql

# Backup de archivos WordPress
docker run --rm -v tienda_wordpress_data:/data -v ~/backups:/backup \
  alpine tar czf /backup/wordpress_$(date +%Y%m%d).tar.gz -C /data .
```

---

## Variables de entorno de Arete

Archivo: `~/servidor/arete/.env`  
Contiene: JWT_SECRET, CLOUDFLARE_TUNNEL_TOKEN, claves de OpenAI/DeepSeek, config PostgreSQL.  
**No subir a GitHub** (está en .gitignore).

---

## Añadir nuevo dominio

1. En Cloudflare Zero Trust → Networks → Tunnels → arete-home → Published application routes:
   - Añadir `nuevo.laiajmp.org` → `http://localhost:80`
2. Añadir bloque server en `~/servidor/nginx/laia.conf`
3. Aplicar: `sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia && sudo nginx -t && sudo systemctl reload nginx`

---

## Estructura de directorios completa

```
/home/laia-arch/
  ├── bin/                ← scripts del sistema (gsave, clone-laia, sclaude...)
  ├── docs/               ← esta documentación
  ├── laia-arch/          ← código fuente LAIA (git: laia-infra)
  │   ├── hermes-agent/   ← Hermes CLI (git: hermes-agent, rama: local-customizations)
  │   ├── workspace-ui/   ← Workspace UI (git: workspace-ui, rama: master)
  │   ├── hermes-config/  ← skills y memorias sincronizados
  │   └── dotfiles/       ← starship.toml, etc.
  ├── servidor/           ← configuración del servidor
  │   ├── arete/          ← código Arete (backend Node.js + frontend React)
  │   ├── tienda/         ← docker-compose WordPress
  │   └── nginx/          ← laia.conf (fuente de verdad nginx)
  └── .hermes/            ← runtime Hermes (NO en git)
      ├── hermes-agent → ~/laia-arch/hermes-agent
      ├── workspace-ui → ~/laia-arch/workspace-ui
      ├── auth.json
      ├── config.yaml
      ├── state.db
      ├── memories/
      └── skills/
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Guía de Mantenimiento

# Guía de mantenimiento

## Operaciones del día a día

### Guardar cambios en GitHub
```bash
gsave   # menú interactivo — elige 3 para guardar todo
```

### Actualizar Arete frontend (tras cambios en el código)
```bash
cd ~/servidor/arete/frontend
npm run build
# nginx sirve directamente dist/ — no hace falta reiniciar nada
```

### Actualizar Arete backend (tras cambios en el código)
```bash
cd ~/servidor/arete/backend
npm run build                     # recompila TypeScript → dist/
source ~/.nvm/nvm.sh && pm2 restart arete-backend
```

### Reiniciar todos los servicios
```bash
sudo systemctl restart nginx hermes workspace-ui
source ~/.nvm/nvm.sh && pm2 restart arete-backend
docker compose -f ~/servidor/tienda/docker-compose.yml restart
```

---

## Actualizar Hermes desde NousResearch

```bash
cd ~/laia-arch/hermes-agent
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
git checkout local-customizations
git rebase main
git push origin local-customizations --force-with-lease

# Reinstalar el paquete con los cambios
source venv/bin/activate
pip install -e . --quiet
sudo systemctl restart hermes workspace-ui
```

---

## Cambiar configuración de nginx

1. Editar `~/servidor/nginx/laia.conf`
2. Aplicar:
```bash
sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia
sudo nginx -t && sudo systemctl reload nginx
```

---

## Logs

```bash
# Hermes
journalctl -u hermes -f

# Workspace-UI
journalctl -u workspace-ui -f

# Nginx (errores)
sudo tail -f /var/log/nginx/error.log

# Nginx (accesos)
sudo tail -f /var/log/nginx/access.log

# Cloudflare Tunnel
journalctl -u cloudflared -f

# Arete backend
source ~/.nvm/nvm.sh && pm2 logs arete-backend

# WordPress
docker logs tienda_wordpress -f
docker logs tienda_db -f
```

---

## Backup de WordPress

```bash
# Backup de la BD MySQL
docker exec tienda_db mysqldump -u wpuser -pwp123456 tienda_smr > ~/backups/tienda_$(date +%Y%m%d).sql

# Backup de archivos WordPress
docker run --rm -v tienda_wordpress_data:/data -v ~/backups:/backup \
  alpine tar czf /backup/wordpress_$(date +%Y%m%d).tar.gz -C /data .
```

---

## Variables de entorno de Arete

Archivo: `~/servidor/arete/.env`  
Contiene: JWT_SECRET, CLOUDFLARE_TUNNEL_TOKEN, claves de OpenAI/DeepSeek, config PostgreSQL.  
**No subir a GitHub** (está en .gitignore).

---

## Añadir nuevo dominio

1. En Cloudflare Zero Trust → Networks → Tunnels → arete-home → Published application routes:
   - Añadir `nuevo.laiajmp.org` → `http://localhost:80`
2. Añadir bloque server en `~/servidor/nginx/laia.conf`
3. Aplicar: `sudo cp ~/servidor/nginx/laia.conf /etc/nginx/sites-available/laia && sudo nginx -t && sudo systemctl reload nginx`

---

## Estructura de directorios completa

```
/home/laia-arch/
  ├── bin/                ← scripts del sistema (gsave, clone-laia, sclaude...)
  ├── docs/               ← esta documentación
  ├── laia-arch/          ← código fuente LAIA (git: laia-infra)
  │   ├── hermes-agent/   ← Hermes CLI (git: hermes-agent, rama: local-customizations)
  │   ├── workspace-ui/   ← Workspace UI (git: workspace-ui, rama: master)
  │   ├── hermes-config/  ← skills y memorias sincronizados
  │   └── dotfiles/       ← starship.toml, etc.
  ├── servidor/           ← configuración del servidor
  │   ├── arete/          ← código Arete (backend Node.js + frontend React)
  │   ├── tienda/         ← docker-compose WordPress
  │   └── nginx/          ← laia.conf (fuente de verdad nginx)
  └── .hermes/            ← runtime Hermes (NO en git)
      ├── hermes-agent → ~/laia-arch/hermes-agent
      ├── workspace-ui → ~/laia-arch/workspace-ui
      ├── auth.json
      ├── config.yaml
      ├── state.db
      ├── memories/
      └── skills/
```


> 📅 Documentado: 2026-05-08
