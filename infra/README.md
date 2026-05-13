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

### Comandos basicos

```bash
infra/laiactl doctor
infra/laiactl setup-lxd
infra/laiactl build-agent-image
infra/laiactl provision-agent jorge    # create + runtime + workspace + profile + verify (todo en uno)
```

### Comandos de flota

```bash
infra/laiactl fleet-status             # tabla de todos los agentes con salud
infra/laiactl restart-agent --all      # reiniciar toda la flota
infra/laiactl agent-status --all       # estado de todos los agentes
infra/laiactl upgrade-all              # actualizar runtime en todos
infra/laiactl upgrade-all --rolling 3  # actualizar de 3 en 3
infra/laiactl list-agents
infra/laiactl verify
```

### Comandos por agente

```bash
infra/laiactl start-agent jorge
infra/laiactl stop-agent jorge
infra/laiactl restart-agent jorge
infra/laiactl agent-status jorge
infra/laiactl verify-agent jorge
infra/laiactl snapshot-agent jorge pre-cambio
infra/laiactl restore-agent jorge pre-cambio --yes
infra/laiactl delete-agent jorge --yes --force
```

### Perfil de agente

```bash
infra/laiactl init-agent-profile jorge
infra/laiactl agent-profile jorge
infra/laiactl set-agent-persona jorge /ruta/persona.md
infra/laiactl set-agent-instructions jorge /ruta/instructions.md
infra/laiactl enable-agent-skill jorge planning.deep
infra/laiactl disable-agent-skill jorge tasks.basic
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
