# laia-resourced — monitor de recursos e invariantes del host

> **Primer binario Go del repo.** Tooling de host (LAIA-ARCH), no es código de producto AGORA.
> Plan: `~/laia-developers/workflow-server/plans/2026-06-02-laia-resourced-v1-implementacion.md`.
> Visión/porqué: `…/2026-06-02-resource-orchestrator.md`.

## Qué es

Daemon residente que vigila los recursos del host (RAM, VRAM, disco), la salud de los servicios
de producción y los invariantes frágiles (egress de `lxdbr0`). **v1 solo monitorea y avisa — NO
muta nada.** La autonomía (suspender/arrancar servicios bajo presupuesto) se habilita tras ~1 mes
demostrando aciertos en sombra, mediante config (`mode: enforce`), no por reescritura.

## Binarios

- `laia-resourced` — el daemon (systemd `laia-resourced.service`). Publica estado a
  `/srv/laia/state/resourced/status.json` cada tick.
- `laia-res` — CLI cliente. `laia-res status` lee el estado de disco (no necesita el daemon vivo).

## Build

Binario estático, sin dependencias externas (solo stdlib en v1):

```sh
cd infra/resourced
go build -o bin/laia-resourced ./cmd/laia-resourced
go build -o bin/laia-res       ./cmd/laia-res
go test ./...
```

`go` es **build-dep**, no runtime-dep (el binario es estático). En v1 se compila/prueba en la VM
`laia-dev`; la integración en el installer (`laia-install`) se cierra en el slice de empaquetado.

## Estado del desarrollo

- **S0 (este commit)**: scaffolding + heartbeat. El daemon escribe un latido; `laia-res status` lo lee.
- S1 egress · S2 alerter Telegram · S3 RAM · S4 VRAM+disco+prod-viva · S5 inactividad (sombra) · S6 audit.
