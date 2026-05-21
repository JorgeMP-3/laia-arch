# Handoff — Resiliencia del rebuild y operación de AGORA

> **Para**: el siguiente agente (Codex) que arranque desde un git limpio en esta máquina.
> **Por**: el agente que acaba de cerrar `control-center-v0.2-polished` (commit `e2b8ea5`).
> **Objetivo**: blindar el ciclo de vida operativo de AGORA para que los problemas que detallo en §1 no vuelvan a aparecer.

---

## 0. Contexto mínimo que necesitas

- Repo: `/home/laia-hermes/LAIA` (rama `feat/agora-redesign-centralized-brain`, último commit `e2b8ea5`).
- Arquitectura desplegada: **cerebro centralizado** en container LXD `laia-agora` (escucha en :8000 dentro del container, expuesto al host vía proxy device en :8088). Cada usuario tiene su propio container `laia-<slug>` que corre el `laia-executor` (escucha en :9091) — el cerebro forwardea tool calls de filesystem/bash al executor del usuario.
- Containers actuales (`lxc list`):
  - `laia-agora` (cerebro) — RUNNING.
  - `laia-jorge-dev` (executor del primer user) — RUNNING.
  - `laia-jorge` (container del sprint 2, **NO TOCAR**, está STOPPED y así debe quedar).
- Bind mounts host→container:
  - `/srv/laia/agora` → `/opt/agora/data` (DB sqlite, sesiones, workspaces compartidos).
  - `/home/laia-hermes/.laia/auth.json` → `/opt/agora/data/auth.json` (OAuth ChatGPT Teams, read-only).
- Persistencia del usuario admin: `jorge` / `dev-admin` (definido como seed en `services/agora-backend/app/storage.py:162`).
- Control center documentado en `docs/CONTROL_CENTER.md`.
- Scripts de rebuild en `infra/lxd/scripts/`:
  - `rebuild-1-cleanup.sh` — limpia containers de test + `agora.db` (preserva `laia-jorge` y `laia-agora`).
  - `rebuild-2-images.sh` — reconstruye imágenes LXD `laia-agora-base` y `laia-agent` desde el código del repo.
  - `rebuild-3-provision-agora.sh` — provisiona el container `laia-agora` (cerebro), escribe state file en `/tmp/laia-agora-state.json`.
  - `rebuild-3b-fix-authjson.sh` — workaround para re-pushear auth.json cuando se rompe el bind mount.
  - `rebuild-4-first-user.sh --slug <slug>` — provisiona container del primer usuario + registra agente en agora.db. Ya es **idempotente** para user/agent existentes (commits posteriores a `e2b8ea5`).

## 1. Qué problemas estamos resolviendo (incidente real, 2026-05-18)

Después de cerrar el control center, intentamos re-provisionar `jorge-dev` y nos comimos esta cascada:

1. **`/tmp/laia-agora-state.json` no existía** — el host se había reiniciado y `/tmp` se limpia. Lo regeneré a mano leyendo el container vivo.
2. **`rebuild-4` falló porque user `jorge-dev` ya existía** — el script no era idempotente; lo parché en caliente. Después fallaba porque el agente seguía linkeado. También lo parché.
3. **Backend del host fantasma** — el `agora-backend.service` (systemd) y un `pm2 agora-backend` estaban respawneando un uvicorn en host:8088, **además** del proxy LXD que ya escucha ahí por diseño. Lo detuve con `pm2 stop` y `systemctl stop && disable`.
4. **Confusión "quién escucha 8088"** — perdí 30 min pensando que era el backend del host, cuando era el proxy LXD `host:8088 → laia-agora:8000`. No hay doc explicando esto.
5. **TUI control center mostraba "API: Not Found"** — la imagen `laia-agora-base` se había construido antes del commit del control center, así que dentro del container no existía `services/agora-backend/app/admin.py`. Tampoco había forma automatizada de detectar que la imagen estaba desincronizada del repo.
6. **Chat con "AIAgent placeholder cannot run a conversation"** — dentro del venv del container faltaba el paquete `laia-agent` (pyproject.toml en `.laia-core/`). El fix curado `pip-install-laia-core` del registry lo arregla, pero solo si lo aplicas tú a mano. La build de la imagen NO lo hace.
7. **`DELETE /api/agents/{slug}` requiere `laiactl`** que no está dentro del container, así que el endpoint del control center está roto para ese caso.

Todos son recurrentes: van a volver a pasar en cuanto haya otro rebuild, reboot, o commit que toque el backend / `.laia-core/`.

## 2. Trabajo a entregar

Implementa los 4 cambios estructurales (P0-P3) y los 2 opcionales (P4-P5) si te queda tiempo. Cada uno con sus tests.

### P0 — `infra/dev/preflight.sh`

Script ejecutable que corra automáticamente al inicio de `rebuild-1-cleanup.sh`, `rebuild-3-provision-agora.sh` y `rebuild-4-first-user.sh`. Detecta y reporta (sin auto-arreglar) los gotchas conocidos:

- Procesos fantasma escuchando en `host:8088`, `host:8089`, `host:9090`, `host:9091`:
  - `pm2 list | grep agora` con conteo de restarts > 50 → ⚠.
  - `systemctl is-active agora-backend.service` ∈ `{active, activating, failed}` → ⚠ (esperado: `inactive`).
  - Cualquier uvicorn manual del repo `LAIA/services/agora-backend` corriendo en el host → ⚠.
- Imagen vs repo:
  - Lee `lxc image info laia-agora-base` (campo `Uploaded` o `created_at`) y lo compara con `git log -1 --format=%ct services/agora-backend/ .laia-core/`. Si el commit es más nuevo que la imagen → ⚠ "imagen desactualizada, conviene rebuild-2".
- Permisos:
  - `/srv/laia/agora` debe ser `laia-hermes:laia-hermes 755`. Si es `UNKNOWN:UNKNOWN 700` (un fallo típico tras un cleanup raw.idmap) → ⚠ con comando para arreglarlo.
  - `~/.laia/auth.json` debe ser modo `644`. Si está `600` → ⚠.
- State files:
  - `/tmp/laia-agora-state.json` existe pero el container `laia-agora` no → ⚠ "state stale".
  - El container `laia-agora` existe pero no hay state → ⚠ "ejecuta rebuild-state.sh".
- Banner final con resumen `X warnings, Y blockers`. Salida exit `0` (warnings) o `2` (blockers).

Flag `--fix` opcional: arregla lo arreglable sin sudo (chmod auth.json, pm2 stop si está respawneando) y pide los sudo necesarios uno por uno.

Tests: `tests/test_preflight.sh` con bats o un script bash que monte escenarios fake (mock con functions, no toca infra real).

### P1 — `infra/dev/smoke-test.sh`

Script ejecutable que corra al final de `rebuild-4-first-user.sh` (o standalone). Hace un end-to-end real, sin mocks:

1. `curl -sf http://127.0.0.1:8088/api/health` → debe responder 200.
2. Login admin con `jorge`/`dev-admin` → debe devolver `access_token`.
3. `GET /api/admin/status` con el token → debe devolver JSON con `health.ok=true`, `containers.running ≥ 2`, `users.total ≥ 1`. Si el endpoint devuelve 404 → falla con mensaje explícito "imagen no incluye control center, corre rebuild-2".
4. `POST /api/admin/tests/run` (asincrono) y espera ≤ 60s → debe terminar con `status=completed` y `result.returncode=0`.
5. Chat de 1 turno con el slug pasado por arg (`--slug jorge-dev` por defecto):
   - `POST /api/login` con `jorge-dev` y la password del state file de su user (`/home/laia-hermes/.laia/state/laia-state-<slug>.json` tras P2, o `/tmp/laia-state-<slug>.json` si aún no migrado).
   - `POST /api/chat/stream` con `{"message":"di hola"}` y consume el stream.
   - Verifica que **no** aparece "AIAgent placeholder cannot run a conversation" en ningún chunk → si aparece, falla con "venv del container sin .laia-core instalado, aplicar fix `pip-install-laia-core`".
   - Espera al menos 1 chunk `type=assistant_message` antes del timeout (30s).
6. Salida verde si todo pasa. Salida roja con la lista de pasos fallidos.

Tests: añadir un job opcional en `services/agora-backend/.github/workflows/` (si existe CI) o un comando `make smoke` que lo invoque. Mínimo: que `smoke-test.sh --help` funcione y `smoke-test.sh --dry-run` no toque nada.

### P2 — State files persistentes en `~/.laia/state/`

- Mover de `/tmp/laia-*.json` a `${LAIA_STATE_DIR:-$HOME/.laia/state/}`.
- Adaptar `rebuild-3-provision-agora.sh` y `rebuild-4-first-user.sh` para escribir ahí. Hacer back-compat: si encuentra el path viejo en `/tmp`, lo mueve y avisa.
- Crear `infra/dev/rebuild-state.sh` — nuevo script: inspecciona los containers vivos y regenera los state files. Útil tras reboot o cuando alguien borró `~/.laia/state/`. Lo que hice a mano hoy reconstruyendo `laia-agora-state.json` debe ser este script.
- Test: `tests/test_rebuild_state.sh` que mockea `lxc list` y verifica el JSON generado.

### P3 — Build de imagen instala `.laia-core` como paquete

- En `infra/lxd/scripts/build-agora-image.sh` (o equivalente que construye `laia-agora-base`), añadir paso `pip install /opt/agora/app/.laia-core` (usa el `pyproject.toml`, NO `requirements.txt` que ya no existe) **dentro del cloud-init / build steps**, antes del snapshot final de la imagen.
- Como consecuencia, **elimina el fix `pip-install-laia-core` del registry** en `services/agora-backend/app/admin.py:_FIX_REGISTRY`, o reescríbelo a `pip-reinstall-laia-core` orientado a upgrades futuros.
- Actualizar `docs/CONTROL_CENTER.md` para reflejar el cambio en la lista de fixes.
- Test backend: `tests/test_admin_control_center.py::test_list_fixes_returns_curated_registry` — actualízalo para validar la nueva lista. Suite completa debe seguir verde (193/193 antes del cambio).

### P4 — Doctor / detector de desincronización imagen↔repo (opcional)

- Endpoint nuevo `GET /api/admin/image/freshness` que devuelva `{built_at, last_commit_touching_backend, drift_seconds, drift_warning_threshold}`. Lo usan tanto el control center TUI (badge "imagen vieja" en Sistema) como el preflight de P0.
- Test backend que mockee `_run_command(["lxc","image","info",...])` y verifique el cómputo.

### P5 — Doc `docs/OPERATIONS.md` (opcional)

Sección "Quién escucha qué":

```
host:8088  → laia-agora :8000   (proxy LXD device, definido en rebuild-3)
host:9090  → laia-jorge-dev :9091 (executor del user, definido en rebuild-4)
host:8077  → laia-core dev server (UI legacy, opcional)
host:8000  → solo accesible desde dentro de containers
```

Sección "Procesos a vigilar":

- `pm2 list` debe estar **vacío** de procesos `agora-backend`. Si aparece, ha respawnado tras un cambio de arquitectura.
- `systemctl status agora-backend.service` debe estar `inactive` **en el host** (corre dentro de `laia-agora`, no en el host).
- Cualquier `uvicorn app.main:app` en `ps -ef` con cwd en el repo del host es un proceso descontrolado.

Sección "Cómo recuperar tras reboot":

```bash
bash infra/dev/preflight.sh           # detecta lo que esté roto
bash infra/dev/rebuild-state.sh       # regenera state files si /tmp se limpió
# (si preflight reporta imagen vieja)
sudo bash infra/lxd/scripts/rebuild-2-images.sh
sudo bash infra/lxd/scripts/rebuild-3-provision-agora.sh
sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev
bash infra/dev/smoke-test.sh --slug jorge-dev
```

## 3. Constraints (durables, deben cumplirse SIEMPRE)

Estas reglas vienen de memorias de sesiones anteriores. No tienes que descubrirlas, te las paso:

- **NUNCA `git rm`**. Si algo está obsoleto, `git mv` a `archived/sprint2-<topic>/` o `archived/<fecha>-<motivo>/`. Mantener la trazabilidad.
- **NO toques `laia-jorge`** — es el container del sprint 2, está intencionalmente STOPPED, hay snapshots con estado valioso.
- **NO toques `laia-ui/packages/agora-app/`** — la UI web es de otro stream y está fuera de scope.
- **Paridad LLM con ARCH** — cualquier cambio que toque providers debe respetar los 30+ providers ya soportados por `.laia-core/laia_cli/plugins/`. No reduzcas.
- **NO commits por iniciativa propia** — solo cuando el usuario lo pida. Mientras tanto trabaja en la rama actual o en una nueva si te lo pide.
- **Tests verdes antes de marcar una fase completa**. Si rompes la suite, no avances.
- **No mockees la DB en tests de integración** — usa la `agora.db` real del test (`tmp_path` fixture).

## 4. Cómo verificar al final

```bash
# 1) Backend tests siguen verde
cd ~/LAIA/services/agora-backend
PYTHONPATH=/home/laia-hermes/LAIA/.laia-core .venv/bin/pytest tests/ -q
# esperado: 193 + tests nuevos que añadas ≥ 193 + N, ZERO failures.

# 2) Preflight ejecuta limpio
bash ~/LAIA/infra/dev/preflight.sh
# esperado: exit 0, sin warnings sobre estado actual del lab.

# 3) Smoke test end-to-end
bash ~/LAIA/infra/dev/smoke-test.sh --slug jorge-dev
# esperado: 6/6 pasos verdes.

# 4) Doc CONTROL_CENTER.md actualizado (fix list refleja P3).
grep -c "pip-install-laia-core" ~/LAIA/docs/CONTROL_CENTER.md
# esperado: 0 (eliminado) o 1 con la nota "removed in PX".

# 5) State files migrados
ls ~/.laia/state/laia-agora-state.json
ls ~/.laia/state/laia-state-jorge-dev.json
# esperado: ambos existen, modo 600 o 644.

# 6) rebuild-2 + 3 + 4 desde cero termina en verde
sudo bash ~/LAIA/infra/lxd/scripts/rebuild-1-cleanup.sh
sudo bash ~/LAIA/infra/lxd/scripts/rebuild-2-images.sh
sudo bash ~/LAIA/infra/lxd/scripts/rebuild-3-provision-agora.sh
sudo bash ~/LAIA/infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev
# y al final el smoke test integrado dentro de rebuild-4 debe pasar.
```

## 5. Entregable esperado

Cuando termines:

1. Resumen de qué hiciste en cada P0/P1/P2/P3 (+ P4/P5 si te dio tiempo) — bullets cortos.
2. Lista de archivos nuevos / modificados.
3. Output del comando de verificación §4 punto (6) — el flujo end-to-end desde cero.
4. Pídele al usuario que haga commit + tag `resilience-hardening-v0.1` (no commitees tú).
5. Si dejas algo sin terminar, documenta el "por qué" y el next step en un comentario en el handoff o en un `TODO_NEXT.md`.

## 6. Anti-patrones que NO debes hacer

- Auto-fixear en `preflight.sh` sin `--fix` explícito. Reportar primero, actuar después.
- Borrar `laia-jorge` ni siquiera "temporalmente para test".
- Cambiar el seed de jorge/dev-admin — hay scripts y docs que dependen de eso.
- Añadir un endpoint admin que ejecute shell arbitrario "para arreglar el problema": el `_FIX_REGISTRY` es **curado**, no se hace genérico.
- Hacer `pm2 delete` ni `systemctl disable` desde scripts automáticos. Eso lo decide el operador.
- Asumir que `/tmp` persiste entre reboots. No lo hace.
- Asumir que la imagen LXD está al día. Verifícalo.

## 7. Si te bloqueas

- Lee el commit `e2b8ea5` y `docs/CONTROL_CENTER.md` para entender el estado del control center.
- Lee `docs/HANDOFF_CONTROL_CENTER.md` (el handoff anterior, te da contexto histórico).
- El log de la incidencia de hoy está implícito en este documento §1 — si necesitas más detalle, pregúntale al usuario.
- Si un test no se reproduce localmente pero falla en CI, es probable que el venv del container y el venv del host estén divergiendo. P3 lo arregla.

Buena suerte.
