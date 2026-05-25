# Deployment Guide

> 📅 Actualizado: 2026-05-19

## Quick Deploy (AGORA)

```bash
# Full deploy: frontend + backend
make deploy-agora

# Or step by step:
laia deploy agora-all
```

## Quick Deploy (LAIA-ARCH)

```bash
make deploy-arch
```

## Manual Deployment

### Prerequisites

```bash
# Data directories
sudo mkdir -p /srv/laia/agora/frontend/dist /srv/laia/state /srv/laia/backups
sudo chown -R laia-hermes:laia-hermes /srv/laia/

# LAIA-AGORA Backend
cd ~/LAIA/services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# LAIA Core venv
cd ~/LAIA/.laia-core
python3 -m venv venv
venv/bin/pip install -e .
venv/bin/pip install uvicorn fastapi python-dotenv watchdog
```

### Systemd Services

```bash
# Install service units
sudo cp ~/LAIA/infra/systemd/agora-backend.service /etc/systemd/system/
sudo cp ~/LAIA/infra/systemd/laia-gateway.service /etc/systemd/system/
sudo cp ~/LAIA/infra/systemd/laia-ui-server.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now laia-gateway agora-backend workspace-ui

# Path daemon (user mode)
mkdir -p ~/.config/systemd/user
cp ~/LAIA/infra/systemd/laia-pathd.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now laia-pathd
```

### nginx

```bash
sudo cp ~/LAIA/infra/nginx/agora.conf /etc/nginx/sites-available/agora.laiajmp.org
sudo ln -sf ../sites-available/agora.laiajmp.org /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Verification

```bash
# Health checks
laia health
curl http://localhost:8088/api/health
curl -o /dev/null -s -w "%{http_code}" http://localhost:8077/

# Fleet status
laiactl fleet-status

# Path registry
laia-path doctor

# Backend tests
cd ~/LAIA/services/agora-backend && .venv/bin/python -m pytest tests/ -q
```

## AGORA Web Access

- **Tailscale:** `http://100.73.36.92:8088`
- **Local:** `http://localhost:8088`
- **Production:** `https://agora.laiajmp.org` (via Cloudflare Tunnel + nginx)

**Default login:** `jorge` / `dev-admin`

## LAIA-ARCH Web Access

- **Tailscale:** `http://100.73.36.92:8077`
- **Local:** `http://localhost:8077`
