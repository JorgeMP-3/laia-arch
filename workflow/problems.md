# Problems log

Bitácora de problemas descubiertos durante el desarrollo. Se anotan AL DESCUBRIRLOS
aunque no se arreglen en ese momento. Sin esto, los problemas se olvidan.

## Cuándo escribir aquí

- Bug visible (algo no funciona como debería).
- Documentación que contradice al código.
- Decisión de arquitectura que parece equivocada (con argumentación).
- UX confuso (preguntas sin contexto suficiente, defaults raros).
- Performance que duele.

## Formato

```
## <slug-corto> (estado)

- **Descubierto**: 2026-MM-DD por <agente>.
- **Síntoma**: qué se ve, dónde.
- **Causa raíz sospechada**: si se sabe; "desconocida" si no.
- **Reproducción**: pasos mínimos.
- **Workaround**: si existe.
- **Owner**: persona/agente, o "sin asignar".
- **Estado**: open | in-progress | blocked | resolved.
```

Cuando un problema se resuelve, no se borra — se marca `(resolved)` en el título y se
añade una línea `- **Resuelto**: 2026-MM-DD en commit <hash>`.

---

## ui-prod-layer-rota-v0.11.0-necesita-remake-v0.2.0 (open)

- **Descubierto**: 2026-05-30 por claude opus 4.8 (Lead) + Jorge, al intentar abrir la consola admin para chatear.
- **Síntoma**: no hay forma de acceder al chat. `laia-ui-server` (consola ARCH Admin, `:8077`) NO arranca
  (`status=203/EXEC`: falta el ejecutable `/opt/laia/.laia-core/venv/bin/uvicorn`). `laia-gateway` y el resto
  de la capa de cara al usuario están inactivos. El backend (`agora-backend`, `:8088`) sí responde — el cerebro
  funciona, pero **no hay UI/consola operativa**.
- **Causa raíz**: el install de prod es **v0.11.0 era-Hermes** y su `laia-ui-server` está **incompleto** (venv
  sin `uvicorn`). Además el `EnvironmentFile=~/LAIA-ARCH/.env.paths` usa líneas `export KEY=val` que **systemd
  no parsea** (las ignora → las anclas de path no llegan al servicio). Es código viejo, desalineado con el
  backend **v0.2.0** que corre en el container `laia-agora`.
- **Reproducción**: `sudo systemctl start laia-ui-server` en prod → falla; ver `journalctl -u laia-ui-server`.
- **Workaround**: NINGUNO aplicado (decisión de Jorge: **no parchear el v0.11.0**). La unit queda en estado
  `failed` (inofensivo) hasta el remake.
- **Owner**: sin asignar.
- **Estado**: open — **MODIFICAR + REMAKE de la capa de UI/consola para v0.2.0** (consola admin + gateway +
  UI de AGORA de cara al usuario, que hoy NO existe operativa en prod). NO parchear el v0.11.0. Incluir: venv
  correcto con `uvicorn`/deps, `.env.paths` en formato systemd (`KEY=val`, sin `export`), y alineación con el
  backend v0.2.0. Es trabajo aparte (despliegue de la capa de usuario), a planificar como FASE cuando toque.

## backup-timer-runs-as-laia-arch-cannot-read-agora (open)

- **Descubierto**: 2026-06-01 por claude opus 4.8 (Lead, en el roadmap) — confirmado por claude-b (Track T)
  al revisar el template para T5.
- **Síntoma**: el backup nocturno correría "OK" **sin `agora.db`** (falso-verde, mismo patrón que el
  outage del cutover). `infra/installer/systemd/laia-backup.service.tmpl` usa `User=${LAIA_USER}`
  (= `laia-arch`), pero `/srv/laia/agora` es `drwx------` del uid del container (`1000999`):
  `laia-arch` no puede leer `agora.db`.
- **Causa raíz**: el servicio de backup corre como el usuario operador, no como `root`; el dir de datos
  de AGORA es root/container-owned y cerrado.
- **Reproducción**: instalar el timer y correr `laia-backup all` como `laia-arch`; el artefacto de
  `agora.db` sale vacío o ausente aunque el exit sea 0.
- **Workaround**: correr `laia-backup` como `root` manualmente.
- **Fix**: el servicio de prod debe correr como `root` (o `User=root` en la plantilla). Validar con
  corrida real que `agora_*.db` pesa ~36M, no vacío. **Fix = código de producción** (plantilla del
  installer) → NO lo toca Track T; coordinado con Codex/Lead.
- **Cobertura (Track T)**: `tests/integration/regression/test_backup_service_runs_as_root.sh` guarda el
  invariante; hoy SKIPea (exit 77) con motivo loud citando esta entrada, y vira a PASS al arreglar la
  plantilla (sin silent gap).
- **Owner**: Codex/Lead (fix del template).
- **Estado**: open.

## migrate-v1-to-v2-prod-outage (resolved)

- **Descubierto**: 2026-05-30 por claude opus 4.8 (Lead) + Jorge, al ejecutar el cutover en prod.
- **Síntoma**: `migrate-v1-to-v2.sh --yes` en prod → verify rojo (`auth_json_ready:false`) →
  auto-rollback → `laia-agora` no arranca (`forkstart exit 1`, "Failed to setup mount entries").
  **Outage ~50 min del cerebro AGORA.** Recuperado a mano (post-mortem en `changelog.md`). Sin pérdida de datos.
- **Causa raíz (4 bugs del script)**:
  1. Borra el mountpoint `/srv/laia/agora/auth.json` al quitar el device `agora-auth` (rebuild-3b).
  2. El swap de auth (`AGORA_ARCH_AUTH_JSON` + mount `arch-laia` en `/var/lib/laia-host`) NO surte
     efecto: el backend v0.2.0 sigue leyendo `/opt/agora/data/auth.json`.
  3. **Auto-rollback buggy**: graba `PRE_AGORA_DATA_OWNER=0:0` (el real era el agora user
     `1000999:1000988`) → deja `/srv/laia/agora` root:root 700 → el agora user del container
     unprivileged no puede entrar (Permission denied) y su restart falla. Un rollback que rompe es lo peor.
  4. Bind-mount anidado `agora-auth` (un fichero dentro de un mount idmapped) es frágil.
- **Causa raíz de fondo**: validado contra install FRESCO v0.2.0 en VM, NO contra la migración de un
  container EXISTENTE en marcha (lo que es prod) → los bugs in-place no se cazaron.
- **Reproducción**: replicar el estado v1 CRUDO de un container EN MARCHA en la VM y correr el script.
- **Workaround (recuperación aplicada)**: ver post-mortem en `changelog.md`.
- **Reproducción confirmada (2026-05-31)**: la pieza que faltaba era el device `agora-auth`
  (file-mount `~/.laia/auth.json` → `/opt/agora/data/auth.json`) que el snapshot pre-fatal SÍ
  tenía — el briefing lo había omitido (describía el estado post-recuperación). Con él, el bench en
  la VM reproduce el "verde falso" del bug #2 (el backend sirve un auth.json vacío tras el swap).
- **Owner**: claude opus 4.8.
- **Estado**: **resolved (2026-05-31)** — los 4 bugs arreglados en `migrate-v1-to-v2.sh`
  (converge al modelo file-mount de `rebuild-3`, modifica el device IN PLACE, verify valida el
  CONTENIDO del auth, auto-rollback captura el owner en vivo y falla-closed). Cubierto por
  `tests/integration/test_cutover_migration.sh` (19/19) + ciclo verde contra la réplica del
  snapshot real de prod (14/14). Detalle en `changelog.md` (2026-05-31) y el PRD reescrito
  `workflow/plans/2026-05-31-prod-cutover-v1v2-redesigned.md`.
  ⚠️ La **ejecución del cutover en prod** sigue siendo un paso HITL de Jorge (no ejecutado).

## backend-tests-hardcodean-ruta-de-plugins-del-host-de-dev (resolved)

- **Descubierto**: 2026-05-30 por claude opus 4.8 (Coder-Opus) durante B1 (CI greenfield).
- **Resuelto**: 2026-05-30 en este PR (branch `wip/claude/robustez-ops`).
- **Síntoma**: 6 tests del backend (`test_agent_delegation`, `test_agent_self_edit`,
  `test_agent_learnings`, `test_scheduler`, `test_auto_import`, `test_secondary_workspaces`)
  cargaban su plugin desde la ruta absoluta hardcodeada del host de dev
  (`.../LAIA/.laia-core/plugins/<X>/__init__.py`). En CI (checkout limpio) →
  `FileNotFoundError`. En local "pasaban" porque esa ruta existe en la máquina de Jorge.
- **Causa raíz**: `.laia-core/` está en `.gitignore` (lo provee la instalación de laia-core,
  no el repo) → esos plugins **no están en el checkout**. El path absoluto enmascaraba la
  dependencia. (Es justo lo que detecta `scripts/check-hardcoded-paths.py`.)
- **Fix**: nuevo helper `services/agora-backend/tests/_laia_core.py` que resuelve el plugin
  vía `LAIA_ROOT`/raíz del repo y hace `pytest.skip` limpio si no está presente. Los 6 tests
  lo usan. Resultado: corren en host/VM con laia-core (63 passed), skipean en CI (38 skip).
- **Owner**: Coder-Opus.
- **Estado**: resolved.

## ensure-disk-free-gb-nonexistent-path-reads-0 (resolved)

- **Descubierto**: 2026-05-30 por claude opus 4.8 (Coder-Opus) durante B1 (CI greenfield).
- **Resuelto**: 2026-05-31 por Codex en commit `d67557e3`.
- **Síntoma**: en CI (runner con sudo passwordless), `test_clone_hardening.sh` falla con
  `✗ Not enough disk space at /tmp/laia-marker-test.XXX/sudo-clone/dest/opt: 0 GB free,
  5 GB required`, aunque el runner tiene >10 GB libres.
- **Causa raíz sospechada**: `infra/installer/lib/system.sh:82` →
  `df -BG --output=avail "$path" 2>/dev/null | tail -1 | tr -dc '0-9'`. Si `$path` aún
  **no existe** (aquí el override `LAIA_INSTALL_ROOT_OVERRIDE=.../dest/opt` que el install
  todavía no creó), `df` falla, el `2>/dev/null` se traga el error y `tr` deja cadena vacía
  → se interpreta como **0 GB** → `die`. Debería medir el ancestro existente más cercano
  (o crear el dir antes de medir).
- **Reproducción**: en un host con sudo passwordless, `bash tests/installer/test_clone_hardening.sh`
  (entra en el bloque `sudo -n true`). En un host sin sudo passwordless el bloque se salta y
  no se ve.
- **Fix**: `ensure_disk_free_gb` mide el ancestro existente más cercano del path antes de
  llamar a `df`; el preflight de install ya no interpreta una ruta override aún no creada
  como 0 GB libres. `test_clone_hardening.sh` añade regresión sin sudo para ese caso y
  vuelve a correr en CI.
- **Owner**: Codex.
- **Estado**: resolved.

## installer-tests-readme-overclaims-host-free (resolved)

- **Descubierto**: 2026-05-30 por claude opus 4.8 (Coder-Opus) durante B1 (CI greenfield).
- **Resuelto**: 2026-05-31 por Codex en commit `d67557e3`.
- **Síntoma**: `tests/installer/README.md` afirma que **todos** los `test_*.sh` corren "without
  root, without LXD, without GitHub". En un runner limpio fallan 2: `test_install_native_layout.sh`
  (su `laia auth` necesita las deps de laia-core: `python-dotenv`, `pyyaml`, … que en un host real
  trae `/opt/laia/.laia-core/venv`) y `test_clone_hardening.sh` (ver problema anterior).
- **Causa raíz sospechada**: docu desactualizada / falso positivo enmascarado por artefactos del
  host de dev (`$HOME/LAIA`, `/opt/laia/.laia-core/venv`). Solo el CI limpio lo destapa.
- **Reproducción**: correr esos 2 tests con `env -i` (sin `/opt/laia` ni `$HOME/LAIA`).
- **Fix**: `tests/installer/README.md` ahora distingue la suite shell/stubs general de los bloques
  host-specific guardados: `test_clone_hardening.sh` ejecuta sudo sólo si está disponible y ya
  no está excluido en CI; `test_install_native_layout.sh` queda documentado como el único skip
  por depender de deps de laia-core en un host/VM real.
- **Owner**: Codex.
- **Estado**: resolved.

## agora-backend-test-pool-contamination (resolved)

- **Descubierto**: 2026-05-28 por claude opus 4.7 durante PR-2 de atlas adoption.
- **Resuelto**: 2026-05-29 en commit `9f7f7887`.
- **Síntoma**: `tests/test_laia_coordinator.py::test_laia_chat_endpoint_employee_uses_base_toolset`
  y `test_laia_chat_endpoint_admin_streams` fallan SOLO cuando la suite completa
  corre desde el principio, con: `worker crashed: test_session_id_defaults_to_user_scoped.<locals>._capture()
  got an unexpected keyword argument 'mode'`.
- **Causa raíz sospechada**: `tests/test_chat_engine.py::test_session_id_defaults_to_user_scoped`
  (línea 303) instala `pool.get_or_create = _capture` vía `chat_engine.set_pool(pool)`.
  El pool es un global mutado que persiste entre tests; cuando `test_laia_coordinator`
  corre después, invoca `pool.get_or_create(..., mode=...)` y el mock obsoleto crashea.
- **Reproducción**:
  ```bash
  cd services/agora-backend
  .venv/bin/python -m pytest tests/ -q -x  # falla
  .venv/bin/python -m pytest tests/test_laia_coordinator.py -q  # solo: pasa
  ```
- **Workaround**: ejecutar con `--deselect` los 2 tests o aislar `test_chat_engine`
  con `pytest --forked` (requiere pytest-forked).
- **Fix propuesto**: aislar el `pool` global entre tests (reset/teardown del fixture que lo
  muta, o `set_pool` con cleanup) para que el mock obsoleto no se filtre. Causa raíz ya
  identificada → **ready-for-agent**.
- **Owner**: Coder-Codex.
- **Estado**: resolved.
- **Plan**: slice **A2** de la estabilización — ver
  [`plans/estabilizacion/slices.md`](plans/estabilizacion/slices.md). Consolida también
  `backend-suite-laia-chat-test-leak` (mismo bug).

---

## laia-core-cron-package-gitignored-lost-in-migration (in-progress)

- **Descubierto**: 2026-05-27 por claude opus 4.7.
- **Síntoma**: `laia chat`/one-shot crashea con `ModuleNotFoundError: No module named
  'cron'` (`cli.py:662`, `laia_cli/cron.py:194`). El dispatcher bash y `laia --help`
  funcionan; solo cae el CLI Python del agente.
- **Causa raíz**: `.laia-core/cron/` (`__init__.py`, `jobs.py`, `scheduler.py`) está
  gitignored (`.gitignore:31 cron/` + `:61 .laia-core/`), nunca se commiteó, y la
  migración `laia-hermes`→`laia-arch` (rsync/git respetando `.gitignore`) lo perdió.
  Mismo mecanismo borró 10 entradas más de `.laia-core/` (SOUL.md, skills/, scripts/,
  bin/, ai-agents.json, packaging/, tinker-atropos/, flake.lock, uv.lock).
- **Reproducción**: `cd /tmp && laia -z "hola"` con el árbol pre-recuperación.
- **Workaround**: recuperado de la VM original vía `rsync --ignore-existing`; en `/opt`
  un `.pth` (`zz_laia_core_root.pth`) añade `.laia-core` al `sys.path`. Validado: el
  agente ya pasa el import de `cron`.
- **Owner**: Jorge / claude.
- **Estado**: in-progress — falta `git add -f` para durabilidad y que `laia release`
  incluya `cron/` nativamente (no vía `.pth`).

## installer-shell-rc-bashrc-root-owned (resolved en código, sin commit)

- **Descubierto**: 2026-05-27 por claude opus 4.7 (reporte de otra sesión).
- **Síntoma**: tras `install` con sudo, `~/.bashrc` queda `root:root 0600`; el usuario
  no puede leerlo y la siguiente shell perdería el `.bashrc`. `✗ Failed at shell_rc.sh:46`.
- **Causa raíz**: `shell_rc_apply`/`_remove` usan `mktemp`+`mv`; `mv` hereda metadata del
  tmp (root:root 0600 bajo sudo) y no restauraba propiedad/modo.
- **Reproducción**: correr el instalador vía `sudo -E` y mirar `ls -l ~/.bashrc`.
- **Workaround**: `sudo chown laia-arch:laia-arch ~/.bashrc && sudo chmod 644 ~/.bashrc`.
- **Owner**: claude.
- **Estado**: resolved en código (`shell_rc.sh` helper `shell_rc_restore_meta` + Test 7,
  suite 19/19) — **pendiente de commit**.

## installer-clone-leaves-root-owned-home-artifacts (resolved)

- **Descubierto**: 2026-05-27 por claude opus 4.7.
- **Síntoma**: el cloner deja en el HOME del usuario `~/.laia-clone-stage/` y
  `~/LAIA-ARCH/.clone-state/*.done` como `root:root` (rsync bajo sudo). El staging es
  basura; los markers `--resume` rotos impedirían re-ejecutar el clone como usuario.
- **Causa raíz**: `clone.sh` (`clone_phase_mark_done`, dirs `.laia-clone-stage`) crea
  estos paths bajo sudo y no hace `chown`/cleanup al cerrar. Mismo patrón que el bug de
  `.bashrc`.
- **Workaround**: `sudo rm -rf ~/.laia-clone-stage ~/LAIA-ARCH/.clone-state`.
- **Owner**: Coder-Codex.
- **Estado**: resolved.
- **Resuelto**: 2026-05-29 en commit `f56fb832`.

## backend-suite-laia-chat-test-leak (resolved · duplicate)

> **Duplicado de `agora-backend-test-pool-contamination`** (mismo síntoma y causa raíz, mejor
> diagnosticada allí). Se trata como **slice A2** del plan de estabilización. No trabajar este
> por separado; ver la entrada consolidada.

- **Descubierto**: 2026-05-25 por codex durante `tests/run_integrity.py --tier unit`
  fuera del sandbox.
- **Síntoma**: la suite completa de `services/agora-backend/tests/` falla en
  `test_laia_chat_endpoint_employee_uses_base_toolset` y
  `test_laia_chat_endpoint_admin_streams`. El SSE devuelve
  `worker crashed: test_session_id_defaults_to_user_scoped.<locals>._capture()
  got an unexpected keyword argument 'mode'`.
- **Causa raíz sospechada**: fuga de monkeypatch/callback entre tests del chat
  engine y tests de LAIA coordinator, o singleton de AgentPool/chat worker no
  reseteado entre casos.
- **Reproducción**:
  `cd services/agora-backend && .venv/bin/python -m pytest tests/ -q`.
- **Workaround**: ejecutar los ficheros afectados de forma aislada para diagnosis;
  la suite completa sigue siendo roja hasta resetear el estado compartido.
- **Owner**: Coder-Codex (vía la entrada consolidada).
- **Estado**: resolved — mismo fix que `agora-backend-test-pool-contamination`
  (slice A2, PR #14, commit `9f7f7887`, mergeado el 2026-05-29).

## install-wizard-ui-tests-stale (resolved)

- **Descubierto**: 2026-05-25 por codex durante la implementación del runner de
  integridad.
- **Síntoma**: `tests/wizard/test_ui_*.py` y
  `tests/installer/test_wizard_yesno_input.sh` fallan al importar
  `laia_cli.install_wizard.ui`.
- **Causa raíz**: los tests unitarios atacaban internals (`_ask_yesno`,
  `_NavigationSentinel`, `Prompt.ask`) de la capa rich `install_wizard.ui`
  que se borró en Fase 4 del remake del wizard (commit del flip a Textual).
  La cobertura equivalente vive ahora en `.laia-core/tests/test_tui_app.py`
  contra el FormScreen Textual.
- **Resuelto**: 2026-05-25 — borrados los 4 archivos de test obsoletos
  (`tests/installer/test_wizard_yesno_input.sh`,
  `tests/wizard/test_ui_components.py`, `tests/wizard/test_ui_render.py`,
  `tests/wizard/test_ui_progress.py`) junto con la capa rich que testeaban.
- **Verificación**: `tests/installer/run_all.sh` 29/29 verde tras la
  limpieza; `pytest tests/wizard/` baja a 159/160 (la failure restante
  `test_clone_security::test_clone_execute_aborts_on_ssh_setup_mode` es
  pre-existente y testea comportamiento intencional que NO es parte del
  remake — ver entrada propia abajo).

## clone-ssh-setup-mode-continues (open)

- **Descubierto**: 2026-05-25 por claude-code al correr `pytest tests/wizard/`
  durante Fase 4. La falla es pre-existente; el test viene del commit
  `5e786ac5` (codex añadiendo asserts de seguridad).
- **Síntoma**: `tests/wizard/test_clone_security.py::test_clone_execute_aborts_on_ssh_setup_mode`
  asserta que cuando `ssh_auth_mode='setup'` el flow `execute()` debe yieldar
  `step_error` ANTES de invocar `bin/laia-clone`. El código actual hace el
  setup SSH y luego sí continúa al clone, contradiciendo el test.
- **Causa raíz sospechada**: divergencia entre intent (la sesión de "sólo
  setup" debería ser una pasada separada, no fold-into-clone) y la
  implementación heredada en `flows/clone.py:402-408` que continúa.
- **Reproducción**: `cd .laia-core && PYTHONPATH=. venv/bin/python -m pytest
  ../tests/wizard/test_clone_security.py -k aborts_on_ssh_setup -o addopts=""`.
- **Workaround**: usar `ssh_auth_mode='existing'` después del setup manual,
  o no marcar la opción setup si quieres clonar en la misma ejecución.
- **Owner**: sin asignar — decisión de Jorge sobre si la semántica correcta
  es "abort después de setup" o "encadenar setup + clone".
- **Estado**: open.

## wizard-clone-tty (resolved)

- **Descubierto**: 2026-05-25 por claude-code durante prueba en VM Ubuntu 26.04 arm64.
- **Síntoma**: `infra/installer/lib/clone.sh: line 225: /dev/tty: No such device or address`
  al ejecutar el wizard vía `curl | sudo bash` en modo clone, durante el preflight
  cuando el SSH key auth falla y se intenta SSH password.
- **Causa raíz**: `clone_prompt_ssh_password()` en `clone.sh` leía de `/dev/tty`
  directamente como fallback cuando key auth fallaba, ignorando el mecanismo
  `--ssh-pass-file` que Python ya implementaba correctamente vía
  `_secret_to_tempfile` + `bin/laia-clone::resolve_ssh_pass_file`. En `curl|sudo bash`
  bajo subprocess, ese `/dev/tty` no estaba disponible aunque el wizard Python tuviera
  su propio reattach.
- **Resuelto**: 2026-05-25 — borrada la función `clone_prompt_ssh_password()` y el
  fallback que la llamaba. Cuando key auth falla sin `--ssh-pass-file`, `clone.sh`
  ahora `die`'s con código 3 y mensaje claro apuntando al wizard para reintentar
  con password mode. Bash nunca más promptea — todo secreto entra por el path
  `--ssh-pass-file` (Python escribe tempfile 0600, bash lo lee y lo unlinkea).
  Además, el reattach `/dev/tty` redundante en `bin/laia-wizard:86-89` se eliminó;
  el único reattach vive en `install.sh` (curl|bash hand-off) y la red de seguridad
  `_reattach_tty()` en `__main__.py`. Commits asociados en rama `feat/installer-wizard`.
- **Verificación**: `tests/installer/test_clone_ssh_no_password_fallback.sh` —
  stubea ssh para que falle, invoca `bin/laia-clone --source user@unreachable.invalid
  --yes` sin `--ssh-pass-file`, asserts: exit 3, mensaje claro, sin mención a
  `/dev/tty` en la salida. La suite completa `tests/installer/run_all.sh` pasa.

## env-laia-home-stale (resolved)

- **Descubierto**: 2026-05-25 por claude-code al lanzar `scripts/sync-workspace-markdown.py`.
- **Síntoma**: scripts que leen `LAIA_HOME` fallan apuntando a
  `/home/laia-hermes/laia-partial-install.02XwlG/LAIA-ARCH` en vez de a `~/.laia`.
  Error visible: `ERROR: /home/laia-hermes/laia-partial-install.02XwlG/LAIA-ARCH/workspaces no existe`.
- **Causa raíz**: bloque `# >>> laia >>> / <<< laia <<<` en `~/.bashrc` (líneas
  157-160) añadido por `laia-install` durante un clone interrumpido, que sobreescribía
  el export bueno de la línea 154.
- **Reproducción**: `echo $LAIA_HOME` en una shell nueva → devolvía la ruta fantasma.
- **Resuelto**: 2026-05-25 — bloque retirado de `~/.bashrc`, sustituido por un comentario
  que apunta a esta entrada. La línea 154 (`export LAIA_HOME="$HOME/.laia"`) sigue siendo
  la única autoritativa.
- **Verificación**: shell nueva → `echo $LAIA_HOME` devuelve `/home/laia-hermes/.laia`.
  Systemd unit `laia-docs-sync.service` declara `Environment=LAIA_HOME=/home/laia-hermes/.laia`
  explícitamente como cinturón y tirantes.
- **Pendiente relacionado**: la carpeta `~/laia-partial-install.02XwlG/` que motivó el
  bloque sigue existiendo en el home. Decisión sobre borrarla, abierta — ver changelog.

## wizard-prompts-sin-contexto (resolved)

- **Descubierto**: 2026-05-25 por Jorge durante prueba del wizard.
- **Síntoma**: prompts del wizard con defaults raros o sin default sin explicación
  suficiente. Ejemplos:
  - "Límite de ancho de banda rsync (opcional)" con default `50M` — no se explica qué
    pasa si lo dejas vacío vs si lo cambias.
  - "¿Mantener sesión de admin del viejo?" sin default y sin pista de qué teclear.
  - "¿Modo --resume (saltar fases ya completadas)?" sin default visible.
- **Causa raíz**: doble — la prosa de `help_text` era escasa, y la UI legacy
  `rich.prompt` no renderizaba `help_text` de manera prominente aunque
  estuviera. La data estaba ahí; la presentación no la mostraba.
- **Resuelto**: 2026-05-25 — combinación de cambios en Fase 3 y Fase 4 del
  remake del wizard:
  - Fase 3 part 2 (commit `b31287b8`): `help_text` reescrito para los 3
    campos en `flows/clone.py::_OPTIONS_SCREEN`. De 50-100 chars a 200-330
    chars cada uno con guía explícita: bwlimit explica WAN vs LAN y qué
    pasa con vacío; keep_session deja claro que `No` es recomendado y
    describe el flujo de credenciales; resume tiene "primera vez? `No`"
    up-front.
  - Fase 4 part 1 (commit `58b6e88e`): la UI Textual es default; renderiza
    `help_text` inline bajo el label de cada campo con estilo `field-help`
    (color muted, padding consistente). La UI rich legacy se borró.
- **Verificación**: cualquier `Field` con `help_text` ahora muestra ese texto
  bajo el input en la UI Textual. Probar con `laia wizard --mode clone` y
  ver las pantallas de opciones.
- **Workaround**: dejar todo en default y rezar.
- **Owner**: sin asignar.
- **Estado**: open.
