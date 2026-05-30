# PRD — Cutover de PRODUCCIÓN v1→v2 + deploy v0.2.0  · **el más difícil — Lead**

> ⛔ **FALLÓ EN PROD (2026-05-30) — NO EJECUTAR.** El intento causó un **outage ~50 min** de
> `laia-agora`; `migrate-v1-to-v2.sh` tiene **4 bugs + auto-rollback roto**. Post-mortem en
> `workflow/changelog.md` y `workflow/problems.md` (`migrate-v1-to-v2-prod-outage`). Requiere
> **rediseño + re-test contra una réplica de container EN MARCHA** (no install fresco) antes de
> cualquier reintento. El plan de fases de abajo queda como referencia histórica, no operativo.

- **Fecha**: 2026-05-30
- **Owner**: **Lead** (Claude Opus — orquesta y ejecuta paso a paso) · **Jorge (HITL — gatea y supervisa EN VIVO)**
- **Estado**: ⛔ **FALLÓ — EN PAUSA** (ver banner arriba)
- **Track**: PROD-cutover · **Agente**: **Lead (yo)** — NO es AFK, es supervisado en directo.
- **Depende de**: **Track A mergeado** (§2.2 fixes) · D2 verde en VM (✅ ya) · backup D1 corriendo.

## Por qué es el más difícil

Toca el **AGORA vivo con usuarios reales**; es **parcialmente irreversible** pasado el cleanup;
coordina **tres** operaciones que deben encajar (migración de layout + release de código +
verificación); y un fallo en `raw.idmap`, secretos o resolución de paths deja a los usuarios sin
servicio. Por eso lo lleva el Lead con Jorge delante, y no un agente AFK.

## Contexto

- Prod: `/opt/laia → v0.11.0` (era-Hermes), layout **v1** (`~/.laia`, `auth.json` 644). El AGORA real
  corre en el container `laia-agora` (RUNNING) + 3 agentes.
- Código **`v0.2.0`** (en `stable`) **asume v2** (`/srv/laia/arch`). `laia-release` re-renderiza la unit
  de `laia-pathd` con `LAIA_CONFIG_HOME=/srv/laia/arch` → **desplegar sobre v1 ROMPE la resolución de
  paths**. Orden obligatorio: **migrar a v2 primero, desplegar después**.
- Secuencia **validada end-to-end en la VM `laia-dev`**: D2 9/0; migración + idempotencia + rollback ✅.

## Objetivo

Prod en **v2 + v0.2.0**, **D2 verde**, login y chat reales OK, con **downtime de segundos** (solo el
restart de `laia-agora`) y **rollback disponible en cada paso**.

## No-objetivos

- Features/integraciones nuevas. Cambiar el storage driver del pool (eso es decisión de PRD-C). Tocar
  datos de usuario.

## Pre-requisitos (gates — NO abrir ventana sin esto)

1. ✅ D2 verde en la VM sobre install v2 limpio.
2. ✅ **Track A mergeado** (PR #31): `safe.directory`, `--skip-frontend`, `setup-prod-dirs` agents→users,
   install crea state/users, assert de rollback.
3. ✅ **Backup del cutover = el del propio script** (`lxc snapshot` + tar → `/mnt/data/laia-migration-backups/`,
   fase 1) — **independiente de D1**. Corrección (2026-05-30): D1 (backup permanente) **NO** es prerrequisito;
   no está activo en prod (no hay `laia-backup.timer` ni `/mnt/data/laia-backups`) y es correcto, porque se
   **instala con el deploy de v0.2.0**. → **Nuevo gate POST-deploy:** confirmar `laia-backup.timer` activo +
   1er artefacto tras la fase 4.
4. ⬜ Ventana anunciada (reinicio de `laia-agora`, segundos) y Jorge disponible para supervisar.

## Fases (ejecución supervisada; cada una con su gate)

0. **Pre-flight** — `migrate-v1-to-v2.sh --dry-run --yes`; revisar el plan juntos; confirmar deps
   (`lxc jq rsync tar curl install`).
1. **Backup one-shot** — el script hace `lxc snapshot laia-agora/pre-v2-migration-<ts>` + tar de
   `/srv/laia/agora`, `~/.laia`, `~/LAIA-ARCH` → `/mnt/data/laia-migration-backups/`. **Gate: backup presente.**
2. **Migrar v1→v2** — `migrate-v1-to-v2.sh --yes` (add-before-remove; `raw.idmap` aplicado vía
   `lxc restart laia-agora`; secretos a `/srv/laia/arch/secrets` 0600). **Auto-rollback si swap/verify
   falla; `~/.laia` intacto hasta el cleanup.**
3. **Verify migración** — `/api/health` `ok:true` + `auth_json_ready:true`. **Gate.** Si rojo →
   `--rollback`, parar y diagnosticar (NO seguir al deploy).
4. **Deploy v0.2.0** — checkout de `stable` actualizado en el host → `sudo laia-release` (con
   `--skip-frontend` o dist según Track A). **Gate: `/opt/laia → v0.2.0`, servicios activos verdes.**
5. **Completar layout** — `infra/scripts/setup-prod-dirs.sh` (crea `/srv/laia/state`, `/srv/laia/users`
   canónico). **Gate.**
6. **D2 total en prod + smoke real** — login + 1 chat de un usuario. **Gate FINAL: D2 verde.**
7. **B2** — reconvertir `~/LAIA` del host a checkout pristino de `stable` (premisa: dev ya vive en la VM).
8. **Observación (24–48 h)** → en verde y con backup confirmado: retirar `~/.laia.v1-migrated-<ts>`
   (`--purge-old` o a mano).

## Criterios de aceptación

- D2 verde en prod (6 capas) + login y chat reales OK.
- `auth.json` **0600** en `/srv/laia/arch/secrets`; `~/.laia` **archivado** (no borrado hasta observación).
- Snapshot + tar verificados ANTES de la fase 2; rollback claro en cada gate.
- `laia-rollback` apunta al `/opt/laia-v0.11.0` previo por si hay que revertir el código.

## Rollback

- **Antes del cleanup:** `migrate-v1-to-v2.sh --rollback` (instantáneo, `~/.laia` intacto) y/o
  `laia-rollback` para el código.
- **Después del cleanup:** `lxc restore laia-agora pre-v2-migration-<ts>`, o `mv ~/.laia.v1-migrated-<ts>
  ~/.laia`, o el tar de `/mnt/data/laia-migration-backups/<ts>/`.

## Riesgos

- 🔴 **Downtime de `laia-agora`** (restart por `raw.idmap`) — segundos; anunciar ventana.
- 🔴 **`raw.idmap` mal mapeado** → el container no lee los secretos → el auto-rollback lo cubre; verificar
  `auth_json_ready` en la fase 3.
- 🟡 **`laia-release` como root + dist de frontend** → cubierto por Track A. **NO abrir ventana sin A.**
- 🟡 **Confusión de versiones** `/opt/laia-vX` (era-Hermes dejó `v0.11.0`) — tras el deploy el symlink
  `laia` debe apuntar a `laia-v0.2.0`.

## Decisiones de Jorge

- ⬜ **Cuándo** la ventana (usuarios avisados).
- ⬜ Aceptar el **downtime de segundos** del restart.
- ⬜ **Timing del `--purge-old`** (tras cuántas horas de observación se retira `~/.laia`).
