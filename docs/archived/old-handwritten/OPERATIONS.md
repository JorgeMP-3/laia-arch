# AGORA Operations

> 📅 Actualizado: 2026-05-19

Guía rápida para operar la arquitectura LXD actual sin confundir procesos del
host con servicios dentro de containers.

## Quién Escucha Qué

| Endpoint host | Destino | Notas |
|---|---|---|
| `host:8088` | `laia-agora:8000` | Proxy LXD device creado por `rebuild-3-provision-agora.sh`. |
| `host:9090` | `laia-jorge-dev:9091` | Executor del primer usuario si se expone para pruebas. |
| `host:8077` | laia-core dev server | UI legacy opcional. |
| `host:8000` | solo dentro de containers | No debe haber backend AGORA del host ocupándolo. |

El backend AGORA de producción corre dentro de `laia-agora` como
`agora-backend.service`. En el host, `127.0.0.1:8088` debe ser el proxy LXD, no
un `uvicorn` manual ni PM2.

## Procesos a Vigilar

- `pm2 list` debe estar vacío de procesos `agora-backend`. Si aparece,
  probablemente está respawneando una arquitectura anterior.
- `systemctl status agora-backend.service` debe estar `inactive` en el host.
  El servicio real corre dentro de `laia-agora`.
- `ps -ef | grep "uvicorn app.main:app"` no debe mostrar un proceso con cwd en
  `LAIA/services/agora-backend` en el host.
- `lxc list` debe mostrar `laia-agora` y el executor del usuario activo en
  `RUNNING`. `laia-jorge` es estado histórico de sprint 2: no tocar.

## Recuperación Tras Reboot

```bash
bash infra/dev/preflight.sh
bash infra/dev/rebuild-state.sh

# Si preflight reporta imagen vieja:
sudo bash infra/lxd/scripts/rebuild-2-images.sh
sudo bash infra/lxd/scripts/rebuild-3-provision-agora.sh
sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev

bash infra/dev/smoke-test.sh --slug jorge-dev
```

Los state files persistentes viven en:

```bash
~/.laia/state/laia-agora-state.json
~/.laia/state/laia-state-<slug>.json
```

Los scripts mantienen compatibilidad con `/tmp/laia-*.json`, pero `/tmp` no
debe considerarse persistente.

En hosts con containers LXD unprivileged, `/srv/laia/agora` puede aparecer
como `UNKNOWN:UNKNOWN` desde el host porque pertenece al uid/gid mapeado del
usuario `agora` dentro del container. Es correcto si dentro de `laia-agora`
se ve como `agora:agora` y el backend responde en `/api/health`.

## Checks Habituales

```bash
bash infra/dev/preflight.sh
curl -fsS http://127.0.0.1:8088/api/health | jq .
python3 infra/dev/agora-control-center-tui.py --print-status
make smoke
```

## Marketplace (marketplace-v0.1)

Cuatro tablas nuevas en `agora.db`: `plugin_registry`, `plugin_installs`,
`skill_registry`, `skill_installs`. Una columna nueva en `users`:
`mcp_servers_json`. Migraciones idempotentes — no requieren backfill manual.

Blobs publicados y áreas de instalación por usuario:

```
/srv/laia/agora/plugin-store/<slug>-<version>.tar.gz
/srv/laia/agora/skill-store/<slug>.md
/srv/laia/agora/installed-plugins/<user_slug>/<plugin_slug>/
/srv/laia/agora/installed-skills/<user_slug>/<skill_slug>.md
```

Estos paths viven dentro de `laia-agora`, mapeados desde el host vía el bind
mount `/srv/laia/agora → /opt/agora/data` que ya existía. No requieren
configuración adicional.

### CLI

```bash
infra/dev/laia-marketplace.py --slug jorge-dev plugin publish ./hello-plugin --publish
infra/dev/laia-marketplace.py --slug jorge-dev plugin list --installed
infra/dev/laia-marketplace.py --slug jorge-dev plugin install hello-mp
infra/dev/laia-marketplace.py --slug jorge-dev plugin uninstall hello-mp
infra/dev/laia-marketplace.py --slug jorge-dev mcp add notion https://mcp.notion.com --header "Authorization=Bearer t"
```

Auth resuelta por orden: `AGORA_TOKEN` → `AGORA_USERNAME+PASSWORD` →
`--slug` con state file (`~/.laia/state/laia-state-<slug>.json`).

### Aprobación de plugins/skills

Las acciones admin viven en el **Control Center TUI**, pestaña 9 — `Marketplace`:

```bash
python3 infra/dev/agora-control-center-tui.py
# Tab hasta Marketplace o 9
# a = aprobar  x = rechazar  v = revocar (catálogo)
```

Sin TUI, vía curl con token admin:

```bash
TOKEN="dev-admin-token"     # seed token del admin jorge
curl -sH "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:8088/api/admin/marketplace/pending | jq .
curl -sH "Authorization: Bearer $TOKEN" \
     -X POST http://127.0.0.1:8088/api/admin/plugins/<id>/approve | jq .
```

### Mantenimiento

- Listar blobs huérfanos: `ls /srv/laia/agora/plugin-store/` vs
  `SELECT blob_path FROM plugin_registry`. Cualquier `.tar.gz` que no
  aparezca en la DB se puede borrar a mano.
- Revocar plugin aprobado: `POST /api/admin/plugins/<id>/revoke` (degrada
  a `personal+rejected`; los usuarios con instalación activa lo siguen
  viendo hasta que reinstalen).
- Reset de un user: `infra/dev/laia-marketplace.py --slug X plugin uninstall <slug>`.
- Tamaño máximo por upload: `AGORA_PLUGIN_MAX_BYTES` (default 5MB),
  `AGORA_SKILL_MAX_BYTES` (default 256KB).

### Riesgos conocidos

- v0.1 **no aísla plugins por usuario concurrente**: la materialización
  vía `LAIA_EXTRA_PLUGIN_DIRS` se serializa bajo el lock del `AgentPool`,
  así que el contenido del PluginManager refleja siempre al *último*
  user que construyó sesión. Para uso de un solo usuario activo
  (jorge-dev), no es un problema. Multi-usuario simultáneo: P1.
- Los plugins aprobados ejecutan código Python en `laia-agora`. v0.1
  confía en review humana antes de aprobar (`status=review`). No hay
  sandbox seccomp/AppArmor todavía.
