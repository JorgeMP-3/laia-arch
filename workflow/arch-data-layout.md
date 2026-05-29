# LAIA-ARCH Data Layout

Este documento describe la separación operativa de datos de LAIA-ARCH durante
instalación y clone. Es una guía de trabajo; el contrato conceptual sigue siendo
`LAIA_ECOSYSTEM.md`.

> 🛠️ **Layout v2 (2026-05-29):** los secretos (`auth.json`, `.env`) pasan de `~/.laia/` a
> `/srv/laia/arch/secrets/`, y `~/.laia/` se elimina; `SOUL.md` pasa a la mesa viva
> (`~/LAIA-ARCH/`). Es el objetivo decidido en [`plans/estabilizacion/`](plans/estabilizacion/)
> (Bloque C). **El código (`clone.sh`, `rebuild-3*`) aún implementa v1** (secretos en
> `~/.laia/`) hasta ejecutar la migración; ver §"Compatibilidad temporal".

## Principio

Separar la mesa de trabajo viva del admin del runtime operacional y de los secretos:

| Zona | Uso |
|---|---|
| `/home/laia-arch/LAIA-ARCH/` | Datos interactivos que Jorge/LAIA-ARCH crea, edita o instala con frecuencia. |
| `/srv/laia/arch/` | Estado operacional/sensible de LAIA-ARCH. No se toca a mano salvo mantenimiento. |
| `/srv/laia/arch/secrets/` | Secretos (`auth.json`, `.env`). Subdir `0700`, archivos `0600`, root-owned. |

## `/home/laia-arch/LAIA-ARCH/`

Aquí viven datos vivos del admin:

```text
/home/laia-arch/LAIA-ARCH/
├── workspaces/
├── memories/
├── skills/
├── plugins/
└── SOUL.md            (identidad — contenido curado por Jorge)
```

Regla: si Jorge o LAIA-ARCH lo crea, edita, instala o reorganiza de forma
frecuente, va aquí.

## `/srv/laia/arch/`

Aquí vive estado interno, sensible u operacional:

```text
/srv/laia/arch/
├── secrets/           (auth.json, .env — 0700/0600)
├── config.yaml
├── atlas.yaml
├── .env.paths
├── sessions/
├── sandboxes/
├── atlas/
├── cron/
├── logs/
├── platforms/
├── orchestrator-runs/
├── migration/
├── whatsapp/
├── state.db
└── response_store.db
```

Regla: si contiene configuración, sesiones, logs, ejecución temporal, automatización,
snapshots, estado interno o secretos, va aquí.

## Compatibilidad temporal (migración v1 → v2)

En v1 los secretos vivían en `~/.laia/`, y algunos scripts LXD todavía esperan ese path
para montar credenciales en `laia-agora`:

- `infra/lxd/scripts/rebuild-3-provision-agora.sh`
- `infra/lxd/scripts/rebuild-3b-fix-authjson.sh`
- tests de preflight/auth
- documentación de seguridad

Mover los secretos a `/srv/laia/arch/secrets/` como ubicación canónica (v2) requiere
actualizar esos componentes **en lockstep y con backup**. Es el **Bloque C** del plan
(`plans/estabilizacion/`), que se ensaya antes en la VM de desarrollo. Hasta entonces,
`~/.laia/` sigue siendo la fuente del bind-mount en disco.

## Comportamiento del clone

Cuando `laia-clone` migra una instalación (origen v1 en `~/.laia/`, o v2 en
`/srv/laia/arch/`):

- `workspaces`, `memories`, `skills`, `plugins` y `SOUL.md` se copian a `LAIA_HOME`
  (`/home/laia-arch/LAIA-ARCH` por defecto).
- `sessions`, `sandboxes`, `atlas`, `cron`, `logs` y el resto de runtime sensible se
  copian a `/srv/laia/arch`.
- los secretos (`auth.json`, `.env`) se copian a `/srv/laia/arch/secrets` (v2). *(El código
  actual los deja en `~/.laia/`; el repunte de `clone_dest_arch_creds_dir` es parte del
  Bloque C.)*
- `config.yaml` se reescribe para que:
  - `laia_root` apunte a `/opt/laia`
  - `agora_data` apunte a `/srv/laia/agora/agora.db`
  - `workspaces`, `memories`, `skills`, `plugins` apunten a `LAIA_HOME`
  - paths legacy desconocidos bajo `~/.laia` caigan por defecto en `/srv/laia/arch`

Este default conservador evita mandar estado sensible a la zona editable por error.
