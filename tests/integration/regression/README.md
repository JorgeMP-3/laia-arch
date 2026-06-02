# Regresión de bugs (Track T · T5)

Por cada bug `resolved` de `~/laia-developers/workflow-main/problems.md` debe existir **un test que lo
fije** (que no vuelva nunca). Esta tabla es la matriz de cobertura: ningún bug
resuelto queda sin guard, y los gaps (bugs aún abiertos, o cubiertos fuera de
esta carpeta) están **documentados, no silenciados**.

| Bug resuelto (`problems.md`) | Regresión | Dónde |
|---|---|---|
| `migrate-v1-to-v2-prod-outage` | `integration/data/test_migrate_v1_to_v2_prod_outage_regression.sh` (auth mount + acceso del user agora + `/api/health`) y `test_cutover_migration.sh` (ciclo migrate/rollback, 19/19) | VM (`host`/`vm`) |
| `backend-tests-hardcodean-ruta-de-plugins-del-host-de-dev` | `regression/test_backend_no_hardcoded_plugin_paths.sh` (guard: ningún test del backend hardcodea `/home/.../.laia-core`) | **CI** (`ci`) |
| `ensure-disk-free-gb-nonexistent-path-reads-0` | `tests/installer/test_clone_hardening.sh` (preflight con install-root inexistente, sin sudo) | CI (suite installer) |
| `installer-tests-readme-overclaims-host-free` | `tests/installer/run_all.sh` corre los tests afectados en CI con la matriz `INSTALLER_SKIP` documentada | CI (suite installer) |
| `agora-backend-test-pool-contamination` (+ duplicado `backend-suite-laia-chat-test-leak`) | la suite completa `services/agora-backend/tests/` corre **en orden** en CI (py3.11 + py3.14); el bug era una fuga de estado entre tests que solo aparece con la suite entera | CI (job `backend`) |
| `installer-clone-leaves-root-owned-home-artifacts` | `tests/installer/test_clone_hardening.sh` | CI (suite installer) |
| `wizard-clone-tty` | `tests/installer/test_clone_ssh_no_password_fallback.sh` | CI (suite installer) |
| `installer-shell-rc-bashrc-root-owned` | `tests/installer/test_shell_rc.sh` (Test 7, `shell_rc_restore_meta`) — **resuelto en código, pendiente de commit** según `problems.md` | CI cuando se commitee |
| `env-laia-home-stale` | sin guard automatizable (era un bloque obsoleto en `~/.bashrc` de una máquina concreta; no reproducible en repo). Documentado aquí como **no automatizable**. | — |
| `install-wizard-ui-tests-stale` | resuelto **borrando** los 4 tests obsoletos; la cobertura equivalente vive en `.laia-core/tests/test_tui_app.py`. Sin regresión propia (no hay código que pueda "volver"). | — |

## Bugs ABIERTOS con guard listo (vira a verde al arreglarse)

| Bug abierto (`problems.md`) | Guard | Comportamiento hoy |
|---|---|---|
| `backup-timer-runs-as-laia-arch-cannot-read-agora` | `regression/test_backup_service_runs_as_root.sh` | **SKIP (exit 77)** con motivo loud citando el bug. Vira a PASS cuando la plantilla use `User=root`. Fix = código de producción (Codex/Lead). |

Los SKIP no son silenciosos: el runner los reporta en el JSON con su `reason`, y
el job `skip-matrix` del CI los hace visibles en cada PR.
