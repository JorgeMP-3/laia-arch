# Build image `laia-agent`

Estado: plan inicial. No ejecutar sin revisar en el servidor real.

## Objetivo

Crear una imagen base LXD para agentes personales de AGORA.

La imagen debe incluir:

- Ubuntu LTS.
- Python.
- runtime LAIA/Hermes limitado.
- WorkspaceStore.
- toolset AGORA.
- estructura `/opt/laia`.

## Pasos propuestos

```bash
lxc launch ubuntu:22.04 laia-agent-base -p default -p laia-employee
lxc exec laia-agent-base -- apt update
lxc exec laia-agent-base -- apt install -y python3 python3-venv git curl ca-certificates

lxc exec laia-agent-base -- mkdir -p /opt/laia/workspaces/personal /opt/laia/data /opt/laia/runtime /opt/laia/logs
lxc exec laia-agent-base -- python3 -m venv /opt/laia/runtime/venv

# TODO: instalar runtime LAIA/Hermes limitado.
# TODO: inicializar workspace personal con WorkspaceStore.

lxc stop laia-agent-base
lxc publish laia-agent-base --alias laia-agent
lxc delete laia-agent-base
```

## Script

```bash
infra/lxd/image-build/build-base-image.sh
```

Variables:

```text
BASE_IMAGE=ubuntu:22.04
BASE_CONTAINER=laia-agent-base
ALIAS=laia-agent
PROFILE=laia-employee
```

## Pendientes

- Decidir si se instala Hermes desde repo oficial o paquete local.
- Definir toolset AGORA final.
- Crear healthcheck interno del agente.
- Definir API interna de agente.
