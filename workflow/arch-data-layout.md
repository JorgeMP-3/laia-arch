# LAIA-ARCH Data Layout

Este documento describe la organización de datos de LAIA-ARCH. Es una guía de
trabajo; el contrato conceptual sigue siendo `LAIA_ECOSYSTEM.md`.

> **Cambio 2026-05-26** (post-T.14.1): la zona `/srv/laia/arch/` queda
> deprecada. Toda la data de ARCH (interactiva + operacional) vive ahora
> bajo `LAIA_HOME` (`~/LAIA-ARCH/` por defecto). Razón: el código de
> `laia_cli` y `laia-pathd` corre como `laia-hermes` y lee `config.yaml`,
> `state.db`, `sessions/`, etc. via `get_laia_home() / "<path>"`. Una
> zona `root:root 700` separada los dejaba sin acceso. La separación
> "caja fuerte vs. mesa de trabajo" del diseño original no se sostiene
> con procesos user-mode y se cancela hasta que existan procesos
> privilegiados que justifiquen la separación.

## Principio (actualizado)

Todo el estado de ARCH (interactivo + operacional) vive bajo `LAIA_HOME`,
user-owned con perms 700. La separación entre "vivo" y "operacional" es
**lógica** (subdirectorios), no de permisos ni de owner.

| Zona | Uso |
|---|---|
| `LAIA_HOME` (= `~/LAIA-ARCH/`) | Toda la data de ARCH: interactiva + operacional. User-owned 700. |
| `~/.laia/` | Solo compat legacy: `auth.json`, `.env`, `auth.lock`, `bin/`, `cache/`, `admin-session.json`, caches de modelos. |

`auth.json` y `.env` siguen en `~/.laia/` porque los scripts LXD que
montan credenciales en `laia-agora` todavía esperan ese path. Mover esos
secrets requiere una fase aparte que actualice
`infra/lxd/scripts/rebuild-3-provision-agora.sh`,
`infra/lxd/scripts/rebuild-3b-fix-authjson.sh` y tests de preflight.

## `~/LAIA-ARCH/`

```text
~/LAIA-ARCH/
├── workspaces/                  # interactivo
├── memories/                    # interactivo
├── skills/                      # interactivo (typically symlink al repo)
├── plugins/                     # interactivo
├── SOUL.md                      # operacional (identidad)
├── config.yaml                  # operacional (config principal del CLI/pathd)
├── state.db                     # operacional (state DB)
├── response_store.db            # operacional
├── pathd.sock                   # runtime (socket de laia-pathd)
├── sessions/                    # operacional (historia chat)
├── atlas/                       # operacional
├── cron/                        # operacional
├── checkpoints/                 # operacional
├── sandboxes/                   # operacional
├── orchestrator-runs/           # operacional
├── migration/                   # operacional
├── whatsapp/                    # operacional
├── logs/                        # operacional
├── platforms/                   # operacional
├── pastes/                      # operacional
└── state/                       # operacional
```

Regla: si lo lee o escribe `laia_cli`, `laia-pathd`, `laia-ui-server` o el
ARCH UI, vive aquí.

## `/srv/laia/` (zonas que SÍ se mantienen)

```text
/srv/laia/
├── agora/         # AGORA backend (root-mapped UID 1000999) — agora.db, etc.
├── users/         # bind-mount areas hacia agent containers (jorge-dev, verify_bob)
├── backups/       # backups operacionales del host
└── state/         # LXD orchestrator state (agents.json)
```

`/srv/laia/agora/` mantiene root-only (UID 1000999) porque es propiedad
del backend AGORA y se monta en containers. Esa separación SÍ funciona
porque el backend es el único que escribe ahí.

## Comportamiento Del Clone (actualizado)

Cuando `laia-clone` migra una instalación legacy (`~/.laia/`):

- Todo lo que el ARCH usa (`workspaces`, `memories`, `skills`, `plugins`,
  `sessions`, `atlas`, `cron`, `logs`, `state.db`, `SOUL.md`,
  `config.yaml`, etc.) se copia a `LAIA_HOME` (`~/LAIA-ARCH/` por defecto).
- `auth.json` y `.env` permanecen en `~/.laia/` (compat legacy).
- `config.yaml` se reescribe para que:
  - `laia_root` apunte a `/opt/laia` (o `~/LAIA` en dev-style)
  - `agora_data` apunte a `/srv/laia/agora/agora.db`
  - `laia_home` apunte a `LAIA_HOME` (= `~/LAIA-ARCH/`)
  - Todos los subpaths se resuelvan vía `${paths.laia_home}/<subdir>`.

`infra/installer/lib/clone.sh:clone_phase_h_rewrite_config_paths` y
`infra/installer/lib/*.sh` deben converger en este layout. Cualquier
referencia a `/srv/laia/arch/` en esos scripts es código muerto y debe
removerse en T.14.7/T.14.8.

## Quién usa qué

| Componente | Lee/escribe |
|---|---|
| `agora-backend` (PM2 o systemd) | `/srv/laia/agora/` (su propio LAIA_HOME forzado en `main.py:221`) |
| `laia-cli`, `laia-pathd`, `laia-ui-server` | `$LAIA_HOME/` (= `~/LAIA-ARCH/`) |
| Containers `agent-*` | `/srv/laia/users/<user>/{home,plugins,workspace}` bind-mount |
| Container `laia-agora` (legacy) | Originalmente sirvió 8088; hoy PM2 lo eclipsa con backend en host |
