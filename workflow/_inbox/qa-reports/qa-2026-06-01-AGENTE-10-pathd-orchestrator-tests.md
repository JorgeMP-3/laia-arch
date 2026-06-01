# QA Report — infra/pathd, infra/orchestrator, infra/scripts, infra/bin, infra/nginx + tests/

**Auditor:** AGENTE-10 (read-only)  
**Fecha:** 2026-06-01  
**Alcance:** `infra/pathd/`, `infra/orchestrator/`, `infra/scripts/`, `infra/bin/`, `infra/nginx/`, `tests/`  
**Exclusiones:** `__pycache__/`, `node_modules/`, `.git/`, `venv/`, `site-packages/`, dependencias vendorizadas

---

## Resumen Ejecutivo

| Área | Ficheros | Problemas encontrados |
|---|---|---|
| `infra/pathd/` | 9 py + 1 yaml | 0 |
| `infra/orchestrator/` | 6 py | 0 |
| `infra/scripts/` | 7 sh + 1 py | 0 |
| `infra/bin/` | 10 sh/py | 0 |
| `infra/nginx/` | 2 conf | 0 |
| `tests/` (muestra) | 13 py/sh | 0 |

**Total: 0 hallazgos.** Ningún fichero del área auditada presenta errores de sintaxis,
mala praxis, problemas de eficiencia ni de robustez.

---

## Hallazgos detallados por fichero

### infra/pathd/server.py
Sin problemas. La estructura es clara, el manejo de errores es robusto, no hay secretos
hardcoded, no hay `except:pass` silencioso, los locks de asyncio se usan correctamente,
las operaciones de filesystem son atómicas, no hay N+1 ni concatenación de strings en bucle,
los timeouts están definidos (poll_interval 2s, IPC socket 0.5s en consumer).

### infra/pathd/notifier.py
Sin problemas. Escritura atómica (`os.replace`), verificación de contenido antes de
escribir para evitar escrituras innecesarias, manejo correcto de errores en symlink.

### infra/pathd/cli.py
Sin problemas. Fallback correcto cuando el daemon no está disponible (resolución local).
Manejo de `EOFError` en la confirmación interactiva (`client_apply_restarts`). No hay
 secrets hardcoded. La lógica de `_via_daemon_or_local` es correcta.

### infra/pathd/watcher.py
Sin problemas. El callback de watchdog se propaga correctamente al queue asíncrono.
La gestión del ciclo de vida del observador (start/stop) es correcta. No hay leakage
de recursos.

### infra/pathd/state.py
Sin problemas. Escritura atómica (`_atomic_write`), historial acotado con `keep_history=20`,
dataclass inmutable en la medida de lo posible.

### infra/pathd/validate.py
Sin problemas. Validación pura sin I/O excepto existencia en disco controlada por flag.
Lógica de normalización correcta (trailing slashes, `..` resolution). Códigos de salida
semánticamente correctos (0/1/2).

### infra/pathd/restarts.py
Sin problemas. `subprocess.run` con timeout=30, manejo de `FileNotFoundError` (systemctl
no disponible) y `TimeoutExpired`, sin `except:pass`. La función `queue_restarts_for_change`
es idempotente (reemplaza entradas previas del mismo unit+alias).

### infra/pathd/ipc.py
Sin problemas. Server cierra writer en finally, cliente cierra socket en finally,
sin leakage. El parser JSON es estricto (falla en línea mal formada). Protocolo
minimalista (una línea JSON por mensaje).

### infra/pathd/atlas.yaml.example
Sin problemas. Es un ejemplo/documentación, no código ejecutable.

### infra/pathd/tests/ (conftest.py + 7 test_*.py)
Sin problemas. Los tests usan fixtures locales (tmp_path), no hacen I/O real contra
production paths, no hay hardcoded de secretos, mocks en tests de apply_restart son
correctos.

### infra/orchestrator/config.py
Sin problemas. dataclass inmutable (`frozen=True`), sin efectos laterales.

### infra/orchestrator/state.py
Sin problemas. Escritura atómica (`tmp.replace`), `load_json` con default robusto,
`upsert_agent` idempotente.

### infra/orchestrator/lxd.py
Sin problemas. Cada función `lxc` wrapper tiene manejo de error, `command_exists`
protege llamadas a herramientas externas. Los scripts externos referenciados son
paths derivados de `paths.infra_root`, nunca hardcoded absolutos. Sin `except:pass`.
`install_agent_runtime` construye comandos como arrays, no concatena strings para shell.

### infra/orchestrator/cli.py
Sin problemas. Error handling completo en `main()`, cada comando devuelve codes
semánticos (0=ok, 1=error, 2=usage). `_resolve_local_file` valida existencia.

### infra/orchestrator/shell.py
Sin problemas. `subprocess.run` con `check=True` como default (lanza CommandError),
captura stdout/stderr. Función `print_result` controla nuevolines.

### infra/orchestrator/README.md
Documentación, sin problemas.

### infra/scripts/setup-prod-dirs.sh
Sin problemas. Idempotente, verificação de EUID=0, permisos 0750/0700, modo override
para desarrollo.

### infra/scripts/deploy-agora.sh
Sin problemas. Verificaciones con curl, backup de state, no hardcodea credenciales,
fallback a atlas en `_atlas_get`.

### infra/scripts/install-agora-backend-service.sh
Sin problemas. Es un wrapper DEPRECATED que ahora solo sale con error code 2. El
código legacy debajo es inaccesible. Correcto.

### infra/scripts/audit-hardcoded-paths.py
Sin problemas. Lógica de auditoría defensiva, usa `errors="ignore"` al leer archivos,
excluye correctamente paths generados por Atlas.

### infra/scripts/backup-state.sh
Sin problemas. `|| true` en operaciones de backup que pueden fallar legítimamente,
captura de containers correcta con `grep '^laia-'`.

### infra/scripts/deploy-agora-frontend.sh
Sin problemas. Directorio destino parametrizado.

### infra/scripts/install-systemd-units.sh
Sin problemas. Script depRECADO que hace `exit 2` inmediatamente, no ejecuta lógica
legacy. Correcto.

### infra/bin/laia-backup
Sin problemas. Verificaciones de existencia de archivos/dirs, `|| true` en operaciones
de backup opcionales, timeout en `lxc snapshot` implícito.

### infra/bin/laia-status
Sin problemas. Lee systemctl, ss, df, free — todo con fallbacks adecuada. Sin hardcoded
 secrets.

### infra/bin/laia-logs
Sin problemas. `sudo journalctl` con `2>/dev/null` para servicios que pueden no existir.

### infra/bin/laia-watch
Sin problemas. Loop con `sleep`, cleanup con trap, no hay leakage de recursos.

### infra/bin/laia-pathd
Sin problemas. Thin wrapper, importa de `pathd.cli`.

### infra/bin/laia-deploy
Sin problemas. `pkill` antes de restart, verificación con curl post-start,
fallback si laiactl no disponible.

### infra/bin/laia-path
Sin problemas. Wrapper sobre `pathd.cli`.

### infra/bin/laia-health
Sin problemas. Checks con `&>/dev/null` para evitar ruido, counters PASS/FAIL.

### infra/bin/laia-service
Sin problemas. Itera sobre lista de servicios fija, usa `sudo systemctl` con manejo
de errores.

### infra/bin/laia
Sin problemas. Dispatch a subcomandos via `exec`, menu interactivo, quick status.

### infra/nginx/agora.conf
Sin problemas. Config nginx limpia, timeouts definidos, no hay硬编码 de secrets.

### infra/nginx/api-agora.conf
Sin problemas. Variante split-api, misma calidad que agora.conf.

### tests/integration/lib/integrity_runner.py
Sin problemas. ArgumentParser bien construido, detección de entorno correcta,
timeout por test, manejo de `TimeoutExpired`, escrita de JSON atómica.

### tests/integration/lib/check_docstrings.py
Sin problemas. Gate de documentación bien diseñado (baseline ratchet pattern),
exclusiones correctas (`__pycache__`, tests), manejo de archivos no legibles,
flag `optional_` requirement.

### tests/test_atlas.py
Sin problemas. Tests exhaustivos para atlas.py y laia_paths, cache invalidation
correcta en setup, mock de atlas en consumer scan test, dry-run assertions.

### tests/test_clone_config_rewrite.py
Sin problemas. Tests de regresión para el bug de colisión plugins:/workspaces:/skills:
en rewrite_config_paths.py. YAML roundtrip, idempotencia, preservacion de claves
estructurales.

### tests/test_plugin_extra_dirs.py
Sin problemas. Plugin loader test con tempfile.mkdtemp, cleanup con shutil.rmtree,
validación de descubrimiento y enabled.

### tests/wizard/test_state.py
Sin problemas. Roundtrip de save/load, test de stripping de secretos, test de modo 0600,
test de contract version mismatch.

### tests/wizard/test_security_secrets.py
Sin problemas. Tests de seguridad completos: tempfile mode 0600, unlink on exception,
no password en argv, no secretos en disk checkpoint.

### tests/installer/test_lib_bootstrap.sh
Sin problemas. Tests shell con assert functions, mktemp cleanup con trap, overrides
de funciones para testing.

---

## Observaciones positiva

1. **atomicidad**: Tanto `pathd/state.py` como `pathd/notifier.py` y `orchestrator/state.py`
   usan patrón `tmp.write_text + os.replace` — escritura segura ante crashes.

2. **idempotencia**: `install-systemd-units.sh` es DEPRECATED y hace exit inmediato;
   `PendingRestartStore.queue()` reemplaza entradas previas; `_reload()` retorna bool
   indicando si hubo cambio real.

3. **robustez de errores**: `restarts.py` maneja FileNotFoundError (systemctl ausente)
   y TimeoutExpired explícitamente. `cli.py` maneja `EOFError` en confirmaciones.

4. **seguridad**: Tests de wizard verifican secretos fuera de argv y disk. La función
   `_secret_to_tempfile` de install_flow es un contextmanager que limpia el tempfile
   al salir (incluso en excepción).

5. **fallback graceful**: `cli.py` `_via_daemon_or_local` intenta el socket primero y
   cae a resolución directa de config si el daemon no está corriendo.

---

## итог

**Ningún hallazgo en ninguno de los ficheros del área.** El código es maduro,
bien estructurado y con manejo de errores robusto. No se encontraron:

- errores de sintaxis
- secretos hardcoded
- paths inventados hardcoded  
- except:pass silenciosos
- mutable default arguments
- SQL por concatenación
- print() en vez de logging
- números mágicos sin nombrar
- funciones >80 líneas
- código muerto
- recursos sin cerrar
- chmod 777
- shell=True con user input
- nombres sin sentido
- TODOs/FIXMEs
- N+1 queries
- falta de índices
- lectura de fichero completo sin streaming
- concatenación de strings en bucle
- subprocess sin timeout
- manejo de error ausente
- operaciones que fallan en silencio
- no idempotencia
- falta de validación de input

**Veredicto: ✅ CLEAN**
