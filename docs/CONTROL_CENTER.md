# AGORA Control Center

Centro de control operativo del backend AGORA. Permite al admin (rol
`admin` en `agora-backend`) provisionar usuarios, gestionar containers
LXD, ver jobs en curso, inspeccionar audit/logs/errors y aplicar fixes
curados ante incidencias conocidas — todo desde una TUI dependency-free
o desde la API directa.

## Componentes

- **Backend admin (`services/agora-backend/app/admin.py`)** — router
  `/api/admin/*` con jobs en `ThreadPoolExecutor`, persistencia en
  SQLite (`admin_jobs`), rate-limiting (30 mutating req/60 s/actor),
  logger estructurado `agora.admin` y registry de fixes curados.
- **TUI (`infra/dev/agora-control-center-tui.py`)** — interfaz curses
  con 8 vistas. Solo `stdlib` (curses + urllib + json). No requiere
  modificar el venv del backend; corre desde el host.

## Lanzar la TUI

```bash
# 1. Backend escuchando en el endpoint admin
sudo systemctl status agora-backend.service

# 2. Lanzar la TUI (login interactivo)
python3 infra/dev/agora-control-center-tui.py --api-url http://127.0.0.1:8088

# 3. O usando variables de entorno
AGORA_API_URL=http://127.0.0.1:8088 \
AGORA_ADMIN_USERNAME=jorge \
AGORA_ADMIN_PASSWORD=... \
python3 infra/dev/agora-control-center-tui.py

# 4. Token persistido: tras el primer login el token JWT queda en
#    ~/.laia/admin-session.json (modo 600). Re-ejecutar la TUI no
#    pedirá password mientras el token siga vigente.

# 5. Snapshot one-shot sin entrar a la TUI (útil en scripts)
python3 infra/dev/agora-control-center-tui.py --print-status
```

Flags soportadas: `--api-url`, `--token`, `--username`, `--password`,
`--print-status`, `--timeout`.

Variables: `AGORA_API_URL`, `AGORA_ADMIN_TOKEN`,
`AGORA_ADMIN_USERNAME`, `AGORA_ADMIN_PASSWORD`, `AGORA_SESSION_PATH`
(por defecto `~/.laia/admin-session.json`).

## Vistas

| # | Vista       | Para qué sirve                                                                |
|---|-------------|-------------------------------------------------------------------------------|
| 1 | Panel       | Salud global: backend up, auth.json status, containers/usuarios/agentes.      |
| 2 | Usuarios    | Listado enriquecido con LXC + provisionar / rebuild / borrar.                 |
| 3 | Containers  | Estado LXD por container + restart / snapshot / restore.                      |
| 4 | Jobs        | Jobs admin en curso/recientes + detalle con tail de log.                      |
| 5 | Logs        | journalctl de cualquier unidad (default `agora-backend`).                     |
| 6 | Audit       | Tool calls registrados (con cursor pagination y filtro por user).             |
| 7 | Errores     | Errores recientes capturados por el logger `agora.admin`.                     |
| 8 | Sistema     | Salud + acciones globales (OAuth refresh, restart backend, tests, fixes).     |

### Atajos comunes

- `Tab` / flechas izquierda-derecha / `1..8` — cambiar vista.
- Flechas arriba-abajo — mover selección dentro de la vista.
- `r` — refrescar (`R` solo en Containers para evitar conflicto con
  `R = restart`).
- `Ctrl+L` — clear screen + refresh forzado.
- `?` / `h` — ayuda.
- `Ctrl+C` o `q` — salir limpio (restaura handler de señales).

### Badges

- `Jobs (N)` — N jobs en estado `running`. Tomado de
  `GET /api/admin/status` → `jobs.running`.
- `Errores (N)` — N errores capturados recientemente en
  `status.recent_errors`.

Cuando el badge aparece sobre una tab no seleccionada, se pinta en
amarillo para que el operador note la novedad sin saltar de vista.

## Acciones críticas

| Vista       | Tecla | Acción                                                          |
|-------------|-------|------------------------------------------------------------------|
| Usuarios    | `p`   | Provisionar usuario nuevo + container (job async).               |
| Usuarios    | `b`   | Rebuild del container del usuario seleccionado.                  |
| Usuarios    | `d`   | Soft-delete + borrado de container y bind mount.                 |
| Containers  | `R`   | Restart del container LXD seleccionado.                          |
| Containers  | `s`   | Snapshot con nombre (default `snap-YYYYMMDD-HHMM`).              |
| Containers  | `o`   | Restore desde snapshot existente.                                |
| Sistema     | `a`   | Re-push de `~/.laia/auth.json` al container `laia-agora`.        |
| Sistema     | `B`   | Restart `agora-backend.service` (perderás la conexión brevemente). |
| Sistema     | `T`   | Lanza `pytest` del backend como job async.                       |
| Sistema     | `F`   | Aplica un fix curado del registry (ver más abajo).               |

Todas las mutaciones pasan por:

1. `_admin_rate_limit(actor.id)` — 30 acciones/60 s; si excede,
   `429 Too Many Requests` con `Retry-After`.
2. `_log_admin_action(...)` — log estructurado JSON en
   `agora.admin` con campos `actor_id`, `event`, `target`, `params`.
3. SQLite `admin_jobs` — registro del job, status, params, result,
   error y `log_tail`.

## Fix registry curado

`GET /api/admin/fixes` devuelve los fixes disponibles. `POST
/api/admin/fix/{name}` los ejecuta. Cubren incidencias conocidas:

| Nombre                    | Qué resuelve                                                     |
|---------------------------|------------------------------------------------------------------|
| `auth-json-push`          | Re-pushea `~/.laia/auth.json` al container `laia-agora` con permisos correctos (workaround del bind mount sobre directorio nested). |
| `pip-reinstall-laia-core` | Reinstala `.laia-core` desde `pyproject.toml` en el venv de `laia-agora`. Las imágenes nuevas ya lo instalan durante build; este fix queda para upgrades/venvs dañados. |
| `pm2-stop-respawner`      | Detiene cualquier proceso pm2 que esté respawneando uvicorn viejo. |
| `chmod-laia-dir`          | Re-aplica `chmod 755 ~/.laia` cuando LAIA-ARCH vuelve a fijarlo a 700 y rompe el bind mount.       |

Desde la TUI: vista Sistema → `F` → se elige el fix por nombre.

Desde curl:

```bash
TOKEN=$(curl -sX POST http://127.0.0.1:8088/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"jorge","password":"..."}' | jq -r .access_token)

curl -sX POST http://127.0.0.1:8088/api/admin/fix/auth-json-push \
  -H "Authorization: Bearer $TOKEN"
```

## Tests

- `GET /api/admin/tests/status` — último run conocido (`unknown` si
  no se ha lanzado en esta sesión).
- `POST /api/admin/tests/run` — ejecuta `pytest tests/` del backend
  como job async, captura return code, duración, tail de stdout.

Desde TUI: vista Sistema → `T`.

## Endpoints disponibles

Resumen, todos prefijados con `/api/admin`:

- `GET  /status` — health + auth + containers + users + agents +
  `jobs` + `tests` + `recent_errors`.
- `GET  /containers`, `POST /containers/{name}/restart`,
  `POST /containers/{name}/snapshot`, `POST /containers/{name}/restore`.
- `GET  /users`, `POST /users/provision`,
  `POST /users/{slug}/rebuild`, `DELETE /users/{slug}`.
- `GET  /jobs`, `GET /jobs/{id}`.
- `GET  /logs/{name}` — wraps `journalctl -u`.
- `GET  /audit/tools?limit=N&user_id=...&before=ISO` — cursor
  pagination: la respuesta incluye `next_before` para paginar hacia
  atrás en el tiempo.
- `GET  /errors?limit=N` — errores recientes del logger.
- `GET  /fixes`, `POST /fix/{name}`.
- `GET  /image/freshness` — compara timestamp de imagen `laia-agora`
  contra el último commit que toca `services/agora-backend` o `.laia-core`.
- `GET  /tests/status`, `POST /tests/run`.
- `POST /system/refresh-oauth`, `POST /system/restart-backend`.

## Seguridad

- Toda ruta admin requiere JWT con `role=admin` (verificado por
  dependency `require_admin`).
- Rate limit por `actor.id` (no por IP) para evitar burst de
  mutaciones.
- `image_alias` validado contra `_ALLOWED_IMAGE_ALIASES` antes de
  llamar a LXD.
- `slug` validado contra regex estricto antes de cualquier llamada a
  `lxc`.
- El token persistido se guarda en `~/.laia/admin-session.json` modo
  600. Para invalidar la sesión basta con borrar el fichero o
  reiniciar el backend.
- El backend rechaza `delete_user` sobre el slug del propio actor
  (no podés borrarte a ti mismo).

## Troubleshooting

- **TUI no arranca / "non-json response"** — el backend devuelve HTML
  de error. Verificar `journalctl -u agora-backend.service -n 50`.
- **401 al refrescar** — el token persistido expiró. La TUI lo detecta
  en arranque y limpia `~/.laia/admin-session.json` automáticamente,
  pero si entras en medio de la sesión, sal con `q` y vuelve a
  ejecutar para forzar nuevo login.
- **`refresh-oauth` falla con `permission denied`** — el bind mount de
  `~/.laia` está en modo 700. Aplicar fix `chmod-laia-dir`.
- **Jobs colgados en `running`** — revisar `journalctl -u
  agora-backend -f` y `GET /api/admin/jobs/{id}` para ver `log_tail`.
  Si el backend reinició a mitad del job, el estado quedará
  inconsistente; restart-backend + relanzar la acción.
- **Badge Sistema `(!)` / imagen vieja** — `GET
  /api/admin/image/freshness` detectó que el repo tiene cambios más
  nuevos que la imagen `laia-agora`. Ejecutar `rebuild-2-images.sh`
  antes de reprovisionar.
- **Vista Errores siempre vacía** — el logger solo captura errores
  emitidos desde `agora.admin`. Logs ad-hoc con `print(...)` o
  excepciones no capturadas por el handler no aparecen aquí; usar la
  vista Logs (`journalctl`) para esos.

## Tests del propio control center

```bash
cd ~/LAIA/services/agora-backend
PYTHONPATH=/home/laia-hermes/LAIA/.laia-core .venv/bin/pytest \
  tests/test_admin_control_center.py -q
# tests específicos del control center + suite completa del backend.
```
