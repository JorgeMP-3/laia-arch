# Estado v2 — qué se ha hecho y qué queda hasta cerrar v2 en prod

> **Fecha:** 2026-05-31 · **Autor:** Claude Opus 4.8 (rol Lead). Snapshot del camino crítico para
> declarar **v2 vivo en producción**. Complementa (no duplica):
> - Visión → `LAIA_ECOSYSTEM.md` (canónico).
> - Roadmap previo → `workflow/plans/2026-05-30-estado-roadmap-integraciones.md` (parcialmente stale; ver §5).
> - Plan del cutover (detalle de la ventana HITL) → `workflow/plans/2026-05-31-prod-cutover-v1v2-redesigned.md`.
> - Bitácora → `workflow/changelog.md` · Bugs → `workflow/problems.md` · Briefing técnico → `workflow/_inbox/handoff-cutover-redesign.md`.
>
> Marcas: ✅ hecho · 🟡 listo/pendiente de acción puntual · 🔴 bloqueado/HITL · 🧪 paralelo (no bloquea v2).

---

## 1. Qué significa "terminar v2"

**v2 vivo en prod** = el host de producción corre el **layout v2** (runtime en `/srv/laia/arch`,
secretos en `/srv/laia/arch/secrets` 0600 leídos por `laia-agora` vía `raw.idmap`, sin world-read)
**+ código v0.2.0**, con **D2 verde**, backups activos y login/chat reales OK.

**Hoy NO lo está:** la capa **ARCH del host sigue en `/opt/laia-v0.11.0` (era-Hermes), layout v1**
(`~/.laia`). El container `laia-agora` corre imagen ≈v0.2.0 pero en estado **recuperado a mano** tras
el outage del 30-may (`auth.json` como copia en `/srv/laia/agora`, sin device `agora-auth`, sin
`raw.idmap`). Cerrar v2 = ejecutar el cutover (migración + deploy) de forma supervisada.

## 2. Hecho ✅

**Base (pre-31-may):**
- ✅ Estabilización completa y **v0.2.0 cortado en `stable`** (slices era-estabilización B1–D2: VM
  `laia-dev`, anclas ARCH, idmap+secretos 0600, migración in-place C3, install-native C4, backups
  D1, suite de integridad D2). Detalle en el roadmap del 30-may.
- ✅ **CI greenfield** (PRD-B · B1): `.github/workflows/ci.yml` mergeado y verde.
- 🔴 **Cutover intentado en prod el 30-may → outage ~50 min** → recuperado a mano, **0 datos
  perdidos**, cutover EN PAUSA. Post-mortem en `changelog.md`.

**Esta tanda (30–31 may):**
- ✅ **Tracker saneado:** 2 entradas stale de `problems.md` cerradas (shell_rc, cron — ya estaban en
  git). Estado real de prod inspeccionado y documentado (briefing).
- ✅ **8 branches mergeadas archivadas** en `archive/*` (claude/infra ×6 + codex ×2).
- ✅ **Contradicción de versiones resuelta:** host ARCH = v0.11.0 era-Hermes; backend AGORA ≈v0.2.0.
- ✅ **Cutover REDISEÑADO + re-testeado** (PR #38 — Claude Code 2): el script `migrate-v1-to-v2.sh`
  **converge al modelo canónico `rebuild-3`** (file-mount del secreto v2 sobre `/opt/agora/data/auth.json`),
  arregla los **4 bugs** del outage (swap in-place sin destruir el mountpoint, verify **por contenido**
  del auth servido, auto-rollback que captura el owner real `1000999:1000988` y **falla closed** en
  `0:0`, sin bind anidado frágil) y añade `--no-cleanup` para el HITL. **Validado:** regresión 19/19 +
  ciclo completo contra réplica del **snapshot real de prod** 14/14, sin tocar prod. CI 4/4 verde.
- ✅ **Bug del installer** `ensure-disk-free-gb-nonexistent-path-reads-0` arreglado (PR #37 — Codex):
  mide el ancestro existente más cercano; **mergeado a `main`**.

## 3. Camino crítico hasta cerrar v2 (en orden)

1. 🟡 **Mergear PR #38 a `main`** — *acción de Jorge* (merge a main está gateado por `CLAUDE.md`;
   el guard exige su OK explícito). Está MERGEABLE + CI verde; conflicto de `changelog.md` ya resuelto.
   → Tras esto, `main` tiene el cutover seguro y re-testeado.
2. 🔴 **Ventana de cutover de prod (HITL — el hito)** — *Jorge fija la ventana + supervisa en vivo*.
   Secuencia y gates en `2026-05-31-prod-cutover-v1v2-redesigned.md`. Resumen:
   - (Opcional pero recomendado) **ensayo en el bench** `laia-agora-v1` de la VM (parado, snapshot
     `clean-v1`) antes de la ventana.
   - **Re-baseline contra el prod VIVO de hoy** (estado recuperado, NO el snapshot) · `--dry-run`.
   - Backup one-shot + `lxc snapshot`.
   - `migrate-v1-to-v2.sh --yes --no-cleanup` (conserva `~/.laia`, rollback instantáneo).
   - **Verify por contenido** + `/api/health` + D2 → si rojo, auto-rollback.
   - **Deploy v0.2.0** (`laia-release`, con los follow-ups de Track A ya mergeados).
   - `setup-prod-dirs.sh` → **D2 verde total** + smoke real (login + 1 chat).
   - Ventana de observación (24–48 h) → completar (`--resume --yes`) y retirar `~/.laia` viejo.
3. 🟡 **Post-cutover (cierre fino de v2):**
   - **B2 (era-estabilización):** reconvertir `~/LAIA` del host a checkout pristino de `stable`.
   - Alinear versionado `/opt/laia-vX.Y.Z` (era-Hermes dejó `v0.11.0`) + a dónde apunta `laia-rollback`.
   - **B3 / D5b:** backup off-site a USB `VM-USB` (ahora relevante con prod en v2).
   - Confirmar `laia-backup.timer` activo + 1er artefacto.

**Con esos pasos en verde → v2 está CERRADO en prod.**

## 4. Paralelo / post-v2 (no bloquea el cierre de v2) 🧪

- **Track B:** B2 monitor/dashboard (en curso, worktree `LAIA-wt-robustez`) · B3 backup off-site.
- **Track C** (escalar a 10: idle-eviction) · **Track D** (eficiencia/footprint, alimenta C) ·
  **Track T** (red de regresión; el test del cutover ya alimenta T) — los 4 PRDs siguen **draft en
  `_inbox/`, pendientes de OK de Jorge** para moverlos a `plans/`.
- **UI de prod rota** (`note-ui-remake-v2`): la capa de consola de v0.11.0 está rota → remake para v0.2.0.
- Decisión pendiente: semántica de `clone-ssh-setup` (`problems.md`).

## 5. Estado git / PRs al cierre de esta sesión

- **`main`:** tiene PR #37 (installer). **PR #38 (cutover) MERGEABLE + verde, pendiente del merge de Jorge.**
- **Branches activas:** `cutover-redesign` (PR #38, en worktree `~/LAIA-wt-cutover`), `monitor-dashboard`
  (B2), `codex/regression-t2` (T), `note-ui-remake-v2`, `tracker-hygiene` (docs del Lead, esta sesión).
- **Limpieza pendiente** (tras mergear): archivar `cutover-redesign` + `installer-disk-free` en
  `archive/*` (como las otras 8); retirar el worktree `~/LAIA-wt-cutover`.
- **Stale a sabiendas:** el roadmap del 30-may dice "no hay CI" (ya lo hay) y trata el cutover como
  pendiente de re-test (ya rediseñado). Este doc lo supersede para el tema v2.

## 6. Una línea

v2 está **a un merge (PR #38) + una ventana HITL de cutover** de estar vivo en prod; lo demás
(escalado, eficiencia, regresión, UI) es post-v2 y no bloquea el cierre.
