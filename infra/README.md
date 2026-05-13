# LAIA infra

Configuracion de servidor e infraestructura para LAIA.

## Estructura prevista

```text
infra/
├── laiactl
├── orchestrator/
├── nginx/
├── systemd/
├── docker/
├── lxd/
│   ├── profiles/
│   ├── scripts/
│   └── image-build/
└── backups/
```

## Archivos actuales

```text
PORTS.md
laiactl
orchestrator/
nginx/agora.conf
nginx/api-agora.conf
systemd/agora-backend.service
scripts/deploy-agora-frontend.sh
scripts/install-agora-backend-service.sh
docs/AGORA_DEPLOYMENT.md
```

## Orquestador

`laiactl` automatiza la preparacion de LXD y agentes personales.

Pertenece al lado ARCH/admin. No es una interfaz de usuario final.

```bash
infra/laiactl doctor
infra/laiactl setup-lxd
infra/laiactl build-agent-image
infra/laiactl create-agent jorge
infra/laiactl verify-agent jorge
infra/laiactl list-agents
infra/laiactl verify
```

La salida a Internet de contenedores LXD puede requerir reglas root:

```bash
sudo infra/lxd/scripts/fix-egress-root.sh
```

## Reglas

- nginx/cloudflared enrutan ARCH y AGORA.
- ARCH es privado/admin.
- AGORA es la app personal del usuario sobre su propio agente.
- `laiactl`, LXD, snapshots y operaciones globales pertenecen a ARCH.
- Agentes personales se ejecutan en LXD.
- Datos productivos viven en `/srv/laia`, no dentro del repo.
