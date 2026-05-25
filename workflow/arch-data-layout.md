# LAIA-ARCH Data Layout

Este documento describe la separación operativa de datos de LAIA-ARCH durante
instalación y clone. Es una guía de trabajo; el contrato conceptual sigue siendo
`LAIA_ECOSYSTEM.md`.

## Principio

Separar la mesa de trabajo viva del admin de la caja fuerte/runtime sensible:

| Zona | Uso |
|---|---|
| `/home/jorge/LAIA-ARCH/` | Datos interactivos que Jorge/LAIA-ARCH crea, edita o instala con frecuencia. |
| `/srv/laia/arch/` | Estado operacional/sensible de LAIA-ARCH. No se toca a mano salvo mantenimiento. |

## `/home/jorge/LAIA-ARCH/`

Aquí viven datos vivos del admin:

```text
/home/jorge/LAIA-ARCH/
├── workspaces/
├── memories/
├── skills/
└── plugins/
```

Regla: si Jorge o LAIA-ARCH lo crea, edita, instala o reorganiza de forma
frecuente, va aquí.

## `/srv/laia/arch/`

Aquí vive estado interno, sensible u operacional:

```text
/srv/laia/arch/
├── SOUL.md
├── config.yaml
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

Regla: si contiene identidad, configuración, sesiones, logs, ejecución temporal,
automatización, snapshots o estado interno, va aquí.

## Compatibilidad Temporal

`auth.json` y `.env` siguen copiándose al directorio de credenciales legacy
(`~/.laia/` o su override) porque algunos scripts LXD todavía esperan ese path
para montar credenciales en `laia-agora`.

Mover esos secrets a `/srv/laia/arch/` como ubicación canónica requiere una fase
separada que actualice:

- `infra/lxd/scripts/rebuild-3-provision-agora.sh`
- `infra/lxd/scripts/rebuild-3b-fix-authjson.sh`
- tests de preflight/auth
- documentación de seguridad

## Comportamiento Del Clone

Cuando `laia-clone` migra una instalación legacy (`~/.laia/`):

- `workspaces`, `memories`, `skills` y `plugins` se copian a `LAIA_HOME`
  (`/home/jorge/LAIA-ARCH` por defecto).
- `sessions`, `sandboxes`, `atlas`, `cron`, `logs` y el resto de runtime
  sensible se copian a `/srv/laia/arch`.
- `config.yaml` se reescribe para que:
  - `laia_root` apunte a `/opt/laia`
  - `agora_data` apunte a `/srv/laia/agora/agora.db`
  - `workspaces`, `memories`, `skills`, `plugins` apunten a `LAIA_HOME`
  - paths legacy desconocidos bajo `~/.laia` caigan por defecto en
    `/srv/laia/arch`

Este default conservador evita mandar estado sensible a la zona editable por
error.
