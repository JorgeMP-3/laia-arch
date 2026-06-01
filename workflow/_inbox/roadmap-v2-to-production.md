# Roadmap — Terminar V2 y ponerla en PRODUCCIÓN (100% funcional + integridad verificada)

- **Fecha**: 2026-06-01
- **Autor**: Claude Code (Opus 4.8, rol Lead) — borrador para aprobación de Jorge
- **Estado**: draft en `_inbox/` → al aprobar Jorge, mover a `workflow/plans/`
- **Objetivo de negocio**: cerrar V2, desplegarla en el host de prod, dejarla **100% funcional**
  y con una **red de tests de integridad** que la vigile en cada cambio.
- **Complementa, no sustituye**: `LAIA_ECOSYSTEM.md` (visión canónica),
  `workflow/plans/2026-05-30-estado-roadmap-integraciones.md` (snapshot de estabilización),
  `workflow/plans/2026-05-31-prod-cutover-v1v2-redesigned.md` (PRD del cutover),
  los drafts `prd-B/C/D/T` de `_inbox/`.

> Marcas: ✅ hecho · 🟡 listo/pendiente de ventana · 🔴 bloqueante · 🧪 propuesta · ⏳ en curso.

---

## 0. Definición de "V2 100% funcional en producción"

V2 se declara **terminada** cuando TODOS estos criterios son verdes **en el host de prod**
(no solo en la VM):

1. **Layout v2 aplicado**: secretos en `/srv/laia/arch/secrets` (`0700`/`0600`, sin `644`
   world-readable), runtime ARCH en `/srv/laia/arch`, `~/.laia` retirado.
2. **Release v0.2.0 desplegada** desde `stable` (no era-Hermes `v0.11.0`).
3. **Suite de integridad D2/T verde total** en prod (las 6 capas: host → LXD → AGORA →
   executor → datos 2 zonas → Atlas + backups).
4. **Smoke e2e verde**: login + chat con el PA-AGORA + tool-call que ejecuta en el container
   del usuario + chat con LAIA coordinador.
5. **Backups automáticos** corriendo (nocturno a `/mnt/data`) **+ copia off-site** (USB).
6. **Monitor en caliente** publicando salud a un estado consultable.
7. **CI verde** en cada PR; **cero** `problems.md` en estado `open`/`in-progress` que sea
   bloqueante de prod.
8. **Documentación**: código en inglés con docstrings; docs de proyecto en español al día.

---

## 1. El equipo de IAs y reglas de colaboración

Cuatro roles. **Solo Jorge mergea a `main`** (con visto bueno del Lead); cualquier cosa hacia
`stable`/prod es **HITL de Jorge**.

| Rol | Quién | Qué hace | NO hace | Branch |
|---|---|---|---|---|
| **A · Lead / Coder prod-risk** | Claude Code (cuenta 1 — *esta*) | Diseño + arquitectura; **código crítico y arriesgado** (migración prod, infra LXD, secretos, release); revisión final; gating de merge. | — | `wip/claude-a/<slug>` |
| **B · Coder** | Claude Code (cuenta 2) | Features y código **no-prod-risk** en paralelo (UI, partes de Tracks B/C/D, tests). | Tocar migración prod / secretos sin el Lead. | `wip/claude-b/<slug>` |
| **C · Coder** | Codex | Backend, refactors mecánicos, tests, scripts en paralelo. | Decisiones de arquitectura en solitario. | `wip/codex/<slug>` |
| **Q · QA / Reviewer** | Modelo ligero | **Auditoría continua**: bugs, code smells, errores de sintaxis, código que no cumple estándar de producción, **falta de documentación en inglés en el código**, TODO/FIXME/deuda, paths inventados. Entrega **informes**. | **NO escribe código importante / lógica.** Solo fixes mecánicos (typos, formato, lint autofix). | `wip/qa/<slug>` (solo fixes triviales) |

**Reglas (de `CLAUDE.md`/`workflow/`):**
- **1 tarea = 1 branch = 1 PR consolidado** (commits separados dentro). **Nada de stacked PRs.**
- Conventional Commits. Nunca commit directo a `main`. Nunca `--no-verify`.
- Toda integración nueva → su test en `~/LAIA/tests/`; **suite completa verde** antes de "hecho".
- Docs grandes de `workflow/*` → draft en `_inbox/` primero.
- Coordinación multi-IA en paralelo: ver `workflow/03-multi-ai-coordination.md`.

**Entregables del Reviewer (Q):**
- Informe por barrido en `workflow/_inbox/qa-reports/qa-YYYY-MM-DD-<area>.md` (en español; los
  *snippets* de código que cite van tal cual).
- Cada hallazgo: `fichero:línea`, severidad (blocker/major/minor/nit), categoría
  (bug | sintaxis | smell | estándar-prod | doc-EN-faltante | deuda), y fix sugerido.
- Findings bloqueantes → además entrada en `workflow/problems.md` (formato del repo).

---

## 2. Política de documentación (decisión de Jorge, 2026-06-01)

- **Código → INGLÉS.** Comentarios, docstrings, nombres, mensajes de log, READMEs técnicos
  *dentro* de módulos, ayuda de CLI. Estándar profesional de producción.
- **Docs de proyecto (las que usa Jorge) → ESPAÑOL.** `LAIA_ECOSYSTEM.md`, `workflow/*`,
  roadmaps, PRDs, runbooks, `changelog`/`problems`/`security`.
- **Tarea transversal**: el Reviewer (Q) marca todo módulo/función pública sin docstring en
  inglés; se cierra incrementalmente (no big-bang). Gate futuro: linter de docstrings en CI
  (ver Fase 4, T-DOC).

---

## 3. Fases (con dependencias, owner y *definition of done*)

### FASE 0 — Baseline del servidor ⏳ (hoy, casi cerrado)
*Owner: A + Jorge (HITL).*
| # | Tarea | DoD | Estado |
|---|---|---|---|
| 0.1 | Kernel `7.0.0-22` + NVIDIA: backup manual + snapshots de las 5 instancias | backup en `/mnt/data`, 5 snapshots `pre-reboot-*` | ✅ hecho esta sesión |
| 0.2 | **Reboot** del host (ventana) | host arriba, las 5 instancias autostart OK, `/api/health` ok | 🟡 pendiente ventana |
| 0.3 | **Timer de backup nocturno con `User=root`** (fix del falso-verde: `/srv/laia/agora` es `700`) | `laia-backup.service`/`.timer` instalados; corrida real respalda `agora.db` (36M) no vacío | 🔴 nuevo — ver §6 deuda |

### FASE S — Hardening de seguridad del host 🔴 (PRIORITARIO — marcado por Jorge 2026-06-01)
*Owner: A (Lead, prod-risk: toca SSH/UFW/secretos) + Jorge (HITL en los cambios de red/SSH). Plan
completo y auditoría (Claude + Codex) en `workflow/_inbox/security-hardening-plan.md`.*
Auditoría read-only hecha; **sin IoC** (internet cerrado por UFW). Riesgos = misconfiguraciones de
hardening. **P0 a cerrar (cuasi-prerequisito de la ventana de prod):**
| # | Tarea | DoD |
|---|---|---|
| S0.1 | **`~/.laia/auth.json` `0644` world-readable con tokens OAuth reales** (F1) → `0600` + `~`/`~/.laia` a `0700` + **rotar** los tokens expuestos | secreto no legible por otros; tokens rotados. Converge con el cutover v2 (secretos `0600`). |
| S0.2 | **SSH**: `PasswordAuthentication no` + `PermitRootLogin no` + `AllowUsers` (F3/F4) | solo clave; root sin login directo |
| S0.3 | **UFW**: confirmar bloqueo de puertos web desde internet/IPv6 (F6/F8) + rebindear proxy AGORA a `127.0.0.1`/`tailscale0` (F7) | nada de prod expuesto a internet (ya verificado) + higiene de bind |
| S0.4 | **Password admin de Nextcloud** (F-Nextcloud) | credencial fuerte |
| S1 | Resto del plan (Fail2Ban F10, TLS/reverse-proxy F9, drift de copias legacy F2) + protocolos de mantenimiento | según `security-hardening-plan.md` |
**DoD Fase S**: los 4 P0 cerrados y verificados; `workflow/security.md` actualizado.

### FASE 1 — Pre-prod hardening 🔴 (desbloquea la ventana)
*Owner: C (Codex) + B (Claude-2) en paralelo; revisa A; audita Q.*
Los 5 follow-ups del runbook de deploy v0.2.0 (§2.2 del roadmap de integraciones) + reconciliaciones:
| # | Tarea | Owner | DoD |
|---|---|---|---|
| 1.1 | `laia-release` corre como root → añadir `git config --global --add safe.directory` (en el propio script) | C | deploy en VM sin warning de dubious ownership |
| 1.2 | Smoke `test_flags.sh`: relajar assert de `laia-rollback --dry-run` con <2 versiones | C | test verde con 1 y con ≥2 versiones |
| 1.3 | `laia-release` exige frontend → flujo `--skip-frontend` o build `laia-ui` documentado | B | release reproducible documentada |
| 1.4 | Install factory crea `/srv/laia/{state,users}` (no paso aparte) | C | install limpio deja layout completo |
| 1.5 | Reconciliar `setup-prod-dirs.sh`: crea `agents` → debe ser `users` (`arch-layout.md` §2.2) | C | nombres canónicos; D2 no se queja |
| 1.6 | Reconciliar consumidores de `~/.laia/state` (`preflight.sh`, `smoke-test.sh`, `audit-hardcoded-paths.py`) al layout v2 | B | scripts apuntan a `/srv/laia/...` |
| 1.7 | Deps VM: `pytest-asyncio` + `watchdog` para `infra/pathd/tests` | C | suite async verde en VM |
**DoD Fase 1**: install+deploy v0.2.0 reproducible en la VM, suite installer + pathd verde, sin follow-ups abiertos.

### FASE 2 — Ventana de PRODUCCIÓN 🔴 (el hito) — **HITL Jorge + A**
*Secuencia validada; runbook: `c3-migration-runbook.md` + PRD cutover. NO delegable a B/C/Q.*
| # | Paso | DoD |
|---|---|---|
| 2.1 | Pre-flight: backup one-shot (`laia-backup all`) + `lxc snapshot` de `laia-agora` | snapshot fresco + backup verificado |
| 2.2 | `migrate-v1-to-v2.sh --dry-run` → `--no-cleanup --yes` | rollback instantáneo disponible |
| 2.3 | **Verify**: `/api/health` + auth servido = secreto v2 (sha, no vacío) | verde real (no falso-verde) |
| 2.4 | `laia-release` (deploy v0.2.0) + `setup-prod-dirs.sh` | `/opt/laia` apunta a v0.2.0 |
| 2.5 | **D2/T verde total en prod** + smoke (login + chat PA + tool-call + chat LAIA) | 6 capas verdes + e2e verde |
| 2.6 | `--resume --yes` (retira `~/.laia`) | layout v2 limpio; `~/.laia` fuera |
| 2.7 | **B2 del plan**: reconvertir `~/LAIA` del host a checkout pristino de `stable` | dev movido a la VM |
**Rollback**: en cada paso (owner exacto capturado en vivo; device in-place; `raw.idmap` revertido).
**DoD Fase 2 = Definición §0 puntos 1–4 verdes en prod.**

### FASE 3 — Robustez en prod (Track B) 🟡
*Owner: B (impl) + A (diseño); audita Q. Aprobar `prd-B`.*
| # | Tarea | DoD |
|---|---|---|
| 3.1 | **B2 · Monitor de salud + dashboard**: `systemd timer` que corre aserciones D2 en caliente y escribe a `/srv/laia/state/health/` (JSON + histórico corto) | estado consultable; último + histórico |
| 3.2 | **B3 · Backup off-site**: extender `laia-backup` a USB removible `VM-USB` (`/dev/sdb1`) | copia fuera de la máquina + verificación restore |
**DoD Fase 3 = Definición §0 puntos 5–6 verdes.**

### FASE 4 — Red de integridad completa (Track T) 🧪 — *el "todos los tests"*
*Owner: **B (Claude Code, cuenta 2)** — adopta como base el WIP de Codex `wip/codex/regression-t2`
(T2 contracts de las 6 capas + T5 cutover + T6 backup, ya hechos; rebase sobre main) y lo extiende.
A revisa cobertura; Q audita gaps. Aprobar `prd-T`. Prioridad alta: garantía de "no romper al añadir".*
*Reasignación 2026-06-01: Track T pasó de Codex a B (Claude-2) porque Codex va all-in a backend;
Codex deja de tocar `regression-t2`.*
Pirámide (muchos unit + integración medianos + pocos e2e), determinista, teardown limpio, **explícito qué corre dónde** (CI sin-LXD vs VM/host con-LXD):
| # | Slice | DoD |
|---|---|---|
| 4.1 | **T1 · Runner + taxonomía** `tests/integration/run_integrity.sh`: descubre por capa/nivel, selecciona subset por entorno, **reporta JSON + exit code** (consumible por el monitor B2). Migra D2 sin perder cobertura. | runner unificado verde en CI y VM |
| 4.2 | **T2 · Invariantes por capa** (las 6): usuario provisionado ⇒ container+executor+workspace+fila DB consistentes; refs Atlas resuelven; `secrets` 0600; `agora.db` schema/integrity | cada capa asume su contrato |
| 4.3 | **T3 · Camino dorado e2e**: provisionar → crear agente → chat → tool-call en SU container → desprovisionar sin residuo (VM golden) | e2e verde reproducible |
| 4.4 | **T4 · Consistencia cruzada**: DB ↔ FS ↔ containers sin huérfanos en ambos sentidos | sin huérfanos |
| 4.5 | **T5 · Regresión de bugs**: por cada bug `resolved` de `problems.md`, un test que lo fija (empezando por los 4 del outage del cutover) | cada bug resuelto tiene su test |
| 4.6 | **T6 · Smoke de carga** (absorbe C5): N usuarios concurrentes sin agotar RAM/disco | smoke de carga documentado |
| 4.7 | **T-DOC · Gate de documentación**: linter en CI que falla si una función/módulo público no tiene docstring en inglés (ruff/pydocstyle para Python; equivalente para bash) | CI rojo ante docstring EN faltante |
**DoD Fase 4 = Definición §0 punto 7; la suite es el gate de todo lo demás.**

### FASE 5 — Escalabilidad para 10 usuarios (Track C) 🧪
*Owner: A (prod-risk: idle-eviction toca el cerebro) + C (provisioning); Q audita. Aprobar `prd-C`.*
| # | Slice | DoD |
|---|---|---|
| 5.1 | **Idle-eviction**: (a) evictar sesiones ociosas del pool AIAgent en `laia-agora`; (b) `freeze`/`stop` de containers per-usuario ociosos + re-despertar on-demand | overcommit seguro; RAM liberada bajo inactividad |
| 5.2 | **Cuotas de disco**: el pool LXD es driver `dir` (sin `root.size`) → mitigar (mover a pool con cuota, o quota FS, o monitor+límite) para que un user no llene el NVMe | un user no puede tumbar a otros |
| 5.3 | **Provisionar/desprovisionar idempotente y limpio** | sin residuos; cubierto por T4 |
**DoD Fase 5 = 10 usuarios concurrentes simulados sin degradación (smoke T6 verde).**

### FASE 6 — Eficiencia y deuda técnica (Track D) 🧪 — *Reviewer-heavy*
*Owner: Q lidera el audit (read-only) + C aplica quick-wins; A aprueba refactors profundos. Aprobar `prd-D`.*
| # | Slice | DoD |
|---|---|---|
| 6.1 | **D1 · Audit** (Q + lens `improve-codebase-architecture`): recursos (cold-start, footprint RAM/disco, tamaño imagen LXC), datos (queries lentas / índices en `agora.db`), código (duplicación `bin/atlas.py`, muerto era-Hermes, módulos acoplados). Informe priorizado por impacto×esfuerzo a `_inbox/`. | informe accionable |
| 6.2 | **D2 · Quick-wins** (C): dedup, borrar muerto, índices DB, imagen LXC lean — **cada uno con benchmark antes/después** y tests verdes | mejoras medidas |
| 6.3 | **D3 · Refactors profundos** (A/B): solo los que el audit justifique; cada uno con su test | sin regresión |
**DoD Fase 6 = footprint/cold-start medidos a la baja; sin código muerto; duplicados eliminados.**

### FASE 7 — UI nueva de LAIA-AGORA (visión canónica §9) 🧪
*Owner: B (front-end) + C (endpoints); A diseño de contratos; Q revisa accesibilidad/calidad. PRD propio antes de empezar.*
Reconstruir la web desde cero (v1 se archiva): chat con PA-AGORA + chat con LAIA, config del
agente (nombre/personalidad/LLM), Marketplace (explorar/instalar), Workspaces, **panel de admin
de la flota**. *(Hay trabajo iniciado en `wip/claude/note-ui-remake-v2`.)*
**DoD Fase 7 = los 5 bloques usables + e2e de UI en la suite.**

> **Futuro (fuera de V2)**: LAIA OS — ISO Ubuntu con LAIA preinstalado, instalador gráfico,
> Whisper local en GPU. No es parte de "terminar V2".

---

## 4. Trabajo continuo (transversal a todas las fases)

| Flujo | Owner | Detalle |
|---|---|---|
| **Auditoría continua** | Q | Barridos periódicos (lint, smells, sintaxis, estándar-prod, docs-EN, paths inventados) → informes a `_inbox/qa-reports/`. Corre tras cada PR grande. |
| **Migración docs código → inglés** | C + Q | Incremental, archivo a archivo; Q detecta, C/B aplican. Gate final = T-DOC (4.7). |
| **Backlog de bugs** | A/B | `laia-core-cron`: `git add -f cron/` + que `laia release` lo incluya nativo (in-progress). `clone-ssh-setup-mode`: **decisión de Jorge** sobre semántica → luego fix + test. |
| **Higiene de repo** | C | Borrar ramas `wip/*` mergeadas + worktrees viejos; reconciliar `slices.md` (stale); `/opt/laia` versionado `current→versions/`; limpiar `~/laia-partial-install.*`. |
| **CI** | — | Ya existe (`.github/workflows/ci.yml`, PR #30). Cada PR a `main` corre pytest backend + tests installer host-free; D2/T con-LXD se skipea en runner (documentado, sin silent gap). |

---

## 5. Orden recomendado / camino crítico

```
FASE 0 (server) ─┐
                 ├─> FASE 1 (pre-prod hardening) ──> FASE 2 (VENTANA PROD) ──> FASE 3 (robustez prod)
FASE 4 (Track T, ya) ─┘ (en paralelo, no bloquea; es el gate de calidad de todo)
                                                          │
                        FASE 5 (escala) ─ FASE 6 (eficiencia) ─ FASE 7 (UI)  (post-prod, paralelizables)
```

- **Crítico y serializado**: 0 → 1 → 2 → 3. Es lo que pone V2 en prod.
- **Paralelo desde ya**: Fase 4 (Track T) la arranca Codex sin tocar prod — cuanto antes esté
  la red de tests, más seguro es todo lo demás. Q audita en continuo.
- **Post-prod** (tras Fase 2 verde): Fases 5/6/7 en paralelo, cada una con su PRD aprobado.

---

## 6. Item nuevo para `problems.md` (descubierto 2026-06-01)

**`backup-timer-runs-as-laia-arch-cannot-read-agora` (open)** — la plantilla
`infra/installer/systemd/laia-backup.service.tmpl` usa `User=${LAIA_USER}` (= `laia-arch`), pero
`/srv/laia/agora` es `drwx------` del uid del container (`1000999`). `laia-backup` como `laia-arch`
**no puede leer `agora.db`** → backup nocturno daría OK sin la DB (falso-verde, mismo patrón que
el outage del cutover). **Fix**: el servicio de prod corre como `root` (o `User=root` en la
plantilla). Validar con corrida real que `agora_*.db` pesa ~36M, no vacío. Cubrir con test (T5).

---

## 7. Criterios de aceptación de release (checklist final de V2)

- [ ] Layout v2 en prod (secretos 0600, `~/.laia` retirado).
- [ ] `v0.2.0` desplegada desde `stable`.
- [ ] Suite de integridad T1–T6 **verde en prod**.
- [ ] Smoke e2e (login + chat PA + tool-call + chat LAIA) verde.
- [ ] Backups nocturnos (como root) + off-site funcionando, con restore verificado.
- [ ] Monitor de salud publicando estado.
- [ ] CI verde; `problems.md` sin bloqueantes de prod.
- [ ] Código con docstrings en inglés (gate T-DOC); docs de proyecto en español al día.
- [ ] `changelog.md` actualizado; ramas `wip/*` mergeadas limpiadas.
