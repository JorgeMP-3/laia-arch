# AGORA deployment runbook

Estado: operativo.

## Deploy rapido (script unico)

```bash
/home/laia-hermes/LAIA/infra/scripts/deploy-agora.sh
```

Verificar sin desplegar:

```bash
/home/laia-hermes/LAIA/infra/scripts/deploy-agora.sh --check
```

---

## Despliegue paso a paso (manual)

### 1. Preparar datos productivos

```bash
sudo mkdir -p /srv/laia/agora/frontend/dist
sudo mkdir -p /srv/laia/agora/uploads
sudo mkdir -p /srv/laia/state
sudo mkdir -p /srv/laia/backups
sudo chown -R laia-hermes:laia-hermes /srv/laia
```

### 2. Backend (Python FastAPI)

```bash
cd /home/laia-hermes/LAIA/services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Prueba manual:

```bash
AGORA_ENV=prod \
AGORA_DATA_DIR=/srv/laia/agora \
LAIA_ROOT=/home/laia-hermes/LAIA \
LAIA_STATE_ROOT=/srv/laia/state \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Health:

```bash
curl http://127.0.0.1:8088/api/health
# {"ok":true,"service":"agora-backend",...}
```

### 3. Instalar systemd service

```bash
sudo cp /home/laia-hermes/LAIA/infra/systemd/agora-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable agora-backend
sudo systemctl start agora-backend
sudo systemctl status agora-backend
```

### 4. Build y desplegar frontend

```bash
cd /home/laia-hermes/LAIA/laia-ui
pnpm build:agora
rm -rf /srv/laia/agora/frontend/dist
mkdir -p /srv/laia/agora/frontend
cp -r packages/agora-app/dist /srv/laia/agora/frontend/dist
```

### 5. Activar nginx

```bash
sudo cp /home/laia-hermes/LAIA/infra/nginx/agora.conf /etc/nginx/sites-available/agora.laiajmp.org
sudo ln -sf ../sites-available/agora.laiajmp.org /etc/nginx/sites-enabled/agora.laiajmp.org
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Configurar Cloudflare Tunnel

En el dashboard de Cloudflare, añadir el subdominio:

```
agora.laiajmp.org → localhost:8090
```

O via cloudflared config (`~/.cloudflared/config.yml`):

```yaml
ingress:
  - hostname: agora.laiajmp.org
    service: http://localhost:8090
  - service: http_status:404
```

### 7. Verificar

```bash
# Backend
curl http://127.0.0.1:8088/api/health

# Frontend via nginx
curl -s -o /dev/null -w "%{http_code}" -H "Host: agora.laiajmp.org" http://127.0.0.1:8090/
# → 200

# Login
curl -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}'
```

### 8. Acceder publicamente

```
https://agora.laiajmp.org
```

---

## Endpoints de AGORA

| Ruta | Descripcion |
|---|---|
| `/api/health` | Healthcheck |
| `/api/login` | Login |
| `/api/me` | Perfil del usuario autenticado |
| `/api/agent/profile` | Leer perfil del agente personal |
| `/api/agent/profile` (PATCH) | Actualizar perfil del agente personal |
| `/api/agent/status` | Estado del runtime del agente personal |
| `/api/agent/tasks` | Cola de tareas del agente personal |
| `/api/agent` (PATCH) | Cambiar nombre visible del agente |
| `/api/tasks` | Listar tareas asignadas |
| `/api/agents` | Listar agentes (admin: todos, user: solo el suyo) |
| `/api/coordinator/report` | Reporte de LAIA AGORA (admin) |
| `/api/coordinator/assign` | Asignar tarea global (admin) |

---

## Pendientes antes de produccion

- Sustituir auth dev por tokens con expiracion y passwords hasheadas.
- Activar HTTPS/Cloudflare Access para `arch.laiajmp.org`.
- Definir backups de `/srv/laia/agora`.
- Crear agentes LXD reales (minimo `laia-agora` y `laia-jorge`).
