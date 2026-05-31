# PRD — Cutover de PRODUCCIÓN v1→v2 (rediseñado y re-testeado)

> ✅ **REDISEÑADO + VALIDADO EN VM (2026-05-31).** Sustituye al intento que falló el
> 2026-05-30 (outage ~50 min de `laia-agora`; post-mortem en `workflow/changelog.md` y
> `workflow/problems.md` → `migrate-v1-to-v2-prod-outage`, ahora resuelto). Los 4 bugs +
> el auto-rollback están arreglados y cubiertos por un test de regresión verde.
> **La ejecución real contra PROD sigue siendo un paso HITL de Jorge** (ventana de reinicio
> de `laia-agora`), fuera del alcance de la IA.

- **Fecha**: 2026-05-31 (rediseño) · intento fallido 2026-05-30
- **Owner**: Jorge (HITL — ejecuta y supervisa en vivo) · IA (diseña, testea, prepara)
- **Estado**: ✅ script arreglado + validado en VM · ⬜ ejecución HITL en prod pendiente
- **Track**: PROD-cutover · **Script**: `infra/lxd/scripts/migrate-v1-to-v2.sh`
- **Test de regresión**: `tests/integration/test_cutover_migration.sh` (profile `vm`)

## Por qué falló el intento del 2026-05-30 (causa raíz)

La migración usaba `rebuild-3b-fix-authjson.sh` (dir-mount `arch-laia` → `/var/lib/laia-host`
+ env `AGORA_ARCH_AUTH_JSON`), un modelo de auth **divergente** del que usa un install fresco
v2. El backend (`agent_pool.py`) lee `/opt/agora/data/auth.json` y **ignora** ese env cuando el
fichero ya existe → el swap no surtía efecto. Encadenado con el borrado del mountpoint del
auth vivo y un auto-rollback que grababa el owner equivocado (`0:0`), dejó `laia-agora` caído.

Los **4 bugs** (detalle en `problems.md`):
1. Quitar el device `agora-auth` destruía el mountpoint `/opt/agora/data/auth.json` (vivo).
2. El swap de auth no surtía efecto (backend lee `/opt/agora/data/auth.json`, ignora el env).
3. Auto-rollback grababa `PRE_AGORA_DATA_OWNER=0:0` (real: `1000999:1000988`) → dir root:root
   → el user `agora` unprivileged pierde acceso → restart falla.
4. File-mount anidado frágil.

**Causa de proceso**: se validó contra un install FRESCO, no contra la migración de un
container EXISTENTE en marcha (lo que es prod).

## El rediseño (qué cambia en `migrate-v1-to-v2.sh`)

Principio: **converger al modelo de auth del install fresco** (`rebuild-3-provision-agora.sh`),
para que un host migrado quede **idéntico** a uno instalado limpio. Sin tocar el backend.

- **Auth (bugs #1/#2/#4)** — el swap deja de usar `rebuild-3b`. Ahora apunta el **file-mount
  `agora-auth`** al secreto v2 `/srv/laia/arch/secrets/auth.json` **modificando el `source` del
  device IN PLACE** (`lxc config device set`, nunca remove+recreate → no se destruye el
  mountpoint vivo). Si no hay `agora-auth`, se añade. `raw.idmap` (host admin ↔ agora) hace el
  secreto 0600 legible sin world-read. Se hace OFFLINE (stop → reconfig → start) para que el
  cambio de mount + el re-shift del idmap apliquen juntos.
- **Verify (bug #2)** — `auth_json_ready` solo comprueba que el fichero existe, no el contenido
  (`main.py:342-344`). El verify ahora exige además que el auth servido sea **EXACTAMENTE el
  secreto v2** (sha, y no vacío); si no, auto-rollback. Mata el "verde falso".
- **Auto-rollback (bug #3)** — `record_rollback_state` captura el owner numérico **en vivo** y
  **falla closed** si no puede leerlo o si es `0:0` (nunca graba un valor que bloquee a `agora`).
  El rollback restaura el owner EXACTO, repunta el `source` del device IN PLACE (sin remove), y
  revierte `raw.idmap`. Tras `cleanup`, el rollback de dispositivo se **rehúsa** y apunta al
  snapshot/backup (correcto: el v1 ya está archivado).
- **Nuevo flag `--no-cleanup`** — migra + verifica pero **conserva `~/.laia`** (no retira v1),
  dejando el `--rollback` de dispositivo instantáneo disponible. Recomendado para el HITL prod:
  observar verde antes de comprometer el cleanup; completar luego con `--resume --yes`.

## Evidencia de validación (VM `laia-dev`, 2026-05-31)

- **Test de regresión** `tests/integration/test_cutover_migration.sh` (construye una réplica v1
  fiel desde la imagen local, sin tocar prod): **19/19 PASS**. 4 escenarios: (1) migrate sirve el
  secreto v2; (2) `--rollback` manual restaura v1 EXACTO; (3) auto-rollback en fallo de verify
  restaura el owner exacto y deja el container verde; (4) tras cleanup el `--rollback` se rehúsa
  sin dañar nada.
- **Réplica fiel del snapshot REAL de prod** (`pre-v2-migration-20260530T182010Z` importado en la
  VM): ciclo baseline verde → migrate (sirve secreto v2) → `--rollback` → verde v1, owner
  `1000999:1000988` restaurado exacto. **14/14 PASS.**

## Ejecución en PROD (HITL — pendiente, Jorge)

> Recordatorio: re-baselinar contra el prod **vivo** del momento (no el snapshot); el prod vivo
> quedó en un estado recuperado a mano que difiere del snapshot (ver `security.md`).

1. Anunciar ventana (reinicio de `laia-agora`, segundos).
2. `sudo bash migrate-v1-to-v2.sh --dry-run --yes` — revisar el plan.
3. `sudo bash migrate-v1-to-v2.sh --yes --no-cleanup` — migra + verifica, conserva `~/.laia`.
   - **Gate**: `/api/health` `ok:true` + auth servido = secreto v2 + login/chat de humo real.
   - Si rojo → auto-rollback ya disparado (o `--rollback` manual): v1 intacto. Parar y diagnosticar.
4. Periodo de observación con `~/.laia` aún disponible (rollback instantáneo).
5. En verde sostenido: `sudo bash migrate-v1-to-v2.sh --resume --yes` (ejecuta el cleanup =
   archiva `~/.laia`). Tras backup confirmado: `--purge-old` o borrar `~/.laia.v1-migrated-*`.
6. Deploy v0.2.0 + completar layout + D2 en prod (fases del plan original, sin cambios).

## Rollback

- **Antes de cleanup**: `migrate-v1-to-v2.sh --rollback` (instantáneo, `~/.laia` intacto,
  restaura device + idmap + owner exacto) y/o `laia-rollback` para el código.
- **Después de cleanup**: el script rehúsa el rollback de dispositivo y apunta a
  `lxc restore laia-agora pre-v2-migration-<ts>`, `mv ~/.laia.v1-migrated-<ts> ~/.laia`, o el tar.

## Criterios de aceptación (prod)

- `/api/health` `ok:true` y el auth servido **es** el secreto v2 (`/srv/laia/arch/secrets`, 0600).
- D2 verde en prod + login y chat reales OK.
- `~/.laia` archivado (no borrado hasta observación). Snapshot + tar verificados antes de migrar.
