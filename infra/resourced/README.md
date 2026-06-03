# laia-resourced — monitor de recursos e invariantes del host

> **Primer binario Go del repo.** Tooling de host (LAIA-ARCH), no es código de producto AGORA.
> Plan: `~/laia-developers/workflow-server/plans/2026-06-02-laia-resourced-v1-implementacion.md`.
> Spec ejecutable (la que implementé): `2026-06-03-laia-resourced-v1-spec-minimax.md`.
> Visión/porqué: `…/2026-06-02-resource-orchestrator.md`.

## Qué es

Daemon residente que vigila los recursos del host (RAM, VRAM, disco), la salud de los servicios
de producción, el egress de `lxdbr0` y la inactividad de `laia-dev` (en sombra — no suspende).
**v1 solo monitorea y avisa — NO muta nada.** La autonomía (suspender/arrancar servicios bajo
presupuesto) se habilita tras ~1 mes demostrando aciertos en sombra, mediante config
(`mode: enforce`), no por reescritura.

## Binarios

- `laia-resourced` — el daemon (systemd `laia-resourced.service`). Publica estado a
  `/srv/laia/state/resourced/status.json` cada tick.
  - Flags: `--state-dir DIR` (default `/srv/laia/state/resourced`),
    `--tick 30s`, `--mode monitor` (v1 rechaza `enforce`),
    `--config /srv/laia/arch/resourced.yaml`,
    `--once` (smoke/test).
- `laia-res` — CLI cliente; lee del estado en disco (no necesita el daemon vivo).
  - Subcomandos: `status`, `audit`, `version`.
  - Flags globales: `--state-dir DIR`.
  - `audit` además: `--since 30d` (default), `24h`, `7d`, `1d`, o cualquier `time.ParseDuration`.

### Exit codes de `laia-res status` (contrato para scripts)

- `0` — estado fresco y sin dimensión en rojo
- `1` — sin archivo de estado, estado *stale* (>2× tick), o error de lectura
- `2` — estado fresco pero alguna dimensión en `red`

## Build

Binario estático, una sola dep externa (`gopkg.in/yaml.v3 v3.0.1`):

```sh
cd infra/resourced
gofmt -l .                              # debe salir vacío
go vet ./...
CGO_ENABLED=0 go build -o bin/laia-resourced ./cmd/laia-resourced
CGO_ENABLED=0 go build -o bin/laia-res       ./cmd/laia-res
go test ./...
```

`go` es **build-dep**, no runtime-dep (el binario es estático). En v1 se compila/prueba en la VM
`laia-dev`; la integración en el installer (`laia-install`) se cierra en el slice de empaquetado.

## Archivos en el state dir

`/srv/laia/state/resourced/`:

- `status.json` — último snapshot (schema **2**). Lo lee `laia-res status`.
  - `overall` — peor luz (excluye `dev_idle`).
  - `dimensions` — `egress`, `ram`, `vram`, `disk`, `prod`, `dev_idle`.
  - `services` — mapa por nombre (`class`, `alive` ∈ `ok|down|unknown`, `detail`).
- `events.jsonl` — alertas emitidas (transiciones de luz). Una línea JSON por evento.
- `decisions.jsonl` — **el sustrato de la auditoría del mes**. Una línea por decisión-sombra
  que el daemon *habría* tomado en `enforce` (`suspend` / `suspend_still` / `end_idle`).
  `laia-res audit` lo resume.

## Estado del desarrollo

- **S0** (PR #65) — scaffolding + heartbeat. `laia-res status` lee el estado.
- **S1** — egress probe (con oneshot al boot) + config declarativa + Status v2.
- **S2** — alerter: eventos JSONL + Telegram con throttle por Kind.
- **S3** — presupuesto RAM (collector `/proc/meminfo` + evaluador budget).
- **S4** — VRAM (nvidia-smi) + disco (statfs multi-path) + prod-viva (lxc/systemd/lxc_systemd).
- **S5** — inactividad `laia-dev` en sombra (`decisions.jsonl`).
- **S6** — CLI pulida: `laia-res status` (tabla alineada + exit codes) y `laia-res audit`.

## Comportamiento esperado (contrato)

- El binario rechaza `--mode enforce` (segunda capa; `config.Validate` repite el check).
- `unknown` (4ª luz) existe para "no pude medir" — peor que `warn`, mejor que `red`. Evita
  falsos verdes y falsas alarmas.
- `dev_idle` no afecta a `Overall` (es la sombra de v2; siempre informativa).
- Todo comando externo pasa por el `Runner` (seam de testabilidad); los colectores son puros
  y se prueban con Runners fake.
- v1 no muta estado del host. La única mutación es escribir `status.json` / `events.jsonl` /
  `decisions.jsonl` en su propio state-dir.
