# Runbook — Migración in-place v1 → v2 (`migrate-v1-to-v2.sh`)

> ⚠️ **ACTUALIZADO 2026-05-31 tras el outage del 2026-05-30.** El primer intento en prod falló
> (post-mortem en `changelog.md`). El script fue **rediseñado y re-testeado**; la fase 7 ya **no**
> usa `rebuild-3b` (dir-mount + env), sino que **converge al modelo file-mount de `rebuild-3`**
> (apunta el device `agora-auth` al secreto v2, modificando su `source` IN PLACE). El plan HITL
> de prod, la evidencia de validación y el detalle del rediseño están en el PRD canónico:
> [`workflow/plans/2026-05-31-prod-cutover-v1v2-redesigned.md`](../2026-05-31-prod-cutover-v1v2-redesigned.md).
> Este runbook conserva el procedimiento general; donde diga "rebuild-3b" léase el nuevo swap in-place.

> **Qué es esto:** el procedimiento HITL para aplicar el layout **v2** a un host ARCH **v1**
> existente (como producción) **in-place**, idempotente, con backup y rollback. Slice **C3** ·
> módulo **M6** · decisión **T2** del [plan técnico](2026-05-29-estabilizacion-plan-tecnico.md).
>
> **Script:** [`infra/lxd/scripts/migrate-v1-to-v2.sh`](../../../infra/lxd/scripts/migrate-v1-to-v2.sh)
> **Re-testeado en la VM `laia-dev`** contra una réplica del snapshot REAL de prod + un test de
> regresión (`tests/integration/test_cutover_migration.sh`). **Aplicar a PROD es el paso HITL
> final** (Jorge), con ventana de reinicio de `laia-agora` planificada.

---

## 0. Qué hace (de v1 a v2)

| | v1 (origen) | v2 (destino) |
|---|---|---|
| Secretos | `~/.laia/{auth.json,.env}` (644, world-read) | `/srv/laia/arch/secrets/` (0700, files 0600) |
| Runtime | `~/.laia/{config.yaml,atlas.yaml,.env.paths,state,…}` | `/srv/laia/arch/` |
| Lectura por `laia-agora` | 644 + mount desde `~/.laia` (hack world-read) | `raw.idmap` (host admin ↔ `agora`) + mount desde `/srv/laia/arch/secrets`, 0600 |

Principio **add-before-remove**: el origen `~/.laia` queda **intacto** hasta que `/api/health`
verifica verde con los secretos nuevos; sólo entonces se retira.

## 1. Fases (cada una deja un marker en `/srv/laia/.laia-migration-state/`)

1. **preflight** — detecta v1, deps (`lxc jq rsync tar curl install`), graba el estado de
   rollback (`rollback.env`: `raw.idmap`, device de secretos, owner de `/srv/laia/agora`).
   Si ya es v2 → sale limpio (idempotente).
2. **backup** — `lxc snapshot laia-agora/pre-v2-migration-<ts>` + tar de
   `/srv/laia/agora`, `~/.laia`, `~/LAIA-ARCH` → `/mnt/data/laia-migration-backups/<ts>/`.
3. **mkdirs** — `/srv/laia/arch` (0750) y `/srv/laia/arch/secrets` (0700), owned `laia-arch`.
4. **sync-runtime** — `rsync` `~/.laia` → `/srv/laia/arch` (excluye secretos; **sin `--delete`,
   origen intacto**).
5. **sync-secrets** — `auth.json`/`.env`/`admin-session.json` → `/srv/laia/arch/secrets` (0600).
6. **anchors** — `laia-path reload` (C1 ya fija el default `/srv/laia/arch`).
7. **swap-mount** — `raw.idmap` (host admin ↔ `agora`) + `chown` de `/srv/laia/agora` +
   **restart del container** (aplica el shift) + swap del device de secretos a
   `/srv/laia/arch/secrets` (vía `rebuild-3b`) + restart backend + verifica `auth_json_ready`.
   Si falla → **auto-rollback** de este paso.
8. **verify** — `/api/health` `ok:true` + `auth_json_ready:true`. Si no → auto-rollback.
9. **cleanup** — **sólo en verde**: retira `~/.laia` → `~/.laia.v1-migrated-<ts>` (o `rm` con
   `--purge-old`).

> ⚠️ **`raw.idmap` sólo aplica al (re)arrancar el container** — por eso la fase 7 hace un
> `lxc restart laia-agora` **antes** del swap del mount (si sólo se reinicia el servicio
> backend, el shift no está activo y el container no puede leer los secretos 0600). Hallazgo
> del ensayo en VM.

## 2. Uso

```bash
# Ensayo / inspección (no ejecuta nada):
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --dry-run --yes

# Migración real (PROD = paso HITL, ventana de reinicio de laia-agora):
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --yes

# Reintento idempotente tras un fallo (salta fases ya hechas):
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --yes --resume

# Rollback manual (sólo válido ANTES de cleanup; ~/.laia aún en su sitio):
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --rollback
```

Flags: `--resume` (salta markers), `--dry-run`, `--yes`, `--rollback`, `--purge-old` (borra
`~/.laia` en vez de archivarlo), `--no-snapshot`. Overrides por env: `LAIA_ADMIN_USER`,
`LAIA_ARCH_DIR_OVERRIDE`, `LAIA_ARCH_CREDS_DIR_OVERRIDE`, `BACKUP_ROOT`, `CONTAINER`.

## 3. Rollback

- **Durante la migración (antes de cleanup):** `--rollback` (o el auto-rollback si falla
  swap/verify) revierte `raw.idmap`, el owner de `/srv/laia/agora` y el device de secretos al
  estado v1 grabado en `rollback.env`, y reinicia. **`~/.laia` está intacto** (no se toca hasta
  cleanup) → recuperación instantánea.
- **Después de cleanup (migración completa):** el rollback de dispositivo se **rehúsa** (el
  origen v1 ya se archivó); recupera con el `lxc restore laia-agora pre-v2-migration-<ts>`, o
  `mv ~/.laia.v1-migrated-<ts> ~/.laia`, o el tar de `/mnt/data/laia-migration-backups/<ts>/`.

## 4. Ensayo en la VM `laia-dev` (verificado 2026-05-29)

Réplica **v1 cruda** construida en la VM (sin `raw.idmap`, `arch-laia` montado desde `~/.laia`
0755 + `auth.json` 644, `/srv/laia/agora` con owner del default-map; `/srv/laia/arch` ausente);
`/api/health` verde como línea base. Resultados:

- ✅ **Migración completa:** `raw.idmap 1001↔999` aplicado vía restart, secretos en
  `/srv/laia/arch/secrets` (0700/0600), `/api/health` `auth_json_ready:true`, `~/.laia`
  archivado.
- ✅ **Idempotencia:** re-ejecución detecta "host ya en v2 — nada que migrar" y sale limpio.
- ✅ **Rollback:** un fallo en swap-mount disparó el **auto-rollback** → volvió a v1 verde con
  `~/.laia` intacto. El guard post-cleanup rehúsa y apunta a backup/snapshot.

## 5. Aplicar a PROD (HITL — pendiente, NO hecho en C3)

1. Anunciar ventana (reinicio de `laia-agora`, segundos).
2. `--dry-run` primero; revisar el plan.
3. `sudo bash migrate-v1-to-v2.sh --yes` (deja el backup one-shot + snapshot).
4. Verificar `/api/health` + login + un chat de humo.
5. En verde y tras un periodo de observación: `--purge-old` o borrar `~/.laia.v1-migrated-*`
   a mano (tras confirmar el backup permanente del Bloque D).
