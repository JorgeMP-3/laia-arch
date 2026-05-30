# Changelog del trabajo cooperativo

Bitácora de cambios materiales en el repo. Se actualiza al CIERRE de cada sesión.
**No** es release notes del producto — es la memoria operativa del trabajo cooperativo.

Formato:

```
## 2026-MM-DD — <una línea con lo importante> (agente)

- Qué se hizo (bullets).
- Qué quedó abierto.
- Qué se descubrió.
```

---

## 2026-05-30 — B1 · CI greenfield: la suite corre en cada PR a main (claude opus 4.8 · rol Coder-Opus)

Track B (Robustez/Ops), slice B1. Antes no había `.github/workflows` y la suite solo se
corría a mano. Ahora cada PR a `main` la ejecuta GitHub Actions.

- **`.github/workflows/ci.yml`** (greenfield). 3 jobs, `permissions: contents: read`,
  concurrencia con `cancel-in-progress`:
  - `backend` — `pytest tests/` en `services/agora-backend`, matriz Python **3.11 + 3.14**
    (3.11 = floor real del installer `require_python_min`; 3.14 = versión del dev).
  - `installer` — `tests/installer/run_all.sh` (host-free: stubs de lxc/lxd/snap/curl).
  - `skip-matrix` — imprime como anotaciones del PR qué queda fuera y por qué (no silent cap).
- **`.github/workflows/README.md`** — matriz "qué corre / qué se skipea" + cómo reproducir
  en local + candidatos de ampliación futura (tests/wizard, tests/*.py top-level).
- **SKIP documentado:** D2 (`tests/integration/test_ecosystem_integrity.sh`) requiere LXD +
  container vivo → no ejecutable en runner; se cubrirá en caliente con el monitor B2.
- **Test guard** `tests/test_ci_workflow.sh` — anti-drift: verifica que el CI sigue alineado
  (paths existen, floor de Python del CI == floor real del installer, SKIP de D2 documentado).
  17/17 ✓.
- **El primer run de CI (PR #30) destapó 2 falsos positivos locales** (el valor del CICD):
  1. Backend: `app/storage.py` hace `sys.path.insert(0, laia_root)` para importar `workspace_store`;
     `laia_root` defaultea a `$HOME/LAIA` → en el runner no existe → `ModuleNotFoundError`. En local
     "pasaba" porque `$HOME/LAIA` existe. **Fix:** `LAIA_ROOT=${{ github.workspace }}` en el job.
  2. Installer: 2 tests NO son host-free pese a lo que dice `tests/installer/README.md`:
     `test_install_native_layout.sh` (su `laia auth` necesita deps de laia-core —dotenv/pyyaml—
     que en local toma de `/opt/laia/.laia-core/venv`) y `test_clone_hardening.sh` (bloque sudo-clone
     + preflight de disco que lee 0 GB sobre ruta inexistente). **Fix:** `INSTALLER_SKIP` en
     `run_all.sh` (nuevo, retrocompatible, imprime los skips → no silent cap), excluidos en CI con
     razón; cubiertos por VM E2E.
- **2º run de CI destapó un 3er falso positivo (rutas hardcodeadas):** 6 tests del backend
  cargaban su plugin desde la ruta absoluta del host de dev (`.laia-core/` está en .gitignore →
  los plugins no están en el checkout). **Fix:** helper `tests/_laia_core.py` que resuelve vía
  `LAIA_ROOT`/raíz del repo y hace `pytest.skip` limpio si el plugin no está. Los 6 tests corren
  en host/VM con laia-core (63 passed) y skipean en CI (38 skip). Suite backend en réplica-CI:
  317 passed / 46 skipped / exit 0.
- **Problemas registrados** (`workflow/problems.md`): `ensure-disk-free-gb-nonexistent-path-reads-0`
  (open), `installer-tests-readme-overclaims-host-free` (open) y
  `backend-tests-hardcodean-ruta-de-plugins-del-host-de-dev` (resolved en este PR).
- **Verificado:** backend 355 passed / 8 skipped en py3.11 y py3.14 con HOME vacío + LAIA_ROOT=checkout
  (réplica fiel del runner); `INSTALLER_SKIP` salta los 2 y deja 31 ok / exit 0; YAML válido; guard
  `test_ci_workflow.sh` 23/23. (En *worktree* fallan además 4 release tests por `.git`-fichero — no
  aplica en CI, que usa `actions/checkout`.)
- **CI verde sobre el PR #30** (merge commit): los 4 checks SUCCESS (backend py3.11/py3.14,
  installer, skip-matrix) → criterio de aceptación B1 cumplido. Pendiente sólo revisión del Lead.
  Siguientes slices: B2 (monitor→dashboard), B3 (backup off-site, prod-risk).

## 2026-05-30 — Track A pre-prod hardening para deploy v2 (Coder-Codex)

- Resueltos los 5 follow-ups bloqueantes de la ventana pre-prod:
  `laia-release` registra idempotentemente el repo como `git safe.directory` cuando corre como root;
  `test_flags.sh` ya no falla `laia-rollback --dry-run` con menos de 2 versiones instaladas;
  `laia-release` exige artefactos `laia-ui` salvo `--skip-frontend` explícito;
  `laia-install` crea en factory `/srv/laia/state` y `/srv/laia/users`;
  `setup-prod-dirs.sh` deja de crear `/srv/laia/agents` y usa el canónico `/srv/laia/users`.
- Tests añadidos/ajustados en `tests/installer/`: cobertura de `safe.directory`, rollback de primer deploy,
  gate de frontend, layout factory state/users y `setup-prod-dirs` con override sandbox.
- Docs operativas reconciliadas para no propagar `/srv/laia/agents`.
- Validación: `tests/installer/run_all.sh` verde (**33/33 scripts**). Ensayo en VM `laia-dev`
  de `setup-prod-dirs.sh` con `LAIA_SRV_DIR_OVERRIDE` bajo `/tmp`: crea `users` 0750, no crea
  `agents`, y mantiene `arch/secrets` 0700. Prod no tocado.
- Pendiente de cierre: PR único contra `main`.

## 2026-05-30 — Validación del deploy v0.2.0 en la VM laia-dev + D2 fresh-install-aware (claude opus 4.8 · rol Lead)

Tras cortar el release **v0.2.0** (main→stable + tag, ver abajo), se validó el deploy en la VM
`laia-dev` **antes de tocar prod** (decisión de Jorge). NO toca prod.

- **Hallazgo bloqueante para prod (clave):** el host de prod sigue en **layout v1** (`~/.laia`,
  `/srv/laia/arch` ausente) y el código v0.2.0 **asume v2**. `laia-release` re-renderiza la unit
  de `laia-pathd` apuntando `LAIA_CONFIG_HOME=/srv/laia/arch` → desplegar v0.2.0 sobre v1 **rompe
  la resolución de paths**. **El deploy a prod está bloqueado por la migración C3** (orden correcto:
  migrar a v2 primero, desplegar después). `laia-release` **no** toca el AGORA del container (vive
  en LXD); sólo `/opt` del host + reinicia servicios activos.
- **Validación en la VM (v2):** `laia-install --from-local v0.2.0` factory limpio (tras limpiar el
  estado de ensayo) → **D2 VERDE: 9 PASS / 0 FAIL / 3 PEND / 1 SKIP**. atlas doctor **sin refs
  rotas**, secrets 0700 / auth.json 0600 (644 cerrado), `/api/health ok`, `agora.db integrity ok`.
  Confirmado que las "13 refs DEAD" vistas antes eran **suciedad del ensayo**, NO un bug de v0.2.0.
- **D2 refinado (fix de correctitud):** Capa 1 — `/srv/laia/users` y `/srv/laia/state` ausentes en
  un install fresco (0 usuarios) = **PEND**, no FAIL (se pueblan al provisionar el primer
  usuario/agente). Alinea Capa 1 con Capa 5. `/srv/laia/agora` ausente sí es FAIL (núcleo).
- **Hallazgos/follow-ups para el runbook de deploy v2** (no resueltos aquí):
  1. `laia-release` corre como root → git "dubious ownership" si el repo es de otro user;
     necesita `git config --global --add safe.directory <repo>` (prod probablemente ya lo tiene).
  2. El smoke `test_flags.sh` falla en `laia-rollback --dry-run` si hay **<2 versiones** en `/opt`
     (benigno en el primer deploy; prod tiene ≥2). Posible mejora: relajar ese assert.
  3. `laia-release` exige **artefactos de frontend** (`laia-ui` dist) o `--skip-frontend`, si no
     `laia-ui-server` no arranca → en prod hacer `pnpm build` antes o pasar `--skip-frontend`.
  4. `laia-install` **no crea** los dirs operacionales `/srv/laia/{state,users,...}` — los crea
     `setup-prod-dirs.sh` (paso separado). Un factory install "completo" = install + setup-prod-dirs.
  5. `setup-prod-dirs.sh` crea `/srv/laia/agents` (nombre viejo) en vez de `/srv/laia/users`
     (canónico, `arch-layout.md` §2.2). Inconsistencia a reconciliar.
- **Estado VM:** queda con un install limpio v0.2.0 (sandbox); los cambios de ensayo previos están
  en `git stash`. **Prod sin tocar.**

## 2026-05-29 — D2: suite de integridad end-to-end del ecosistema (gate final) (claude opus 4.8 · rol Lead)

Slice **D2** (módulo M7) — AFK. Branch `wip/claude/d2-integrity`. **READ-ONLY**, no muta nada.
Cierra el último slice AFK del plan de estabilización (quedaba solo B2, que es HITL/prod).

- **`tests/integration/test_ecosystem_integrity.sh`** — verifica las **6 capas** del ecosistema:
  (1) host & estructura `/srv/laia`, (2) containers LXD (`laia-agora` RUNNING), (3) AGORA
  (`/api/health ok:true` + `agora.db` integrity_check), (4) executors por-usuario (`agent-<slug>`
  RUNNING), (5) datos modelo 2 zonas (secrets ARCH 0700/0600 + zona usuarios), (6) Atlas
  (`atlas doctor` sin refs rotas) + backups (artefactos presentes).
- **Diseño honesto v1/v2:** cada check es `PASS`/`FAIL`/`PEND`/`SKIP`. El gate falla (exit 1)
  **sólo** si hay `FAIL`. `PEND` = estado objetivo v2 aún no aplicado a este host (p.ej. prod
  pre-migración C3) — informativo, no error. Verde total esperado en la VM `laia-dev` (ya v2)
  y en prod **tras la migración C3**. Override-aware (CONTAINER, paths, AGORA_DB, BACKUP_DIR).
- **`agora.db` integrity:** host-side cuando es legible (fixtures/VM/override); en prod los datos
  van idmap-shifted (C2) y no son legibles por el ARCH user → check **dentro del container**
  vía `lxc exec` **opt-in** (`D2_DB_VIA_EXEC=1`, = shell a prod, no automático). `/api/health
  ok:true` ya confirma de por sí que el backend accede a su db.
- **Verificado en el host vivo (v1 prod), read-only:** `PASS:10 FAIL:0 PEND:3 SKIP:1` → exit 0.
  Capas vivas verdes (LXD, AGORA health, 3 executors, atlas doctor, zona usuarios). Los 3 `PEND`
  son legítimos y esperan la migración C3 a prod: `/srv/laia/state`, secrets en
  `/srv/laia/arch/secrets`, y el dir de backups (timer aún desactivado).
- **Hallazgo (informativo):** en este host v1, `/srv/laia/state` no existe aunque el orquestador
  corre (3 agentes RUNNING) → su state vive en otra ruta; `setup-prod-dirs`/migración lo
  normaliza. No es regresión (el sistema funciona); D2 lo marca `PEND` en v1, `FAIL` sólo en v2.
- **Abierto:** **B2** (reconvertir `~/LAIA` del host a checkout de `stable`) sigue **HITL/prod**;
  correr D2 en **verde total** requiere aplicar antes la migración C3 a prod (HITL, ventana de
  reinicio de `laia-agora`).

## 2026-05-29 — D1: sistema de backups permanente (layout v2) + timer nocturno (claude opus 4.8 · rol Lead)

Slice **D1** (módulo M1 · D5) — AFK. Branch `wip/claude/d1-backups`. NO toca prod (tests con
overrides a tmpdir). Sobre el layout v2 ya definido (C1–C4).

- **`infra/bin/laia-backup` reescrito al alcance v2:**
  - Eliminado el `backup_db()` muerto (`pg_dump arete` — Postgres ya no existe).
  - `all` = **`agora.db` + `/srv/laia/users` + `/srv/laia/arch`** (los 3 del slice). Deliberadamente
    **NO** incluye `backup_agents` (que hace `lxc snapshot`) en `all`: corriendo en este host de
    prod habría snapshoteado el `laia-agora` vivo. `agents`/`workspaces` quedan como subcomandos
    **opt-in** explícitos.
  - Destino por defecto → **`/mnt/data/laia-backups`** (otro disco físico). Override `LAIA_BACKUP_DIR`.
  - `users`/`arch` se respaldan como `tar.gz` con el origen intacto; override-aware
    (`LAIA_AGORA_DIR_OVERRIDE`/`LAIA_USERS_DIR_OVERRIDE`/`LAIA_ARCH_DIR_OVERRIDE`/`AGORA_DB`).
  - Retención por defecto **14 días** (`clean`).
- **Timer nocturno:** `laia-backup.service.tmpl` (oneshot: `all` + `clean 14`, Nice/idle) +
  `laia-backup.timer.tmpl` (03:30 + jitter, `Persistent=true`). `systemd.sh` ahora instala
  `*.tmpl` (no solo `*.service.tmpl`) → recoge también el `.timer`. Se instalan **desactivados**
  (como el resto); activar con `systemctl enable --now laia-backup.timer`.
- **Tests (verde):** `test_laia_backup.sh` activado (guard `LAIA_D1_READY` retirado, **11/11**);
  `test_systemd_render.sh` **40/40** (renderiza el nuevo service). **Suite installer completa
  33/33 verde.**
- **Abierto:** D2 (suite de integridad end-to-end) pendiente; off-site del backup (USB `VM-USB`)
  es paso posterior (D5b); aplicar migración C3 a prod sigue HITL.

## 2026-05-29 — C4: instalador install-native (layout v2) + reconciliación state-root (claude opus 4.8 · rol Lead)

Slice **C4** (módulos M2/M3/M4 · T3) — AFK. Branch `wip/claude/c4-install-native`. NO toca prod
(todo en override/sandbox en los tests). Incluye además la decisión del **state-root** que C1
dejó abierta.

- **State-root (decisión de Jorge, 2026-05-29):** `agents.json` (orquestador AGORA) se queda en
  `/srv/laia/state` (top-level, como dice `arch-layout.md` §2.2), **no** bajo `/srv/laia/arch`
  (ARCH-only). Revertido el default de `infra/orchestrator/config.py` que C1 dejó en
  `/srv/laia/arch/state`. Queda alineado con `agora-backend.service`, atlas `srv_state` y
  `setup-prod-dirs.sh` (que ya estaban en `/srv/laia/state`). El state del **resolver pathd**
  (`state.db`/`path-cache.json`) sigue correctamente en `/srv/laia/arch`.
- **C4 — toda instalación nueva nace en layout v2, sin `~/.laia`:**
  - `install.sh`: nuevos globals `INST_ARCH_DIR` (0750) / `INST_ARCH_CREDS_DIR` (0700) +
    `inst_ensure_arch_dirs`. En override/test sandboxea bajo `DATA_DIR` → un test nunca toca el
    `/srv/laia/arch` real (importante: este host es prod).
  - `factory.sh`: `auth.json` y `.env` se siembran en el **secrets dir** (0600), ya no en
    `LAIA_HOME`; `cli-config.yaml` se queda en `LAIA_HOME` (no es secreto).
  - `.laia-core/laia_cli/auth.py`: `_auth_file_path()` resuelve `LAIA_ARCH_CREDS_DIR(_OVERRIDE)`
    **antes** del default `LAIA_HOME` — **aditivo**, cero impacto en el host v1 vivo (que sigue
    leyendo `~/.laia/auth.json` hasta la migración C3).
  - `bin/laia`: nuevo subcomando **`laia auth`** → despacha al CLI de laia-core bajo su venv,
    persistiendo en el secrets dir.
  - `shell_rc.sh`: hornea `LAIA_ARCH_CREDS_DIR` en el bloque rc del operador.
  - `clone.sh`: default de arch creds → `/srv/laia/arch/secrets` (era `~/.laia`).
  - `setup-prod-dirs.sh`: crea `/srv/laia/arch` + `/srv/laia/arch/secrets` (0700).
  - `init-defaults.sh`: **reglas UFW** (`allow in` + `route allow in`) para el bridge LXD nuevo
    cuando UFW está activo (cierra el hallazgo B1: UFW dropea bridges nuevos).
- **Tests (verde):** `test_install_native_layout.sh` activado (guard `LAIA_C4_READY` retirado,
  19/19); `test_install_factory.sh` actualizado a v2; `test_path_rewrite_cross_user.sh` arreglado
  (colisión de nombre `ARCH_DIR` → `INST_ARCH_DIR`). **Suite installer completa 33/33 verde**
  (D1 skip), **82 pytest** del ecosistema verde, `discover_paths()` → `/srv/laia/state`.
- **Abierto:** D1 (backups) y D2 (integridad) pendientes; aplicar la migración C3 a prod sigue
  siendo HITL.

## 2026-05-29 — C3: script de migración in-place v1 → v2 (ensayado en VM; PROD = HITL pendiente) (claude opus 4.8 · Coder-Opus)

Slice **C3** · módulo **M6** · decisión **T2**. AFK (build + ensayo en VM); aplicar a prod es
HITL. Branch `wip/claude/c3-migration-inplace`. NO toca prod.

- **`infra/lxd/scripts/migrate-v1-to-v2.sh`** — migración **in-place idempotente** de un host
  ARCH v1 (secretos+runtime en `~/.laia`) a v2 (`/srv/laia/arch` + `/srv/laia/arch/secrets`):
  preflight → **backup one-shot** (`lxc snapshot` + tar de `/srv/laia/agora`+`~/.laia`+
  `~/LAIA-ARCH` → `/mnt/data/laia-migration-backups`) → `mkdirs` (0750 / secrets 0700) →
  `rsync` runtime+secretos (**origen intacto**) → repuntar anclas (pathd) → **add-before-remove**
  del mount (`raw.idmap` + restart container + swap a `/srv/laia/arch/secrets` vía `rebuild-3b`
  + verify `/api/health`) → en verde: retira `~/.laia`. **Markers** en
  `/srv/laia/.laia-migration-state/` (resume) + **rollback** (revierte idmap/owner/device,
  `~/.laia` intacto hasta verde).
- **Hallazgo del ensayo:** `raw.idmap` **sólo aplica al (re)arrancar el container**; `rebuild-3b`
  sólo reinicia el servicio backend → la migración hace un `lxc restart laia-agora` **antes**
  del swap del mount, o el container no lee los secretos 0600. (Bug encontrado y corregido en
  el ensayo: la primera pasada falló ahí y el **auto-rollback** volvió a v1 verde limpiamente.)
- **Runbook:** `workflow/plans/estabilizacion/c3-migration-runbook.md` (fases, flags, rollback,
  pasos HITL para prod).
- **Ensayo en VM `laia-dev` (verificado):** réplica **v1 cruda** (sin idmap, mount desde
  `~/.laia` 0755/644, `/srv/laia/agora` con owner default-map; `/srv/laia/arch` ausente) →
  línea base verde. **(1)** migración completa: `raw.idmap 1001↔999`, secretos en
  `/srv/laia/arch/secrets` 0700/0600, `/api/health auth_json_ready:true`, `~/.laia` archivado.
  **(2)** idempotencia: re-run detecta "host ya en v2 — nada que migrar". **(3)** rollback:
  auto-rollback ante el fallo de swap revirtió a v1 verde con `~/.laia` intacto; el guard
  post-cleanup rehúsa y apunta a backup/snapshot.
- **Abierto:** aplicación a **PROD = paso HITL** (Jorge), con ventana de reinicio de
  `laia-agora` + backup; **no** hecho en C3. La VM queda en estado v2 migrado (con artefactos
  del ensayo: snapshots `pre-v2-migration-*`, backups en `/mnt/data`, `~/.laia.v1-migrated-*`).
  PR contra `main` pendiente; **no** mergear (prod-risk → revisión Lead + Jorge HITL).

## 2026-05-29 — C2: secretos en `/srv/laia/arch/secrets` vía `raw.idmap` — cierra el 644 (claude opus 4.8 · rol Lead, implementado)

Slice **C2** (módulo M3 · T1) — prod-risk. Lo implementó el Lead (Jorge lo asignó). Ensayado
en la VM `laia-dev`. **Pendiente revisión HITL de Jorge antes de aplicar a prod (C3).**

- `rebuild-3-provision-agora.sh` / `rebuild-3b-fix-authjson.sh`: la fuente del bind de
  secretos pasa de `~/.laia` → `/srv/laia/arch/secrets`; se fija `raw.idmap` (host admin
  uid/gid ↔ container `agora` 999/988) y el `auth.json` se queda **0600** (owned admin),
  legible por el container SIN `chmod 644`/`755`. Eliminados los hacks world-readable.
- **Hallazgo de diseño:** mapear container-`agora` ↔ host-admin carva el uid de agora del
  rango base, así que `/srv/laia/agora` (data) se re-chownea al admin host-side para que el
  container lo siga viendo como `agora` (ambos mounts los consume el mismo uid). Resuelto y
  verificado: `/opt/agora/data` se ve `agora:agora` dentro tras el cambio.
- **Ensayo VM (verde):** `auth.json` host `600 laia-arch`; el user `agora` lee el 0600 ✓;
  `/api/health` → `auth_json_ready:true, status:linked`.
- **Verificado:** el MECANISMO (idmap + lectura 0600) de punta a punta en la VM. **No** se
  corrió `rebuild-3` end-to-end (re-provisión completa, pesada) — el ensayo ejecutó a mano
  exactamente los pasos que el script automatiza. Recomendado correr el script una vez en la
  VM como parte del gate de merge/HITL.

## 2026-05-29 — C1: repuntar anclas de path del ARCH a `/srv/laia/arch` (pendiente revisión Lead) (claude opus 4.8 · Coder-Opus)

Slice **C1** (módulo M2) del plan de estabilización. AFK, ensayado en la VM `laia-dev`.
Branch `wip/claude/c1-anclas-arch`. NO toca prod.

- **Ancla del config home del resolver → `/srv/laia/arch`** (era `~/.laia`). El path-resolver
  (`laia_paths.py`), Atlas (`atlas.py`, `bin/atlas`) y el daemon (`infra/pathd/cli.py`) ahora
  derivan config.yaml/.env.paths/pathd.sock/state/ del ancla **`LAIA_CONFIG_HOME`** (default
  `/srv/laia/arch`, constante `ARCH_RUNTIME_HOME_DEFAULT`). **Corregida una deriva**: `cli.py`
  usaba `LAIA_HOME` (la mesa viva `~/LAIA-ARCH`) para el config home → el daemon y el resolver
  apuntaban a sitios distintos; ahora ambos usan `LAIA_CONFIG_HOME`, **separado** de
  `LAIA_HOME`.
- **Clone rewrite** (`rewrite_config_paths.py`): los anclas **operacionales** (`state_db`,
  `response_store`) → `/srv/laia/arch`; los **interactivos** (`laia_home`, `workspaces`,
  `memories`, `skills`, `plugins`) siguen en `${LAIA_HOME}`. Revierte la regla **T.14.1**
  (todo→LAIA_HOME) que el lock v2 (2026-05-29) superó. **Pone verde** el assert
  `state_db defaults to /srv/laia/arch` de `test_path_rewrite_cross_user.sh`.
- **systemd** (`infra/installer/systemd/*.tmpl`): `EnvironmentFile` de las units →
  `/srv/laia/arch/.env.paths`; `laia-pathd` recibe `Environment=LAIA_CONFIG_HOME=/srv/laia/arch`.
- **orchestrator** (`infra/orchestrator/config.py`): default `LAIA_STATE_ROOT` →
  `/srv/laia/arch/state`.
- **Permisos** (diseño): `/srv/laia/arch` = `laia-arch:laia-arch` `0750`, `state/` `0700` →
  el daemon (corre como `laia-arch`) escribe sin sudo. Documentado en `PATH_RESOLVER.md`.
- **Ensayo en VM `laia-dev` (verificado):** creado `/srv/laia/arch` sintético (owner
  laia-arch); `atlas get laia_home` → `/srv/laia/arch`, `pathd_socket` →
  `/srv/laia/arch/pathd.sock`; `laia-pathd` arranca, escribe `.env.paths`+`pathd.sock`+
  `state/path-cache.json`+`atlas/` en `/srv/laia/arch` (owner laia-arch); `atlas doctor`
  resuelve los refs del runtime ARCH a `/srv/laia/arch`; `test_path_rewrite_cross_user.sh`
  **12/12 verde** en la VM. Pytest `test_atlas.py`+`test_clone_config_rewrite.py` 82 verde.
- **Abierto / para el Lead:**
  - **Inconsistencia de state root** a decidir: `infra/orchestrator/config.py` default ahora
    `/srv/laia/arch/state`, pero la unit `agora-backend.service` y `setup-prod-dirs.sh` siguen
    en `/srv/laia/state`, y el ref `srv_state` de `atlas.yaml` también. C1 hizo solo el
    touch-point pedido; reconciliar los tres es decisión del Lead (¿`/srv/laia/state` vs
    `/srv/laia/arch/state`?).
  - **Consumidores `~/.laia/state` no tocados** (fuera de los touch-points de C1, con su
    propia env var): `infra/dev/preflight.sh`, `infra/dev/smoke-test.sh`,
    `infra/scripts/audit-hardcoded-paths.py` (allowlist). Follow-up C3/C4.
  - **`pytest-asyncio`/`watchdog` ausentes** en el venv del VM y del host dev → la suite async
    de `infra/pathd/tests` no corre ahí (pathd cae a polling). Correrá en CI con deps. Los
    tests no-async del resolver van verdes.
  - PR contra `main` pendiente; **no** mergear (revisión Lead).

Slice **B1** del plan de estabilización (infra sobre el host de prod, branch `wip/claude/vm-laia-dev`).

- **VM `laia-dev` provisionada (ADITIVA, no toca prod):** pool `dir` sobre `/mnt/data`
  (`laia-dev`), bridge aislado `laiadev0` (10.123.0.1/24 NAT), perfil `laia-dev`
  (8 GiB / 6 vCPU / `security.nesting=true`), imagen `ubuntu:26.04` (= OS de prod), disco 60 GiB.
  IP estática `10.123.0.50` (netplan, cloud-init net disabled). `lxc list` → RUNNING.
- **🔴 Hallazgo crítico (documentado en el runbook): UFW bloquea bridges LXD nuevos.**
  La FORWARD/INPUT de UFW tiene `policy drop`; las reglas `accept` de la tabla `inet lxd`
  no bastan (un `drop` de UFW gana). `lxdbr0` (prod) funciona por reglas UFW explícitas;
  un bridge nuevo necesita `sudo ufw allow in on <br>` + `sudo ufw route allow in on <br>`.
  **Implica a la migración (C3/C4) y a `laia-install`** si crean un bridge propio.
- **`laia-install` (modo install, branch `stable`) OK dentro de la VM → `/api/health` responde**
  (`auth_json_ready:true`). Owner `laia-arch` (fidelidad a prod). Tailscale 1.98.4 instalado.
  Gotchas documentados: (1) `curl|sudo -E bash -s` anidado = no-op; (2) handoff reabre
  `/dev/tty` → usar `script` (pty); (3) factory bootstrap exige `~/.laia/auth.json` antes de
  provisionar `laia-agora` (copiado el real del host).
- **🔐 Remediación de seguridad (creds throwaway):** el primer provisioning copió el
  `auth.json` **real de prod** a la VM (desbloquear bootstrap) y contaminó el snapshot
  `b1-base`. Sustituido por un **placeholder estructural** (tokens `DEV-PLACEHOLDER-NOT-REAL`),
  in-place (preserva el inode del bind-mount), 644 (lo lee el uid mapeado de `laia-agora`; el
  0600 vía `raw.idmap` es C2, no B1). Snapshot `b1-base` **borrado** → snapshot limpio
  **`golden`** recreado. `laia-agora` lee el placeholder y `/api/health` verde con creds falsas
  (health/pre-flight solo comprueban que `auth.json` exista, no que el token funcione).
  **Pendiente Jorge:** rotar/revocar el token `openai-codex` de prod (un fragmento se expuso
  en logs durante la inspección).
- **§4.3 VERIFICADO:** `laia-agora` RUNNING (LXD anidado) + `/api/health` `ok:true,
  auth_json_status:linked` (salida real en el runbook). `lxd_available:false` esperado (health
  corre dentro del container, sin socket LXD).
- **§5 snapshot crear+restaurar VERIFICADO:** ciclo real — crear `golden` → plantar marker →
  `stop`+`restore`+`start` → marker AUSENTE + `laia-agora` autoarranca + health verde. ⏱️
  Tiempos reales: crear **16m31s**, restaurar **18m35s** (pool `dir`+ext4 en HDD = copia
  completa del `root.img` de 60 GiB, ~67 MB/s; **NO "en segundos"** como pedía el plan — es la
  contrapartida de no tener CoW, ya aceptada en §0). Recomendación documentada: encoger root a
  ~20 GiB o migrar a btrfs/zfs (requiere root) si se quiere rollback rápido.
- **§6 operación + autostart:** documentado start/stop/restart/borrado+limpieza de recursos;
  `boot.autostart=true` en la VM y en `laia-agora` (verificado `true`; el restore confirma que
  el cerebro vuelve solo tras cold-boot).
- **Runbook completo de provisión:** `infra/dev/laia-dev-vm-runbook.md` (§1-6 verificadas;
  base para el ensayo de migración C3).
- **Backup ad-hoc de prod a VM-USB (a petición de Jorge):** script one-shot
  `/tmp/backup-prod-to-usb.sh` (NO commiteado — el sistema permanente es D1). Copia
  consistente de `agora.db` (sqlite `.backup`) + tars de `/srv/laia/{agora,users}` + secretos
  v1 (`~/.laia/{auth.json,.env}`) + manifiesto sha256. Lo ejecuta Jorge con `sudo` (todo es
  root-only). Confirmado: **no había backups** y `/srv/laia/arch/secrets` aún no existe
  (layout v1 vigente).
- **Tailscale VERIFICADO:** Jorge autorizó la URL; VM en el tailnet como `laia-dev` =
  `100.98.22.53`, `tailscale ping` VM→Mac `pong in 17ms`, `sshd` activo. **Los 5 criterios de
  aceptación de B1 quedan en verde.** (Caveat: `golden` es anterior al auth de Tailscale → un
  restore exige re-`tailscale up`; documentado en runbook §3.)
- **Abierto:**
  - **Ampliación pedida por Jorge (más allá de B1):** convertir la VM en **espejo completo** del
    ecosistema — `laia-clone` prod→VM (datos reales: agora.db + users), estado+secretos del
    ARCH, y harness multi-IA (cc1, cc2, Codex, OpenCode) **con secretos reales** (VM solo-tailnet).
    Fase 2 (datos `/srv` root-only) requiere un paso root de Jorge. Solapa user story #11.
  - PR contra `main` pendiente; **no** mergear (revisión Lead + Jorge HITL).

---

## 2026-05-29 — Estabilización: arranca ejecución (A2 mergeado, B1 en curso) (claude opus 4.8, rol Lead)

Multi-agente en marcha: Codex → A2, Coder-Opus → B1. El Lead revisa antes de mergear.

- **A2 (tests) — DONE.** Fuga de estado del pool global entre tests de `agora-backend`
  resuelta: el fixture `autouse` `_isolated_pool_with_stub_agent` ahora inyecta `_pool` vía
  `monkeypatch` (teardown lo restaura y neutraliza el `set_pool` crudo de `test_session_id_
  defaults_to_user_scoped`). 1 línea, cero cambios de producto. **Verificado por el Lead**:
  RED en `main` (`2 failed`) → GREEN×2 con el fix (`363 passed`). PR #14 mergeado a `main`
  (merge commit `43750014`). `problems.md`: entrada consolidada + duplicado marcados resolved.
- **B1 (VM `laia-dev`) — EN CURSO.** VM LXD RUNNING (8 GiB/6 vCPU, nesting, disco `dir` en
  `/mnt/data`, red aislada `laiadev0`), Tailscale documentado, prod intacto. Runbook nuevo:
  `infra/dev/laia-dev-vm-runbook.md`. Branch `wip/claude/vm-laia-dev` (sin push aún).
- **Hallazgos de la revisión del Lead sobre B1:**
  - 🔴 El `auth.json` **real de prod** (tokens OpenAI, 644) se copió a la VM y quedó horneado
    en el snapshot `b1-base`. A remediar (creds throwaway + re-snapshot) antes del PR de B1.
  - 🟢 **UFW bloquea todo bridge LXD nuevo** en este host (drop terminal); requiere
    `ufw allow/route allow`. Incorporado como requisito a las slices **C3** y **C4**.
  - 🟡 Disco `dir` (no zfs): snapshots = copia de `root.img`, no instantáneos. UFW del host
    modificado (aditivo, bridge aislado).
- **Abierto:** cerrar B1 (remediar creds, §5 restore + §6 operación, verificar install+health);
  confirmar con Jorge la decisión `dir`-pool.

## 2026-05-29 — Fix ownership de artefactos de control en `laia-clone` (Coder-Codex)

- `clone.sh` ahora restaura ownership al usuario admin para `.clone-state` y para staging
  transitorio bajo `.laia-clone-stage`, incluso en fallos de stage/promote.
- El staging remoto se limpia al terminar correctamente y el directorio raíz del staging se
  elimina si queda vacío.
- `test_clone_hardening.sh` cubre markers bajo `sudo -n` cuando está disponible y valida el
  lifecycle user-owned/cleanup del staging.
- Verificación: clone hardening/local/phase-H pasan; `tests/installer/run_all.sh` queda con
  un fallo preexistente/no relacionado en `test_path_rewrite_cross_user.sh` (`state_db`).

## 2026-05-29 — Plan de estabilización + evolución del layout de datos a "v2" (claude opus 4.8)

Sesión de planificación (FASE 1+2). NO toca código de producto; cambia docs y planes.

- **Plan técnico** de estabilización LAIA-ARCH + entorno de desarrollo en
  `workflow/plans/estabilizacion/` (bundle: estrategia, plan técnico, auditoría, estado).
  Bloques A (orden/seguridad/tests), B (VM de dev LXD), C (migración datos ARCH + eliminar
  `~/.laia`), D (backups permanentes + suite de integridad). Estado: draft, pendiente OK
  para `to-issues`.
- **Evolución del canon a layout "v2"** (con consentimiento explícito de Jorge): secretos
  pasan de `~/.laia/` → `/srv/laia/arch/secrets/` (0600), runtime ARCH → `/srv/laia/arch/`,
  `SOUL.md` → `~/LAIA-ARCH/`, **`~/.laia/` eliminado**. Actualizados `LAIA_ECOSYSTEM.md §8`,
  `arch-layout.md`, `arch-data-layout.md`, `AGENTS.md`/`CLAUDE.md` (tabla de paths),
  `PATH_RESOLVER.md`, `01-canonical-sources.md`. Cada doc lleva banner "objetivo; disco/código
  aún v1 hasta Bloque C".
- **Decisiones técnicas (grill):** secretos legibles por `laia-agora` vía `raw.idmap` (cierra
  el `644`, que era un hack deliberado), no chmod world-readable; migración prod = script
  in-place idempotente (clone solo ensaya en VM); v2 **install-native** (instalador + `laia
  auth` crean el layout nuevo).
- **Reorg `workflow/plans/`:** mega-proyecto → `plans/estabilizacion/`; archivados los planes
  de Atlas v2 (terminado) y `dev-stable-versioning` (superseded por `release-flow.md`).
- **Fixes de doc:** `release-flow.md` → "VM dev en el host (LXD)" (no "VM en Mac") + paths
  `/home/laia-arch`; corregida ruta de `workspace.db` (real: `~/LAIA-ARCH/workspaces/...`);
  borrado `bin/atlas.py` (duplicado byte-idéntico).
- **Abierto:** ejecutar bloques empezando por `to-issues`. El layout v2 está en docs pero NO
  en disco/código aún (eso es el Bloque C).

## 2026-05-28 — Fix `atlas visualize`: reescritura UI + cero deps externas (claude opus 4.7)

El comando `atlas visualize` (introducido el mismo día en commit `28a47d02`)
generaba HTML con Mermaid 11 pero el grafo no renderizaba ("Syntax error in
text"). Causa raíz: combinación de timing de `startOnLoad`, `graph TD;` con
punto y coma, y `subgraph env_file ["env_file"]` (sintaxis ambigua en algunas
builds de Mermaid 11).

Decisión: en vez de parchear Mermaid, **reescribir el visualize de cero** con
SVG vanilla + JS minimal. Justificación: para 35 nodos / 16 aristas no se
necesita una librería de grafos pesada; control total sobre la estética y
cero dependencias externas (HTML self-contained de verdad, abre desde
`file://` sin red).

### Cambios

- **`bin/atlas`**:
  - `cmd_visualize()` reescrita: recoge refs + edges + health en un payload
    JSON, sustituye un único placeholder en la plantilla.
  - `_HTML_TEMPLATE` reescrito (~750 líneas): CSS con tokens light/dark, HTML
    semántico, JS vanilla.
  - Helper `_open_in_browser()` extraído.
  - **Bug `--no-open` arreglado**: ahora se respeta (antes se ignoraba).
  - Help strings y docstring del módulo actualizados.
- **`tests/test_atlas.py`**: nueva clase `TestCliVisualize` con 6 tests
  (salida HTML, refs presentes, JSON parseable, cero deps de red, placeholder
  sustituido, `--no-open` respetado vía monkey-patch de `webbrowser.open`).
- **`workflow/plans/atlas-visualize-fix.md`**: convertido a post-mortem con
  diagnóstico, decisión técnica, y lista de criterios cumplidos.

### Funcionalidades de la webapp

- Topbar con brand, búsqueda (atajo `/`), contador de estados, toggle de tema
  light/dark.
- Sidebar con filtros por tipo (con conteos) y por estado.
- Vista grafo: SVG con layout layered (una columna por tipo), nodos con punto
  de estado, aristas curvadas con flecha, pan/zoom, hover resalta conectados.
- Vista tabla: columnas ordenables, filas filtrables.
- Panel de detalle: status + detalle de error + repair hint + dependencias y
  consumidores (clickeables para drill-down).
- Esc cierra detalle / limpia búsqueda.

### Verificación

- `pytest tests/test_atlas.py -q` → **74/74 PASS** (68 originales + 6 nuevos).
- HTML resultante: **~47 KB** (cero red en runtime, verificado por test).
- `./bin/atlas visualize --output /tmp/atlas.html --no-open` ahora funciona
  sin abrir navegador.

### Sobre el flujo de trabajo

Aplicada por primera vez la regla recién documentada en AGENTS.md "1 tarea =
1 branch = 1 PR" (PR #10 acababa de mergearse). El trabajo entero va en
`wip/claude/atlas-visualize-fix` contra `main`, no stacked.

---

## 2026-05-28 — Atlas v2 adoption Fase 1: descubrimiento Minimax + 3 PRs Claude (claude opus 4.7 + minimax 5 agentes)

División del trabajo: **5 agentes de Minimax descubrieron** (no escribieron código),
**Claude aplicó** los cambios en 3 PRs incrementales. 2 PRs propuestos se saltaron
con razón técnica documentada.

### Descubrimiento (Minimax × 5 agentes)

Output en `workflow/plans/atlas-v2/` (10 archivos `.md`, ~1133 líneas), inventario
de hardcodes por área:

- `agora-backend-app.md`: 38 hardcodes en `admin.py`, `main.py`, `config.py`,
  `storage.py`, `orchestrator.py`. La mayoría con env-var fallback ya existente.
- `agora-backend-otro.md`: solapamiento + análisis de `agent_pool`, `models`,
  `agent_identity`, `llm_config`, tests.
- `bin-y-libs.md`: 16 hardcodes en `bin/laia*` y `infra/installer/lib/*.sh`.
- `gateway.md`: 15 hardcodes en `.laia-core/gateway/platforms/` (WhatsApp ×9,
  Signal, Feishu, BlueBubbles, API server).
- `laia-core-agent.md`: **0 hardcodes reales** (todo via `get_laia_home()`).
- `laia-core-entry.md`: **0 hardcodes reales** (cli.py, run_agent.py, etc.).
- `laia-core-tools.md`: **0 hardcodes reales** en tools/.
- `laia-executor.md`: 9 hardcodes (paths /etc/laia, /var/lib/laia, /var/log).
- `orchestrator-pathd.md`: 1 hardcode host-side + 4 filter strings; ~50 paths
  container-internal correctamente marcados OUT OF SCOPE.
- `scripts.md`: 18 hardcodes en `infra/dev/*.sh` + `infra/scripts/*.sh`.

**Realidad descubierta**: los 578 hardcodes del scanner `atlas consumers` se
descomponen en ~80 accionables + el resto en comentarios, fixtures de tests,
y rutas container-internal correctamente fuera de scope de Atlas-host.

### Aplicación (Claude × 3 PRs incrementales)

**PR #4 — `feat(atlas): añadir 12 refs nuevas`** (base main):
- Paths del executor (6, optional): `executor_token_file`, `executor_profile_file`,
  `executor_workspace_root`, `executor_plugins_root`, `workspace_store_lib`,
  `laia_process_log_dir`.
- Subdir operacional (1, optional): `srv_state` (`${srv_laia}/state`).
- Servicios del gateway (5, optional): `whatsapp_bridge`, `signal_cli`,
  `gateway_api`, `feishu_webhook`, `bluebubbles_webhook`.
- `~/.laia/atlas.yaml`: 23 → 35 refs. `atlas validate` ✓. `atlas doctor` 0 DEAD
  reales, 14 optional offline (esperado en dev). `pytest tests/test_atlas.py`:
  68/68 PASS.
- Plantilla `infra/pathd/atlas.yaml.example` actualizada en paralelo.
- Discovery reports completos en `workflow/plans/atlas-v2/`.

**PR #5 — `feat(agora-backend): adoptar atlas.get() para paths host-side`**
(stacked sobre #4):
- Nuevo helper `services/agora-backend/app/atlas_paths.py`:
  - `resolved_path(env_var, atlas_ref, default)` → `Path`
  - `resolved_container(env_var, atlas_ref, default)` → `str`
  - `atlas_string(atlas_ref, default)` → `str`
  - Importación lazy de atlas desde `.laia-core`; degrada limpio si falta.
- `config.py` (3 paths): `LAIA_ROOT` → `laia_root`, `AGORA_DATA_DIR` → `srv_agora`,
  `LAIA_STATE_ROOT` → `srv_state`.
- `admin.py:716`: `AGORA_ADMIN_USERS_ROOT` → `srv_users`.
- Suite agora-backend: 361/361 PASS (excluyendo 2 tests con bug pre-existente
  registrado en `workflow/problems.md` como `agora-backend-test-pool-contamination`).

**PR #6 — `feat(infra): shell scripts leen atlas con fallback graceful`**
(stacked sobre #4):
- 4 scripts shell migrados al patrón:
  `${ENV:-$(command -v atlas >/dev/null && atlas get ref 2>/dev/null || echo default)}`
- `infra/dev/smoke-test.sh`, `seed-base-skills.sh`, `rebuild-state.sh`,
  `infra/scripts/deploy-agora.sh` (con helper `_atlas_get()` inline +
  healthcheck URL dinámico).
- bash -n ✓, atlas resuelve correctamente con/sin atlas en PATH.

### PRs saltados con razón

- **PR-3 (laia-executor)**: el executor declara explícitamente
  `tools/__init__.py:6: "No \`.laia-core\` dependency"`. No puede importar atlas
  en runtime. Los defaults ya son env-var-backed; migrar no aporta valor.
- **PR-4 (.laia-core/gateway/platforms/)**: código upstream LAIA Agent
  (mattpocock/teknium). Modificar 5 archivos con 15 hardcodes complicaría
  merges futuros con upstream. Los servicios ya están **registrados** en
  atlas.yaml (PR-1) — el conocimiento queda capturado. Migración del código
  pendiente de coordinar con autor upstream o vía fork explícito.

### Decisiones arquitectónicas aplicadas (sin consenso explícito de Jorge)

1. **Container-internal paths NO añadidos a atlas.yaml** (`opt_laia_internal`,
   `opt_laia_data`, etc.). Atlas-host no debería describir layout interno de
   containers LXD — eso es responsabilidad de la imagen.
2. **`agent-jorge` en atlas pero NO en código real**: se deja como está (la
   ref existe como referencia, optional, repair hint `lxc start agent-jorge`).
3. **Pathd daemon migración a atlas.py**: deferred. Sigue usando `laia_paths.py`
   (legacy config.yaml). Proyecto aparte de mayor scope arquitectónico.

### Bug pre-existente registrado

`workflow/problems.md` → `agora-backend-test-pool-contamination` (open):
2 tests del coordinator fallan cuando la suite completa corre desde el
principio. Causa: `chat_engine.set_pool()` muta global, no se limpia entre
tests. No causado por estos PRs.

### Pendiente (no aplicado)

- **Container refs hardcodeados `laia-agora`** en `admin.py:336, 442, 1489`,
  `main.py:901`, etc. El helper `resolved_container()` ya está listo en PR-2;
  aplicar en un PR-2b si Jorge quiere.
- **Discrepancia `AGORA_IMAGE_ALIAS=laia-agora` vs `_ALLOWED_IMAGE_ALIASES=laia-agent`**
  (admin.py:876 vs config): bug real o intencional, requiere decisión de Jorge.
- **Fase 5 del plan original** (deuda estructural `/opt/laia` plano vs versionado):
  bloqueada por decisión arquitectónica de Jorge.

### Orden de merge sugerido

1. **#4** primero (refs nuevas; riesgo 0).
2. **#5** y **#6** después (rebase automático sobre main).

---

## 2026-05-28 — Fixes release flow: laia-release default OPT_SRC, comentarios obsoletos (claude opus 4.7)

Verificación end-to-end del flujo de release tras el saneamiento (`bin/laia-release`,
`bin/laia-rollback`, `install.sh`, `Makefile`, `tests/installer/run_all.sh`, coherencia
main↔stable). Resultado: el flujo funciona, pero con 3 disonancias.

### Arreglado

- **`bin/laia-release`**: default `OPT_SRC` cambiado de `$LAIA_USER_HOME/.laia` a
  `$LAIA_USER_HOME/LAIA`. Razón: `~/.laia` es runtime (no tiene `.git`), el dev repo
  vive en `~/LAIA` según `LAIA_ECOSYSTEM.md`. Antes, `sudo -E laia-release` sin
  argumentos abortaba con "Source tree is not a git repo". Comentario del header y
  texto del `--help` también actualizados.
- **`bin/laia-rollback`**: comentario del `--help` mencionaba `~/LAIA-ARCH/` (path
  inexistente). Cambiado a `~/.laia/` y `/srv/laia/` (los reales según ecosystem).

### Verificado correcto (sin cambios)

- `install.sh`: `DEFAULT_BRANCH="stable"`, `DEFAULT_REPO_URL` correcto, las 3 URLs
  en el header del script apuntan a stable.
- Wrappers en `bin/`: `laia`, `laia-clone`, `laia-install`, `laia-release`,
  `laia-rollback`, `atlas` — todos ejecutables.
- `tests/installer/run_all.sh`: orquesta 18 tests con HOME temporal aislado.
- `Makefile`: `make test` corre pytest AGORA + TypeScript typecheck.
- `bin/laia-release` lógica interna: preflight → smoke tests → build a
  `/opt/laia-vX.Y.Z` → switch atómico de symlink → restart systemd → healthcheck →
  auto-rollback en fallo. Robusto.
- `bin/laia-rollback`: solo flip symlink + restart (no build), simple y atómico.
- Coherencia main↔stable: `stable` es ancestor de `main`, `git merge --ff-only main`
  funcionaría. `stable` está 14 commits retrasado (esperado post-saneamiento).
- Smoke tests post-fix: 50/50 PASS (`test_flags.sh` 24/24, `test_lib_common.sh` 26/26).

### Pendiente conocido

- Próximo release oficial será `v0.1.3` (o el número que decida Jorge): promoverá
  los 14 commits acumulados (atlas v2, fix migration, fix clone, recovery cron+SOUL,
  shell_rc, trío docs, skills mattpocock, saneamiento, guía git+GitHub, estos fixes)
  de main a stable con `git merge --ff-only main && git tag -a v0.1.3`.

---

## 2026-05-28 — Saneamiento completo del repo en GitHub: unificar LAIA, archivar Hermes (claude opus 4.7)

Operación grande, planificada y ejecutada con verificación obligatoria en cada paso
(`workflow/plans/archive/2026-05-28-github-cleanup-archive-hermes.md`).

### Punto de partida (el lío)

El repo `JorgeMP-3/laia-arch` era un fork de **Hermes Agent** (Nous Research / Teknium)
que en algún momento pivotó hacia LAIA-ARCH. La transición se hizo creando ramas orphan
sin historia común. Resultado: **6 historias paralelas disjoint** en el mismo repo:

- `main` = Hermes upstream + parches de Jorge (6.625 commits desde 2025-07).
- `stable` = snapshot orphan de LAIA del 26-may (1 commit, 2.574 archivos).
- `feat/installer-cloner-v2`, `feat/installer-wizard` = orphans LAIA viejas.
- `wip/codex/dev-stable-versioning` = base oficial LAIA con releases v0.1.0/0.1.1/0.1.2 tageados.
- `local-customizations` = customs pre-LAIA sobre Hermes.

Más, en local, 11 commits de Jorge dispersos: 7 en `stable` orphan, 3 en una wip de
limpieza, 1 en una wip de mattpocock-skills.

`workflow/02-how-to-work.md` decía "main = dev, stable = prod" pero la realidad era opuesta.

### Saneamiento (13 fases, gate de verificación en cada integración)

1. SSH key añadida en GitHub (auth).
2. Push de las 3 wips locales a remote.
3. Backup de las 5 ramas legado en `archive/*` (Hermes upstream, customs, 2 orphans, stable orphan).
4. Default branch movido temporalmente a `wip/codex/dev-stable-versioning` (UI).
5. `origin/main` (Hermes) borrado tras verificar backup íntegro.
6. `wip/codex/dev-stable-versioning` renombrada a `main` (UI). Default vuelve a `main`.
7. Cherry-pick de los 10 commits locales sobre la nueva main, en 3 branches paralelas:
   - `wip/jorge/recent-fixes-on-main` (6 commits: atlas v2, fix migration, fix clone config.yaml
     via Python helper, recover cron+SOUL, shell_rc, docs ecosystem).
   - `wip/jorge/cleanup-and-trio-on-main` (3 commits: refinación trío docs, chore claude
     settings, trace LAIA_TRACE).
   - `wip/claude/mattpocock-dev-skills-on-main` (1 commit: 13 skills + doctrina right-size).
8. Verificación post-cherry-pick (gates obligatorios): 13/13 skills válidas, 12/12 symlinks
   Codex, atlas v2 + cron + SOUL + Python helper presentes, AGENTS.md con right-size +
   guardarraíles + §Agent skills, tags v0.1.x accesibles.
9. `stable` realineado al tip de LAIA (igual a main).
10. Las 3 branches `*-on-main` mergeadas en main con `--no-ff` (resolución manual de
    conflictos en `LAIA_ECOSYSTEM.md`, trío docs, `changelog.md`).
11. Push de main unificado a GitHub.
12. Archivado de las 3 wips orphan-based originales en `archive/wip-*-orphan` y borrado
    de las ramas legado obsoletas (`feat/installer-*`, `local-customizations`).
13. Docs actualizadas: `workflow/git-github-guide.md` (human-facing), `AGENTS.md` §Git workflow
    (AI-facing terso), `00-start-here.md` y `01-canonical-sources.md` apuntando a la guía.

### Estado final en GitHub

```
origin/main                    ← LAIA-ARCH desarrollo unificado (5a41fc87)
origin/stable                  ← LAIA-ARCH prod tip (be965365)
origin/wip/*-on-main           ← 3 ramas integradas (mergeadas en main)
origin/archive/hermes-upstream
origin/archive/hermes-local-customizations
origin/archive/laia-pre-versioning-cloner-v2
origin/archive/laia-pre-versioning-wizard
origin/archive/laia-stable-orphan-snapshot
origin/archive/wip-jorge-recent-fixes-orphan
origin/archive/wip-jorge-cleanup-and-trio-orphan
origin/archive/wip-claude-mattpocock-orphan
tags v0.1.0, v0.1.1, v0.1.2 (accesibles desde main)
```

### Pendientes conocidos

- **b2a99a04 (orphan root del stable)** fue SKIPPED durante el cherry-pick (no se puede
  aplicar como diff por ser orphan). Su único commit era "fix(clone): refrescar wrappers
  bin/". Diferencias detectadas: en main no existe la función `_clone_refresh_bin_wrappers`
  de `bin/laia-clone`, ni el fichero `infra/lxd/image-build/lib-build.sh` (163 líneas). La
  evolución de main puede haber hecho irrelevante ese fix; revisar caso por caso si surge
  el síntoma original ("/opt/laia ya existe y los wrappers no se refrescan").
- Las 3 ramas `wip/*-on-main` en origin están técnicamente obsoletas tras los merges
  (sus commits ya viven en main); pueden borrarse cuando se considere.

### Lecciones registradas

- Refspec restringido (`+refs/heads/stable:...`) ocultaba el resto del repo. Ampliado a `*`.
- `git checkout --orphan` recurrente crea historias paralelas que NO se mergean — solo
  cherry-pick.
- Cuando un commit es orphan-root, su diff "contra el padre" son TODOS los archivos
  como nuevos → cherry-pick imposible. Se salta y se aplican los cambios manualmente si
  hace falta.

---

## 2026-05-27 — Skills de workflow de desarrollo (mattpocock) integradas para las 3 IAs (claude opus 4.7)

Integración de [mattpocock/skills](https://github.com/mattpocock/skills) como **tooling de
dev** (NO producto, NO Marketplace) para Claude Code + Codex + OpenCode.

- **Vendorizadas 13 skills** en `.claude/skills/` (fuente de verdad, commit upstream
  `0288510`): grill-me, grill-with-docs, to-prd, to-issues, tdd, triage, diagnose, handoff,
  zoom-out, improve-codebase-architecture, write-a-skill, setup-matt-pocock-skills,
  git-guardrails. Cada una con bloque `## LAIA context` cerrado (`<!-- LAIA:START/END -->`)
  para poder re-vendorizar reemplazando lo de arriba del marcador.
- **Fan-out a 3 IAs**: `.claude/skills/` lo leen Claude Code y OpenCode nativamente; Codex
  vía symlinks relativos por-skill en `.codex/skills/` (mode 120000 en git).
- **git-guardrails** es solo-Claude (instala hook `PreToolUse`): vendorizada **sin symlink
  Codex** y **NO activada** (no se tocó `.claude/settings.json`). `name` localizado de
  `git-guardrails-claude-code` a `git-guardrails`.
- **AGENTS.md** reescrito como canónico: protocolo FASE 1-4 → punteros a skills; gates duros
  (5 reglas, branching) inline; nuevo bloque `## Agent skills` (tracker=ficheros locales,
  dominio=`LAIA_ECOSYSTEM.md`). **CLAUDE.md** → stub que apunta a AGENTS.md.
- `.claude/skills/UPSTREAM.md` documenta procedencia, SHA y convención de actualización.
- Índice de workflow actualizado (`00-start-here.md`, `01-canonical-sources.md`).
- **Descripciones** de las 13 skills localizadas (prefijo FASE/categoría en español) para
  que el diálogo `/skills` se lea claro; nombres y cuerpos intactos. README de uso en
  `.claude/skills/README.md`.
- **Triaje reconciliado**: el estado canónico sigue siendo el campo `Estado:` de
  `problems.md` (`open`/`in-progress`/`blocked`/`resolved`); los roles de Pocock se mapean
  sobre ese formato (vía `Estado:`+`Owner:`), sin etiquetas nuevas. Mapa en `AGENTS.md`
  §Agent skills y en el bloque LAIA de `/triage`.
- **Doctrina reframe (mínimo)**: `AGENTS.md` pasó de protocolo FASE lineal/obligatorio a
  **right-size** (FASE = default para no-trivial, no ritual) + guardarraíles
  Siempre/Pregunta/Nunca, más terso. La filosofía/porqué se movió a `workflow/ai-mindset.md`
  (human-facing, no se carga cada turno). Respaldo: estudios de context-bloat (más reglas y
  ficheros largos bajan la tasa de éxito de los agentes). CLAUDE.md y 00-start-here actualizados.
- **Abierto**: verificación de invocación en las 3 CLIs (Slice 4) + evidencia.
- **Descubierto**: las skills de Pocock esperan config en un bloque `## Agent skills` de
  AGENTS.md/CLAUDE.md + `docs/agents/` — se mapeó a la realidad LAIA (workflow/) sin crear
  `docs/agents/`. Plan completo en `~/.claude/plans/vale-me-quiero-instalar-frolicking-creek.md`.

## 2026-05-27 — Recuperación de paquete `cron/` perdido en migración + fix bug `.bashrc` del instalador (claude opus 4.7)

Dos hilos en la misma sesión, ambos derivados de la migración `laia-hermes`→`laia-arch`.

### A) Agente CLI no arrancaba: `ModuleNotFoundError: No module named 'cron'`

- **Síntoma**: `laia` (dispatcher bash) y `laia --help` funcionaban, pero `laia chat`
  / one-shot crasheaban en `cli.py:662 from cron import get_job`. También
  `laia_cli/cron.py:194 from cron.jobs import get_job`.
- **Causa raíz**: el paquete fuente `.laia-core/cron/` (`__init__.py`, `jobs.py`,
  `scheduler.py`) está **gitignored** (`.gitignore:31 cron/` y `:61 .laia-core/`).
  Nunca se commiteó, así que la migración (que respeta `.gitignore`) lo dejó atrás.
  Faltaba en `/opt` **y** en el árbol dev. No estaba en host, git, backups ni en los
  contenedores LXD (`laia-agora` = backend; agentes = `laia-executor` only).
- **Hallazgo mayor**: comparando la VM original contra el dev tree faltaban **11
  entradas** gitignored: `cron/`, `SOUL.md`, `skills/`, `scripts/`, `bin/`,
  `ai-agents.json`, `packaging/`, `tinker-atropos/`, `flake.lock`, `uv.lock`,
  `temp_vision_images/` (esta última, basura de runtime). Solo `cron` es blocker de
  import; `SOUL.md` se lee en runtime (auto-inyección de persona).
- **Recuperación** (Jorge ejecutó los `sudo`/VM):
  - `rsync --ignore-existing` VM→dev tree: trae lo ausente sin pisar los ficheros ya
    corregidos (que en la VM tienen rutas `laia-hermes`).
  - Validado: toda la interfaz de `cron` importa (`get_job, create_job, load_jobs,
    save_jobs, get_due_jobs, list_jobs, update_job, pause_job, parse_schedule,
    compute_next_run`, `cron.scheduler`).
  - `rsync --ignore-existing` dev→`/opt/laia-v0.11.0/.laia-core/` para rellenar el
    mismo hueco en producción.
  - El editable finder de `/opt` no mapeaba `cron` (se instaló cuando el dir no
    existía; `pyproject` SÍ lo declara en `packages.find.include`). Reinstalar el
    editable falló (`BackendUnavailable: setuptools.build_meta` — venv sin setuptools,
    sin red). **Workaround aplicado**: `.pth` (`zz_laia_core_root.pth`) que añade
    `/opt/laia-v0.11.0/.laia-core` al `sys.path` del venv → resuelve `cron` y cualquier
    otro módulo no mapeado, offline y sin rebuild.
  - Verificado desde CWD neutro: `cron`/`cli` resuelven a `/opt`; el agente corre la
    cadena completa (ya no rompe en `cron`).
- **Abierto**:
  - **Durabilidad git**: falta `git add -f .laia-core/cron .laia-core/SOUL.md` (el
    convenio aquí ya es force-add dentro de `.laia-core/`). Sin esto, la próxima
    migración/release lo vuelve a perder.
  - El `.pth` es parche de runtime; un futuro `laia release` debería incluir `cron/`
    de forma nativa (depende de cómo sincronice release respecto a `.gitignore`).
  - **Credenciales**: el agente llega a resolver proveedor y pide `laia auth` (Codex).
    El proveedor quedó en `openai-codex` pero el login se hizo con `sudo` → fue a
    `/root/.laia/auth.json`, no a `~/.laia`. Pendiente: `laia model` → Anthropic (hay
    `ANTHROPIC_API_KEY` en `~/.laia/.env`) o `laia auth` SIN sudo.

### B) Bug del instalador: `.bashrc` queda root-owned tras `install` con sudo

- **Síntoma**: `/home/laia-arch/.bashrc` quedó `root:root 0600` → el usuario no podía
  leerlo/editarlo y la siguiente shell perdería el `.bashrc` entero. `✗ Failed at
  shell_rc.sh:46`. (Reparado en disco con `sudo chown`.)
- **Causa raíz**: `shell_rc_apply`/`shell_rc_remove` escriben el rc vía `mktemp` + `mv`;
  `mv` reemplaza el fichero heredando metadata del tmp (root:root 0600 bajo sudo) y
  nunca devolvía propiedad/modo. Mismo patrón que ya se mitigó en `common.sh` para el log.
- **Fix** (`infra/installer/lib/shell_rc.sh`): helper `shell_rc_restore_meta` (chown a
  `$LAIA_USER` solo si root + chmod al modo original capturado con `stat` antes del `mv`),
  invocado tras cada `mv`. Mismo patrón de propiedad de HOME que `factory.sh`.
- **Test** (`tests/installer/test_shell_rc.sh`): Test 7 de regresión (un rc en 644 no
  debe quedar en 600 tras `apply`). Suite **19/19** (antes 18).
- **Abierto**: sin commitear. El cloner (`clone.sh`) deja basura root-owned en el HOME
  (`~/.laia-clone-stage/`, `~/LAIA-ARCH/.clone-state/`) — mismo patrón, no arreglado.

### C) Reescritura de `LAIA_ECOSYSTEM.md` (visión pura) + nuevo `workflow/arch-layout.md`

- **Motivo**: el documento canónico estaba desactualizado y mezclado con basura muy
  técnica (puertos, idmaps, contrato clone, conteos de tests/tools) que ensuciaba la
  idea. Consenso explícito de Jorge para editarlo (regla CLAUDE.md).
- **Acción** (decisión de Jorge vía AskUserQuestion):
  - `LAIA_ECOSYSTEM.md` → **documento de visión puro** (568 → 344 líneas): visión,
    entidades, flujos conceptuales, reglas duras ①–⑭, workspaces, roadmap. §8 (layout
    en disco) reducido a propósito conceptual + enlace.
  - Nuevo **`workflow/arch-layout.md`** (264 líneas): se mueve ahí todo el detalle
    técnico — layout `/opt`/`/srv`/`~/.laia`/`~/LAIA-ARCH`, permisos, idmaps, contrato
    `laia-clone`, flujos `install`/`clone`. Enlace cruzado bidireccional.
  - **Actualizaciones de datos**: Atlas v2 (no "32 aliases"), quitados conteos frágiles
    ("71 tools", "431/342 tests", "80+ endpoints"), versión coherente (v2 — 2026-05-27),
    nota de realidad en `/opt` (volcado plano vs modelo versionado objetivo).
  - Añadida en `arch-layout.md` la **trampa de migración**: fuente gitignored de
    `.laia-core/` (p.ej. `cron/`) no viaja con clone basado en git.
  - Nuevo **`workflow/project-map.md`**: plano anotado de TODO el repo (carpetas más
    importantes, su objetivo, archivos y subcarpetas clave) generado de la estructura
    real. Enlazado desde `LAIA_ECOSYSTEM.md` (header + §8).
  - **Ampliado `project-map.md`** con sección "Mapa del sistema completo": TODAS las
    locations en disco verificadas (`/opt`, `/srv`, `~/.laia`, `~/LAIA-ARCH`, `/root/.laia`,
    containers LXD) con su estado REAL y las divergencias vs spec marcadas. Aclarada la
    jerarquía doc: LAIA_ECOSYSTEM (idea) / arch-layout (modelo objetivo) / project-map
    (estado real). Hallazgo destacado: `LAIA_HOME=~/LAIA-ARCH` → el agente usa
    `~/LAIA-ARCH` como home completo (auth/config/runtime), no solo "mesa viva" →
    3 auth.json descoordinados (config-home, Fase 5).

## 2026-05-26 — Fix installer/clonador: egress preflight no-fatal (claude opus 4.7)

- **Síntoma**: en el Thinkstation `curl ... | sudo bash -- --mode clone`
  caía en `1.5/4 Verificar red LXD hacia internet` con `Terminated
  LAIA_ROOT="$LAIA_ROOT" bash "$script"` — el bash hijo recibía SIGTERM
  externo mientras `lxc launch ubuntu:24.04` descargaba la imagen pública.
- **Causa**: `ensure_lxd_egress` en `rebuild-2-images.sh` lanzaba un
  contenedor temporal pesado (descarga 300 MB) y trataba cualquier fallo
  como fatal (`die`). Introducido hoy en 4 commits (`23e4ba5e`, `ce121756`,
  `111d4a02`, `c933ab59`).
- **Fix** (`infra/lxd/scripts/rebuild-2-images.sh`):
  - Reescrita `ensure_lxd_egress` — preflight informativo, NUNCA fatal.
  - Primary path: host-level check (lxdbr0 up/IP, curl archive.ubuntu.com,
    iptables NAT, lxc image list ubuntu:) en < 5 s. Sin contenedor.
  - Deep probe (contenedor temporal) ahora opt-in via `LAIA_LXD_DEEP_PROBE=1`.
  - Nuevo escape: `LAIA_LXD_SKIP_EGRESS=1` salta toda la sección.
  - stderr de `lxc launch` ahora va a `/tmp/laia-egress-probe.log` (no
    `/dev/null`).
- **Hint extra** (`infra/installer/lib/bootstrap.sh`): si
  `rebuild-2-images.sh` sale con 143/137, log un mensaje accionable
  apuntando a `journalctl` (oom/oomd/snap.lxd.daemon) y a la mitigación
  `LAIA_LXD_SKIP_EGRESS=1`.
- Plan completo en `workflow/plans/2026-05-26-installer-clone-thinkstation-fix.md`.
- Smoke local pasado (Plan C del plan): `ensure_lxd_egress` retorna 0
  en ambos modos (defaults + skip), warnings claros para fallos parciales.
- **Validación parcial en Thinkstation**: el preflight ya NO bloquea
  (commit `5385ca3b`). Pero apareció el problema real: DNS roto dentro
  del container (host alcanza archive.ubuntu.com, container no resuelve).
- **Segundo fix** (commit `be94c18b`): `build-base-image.sh` y
  `build-agora-image.sh` esperan hasta 20 s a que el DNS del container
  funcione; si no, dropean `/etc/resolv.conf` estático con `1.1.1.1` +
  `8.8.8.8` + `9.9.9.9`. Más relax en check `state UP` de lxdbr0
  (bridges suelen reportar UNKNOWN; chequeo el flag `<...,UP,...>` en
  lugar de `state UP`).
- **Tercer fix (commit `b595be98`)**: en el siguiente run de Jorge el
  container `laia-agent-base` quedó RUNNING **sin IPv4** (DHCP del
  bridge no le asignó IP), por lo que el fallback de DNS estático no
  podía resolver (sin ruta, 1.1.1.1 inalcanzable). Nuevo helper
  compartido `infra/lxd/image-build/lib-build.sh::ensure_container_network`
  con escalada DHCP → dhclient/networkctl → **IP estática derivada del
  bridge** (`lxc network get lxdbr0 ipv4.address` → octeto `.249`, gw
  bridge.1), luego DNS con fallback.
- **Cuarto fix (commit pendiente)**: ambas imágenes se construyeron OK
  con el helper, pero el container final `laia-agora` (lanzado por
  `rebuild-3-provision-agora.sh` step 5/7) volvió a quedar sin IPv4
  porque el helper sólo estaba en los build-scripts. Step 7/7 hacía
  `die "no pude obtener IP del container"` y abortaba el clone tras
  todos los rsyncs OK. Fix:
  - `rebuild-3-provision-agora.sh` ahora sourcea `lib-build.sh` y
    llama `ensure_container_network` tras `lxc launch`.
  - Step 7/7 `Esperar /api/health` ahora prueba en paralelo el
    endpoint via bridge (`<container_ip>:8000`) Y el proxy del host
    (`127.0.0.1:8088`); cualquiera que responda es suficiente. Si
    `lxc list` no devuelve IPv4, fallback a `ip -4 -o addr show eth0`
    desde dentro. Diagnóstico extendido si TODO falla (journalctl +
    ip+ss inside container).
  - `lib-build.sh`: añadido alias `info → log` para que se pueda
    sourcear desde scripts que usan `log` (rebuild-3) y desde los
    que usan `info` (build-{base,agora}-image.sh).
  - Bug menor: `dhclient -4 -v` sin timeout colgaba ~60-75s antes
    de rendirse. Ahora envuelto con `timeout 8` + flag `-1` (one-try).
    Ahorra ~60s por container cuando DHCP está roto.
- **Quinto fix (commit pendiente) — causa raíz del DHCP roto en
  Thinkstation**: Claude Code en el server diagnosticó con
  `nft list ruleset` que UFW estaba droppeando 628 DHCP DISCOVERs en
  udp/67 ANTES de las reglas de LXD (cadena `udp dport 67 → ufw-skip-
  to-policy-input`). Es el conflicto clásico UFW + LXD documentado.
  En la VM laia-hermes no aparece porque UFW está inactivo aquí.
  Fix integrado en el installer (`rebuild-2-images.sh::lxd_apply_network_config`):
  detecta `ufw status | head -1 | grep 'Status: active'`, comprueba si
  ya existe regla para el bridge (`Anywhere on lxdbr0` o `on lxdbr0 ALLOW IN`),
  y si no, ejecuta `ufw allow in on lxdbr0 && ufw reload`. Idempotente.
  Más check informativo en `lxd_host_egress_check` que reporta el
  estado de UFW.
- **Sexto fix (commit `a8f15d78`) — UFW fix en init-defaults.sh**: el
  fix anterior vivía en `rebuild-2-images.sh::lxd_apply_network_config`,
  pero `boot_build_images` salta rebuild-2 si las imágenes ya están
  presentes. En el re-run de Jorge tras el quinto fix las imágenes
  existían → rebuild-2 se saltó → UFW fix nunca se aplicó → DHCP
  seguía droppeado. Movido el fix a `init-defaults.sh` (que SIEMPRE
  corre desde `boot_init_defaults`).
- **Séptimo fix (commit `82fe5ecd`) — cloner usa layout pre-T.14.1**:
  Jorge: "el clone solo me trajo cron + state.db + workspaces, falta
  todo lo demás". Causa: la migración E2E T.14.1 del 26-mayo movió toda
  la data ARCH del operador de `~/.laia/` a `~/LAIA-ARCH/`, pero
  `clone_phase_h_rsync_arch_data` seguía usando `legacy_laia` como source
  base. Fix: detectar si la fuente tiene `~/LAIA-ARCH/` poblado y, si sí,
  usarlo como autoritativo (`arch_src_kind=laia_home`).
- **Décimo fix (commit pendiente) — clone refresca wrappers bin/**:
  Tras el noveno fix, la nueva versión de `bin/laia` solo surtía efecto
  si Jorge re-corría `laia-release` (que requiere `--src` y promueve a
  nueva versión completa, demasiado overhead para un cambio de 1 binario).
  Fix en `laia-clone::_clone_refresh_bin_wrappers`: cuando el install-
  first detecta que /opt/laia ya existe (rama de skip), aún copia los
  5 wrappers (`laia`, `laia-install`, `laia-clone`, `laia-release`,
  `laia-rollback`) del repo al `/opt/laia-vX.Y.Z/bin/`. `install -m 0755`,
  idempotente, ~1s. Ahora basta con re-correr el clone (o cualquier
  install-first) para que los bugfixes de los wrappers surtan efecto.
- **Noveno fix (commit `93adc703`) — `laia` lanza chat agente**:
  En el Thinkstation, Jorge esperaba que escribir `laia` (o `laia-arch`)
  en la terminal le abriera el chat interactivo con su agente LLM,
  pero el bash dispatcher (`bin/laia`) solo manejaba subcomandos del
  installer (install/clone/release/rollback/status). Fix:
  - `laia` (sin args) → exec del Python CLI agente
    (`/opt/laia/.laia-core/venv/bin/laia` o fallback al dev tree).
  - Subcomandos no reconocidos (chat, setup, auth, login, model,
    skills, plugins, gateway, cron, doctor, sessions, …) → forward al
    Python CLI.
  - `laia status` ahora va al Python CLI (agent components); el bash
    status del host queda accesible via `laia-status` directo.
  - Installer subcommands (install, clone, release, rollback, init,
    wizard, diagnose, reset) sin cambios.
  - Help text reescrito para mostrar las dos categorías.
- **Octavo fix (commit `0f7d712e`) — rsync único del árbol LAIA-ARCH**:
  Tras el séptimo fix, Jorge re-corrió y el destino aún tenía solo
  `cron response_store.db sessions state.db workspaces` — las loops
  per-spec fallaban silenciosamente después de las primeras 1-2
  iteraciones (causa raíz no identificada; sospecha de interacción
  entre `clone_rsync_to_privileged_dest`/stage promotion y rsync
  exit codes de transferencia parcial). En lugar de seguir parcheando
  las loops, simplificamos: cuando `arch_src_kind=laia_home`, hacemos
  UN SOLO `clone_rsync_to_privileged_dest` del árbol LAIA-ARCH/ entero
  con excludes de runtime cruft (.laia-clone-stage/, *.lock, *.sock,
  .update_check). rsync es incremental → idempotente. Las loops
  per-spec quedan como fallback para layout legacy (~/.laia/). Añadido
  log final que lista el contenido del dest para verificación visual.

## 2026-05-26 — Ecosystem E2E migration + T.14 polish (claude opus 4.7)

- Ejecutado `workflow/plans/2026-05-25-ecosystem-e2e-verification.md` T.0-T.13
  (482 MB migrados de `~/.laia/` a layout canónico; backend on PM2/LXD,
  pathd, ui-server vivos). Reporte completo en `/tmp/laia-migrate-report.md`.
- **T.14.1 (cancela `/srv/laia/arch/`)**: el código (laia_cli, pathd) corre
  como `laia-hermes` y no puede traversar `/srv/laia/arch/` (root:root 700).
  Decisión con Jorge: toda la data de ARCH (interactiva + operacional) vive
  bajo `LAIA_HOME` (= `~/LAIA-ARCH/`). `/srv/laia/arch/` queda deprecado.
  Doc `workflow/arch-data-layout.md` reescrito para reflejarlo.
- **T.14.2 (limpieza `~/.laia/`)**: Jorge cerró su `laia` CLI activo en pts/3
  que había recreado stubs. Stubs vacíos eliminados; los dirs con contenido
  (sessions, workspaces, sandboxes, logs) fusionados con LAIA_HOME. `~/.laia/`
  ahora solo legacy compat (`auth.json`, `.env`, `bin/`, `cache/`, etc.).
- **T.14.3 (LXD)**: daemon LXD estaba colgado en `lxc init` (5+ min sin I/O).
  Restart de `snap.lxd.daemon` lo destrabó. `agent-verify-bob` aprovisionado y
  registrado en AGORA.
- **Bug fixes encontrados en el camino**:
  - `infra/lxd/scripts/create-agent.sh`: container name no soporta `_` (LXD
    rechaza). Mapeo automático `_ → -` en el nombre. Slug DB se mantiene.
  - `infra/lxd/scripts/create-agent.sh`: `LXD_UID_OFFSET` default era `100000`,
    pero LXD usa `1000000` (per `/etc/subuid`). Corregido. Esto rompía bind
    mounts de `/srv/laia/users/<slug>/` — `nobody:nogroup` desde container.
  - `infra/installer/lib/clone.sh`: 5 patches que eliminan refs a `/srv/laia/arch`
    como destino canónico. Las refs como SOURCE legacy se preservan (clones
    desde hosts pre-T.14.1).
- **T.14.4 + T.14.5 (F.5 chat + F.10 executor)**: chat E2E completo
  funciona (verify-bob → openai-codex → write_file → forwarder → executor
  container → bind mount → host file con contenido correcto). Persistencia
  post-recreate (F.5.5) y aislamiento entre containers (F.5.6) verificados.
  Tras destrabar auth.json bind mount con `rebuild-3b-fix-authjson.sh`.
- **T.14.6 (F.14 webhooks)**: endpoint correcto es `/api/webhooks/{slug}`
  con header `X-Laia-Signature: <hex>` (no `sha256=<hex>`). Creación de
  webhooks via LLM tool `webhook_subscribe` (plugin `agent-scheduler`), no
  REST API. F.14.2 (good HMAC = 200) y F.14.3 (bad HMAC = 401) verificados.
- **T.14.9 (test E2E permanente)**: nuevo `tests/e2e/test_ecosystem_layout.sh`
  + target `make test-e2e`. Pasa con LAIA_HOME=~/LAIA-ARCH: 25 OK / 1 WARN
  / 0 FAIL / 1 SKIPPED.
- **Pendiente / abierto**:
  - JWT secret se regenera en cada arranque del backend (config.py:64 sin
    AGORA_JWT_SECRET en env). Bug: invalida tokens a cada restart. Anotado
    en problems.md.
  - PM2 `agora-backend` queda en `errored` 5322 restarts — la copia host
    intenta arrancar pero el container `laia-agora` ya sirve :8088. PM2 debe
    eliminarse o el container debe pararse para no haber doble servicio.
  - Snapshot LXD/Multipass post-T.14: `multipass snapshot <vm-name> --name
    post-t14-clean-2026-05-26` (host Mac, no la VM).
  - Tag git `v2026.05-ecosystem-clean` pendiente de commit + decisión de
    Jorge sobre push.

## 2026-05-25 — LAIA_ECOSYSTEM canonicaliza layout LAIA-ARCH (codex)

- Actualizado `LAIA_ECOSYSTEM.md` §8 para que el documento canónico refleje
  el split ya implementado en `laia-clone`: `workspaces`, `memories`,
  `skills` y `plugins` viven en el `LAIA_HOME` editable del operador,
  mientras `SOUL.md`, `config.yaml`, `sessions`, `sandboxes`, `atlas`,
  `cron`, `logs` y DBs internas quedan en `/srv/laia/arch`.
- El contrato de transferencia de `laia-clone` queda alineado con los tests
  `test_clone_phase_h.sh` y `test_path_rewrite_cross_user.sh`.
- No se cambiaron rutas de credenciales (`auth.json`, `.env`); siguen
  documentadas como compatibilidad legacy en `~/.laia/`.

## 2026-05-25 — Split LAIA-ARCH live data vs sensitive runtime (codex)

- Ajustado `laia-clone` para separar datos legacy de LAIA-ARCH:
  `workspaces`, `memories`, `skills` y `plugins` se migran a `LAIA_HOME`
  (`/home/jorge/LAIA-ARCH` por defecto), mientras que `sessions`,
  `sandboxes`, `atlas`, `cron`, `logs` y runtime sensible quedan en
  `/srv/laia/arch`.
- Actualizada la reescritura de `config.yaml`: `workspaces`, `memories`,
  `skills` y `plugins` apuntan a `${LAIA_HOME:-...}`; paths legacy
  desconocidos bajo `~/.laia` siguen cayendo en `/srv/laia/arch`.
- Añadido `workflow/arch-data-layout.md` con el criterio operativo y la
  compatibilidad temporal de `auth.json`/`.env`.
- Tests actualizados: `test_clone_phase_h.sh` y
  `test_path_rewrite_cross_user.sh`.
- No se movieron datos reales en disco y no se tocó `LAIA_ECOSYSTEM.md`.

## 2026-05-25 — Plan dev/stable convertido a runbook para otra IA (codex)

- Reescrito `workflow/plans/2026-05-25-dev-stable-versioning.md` como runbook
  ejecutable para una IA implementadora: contexto obligatorio, alcance, fases
  numeradas, comandos, verificaciones, riesgos y criterios de hecho.
- Añadido el plan al índice de `workflow/plans/README.md` para que aparezca
  entre los planes activos.
- Ejecutado el plan: `install.sh` ahora apunta por defecto a `stable`, se añadió
  `tests/installer/test_install_default_branch.sh`, y se creó
  `workflow/release-flow.md` con promote, deploy, rollback y hotfix.
- Actualizados `AGENTS.md`, `workflow/00-start-here.md` y
  `workflow/02-how-to-work.md` para documentar `main` como dev y `stable` como
  producción.
- Verificación: `bash -n install.sh`, `git diff --check`,
  `bash tests/installer/test_install_default_branch.sh` y
  `bash tests/installer/run_all.sh` pasan.
- No se tocó `LAIA_ECOSYSTEM.md`.

## 2026-05-25 (cont. 7) — Hardening installer + cloner pre-Fase-5 (claude-code)

Auditoría sistemática del installer y cloner antes de pasar a Fase 5,
seguida de fixes priorizados. Jorge pidió "100% de garantía de que
cumplan al trabajo de forma organizada y profesional".

**Auditoría** (2 Explore agents en paralelo): inventario completo de
`install.sh` + `bin/laia-install` + `infra/installer/lib/{install,
factory,bootstrap}.sh` para installer, y `bin/laia-clone` +
`infra/installer/lib/clone.sh` para cloner. Producto: lista priorizada
de issues por severidad (5 CRITICAL, 7 HIGH, ~15 MEDIUM/LOW, lista de
gaps de tests). Jorge eligió alcance CRITICAL + HIGH.

**CRITICAL fixes** (commit `9c20c3fe`):

1. **Install rollback post-symlink** (`bin/laia-install`,
   `infra/installer/lib/install.sh`): `inst_switch_symlink` captura el
   target previo en `INST_SYMLINK_PREVIOUS`. `inst_install_rollback_trap`
   registra un EXIT trap (ERR no fire en `die` que llama `exit` directo)
   que revierte el symlink si cualquier paso post-symlink falla.
   `inst_clear_rollback_trap` desarma al éxito.

2. **LXD waitready honesto** (`bootstrap.sh:74-94`): el loop de 60s
   ahora trackea `lxd_ready`; si timeout sin éxito, `die` con mensaje
   claro + apuntador al journalctl. Antes "salía silenciosamente" y
   `lxd init --auto` corría contra daemon no-listo.

3. **SSHPASS via -f file, no -e env** (`bin/laia-clone`,
   `clone.sh`): `resolve_ssh_pass_file` reubica el secreto en
   `/run/laia-clone-XXXX/sshpass` (0600, tmpfs preferido). Todas las
   invocaciones de sshpass usan `-f $CLONE_SSHPASS_FILE`. EXIT trap
   scrub. Antes `export SSHPASS` lo dejaba visible en `ps -e`.

4. **UID mapping verification** (`clone.sh::clone_phase_h_fix_uid_mapping`):
   muere con exit 5 + mensaje claro si `lxc info laia-agora` falla o
   `volatile.idmap.base` está vacío. Antes caía a hardcoded 1000000,
   corrompiendo ownership en silent.

5. **Clone phase markers + resume robusto** (`clone.sh`, `bin/laia-clone`):
   nuevos `clone_phase_mark_start` / `mark_done` / `should_skip` en
   `$LAIA_HOME/.clone-state/<phase>.done` (byte-vacío, md5-estable).
   Aplicado a rsync-agora, rsync-users, rsync-arch, rsync-arch-creds.
   `--resume` ahora salta solo phases con marker. Heurística legacy
   (agora.db con ≥ 20 tablas) sigue como safety-net que sintetiza marker.

**HIGH fixes** (commit `a1fd7546`):

6. **verify deeper** (`clone_phase_h_verify`): query agora.db por
   tablas (≥ 10) y users (≥ 1). Antes solo `lxc list` + `curl health`,
   que pasaban con DB corrupta.
7. **SSH connect timeout configurable** (`clone.sh:240`):
   `LAIA_SSH_TIMEOUT` (default 15s, antes hardcoded 5s).
8. **admin reset schema validation** (`factory.sh::fact_reset_imported_admin_password`):
   PRAGMA table_info antes del UPDATE; die exit 6 si `users` no
   existe o le faltan `username`/`password`.
9. **sed anchor** (`clone_phase_h_rewrite_config_paths`): false alarm
   del audit — el comportamiento actual es correcto (`paths:` nesta las
   keys; los comentarios `#` no se ven afectados porque `#` no es
   `[[:space:]]`). Reverted con comentario explicativo inline.

**Tests + VM smoke** (commit `d06aee97`):

- Nuevo `tests/installer/test_clone_hardening.sh` (6 asserts) cubre las
  primitivas de phase markers, `LAIA_SSH_TIMEOUT`, schema validation, y
  guards anti-`export SSHPASS`.
- `tests/installer/vm-wizard-e2e.sh` actualizado a `bin/laia wizard` (Fase 4).
- Nuevo `workflow/plans/2026-05-25-installer-vm-smoke.md` con guía
  paso-a-paso para Jorge: comandos Multipass, qué verificar, dónde
  mirar si falla.

**Tests:** `tests/installer/run_all.sh` **30/30** verde (29 prior +
test_clone_hardening). `pytest .laia-core/tests/test_tui_app.py` 7/7.

**Pendiente (decisiones-de-Jorge antes de Fase 5)**:
- Validación VM real (ver plan VM smoke).
- HIGH #11 (centralizar logs de factory bootstrap a
  `~/.cache/laia-wizard/runs/`) — diferido por scope.
- Decisión sobre `flows/connectivity.py` (todavía modo oculto).
- Decisión sobre la semántica de `ssh_auth_mode='setup'` (pre-existing
  failure de test).

---

## 2026-05-25 — Runner de integridad por capas (codex)

- Añadido `tests/run_integrity.py`, runner stdlib-only con tiers `static`,
  `unit`, `local-runtime`, `deployed`, `lxd-e2e` y `llm-e2e`.
- `make test` ahora ejecuta la ruta rápida `static + unit`; añadidos
  `make integrity`, `make integrity-deployed` y `make integrity-lxd-e2e`.
- Creado `workflow/plans/integrity-tests.md` para dejar registrada la ejecución
  por fases y los gates de seguridad (`LAIA_RUN_LXD_E2E=1`, `LAIA_E2E_LLM_KEY`).
- Verificación: `static` verde; `local-runtime` verde fuera del sandbox;
  `lxd-e2e` y `llm-e2e` skippean sin flags; `unit` detecta dos problemas
  existentes abiertos en `workflow/problems.md`.

## 2026-05-25 (cont. 6) — Fase 4 del installer remake: Textual default + reorg de entrada (claude-code)

Esta fase completa el remake del wizard salvo la Fase 5 (modo headless TOML
+ pirámide de tests).

**Part 1 — Flip default + borrado de UI legacy** (commit `58b6e88e`):

- Textual deja de ser opt-in; ahora es la UI por defecto del wizard.
  `LAIA_UI=rich|dev|text` cae al fallback `_dev_ui` (stdin/stdout plano);
  `--text-ui` mantiene el mismo papel; headless / `--yes` sigue por su
  path independiente.
- Borrados los 5 archivos de la capa rich legacy en
  `.laia-core/laia_cli/install_wizard/ui/` — 959 LOC de UI muerta:
  `__init__.py`, `components.py`, `console.py`, `progress.py`, `theme.py`.
  `_load_ui` reemplazado por `_load_dev_ui` (one-liner).
- Tests obsoletos eliminados con la capa que testeaban:
  `tests/installer/test_wizard_yesno_input.sh`,
  `tests/wizard/test_ui_{components,render,progress}.py`. La cobertura
  equivalente vive en `.laia-core/tests/test_tui_app.py` contra el
  FormScreen Textual.
- Cierra `workflow/problems.md::install-wizard-ui-tests-stale` (flagged
  por codex durante el runner de integridad — ahora con causa raíz y
  resolución).
- Detectado pero NO resuelto en esta fase:
  `tests/wizard/test_clone_security.py::test_clone_execute_aborts_on_ssh_setup_mode`
  falla con código pre-existente (commit `5e786ac5`). Asserta que
  `ssh_auth_mode='setup'` debería abortar antes de invocar clone, pero el
  flow continúa. Logged en `problems.md::clone-ssh-setup-mode-continues`
  como decisión-de-Jorge pendiente.

**Part 2 — Unificación bajo `bin/laia` + borrado de `bin/laia-wizard`**
(commit `54062002`):

- `bin/laia` (dispatcher existente que cubría install/clone/release/
  rollback/init/status) absorbe 3 subcomandos nuevos:
  - `laia wizard` — wizard interactivo (menú install/clone).
  - `laia diagnose` — health check (read-only).
  - `laia reset` — wipe (peligroso, doble confirmación).
  Cada uno hace `exec python -m laia_cli.install_wizard [--mode <x>]`.
- Borrado `bin/laia-wizard`. Su lógica de python-discovery (LAIA_ROOT,
  venv prefencia, PYTHONPATH, log dir) se movió a `bin/laia`.
- `install.sh:474` actualizado: `cmd=("$bin/laia" "wizard")` en lugar de
  `cmd=("$bin/laia-wizard")`. Help text y comentarios consistentes.
- El flow `flows/connectivity.py` NO se borró aún: ya no aparece en el
  menú (Fase 3 lo quitó), pero sigue invocable via `--mode connectivity`
  para scripts. La decisión "borrar definitivamente y inlinear como step
  opcional en install/clone" queda abierta para sesión futura — clone
  ya tiene SSH setup inline (`ssh_auth_mode='setup'`).

**Cierre de bug**:

- `workflow/problems.md::wizard-prompts-sin-contexto` cerrado como
  resolved en esta sesión. Combinación de Fase 3 part 2 (help_text
  expandido) + Fase 4 part 1 (Textual renderiza help_text inline bajo
  cada label).

**Pendiente para Fase 5**:

- Implementar `headless.py` con `tomllib` para `laia install --config
  wizard.toml --yes` sin TTY.
- Env vars override: `LAIA_<FIELD_UPPER>=value`.
- Tests pytest nuevos: validators (232 LOC sin cobertura), secret tmpfile,
  TUI screens completas con `App.run_test()`.
- E2E reducido a 2 smoke tests en VM (install + clone).
- Cobertura Python: subir de ~0% a >60%.

**Pendiente decisión-de-Jorge**:

- ¿Borrar `flows/connectivity.py` y cambiar el aviso tailscale en
  `flows/clone.py:86`?
- ¿Cambiar la semántica de `ssh_auth_mode='setup'` a "setup-only,
  abort después" (lo que pide el test de codex)?

## 2026-05-25 (cont. 5) — Fase 3 del installer remake: Textual UI opt-in (claude-code)

- **Textual UI añadida** detrás del flag `LAIA_UI=textual`. La UI legacy
  `rich.prompt` sigue siendo default; el operador opta in con el env var.
  Files nuevos en `.laia-core/laia_cli/install_wizard/tui/` (~700 LOC):
  - `app.py` — `LaiaWizardApp` (host), `FormScreen` (render dinámico de
    cualquier `WizardScreen`), `ExecuteScreen` (`RichLog` + `ProgressBar`
    alimentados por los `ProgressEvent` del engine).
  - `__init__.py` — exporta `run_textual_wizard()` + `is_textual_available()`.
- **Threading model**: engine sync corre en `run_worker(thread=True)`; cada
  push de screen cruza al main thread con `call_from_thread(push_screen_wait)`.
  El engine y los flows NO cambian de API — el contrato `WizardScreen` /
  `ProgressEvent` que ya era UI-agnóstico encaja directo.
- **Render dinámico de los 7 `Field.type`**: text, password, choice, checklist,
  yesno, path, info. `depends_on`, `help_text`, `placeholder`, `secret`
  honrados. `RadioButton` lleva el `value` original en un atributo custom
  para recuperarlo al submit aunque el label tenga adornos como
  `"(recomendado)"`.
- **Mitigaciones**: `umask(0o077)` en `App.on_mount` (Textual corre bajo
  sudo en este flujo); shell-escape no expuesto.
- **Dispatch**: `__main__.py` chequea `LAIA_UI` en el env; si `textual` y
  `textual` está importable, short-circuita a `tui.run_textual_wizard()`.
  Headless / `--yes` y rich siguen yendo por el path antiguo.
- **Dependencia opcional**: `.laia-core/pyproject.toml` añade extra
  `install_wizard = ["textual>=0.50,<10"]`. La instalación quedará
  cableada en `install.sh` cuando Fase 4 flipee el default.
- **Tests pytest**: `.laia-core/tests/test_tui_app.py` con 7 smoke tests
  usando `App.run_test()`. Cubren composición de FormScreen, value
  collection en todos los Field types, `depends_on` ocultando campos,
  back/quit sentinels vía `dismiss()`, y ExecuteScreen procesando los
  9 `ProgressEvent` types. **7/7 verde.**
- **Menú reducido**: `MODE_SELECT_SCREEN` en `engine.py` baja de 5 a 2
  opciones (install + clone). connectivity/diagnose/reset siguen
  invocables vía `--mode` flag; pasarán a subcomandos `laia <subcmd>`
  en Fase 4.
- **help_text expandido** en `flows/clone.py::_OPTIONS_SCREEN` para los 3
  campos problemáticos:
  - `bwlimit`: explica trade-off WAN vs LAN y qué pasa con valor vacío.
  - `keep_session`: deja claro que `No` (default) es lo recomendado y
    describe el flujo de credenciales que sigue.
  - `resume`: explícito "primera vez? `No`" up-front.
- **Tests**: `tests/installer/run_all.sh` **31/31** verde; `test_tui_app.py`
  **7/7** verde. Suites enteras pasan tras los cambios.
- **Plan actualizado**: `workflow/plans/2026-05-25-installer-textual-remake.md`
  añadido siguiendo la convención del repo (con estado por fase).
- **Coordinación con codex**: durante Fase 3 mi commit cayó accidentalmente
  en `wip/codex/integrity-tests` (codex había switcheado branch en paralelo).
  Lo moví limpio a `feat/installer-wizard` con
  `git branch -f feat/installer-wizard <sha> && git branch -f wip/codex/integrity-tests <pre-sha>`,
  sin tocar el WT de codex. Memoria guardada para próximas sesiones.

**Pendiente**: Fase 4 (flip default, borrar ~959 LOC de UI legacy,
diagnose/reset como subcomandos `laia <sub>`, inlinear connectivity).
Fase 5 (headless TOML + tests pytest-first).

## 2026-05-25 (cont. 4) — Fase 2 del installer remake: contrato JSON DRY (claude-code)

- **Contrato JSON bash→Python** estaba **mucho más adelantado** de lo que
  el plan asumía. `common.sh::emit_json_event` ya emitía 4 event types
  (`step_start`, `step_progress`, `step_done`, `step_error`) bajo
  `LAIA_JSON_PROGRESS=1`, usado en install.sh + clone.sh + bin/laia-install
  + bin/laia-clone. Python `_subprocess.py::_json_progress_event` ya
  parseaba JSON estricto antes del regex legacy. El gap real era el
  acoplamiento `log_step` ↔ `emit_json_event step_start`: 64 callers de
  `log_step`, sólo ~16 emisores explícitos de JSON — drift estructural.
- **Refactor**: `common.sh::log_step` ahora acepta `step_id` opcional como
  2º arg y auto-emite `step_start` cuando `LAIA_JSON_PROGRESS=1`. Si no
  se da id, deriva slug del label (`Phase H: rsync data` → `phase-h-rsync-data`).
- **Nuevo helper**: `common.sh::log_step_done` cierra simétricamente la
  fase con `step_done` JSON + `log_success` humano. Default step_id =
  `$LAIA_CURRENT_STEP`.
- **Colapsados 9 pares redundantes** `log_step` + `emit_json_event step_start`
  adyacentes en `clone.sh` (cada uno se vuelve `log_step "label" "id"`,
  −9 LOC, mismo comportamiento).
- **Tests**: `tests/installer/test_json_progress.sh` extendido con 4
  asserts nuevos (10 total): derived step_id slug, explicit step_id
  honoring, log_step_done emite step_done con current step_id, silencio
  sin `LAIA_JSON_PROGRESS`. **Suite completa 31/31 verde**.

**Decisión**: no se tocaron los `emit_json_event` explícitos en
`bin/laia-install:192-193` y `bin/laia-clone:313-314` porque emiten un
step_id semántico DIFERENTE del log_step que les sigue (banner outer vs.
phase inner). Reordenar arriesgaba romper el contrato.

## 2026-05-25 (cont. 3) — Plan remake installer + Fase 1 (matar bug TTY) (claude-code)

- **Plan aprobado**: `~/.claude/plans/atomic-giggling-shore.md` — remake del
  instalador/wizard en 5 fases. Engine Python (`engine.py`/`flows/`/`contract.py`,
  motor UI-agnóstico) se mantiene; reescribimos sólo la capa UI (`ui/*.py`, 959 LOC)
  hacia Textual. Bash en `infra/installer/lib/` se queda como librería de "acciones
  puras" (sin prompts). Decisiones: 2 modos (install/clone) + 2 subcomandos
  (`laia diagnose`, `laia reset`); todo bajo sudo desde `install.sh`; single branch
  con flag `LAIA_UI=textual|rich`; config headless en TOML (`tomllib` stdlib).
  Referencia inspecting: Hermes Agent (`NousResearch/hermes-agent`) — bash thin que
  invoca wizard Python separado, mismo patrón que LAIA ya tiene pero con mejor
  ejecución.

- **Fase 1 cerrada** — bug `wizard-clone-tty` resuelto:
  - Borrado `clone_prompt_ssh_password()` en `infra/installer/lib/clone.sh` (15 LOC).
    Bash ya no abre `/dev/tty` directamente para preguntar password SSH.
  - Reescrito el fallback de preflight SSH (clone.sh:256-263): si key auth falla
    sin `--ssh-pass-file`, `die` con código 3 y mensaje claro apuntando al wizard.
    Si key auth falla CON `--ssh-pass-file`, también die (el password era erróneo).
  - Eliminado el reattach `/dev/tty` redundante en `bin/laia-wizard:86-89`. Capa
    única: `install.sh` reattach en hand-off (para `curl|bash`) + Python
    `__main__._reattach_tty()` como red de seguridad para invocaciones standalone.
  - Nuevo test: `tests/installer/test_clone_ssh_no_password_fallback.sh` (4 asserts,
    pasa). Regression guard contra el bug.
  - **Suite completa `tests/installer/run_all.sh`: 30/30 verde** tras los cambios.
  - Files tocados: `infra/installer/lib/clone.sh`, `bin/laia-wizard`,
    `tests/installer/test_clone_ssh_no_password_fallback.sh` (nuevo),
    `workflow/problems.md` (cerrado wizard-clone-tty).

- **Pendiente Fase 2**: contrato JSON line-delimited de progreso bash→Python
  (`log_step`/`log_substep` emiten JSON cuando `LAIA_JSON=1`; `JsonEventParser` en
  `_subprocess.py`). El bug `wizard-prompts-sin-contexto` se atacará en Fase 3
  con la capa Textual (los `help_text` ya existen en los `Field`s; el problema es
  la presentación de `rich.prompt`).

- **Checkpoint previo**: commit `36c92fc5` archivó 18 docs hand-written a
  `docs/archived/old-handwritten/` y 3 root-level a `docs/archived/old-root-md/`,
  más 118 archivos auto-generados en `docs/db-export/` desde `workspace.db`.
  `docs/README.md` reescrito como índice minimal.

## 2026-05-25 — Inicio del workflow cooperativo y refresh de LAIA_ECOSYSTEM (claude-code)

- `LAIA_ECOSYSTEM.md` actualizado a v1.2: header con regla anti-alucinación que declara
  el documento canónico sobre la DB; nueva §6.4 "Subsistemas en detalle" (Agent Areas,
  Soul, AgentPool, Tool Forwarder, Command Center, Control Center, DevOps); nota de
  transición HOME en §8.3.
- Creada estructura `workflow/`: `00-start-here.md`, `01-canonical-sources.md`,
  `02-how-to-work.md`, `03-multi-ai-coordination.md`, `changelog.md`, `security.md`,
  `problems.md`, `plans/README.md`.
- Sembrado `problems.md` con los 2 bugs del wizard descubiertos hoy en prueba real
  (wizard-clone-tty, wizard-prompts-sin-contexto) para que no se pierdan.
- Creado `AGENTS.md` (entry para Codex/OpenCode/Aider) y `CLAUDE.md` (entry mínimo
  para Claude Code que apunta a `AGENTS.md`). Ambos en la raíz.
- Añadida regla en `00-start-here.md` y `02-how-to-work.md`: **toda integración
  necesita su test en `~/LAIA/tests/`**; antes de declarar "hecho" se corre la
  suite completa. Sección detallada en `02-how-to-work.md` "Tests (obligatorio)".
- Primer export real de `workspace.db` → `~/LAIA/docs/db-export/` con
  `scripts/sync-workspace-markdown.py`. **118 archivos generados**. Fuente: la DB en
  `~/.laia/workspaces/laia-ecosystem/workspace.db`.
## 2026-05-25 (cont. 3) — Linger activado, db-export "siempre actualizado" (jorge + claude-code)

- Jorge ejecutó `sudo loginctl enable-linger laia-hermes`.
- Verificado: `Linger=yes`, `State=active`. El user manager systemd persiste tras logout
  y arranca en boot.
- `laia-docs-sync.service` queda corriendo en watch indefinidamente. `docs/db-export/`
  se mantiene sincronizado con `workspace.db` sin intervención manual.

---

## 2026-05-25 (cont. 2) — Archive de docs viejos y refs (claude-code)

- Movidos a `docs/archived/old-root-md/` (con `git mv` para preservar historia):
  `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` (los 3 de raíz).
- Movidos a `docs/archived/old-handwritten/` (18 archivos): `AGORA_AGENTS.md`,
  `API.md`, `ARCHITECTURE.md`, `CLI.md`, `CLONE.md`, `CONTROL_CENTER.md`, `DEPLOY.md`,
  `DEVELOPMENT.md`, `INSTALL.md`, `INTEGRATIONS.md`, `MARKETPLACE.md`, `OPERATIONS.md`,
  `PATH_REGISTRY.md`, `RELEASE.md`, `SERVIDOR_CONTEXTO.md`, `WIZARD.md`,
  `WIZARD_BACKEND.md`, `WIZARD_THEMING.md`.
- `docs/` ahora contiene sólo: `README.md` (índice nuevo minimal), `db-export/`,
  `archived/`, y los diagramas `map.drawio` / `map.svg`.
- `~/LAIA/` raíz ahora contiene sólo `AGENTS.md`, `CLAUDE.md`, `LAIA_ECOSYSTEM.md` como
  archivos canónicos `.md`. (Resto: `Makefile`, código, carpetas.)
- Limpiadas 4 referencias rotas a los archivos archivados en `workflow/changelog.md`,
  `workflow/01-canonical-sources.md`, `workflow/02-how-to-work.md`, `workflow/security.md`.
  Inlineadas las reglas de estilo en `02-how-to-work.md` (antes apuntaban a CONTRIBUTING.md).
- `docs/README.md` reescrito como índice minimal del nuevo `docs/`.

---

## 2026-05-25 (cont.) — Limpieza, auto-sync activo, AGENTS.md raíz (claude-code)

- **Auto-sync activo**: systemd user unit `laia-docs-sync.service` ejecutando
  `scripts/sync-workspace-markdown.py --watch --interval 2.0` con `LAIA_HOME` y
  `PYTHONUNBUFFERED=1` declarados en el unit. Verificado: `touch workspace.db`
  → re-export en <4s. Log en `~/.laia/logs/laia-docs-sync.log`.
- **Git policy**: `docs/db-export/` añadido a stage. 118 archivos, 1.3 MB, +31030 líneas.
  Pendiente el commit (decisión de Jorge sobre el mensaje y el momento). `.gitignore`
  no excluye `docs/db-export/`, así que el tracking quedará permanente.
- **`LAIA_HOME` fix**: retirado el bloque malo de `~/.bashrc` (líneas 157-160) que
  apuntaba al partial-install. La línea 154 sigue siendo la única autoritativa.
  Bug `env-laia-home-stale` cerrado en `problems.md`.
- **`docs/README.md` actualizado**: ahora explica el orden canónico (AGENTS.md →
  LAIA_ECOSYSTEM.md → workflow/ → docs/ → docs/db-export/). No se mueven los
  `docs/*.md` viejos a `archived/` — son guías hand-written distintas del export
  técnico, NO redundantes.
- **Pendiente para próxima sesión** (decisión de Jorge):
  - Borrar `/home/laia-hermes/laia-partial-install.02XwlG/` (huérfano del clone
    interrumpido, ya no hay nada que apunte a él). Contiene `auth.json`, `state.db`,
    `SOUL.md` viejos — verificar primero que `~/.laia/` tiene lo equivalente o más nuevo.
  - Activar `loginctl enable-linger laia-hermes` si quieres que `laia-docs-sync` siga
    corriendo aunque cierres sesión SSH.
  - Hacer el commit con todo: `LAIA_ECOSYSTEM.md` v1.2, `workflow/`, `AGENTS.md`,
    `CLAUDE.md`, `docs/db-export/`, `docs/README.md`.
