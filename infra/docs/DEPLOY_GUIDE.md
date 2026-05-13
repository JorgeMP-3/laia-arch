# Guía de Deploy — LAIA en servidor real

## Requisitos del servidor

- Ubuntu 22.04 o 24.04 (ARM64 o AMD64)
- LXD instalado y configurado
- Python 3.11+
- nginx
- Usuario `laia-hermes` con acceso a LXD (`sudo lxd.lxc` o snap LXD)
- Cloudflare Tunnel o certificado TLS para exponer AGORA

---

## Paso 1: Preparar LXD

```bash
# Como root
snap install lxd
lxd init --minimal

# Añadir laia-hermes al grupo lxd
usermod -aG lxd laia-hermes
newgrp lxd
```

## Paso 2: Clonar o sincronizar el código

```bash
# En /home/laia-hermes
git clone <repo> LAIA
cd LAIA
```

## Paso 3: Crear directorios de producción

```bash
sudo LAIA_USER=laia-hermes bash infra/scripts/setup-prod-dirs.sh
```

Esto crea:
- `/srv/laia/state/`       — estado LXD (agents.json)
- `/srv/laia/agora/`       — datos AGORA backend (users, tasks, events)
- `/srv/laia/backups/`     — backups automáticos
- `/srv/laia/agents/`      — reservado para datos de agentes

## Paso 4: Configurar LXD

```bash
# Inicializar defaults de LAIA
python3 infra/laiactl setup-lxd

# Verificar
python3 infra/laiactl doctor

# Si el NAT falla:
sudo bash infra/lxd/scripts/fix-egress-root.sh
```

## Paso 5: Construir imagen base

```bash
python3 infra/laiactl build-agent-image
```

## Paso 6: Crear primer agente

```bash
python3 infra/laiactl create-agent jorge
python3 infra/laiactl install-agent-runtime jorge
python3 infra/laiactl init-agent-workspace jorge
python3 infra/laiactl verify-agent jorge
```

## Paso 7: Instalar AGORA backend

```bash
cd services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Verificar que arranca
AGORA_ENV=prod .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8088 &
curl -s http://127.0.0.1:8088/api/health | python3 -m json.tool
kill %1
```

## Paso 8: Instalar servicio systemd

```bash
sudo bash infra/scripts/install-agora-backend-service.sh
sudo systemctl start agora-backend
sudo systemctl status agora-backend
```

## Paso 9: Build y deploy del frontend AGORA

```bash
cd /home/laia-hermes/LAIA/laia-ui

# Instalar dependencias (pnpm)
npm install -g pnpm@10
pnpm install

# Build
pnpm build:agora

# Deploy a /srv/laia/agora/frontend/dist
sudo bash /home/laia-hermes/LAIA/infra/scripts/deploy-agora-frontend.sh
```

## Paso 10: Configurar nginx

```bash
# Copiar configuración
sudo cp infra/nginx/agora.conf /etc/nginx/sites-available/agora.laiajmp.org
sudo ln -s /etc/nginx/sites-available/agora.laiajmp.org /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Verificación post-deploy

```bash
# 1. Backend health
curl -s http://127.0.0.1:8088/api/health

# 2. Login (dev credentials)
curl -s -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"TU_PASSWORD"}' | python3 -m json.tool

# 3. Listar agentes (usa el token del paso anterior)
TOKEN=$(curl -s -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"TU_PASSWORD"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8088/api/agents | python3 -m json.tool

# 4. Estado del servicio
sudo systemctl status agora-backend

# 5. Verificar agente jorge
python3 /home/laia-hermes/LAIA/infra/laiactl agent-status jorge
```

---

## Backups automáticos

Añadir al crontab de `laia-hermes`:

```cron
# Backup diario a las 3am
0 3 * * * BACKUP_ROOT=/srv/laia/backups bash /home/laia-hermes/LAIA/infra/scripts/backup-state.sh >> /var/log/laia-backup.log 2>&1

# Snapshot semanal (domingo 4am)
0 4 * * 0 BACKUP_ROOT=/srv/laia/backups SNAPSHOT=1 bash /home/laia-hermes/LAIA/infra/scripts/backup-state.sh >> /var/log/laia-backup.log 2>&1
```

---

## Variables de entorno en producción

| Variable | Valor prod | Default dev |
|----------|-----------|-------------|
| `AGORA_ENV` | `prod` | `dev` |
| `LAIA_ROOT` | `/home/laia-hermes/LAIA` | mismo |
| `AGORA_DATA_DIR` | `/srv/laia/agora` | `services/agora-backend/data` |
| `LAIA_STATE_ROOT` | `/srv/laia/state` | `.laia/state` |
| `LAIACTL_PATH` | `/home/laia-hermes/LAIA/infra/laiactl` | mismo |

Estas variables ya están en `/home/laia-hermes/LAIA/infra/systemd/agora-backend.service`.
