# QA Report — 2026-06-01 — AGENTE-C
**Auditoría READ-ONLY** · Áreas: `infra/` · `scripts/` · `infra/bin/`
**Excluidos:** `__pycache__`, `.git`, `venv`, `site-packages`, `node_modules`, `*.min.js`, `RELEASE*.md`

---

## RESUMEN DE HALLAZGOS

| severidad | count |
|---|---|
| blocker | 12 |
| major | 7 |
| minor | 6 |
| nit | 3 |

---

## BLOQUEADORES

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `infra/bin/laia-watch` | BASH | blocker | Falta shebang `#!` y `set -euo pipefail`. El script empieza directamente con comentarios. | Sin shebang el kernel no lo exec como script. Sin `set -euo pipefail` los errores silencian y variables no declaradas se expanden como strings vacíos. | Añadir `#!/usr/bin/env bash` al inicio y `set -euo pipefail` en línea 2. |
| `infra/bin/laia` | BASH | blocker | No tiene `set -euo pipefail`. Líneas 14-18 usan `exec` dentro de `[[ ]]` que podría fallar sin mensaje si `$cmd` es vacío. | Si `laia-$1` no existe, `exec "$cmd"` con cmd vacío поведёт silencio; `set -e` permitiría捕获 el fallo. | Añadir `set -euo pipefail` tras shebang. Verificar que el patrón `[[ -x "$cmd" ]]` es seguro. |
| `infra/dev/add-test-user.sh:140-146` | MALAPRACTICS | blocker | Credentials hardcoded: usuario admin `"jorge"` y password `"dev-admin"` inline en curl. | Credenciales de seed visibles en script plain text. Si el repo es público o compartido, las credenciales quedan expuestas. No hay forma de sobreescribir con variable de entorno. | Exportar `AGORA_ADMIN_USER` y `AGORA_ADMIN_PASSWORD` del entorno con defaults seguros; nunca hardcodear strings en curl. |
| `infra/dev/chat-with-agent.sh:195-196` | MALAPRACTICS | blocker | Credenciales hardcoded: `"jorge","password":"dev-admin"` en login. También línea 228 `"password":"chattest"` en user creation. | Mismo problema: seed admin + test user password en texto plano. Cualquiera con acceso al repo las ve. | Usar variables de entorno `ADMIN_USER` / `ADMIN_PASSWORD` con defaults solo para dev local. |
| `infra/dev/smoke-test.sh:33-34` | MALAPRACTICS | blocker | `ADMIN_USER="${ADMIN_USER:-jorge}"` y `ADMIN_PASSWORD="${ADMIN_PASSWORD:-dev-admin}"` — defaults visibles inline. | Credenciales de seed accesibles. El override desde archivo `LAIA_HOME/.admin-credentials` es buena práctica, pero los defaults inline son el riesgo real. | Los defaults deben ser valores dummy o vacío; el override desde archivo ya existe como fallback robusto. |
| `scripts/ai-orchestrator.py:34-67` | MALAPRACTICS | blocker | `DEFAULT_CONFIG` con `command` hardcoded incluyendo paths del sistema como `/opt/laia/agent/src`, tokens, y prompts con `claude -p "$(cat "$1")" --output-format json`. | Tokens y paths de producción hardcoded. `claude -p` en `--output-format json` puede estar obsoleto. Paths como `/opt/laia/agent/src` son in-container y no existen en host. | Externalizar a `ai-agents.json` en `LAIA_HOME/`; nunca en código fuente. Verificar que los comandos existan antes de usar. |
| `scripts/hermes-backup.py:22` | MALAPRACTICS | blocker | `DEFAULT_DEST = Path("/Volumes/PortableSSD/HermesBackups")` — path macOS específico hardcoded. | Si se ejecuta en Linux (el servidor de producción), este path no existe y el backup falla sin mensaje claro. El usuario no tiene forma de sobreescribirlo si no lee el código. | Usar variable de entorno `HERMES_BACKUP_DEST` con fallback a un valor multi-plataforma (ej. `LAIA_HOME/backups`). |
| `scripts/check-hardcoded-paths.py:48` | MALAPRACTICS | blocker | `WORKSPACE_NAME_RE` incluye nombres de workspaces (`arete`, `doyouwin`, `pixelcore`, `laia-arch`, `servidor-jmp`, `demo-completo`) como literals en el regex. | Detecta estos nombres como "hardcoded workspace names" — pero el propio checker los lista explícitamente, lo que significa que el sistema los considera datos operativos. Si un workspace se renombra, el regex queda obsoleto. Más importante: es una lista de workspaces reales de producción embebida en un script de auditoría. | Esta lista debería living en un archivo de config externo o extraerse del registry de workspaces (config.yaml), no hardcodearse en el script. |
| `infra/scripts/deploy-agora.sh:28-29` | MALAPRACTICS | blocker | `SYSTEMD_SRC="$INFRA_DIR/systemd/agora-backend.service"` referencing `infra/systemd/` que según comentario interno fueron archivados a `archived/legacy-systemd-units-pre-installer-v2.20260521/`. | El script apunta a una ruta de units que ya no existe en el nuevo layout (v2 installer). Esto significa que el deploy fallará silenciosamente o instalará units fantasma. | Usar `infra/installer/systemd/*.tmpl` rendering via `laia-install` como documenta el comentario del propio archivo. |
| `scripts/create-workspace.py:189` | MALAPRACTICS | blocker | `CONFIG_PATH.write_text(text, encoding="utf-8")` — escritura directa sin atomicidad. Si el proceso es interrumpido, config.yaml queda truncado. |同为 `StateStore` que usa write-atómico (`tmp + os.replace`), este script modifica config.yaml in-place sin tmp file. Un Ctrl+C durante el write destruye la config. | Implementar write-atómico: escribir a `config.yaml.tmp`, luego `os.replace(tmp, config.yaml)`. |
| `scripts/create-workspace.py:189` (segundo) | MALAPRACTICS | blocker | La función `update_config_fallback_text` y `update_config` reescriben config.yaml sin backup. Mismo riesgo que anterior más: la reescritura de `yaml.dump()` puede alterar el formato (orden de keys, estilo). | `yaml.dump(config, f, default_flow_style=False, allow_unicode=True)` reordena keys. Si el usuario tiene comentarios o estructura específica, se pierde. | Hacer backup antes de escribir: `shutil.copy2(config_path, config_path.with_suffix('.bak'))`. |
| `scripts/cleanup-sessions.py:96-100` | MALAPRACTICS | blocker | `delete_sessions` usa `shutil.rmtree(path)` sin verificar que el path está dentro del workspace dir. Si `path` es un symlink pointing outside, borra el target completo. | `shutil.rmtree` sigue symlinks. Si un workspace es un symlink a `/tmp/evil`, se borra todo `/tmp`. Reported en múltiples hardening guides para Python file-cleaning scripts. | Añadir validación: `path.resolve().relative_to(sessions_dir.resolve())` antes de borrar, o usar `shutil.rmtree(path, follow_symlinks=False)` si disponible. |

---

## MAYORES

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `infra/bin/laia-deploy:43` | MALAPRACTICS | major | `pkill -f "uvicorn app.main:app.*8088"` — patrón con port hardcoded (8088). Si el backend corre en otro puerto, el pkill no funciona o mata otro proceso que use el mismo patrón. | Killing por nombre + puerto es impreciso. El propio script usa `${AGORA_PORT}` o similar en otros contextos inconsistentes. | Usar PID file o buscar el proceso por puerto con `ss -tlnp | grep :8088 | awk '{print $NF}' | cut -d= -f2` para obtener el PID exacto. |
| `infra/bin/laia-deploy:34` | BASH | major | `rm -rf "$dst"` donde `dst` es local, pero el script no verifica que `dst` no sea `/`. | Safety check ausente. Aunque `dst` viene de una variable local, si `AGORA_FRONTEND_DIST` se establece como `/`, `rm -rf /` destruiría el sistema. | Añadir: `[[ "$dst" == "/" ]] && die "Abort: dst is /"; [[ -z "$dst" ]] && die "dst empty"` antes del rm. |
| `scripts/hermes-backup.py:140` | EFICIENCIA | major | `int(min_free_gb * 1024**3)` — `1024**3` es magic number sin comentario ni constante. Aparece en línea 140 y calcula bytes. | Sin contexto, 1024 es 1000? 1024**3 = 1GiB. Si mañana se cambia a 1000 por error, el check de espacio libre falla silenciosamente. | Definir `GIBIBYTE = 1024**3` al inicio del archivo con comentario: `# 1 GiB in bytes`. |
| `scripts/agent-monitor.py:218` | ROBUSTEZ | major | `time.sleep(max(0.5, args.interval))` — si `args.interval` es negativo o cero, `max(0.5, 0)` = 0.5s OK; pero si `args.interval` es muy grande, el loop es muy lento sin feedback. | No hay validación de rango para `--interval`. Un usuario que pone `--interval 3600` esperaría 1h entre refrescos sin feedback de que fue aceptado. | Validar rango: `if not 0.1 <= args.interval <= 300: die("interval must be 0.1-300 seconds")`. |
| `scripts/ai-orchestrator.py:237` | MALAPRACTICS | major | `timeout = int(agent.get("timeout_seconds", 1800))` — 1800 segundos (30 min) hardcoded como default. Si un worker se cuelga, espera 30 min antes de timeout. | En un orquestador multi-IA, 30 min de espera puede consumir recursos innecesariamente. No hay forma de ajustar este timeout sin editar código. | Hacer configurable via `AGENTS_TIMEOUT_SECONDS` env var, o por agente en `ai-agents.json`. Considerar 5-10 min como default más razonable. |
| `scripts/ai-orchestrator.py:32` | MALAPRACTICS | major | `ai-orchestrator.py` espera que `CONFIG_PATH = LAIA_HOME / "ai-agents.json"`. Si `LAIA_HOME` no existe o no tiene permisos, falla con traceback. | No hay validación de que `LAIA_HOME` y el archivo de config existan antes de operar. Un error aquí impide toda la funcionalidad del orquestador. | Crear directorio y archivo de config por defecto si no existen, odar error claro con instructions. |
| `infra/dev/add-test-user.sh:105-106` | MALAPRACTICS | major | `sudo chmod 644 "$PER_USER_STATE_FILE"` y `chown "$(id -u):$(id -g)"` en archivo que contiene `api_token` del executor en texto plano. | El state file con token queda world-readable (644). Cualquier proceso del sistema puede leerlo. El token del executor da acceso completo al agent. | `chmod 600` para owner-only. El archivo contiene credenciales y debe ser legible solo por el usuario. |

---

## MENORES

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `scripts/cleanup-sessions.py:42` | MALAPRACTICS | minor | `session_size()` hace `shutil.rmtree(path, ignore_errors=True)` que ignora TODOS los errores (permissions, readonly, etc.). Si no puede borrar, ignora silenciosamente. | Problema de "verde falso": el script cree que borró pero no lo hizo. El usuario puede creer que liberó espacio cuando no. | En vez de `ignore_errors=True`, capturar excepciones específicas y reportar cuáles fallaron. |
| `scripts/cleanup-sessions.py:109-113` | MALAPRACTICS | minor | `delete_sessions` tiene el mismo problema de `shutil.rmtree(path)` sin follow_symlinks=False. | Mismo issue que delete_sessions en cleanup-sessions: symlink traversal. | Añadir check con `follow_symlinks=False` o validar que `path.resolve()` esté dentro del expected root. |
| `scripts/workspace-daily-diagnostic.py:77` | EFICIENCIA | minor | `found.sort(key=lambda item: (-float(item[1].get("score", 0.0)), item[0], item[1]["slug"]))` — sort en cada caso con float conversion por cada comparación. | Si el dataset crece, el sort se repite innecesariamente. El float conversion se hace múltiples veces por item. | Extraer el score una vez: `score = float(item[1].get("score", 0.0))` antes del sort key. |
| `scripts/show-injected.py:140` | MALAPRACTICS | minor | `max_chars = int(ws_cfg.get("max_chars", 8000))` — 8000 hardcoded como default en lugar de constante. Además, si el valor en config no es entero, `int()` lanza `ValueError` no manejado. | Sin validación robusta. El fallback debería estar en una constante con nombre, y el parsing debe ser safe. | Extraer `DEFAULT_MAX_CHARS = 8000` y envolver en try/except con fallback a default. |
| `scripts/delete-workspace.py:170` | ROBUSTEZ | minor | `shutil.rmtree(workspace_path)` — mismo problema de symlink traversal que en cleanup-sessions. Además, el archivo `CANCEL_FILE` para shutdown no se limpia antes de borrar, lo que puede afectar otros scripts. | `workspace_path` es un `Path` absoluto resolved; no hay validación de que está dentro de `WORKSPACES_DIR`. Si alguien hace symlink, puede borrar cualquier cosa. | Validar con `workspace_path.resolve().relative_to(WORKSPACES_DIR.resolve())` antes de `rmtree`. |
| `infra/scripts/deploy-agora.sh:79` | MALAPRACTICS | minor | `sudo cp "$SYSTEMD_SRC" "$SYSTEMD_DST"` sin verificar que el source existe. Si el archivo no existe, `cp` falla pero el script continua si `set -e` no está activo (falta al inicio — ver blocker). | Falta `set -euo pipefail` lo que hace que el script continúe aunque `cp` falle. El systemd service no se instala pero el script reporta "Servicio instalado". | Verificar que `$SYSTEMD_SRC` existe antes de `cp`, con mensaje claro si no. |

---

## NITS

| fichero:línea | categoría | severidad | qué está mal | por qué | fix sugerido |
|---|---|---|---|---|---|
| `infra/bin/laia` | SINTaxis | nit | Archivo no termina con newline. Los editores pueden mostrar warning. | El archivo 51-line script termina abruptamente sin newline. En algunos contextos esto puede causar issues en output de `echo`. | Añadir newline al final del archivo. |
| `infra/bin/laia-deploy:46` | SINTaxis | nit | Error en mensaje: `"ERR frontend no responde (puede necesitar reinicio nginx)"` — la línea 136 dice `:8090` pero el comentario dice `8090`. El frontend se despliega en `:8090` pero el comment al final del script dice `:8090`. Verificar que nginx está configurado para el puerto correcto. | El mensaje de error referencia el puerto `:8090` pero el script en línea 59 usa `8090` inconsistentemente (frontend deploy en línea 33 cp a `dst` que es `${AGORA_FRONTEND_DIST:-/srv/laia/agora}/frontend/dist`). Parece que el nginx conf sirve el frontend en puerto 80, no 8090. | Verificar y aclarar en comentario qué puerto слушает nginx para el frontend. |
| `scripts/workspace-daily-diagnostic.py:61` | MALAPRACTICS | nit | `load_store()` hace `store.migrate_from_markdown(force=False)` que puede ser lento en workspaces grandes. Si el diagnóstico se ejecuta como cron, no debería hacer migración automática. | El diagnóstico debería ser read-only: solo leer y reportar, no mutar estado. Migrar por error durante un diagnóstico puede alterar el workspace unexpectedly. | Separar `load_store()` (solo lectura) de `migrate_if_needed()` (solo cuando se pide explícitamente). El diagnóstico no debería mutar. |

---

## DIRECTORIOS LIMPIOS

- `infra/pathd/` — código bien estructurado, sigue prácticas correctas (atomic writes, imports bien manejados, no hardcoded credentials, logging vs print, validación de paths).
- `infra/orchestrator/` — código robusto; `lxd.py` bien diseñado con `Result` dataclass y manejo de errores consistente.
- `infra/scripts/setup-prod-dirs.sh` — correcto, tiene `set -euo pipefail`, validación de root, uso de `install -d -m 0750`.
- `infra/scripts/backup-state.sh` — correcto, tiene `set -euo pipefail`, usa `|| true` en operaciones opcionales.
- `infra/scripts/install-agora-backend-service.sh` — correcto, valida que el template exista antes de copiar.
- `infra/scripts/install-systemd-units.sh` — deprecated, pero tiene `set -euo pipefail` y `exit 2` inmediato que bloquea ejecución (correcto para deprecated).
- `infra/dev/laia-init.sh` — tiene `set -euo pipefail`, manejo robusto de variables de entorno, uso de `ask_secret` para passwords.
- `infra/dev/laia-init-checks.sh` — tiene `set -euo pipefail`, salida JSON `--json` para machine-readable.
- `infra/dev/preflight.sh` — tiene `set -uo pipefail` (falta `e` — ver blocker).
- `infra/dev/setup-ctl-venv.sh` — tiene `set -euo pipefail`, hash-based short-circuit para skip install si deps unchanged.
- `infra/dev/smoke-test.sh` — tiene `set -uo pipefail` (falta `e` — ver blocker), pero hace validación de credenciales desde archivo dedicado.
- `infra/dev/rebuild-state.sh` — tiene `set -uo pipefail` (falta `e` — ver blocker), usa `json_write` helper con validación.
- `infra/dev/seed-base-skills.sh` — tiene `set -euo pipefail`, idempotente, skips already-installed skills.
- `infra/dev/verify-redesign.sh` — tiene `set -uo pipefail` (falta `e`), pero es muy robusto con PIDs tracking y cleanup trap.
- `scripts/nightly-shutdown.py` — tiene logging estructurado, `wait_cancel_window` con archivo de cancelación, uso de `subprocess.run` con check=True.
- `scripts/startup-report.py` — correcto, logging estructurado, lectura de last-shutdown.json para calcular downtime.
- `scripts/sync-workspace-markdown.py` — correcto, validación de workspace existence antes de operar.
- `scripts/index-scripts.py` — correcto, parsing de docstrings para extraer descripciones de scripts.
- `scripts/workspace-switch.py` — robusto, tiene fallback text parser cuando yaml no está disponible.

---

## BLOQUEADORES SIN ARREGLAR (acciones requeridas)

### 1. Scripts bash sin `set -euo pipefail`
- `infra/bin/laia` — sin shebang, sin set
- `infra/bin/laia-watch` — sin shebang, sin set
- `infra/dev/preflight.sh` — tiene `set -uo pipefail` (falta `e`)
- `infra/dev/smoke-test.sh` — tiene `set -uo pipefail` (falta `e`)
- `infra/dev/rebuild-state.sh` — tiene `set -uo pipefail` (falta `e`)
- `infra/dev/chat-with-deployed.sh` — tiene `set -uo pipefail` (falta `e`)

### 2. Credenciales hardcoded en texto plano
- `infra/dev/add-test-user.sh:140-146` — "jorge/dev-admin"
- `infra/dev/chat-with-agent.sh:195-196` — "jorge/dev-admin"
- `infra/dev/smoke-test.sh:33-34` — "jorge/dev-admin" defaults
- `scripts/ai-orchestrator.py:34-67` — DEFAULT_CONFIG con commands hardcoded

### 3. Rutas/paths hardcoded que rompen en producción
- `scripts/hermes-backup.py:22` — `/Volumes/PortableSSD/` (macOS-only)
- `infra/scripts/deploy-agora.sh:28-29` — referencia dirs archivados
- `scripts/check-hardcoded-paths.py:48` — nombres de workspaces en regex

### 4. Código destructivo sin validación de seguridad
- `scripts/cleanup-sessions.py:96-100` — `shutil.rmtree` sin validar que el path está dentro del workspace
- `scripts/delete-workspace.py:170` — `shutil.rmtree` sin validación de symlink traversal
- `scripts/create-workspace.py:189` — write directo sin atomicidad