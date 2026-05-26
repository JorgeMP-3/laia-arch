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
- **Séptimo fix (commit pendiente) — cloner usa layout pre-T.14.1**:
  Jorge: "el clone solo me trajo cron + state.db + workspaces, falta
  todo lo demás (sessions, atlas, orchestrator-runs, config.yaml,
  ...)". Causa: la migración E2E T.14.1 del 26-mayo movió toda la data
  ARCH del operador de `~/.laia/` a `~/LAIA-ARCH/`, pero
  `clone_phase_h_rsync_arch_data` (`infra/installer/lib/clone.sh:736`)
  seguía usando `legacy_laia` (→ `~/.laia/`) como source base. Solo se
  rsynchronizaba lo que sobrevivía en `.laia/`: cron (vacío), un mini
  workspaces, y `~/.laia/state.db` (155 KB, no el real de 195 MB en
  LAIA-ARCH). Fix: detectar si la fuente tiene `~/LAIA-ARCH/` poblado
  y, si sí, usarlo como autoritativo (`arch_src_kind=laia_home`).
  Fallback a `~/.laia/` solo para sources pre-migración sin LAIA-ARCH.
  También expanded la check de "source has no ARCH data — skipping"
  para considerar ambos paths. Los mensajes "skip ~/.laia/X" ahora
  usan el path real chequeado. Idempotente — el siguiente clone
  rsynchronizará los dirs faltantes sin tocar lo que ya está.

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
