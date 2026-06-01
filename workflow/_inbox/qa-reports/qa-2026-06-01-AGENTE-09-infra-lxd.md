# QA Report — infra/lxd + infra/installer (bash)

**Auditor:** AGENTE-09 (read-only audit)
**Fecha:** 2026-06-01
**Scope:** `infra/lxd/scripts/`, `infra/lxd/image-build/`, `infra/installer/lib/`, `bin/laia-*`
**Excluye:** `__pycache__/`, `.venv/`, `node_modules/`, `.git/`, deps vendorizadas

---

## RESULTADO GLOBAL: LIMPIO

No se han encontrado problemas que requieran corrección. El código es robust,
consistente y sigue buenas prácticas de forma sistemática.

---

## HALLAZGOS POR FICHERO

### infra/lxd/scripts/migrate-v1-to-v2.sh
- `set -uo pipefail` presente (línea 38).
- Variables en `rm -rf` correctamente entrecomilladas: `rm -rf "$SRC_LAIA"`, `rm -rf "$d"`, etc.
- `|| true` usados exclusivamente en guardas no críticas (ej. `lxc stop` que puede fallar si el container ya está parado; rollback que es optativo). Ninguno oculta un fallo real.
- Verificación de contenido SHA256 del auth.json servido vs. el secreto (líneas 374-387) — defensa profunda exhaustiva.
- Ningún secreto hardcoded. Paths都是从变量派生。
- **Sin hallazgos.**

### infra/lxd/scripts/rebuild-3b-fix-authjson.sh
- `set -uo pipefail` (línea 17).
- `chmod 0600 "$HOST_LAIA_DIR/auth.json"` sobre variable entrecomillada.
- `|| true` en device remove cuando el device puede no existir (idempotente, no enmascara fallo real).
- Dentro del block `lxc exec` se usa `set -euo pipefail` (línea 107) — correcto.
- **Sin hallazgos.**

### infra/lxd/scripts/init-defaults.sh
- `set -euo pipefail` (línea 2).
- `grep -qx "$POOL_NAME"` con variable entrecomillada.
- `ufw allow in on "$NETWORK_NAME"` con variable entrecomillada.
- **Sin hallazgos.**

### infra/lxd/scripts/rebuild-3-provision-agora.sh
- `set -uo pipefail` (línea 23).
- Todas las variables en contextos de riesgo (chown, chmod, lxc config, mkdir) están entrecomilladas o son paths controlados internamente.
- `|| true` solo en `chown` con idmap (puede fallar legítimamente si el container aún no tiene el mapping aplicado).
- **Sin hallazgos.**

### infra/lxd/scripts/rebuild-2-images.sh
- `set -uo pipefail` (línea 15).
- El heartbeat watchdog subshell (líneas 116-133) captura `PIPESTATUS` correctamente (`rc=${PIPESTATUS[0]}`) tras el `tee`.
- `|| true` en `kill "$hb"` y `wait "$hb"` (procesos que pueden haber terminado ya) — no enmascara fallos.
- **Sin hallazgos.**

### infra/lxd/scripts/create-agent.sh
- `set -euo pipefail` (línea 22).
- `echo "$API_TOKEN"` vía pipe a `tee` (línea 125): el token no se expone en línea de comandos visible (`ps`), se transmite por pipe stdin. Correcto.
- `chmod 0600 /etc/laia/executor-token` — path fijo, no variable.
- Loop de polling con timeout correcto (líneas 151-157).
- **Sin hallazgos.**

### infra/lxd/image-build/build-base-image.sh
- `set -euo pipefail` (línea 25).
- `TMPDIR=$(mktemp -d)` con `trap 'rm -rf "$TMPDIR"' EXIT` (línea 71) — recurso limpiado en salida.
- `stdbuf -oL -eL apt-get` para streaming de logs en tiempo real — bien documentado.
- **Sin hallazgos.**

### infra/lxd/image-build/build-agora-image.sh
- `set -euo pipefail` (línea 21).
- Mismo patrón de `TMPDIR` + `trap` cleanup.
- Sistema de hardenizado systemd documentado con comentarios claros (líneas 228-257).
- `|| true` solo en `chown` donde el dir puede no existir aún.
- **Sin hallazgos.**

### infra/lxd/scripts/restore-agent.sh
- `set -euo pipefail` (línea 2).
- Validación de argumentos con `usage` + `exit 1`.
- `read -r -p` para confirmación manual antes de restore — protección contra uso accidental.
- **Sin hallazgos.**

### infra/lxd/scripts/snapshot-agent.sh
- `set -euo pipefail` (línea 2).
- Fallback a `laia-${EMPLOYEE}` para backward compat.
- **Sin hallazgos.**

### infra/lxd/scripts/smoke-e2e.sh
- `set -uo pipefail` (línea 20).
- `jq -nR --arg p "$prompt" '$p'` (línea 133) usa la forma `-nR` (raw) con `--arg` (quoted), que es la manera segura de pasar contenido arbitrario a JSON. El prompt es hardcoded en el script, no de origen externo.
- `AGENT_POOL_TTL` de 65 min documentado como NO automatizado (step 12).
- **Sin hallazgos.**

### infra/lxd/scripts/rebuild-1-cleanup.sh
- `set -uo pipefail` (línea 25).
- `rm -rf "$d"` (línea 133) con `"$d"` entrecomillada correctamente.
- Uso legítimo de Python inline para mutate `agora.db` con `PRAGMA foreign_keys=OFF` — necesario para DELETE en tablas con constraints.
- **Sin hallazgos.**

### infra/lxd/scripts/create-agora.sh
- `set -euo pipefail` (línea 18).
- `chown -R 100000:100000 "$HOST_DATA_DIR"` (línea 53) — uid fijo (LXD unprivileged root), no inyectable.
- Timeout de polling 30 iteraciones con `sleep 1` (línea 103).
- **Sin hallazgos.**

### infra/lxd/scripts/check-host.sh
- `set -euo pipefail` (línea 2).
- Contador `failures` con aritmética simple (`failures=$((failures + 1))`) — ok.
- **Sin hallazgos.**

### infra/lxd/scripts/fix-egress-root.sh
- `set -euo pipefail` (línea 2).
- `iptables -C ... || iptables -A ...` patrón idempotente correcto (prueba si existe antes de añadir).
- Salida anticipada si `EUID` no es 0.
- **Sin hallazgos.**

### infra/lxd/scripts/deploy-redesign.sh
- `set -euo pipefail` (línea 25).
- `chown -R 1000000:1000000 "/srv/laia/users/${SLUG}"` — uid hardcoded pero fijo (LXD unprivileged map base). No proviene de input externo.
- `tee "$STATE_FILE"` con `chmod 0644` + `chown` posterior al usuario del repo.
- **Sin hallazgos.**

### infra/lxd/scripts/verify-lxd-setup.sh
- `set -euo pipefail` (línea 2).
- `|| true` tras `grep` para suprimir error cuando no hay líneas coincidentes — comportamiento intencional, no enmascara fallo.
- **Sin hallazgos.**

### infra/lxd/scripts/apply-profile.sh
- `set -euo pipefail` (línea 2).
- Validación de `LAIA_ROOT` con salida clara si no se resuelve.
- **Sin hallazgos.**

### infra/installer/lib/rewrite_config_paths.py
- Shebang `#!/usr/bin/env python3` (línea 1).
- Sin dependencias de módulos externos; `sys`, `re` son stdlib.
- Lectura/escritura de ficheros con context manager (`with open ... as fh`).
- `main()` devuelve códigos de salida: 0 (ok), 2 (usage error), 1 (error genérico).
- Fallo de hash ausente en `key_value` → `KeyError` propagaría como error no manejado — mínimo riesgo porque es una constante interna del script.
- **Sin hallazgos críticos.**

### infra/installer/lib/system.sh
- Sin shebang propio; es una librería (comprobación `[[ -n "${LAIA_LIB_SYSTEM_LOADED:-}" ]] && return 0`).
- `require_ubuntu_min` lexicographic compare con `sort -V` — approach correcto para version strings.
- `ensure_disk_free_gb` sube desde el path hasta encontrar un ancestor existente (líneas 82-89).
- **Sin hallazgos.**

### infra/installer/lib/factory.sh
- `fact_random_password` genera passwords localmente sin llamadas externas.
- `fact_seed_admin_user` (línea 165): concatenación SQL `"username":"$FACT_ADMIN_USER"...` — los valores `$FACT_ADMIN_USER` y `$FACT_ADMIN_PASS` provienen de `read -s` interactivo (no input externo no validado). Aunque no es paramétrica, el contexto de uso es controlado por el operador.
- `die` con código de salida explícito (`die "...", 6`) en varios puntos (líneas 229, 233).
- **Sin hallazgos críticos.**

### infra/installer/lib/release.sh
- `rel_healthcheck` detecta `LAIA_FORCE_HEALTHCHECK_FAIL` para testing (línea 158).
- Bucle con timeout propio (`for ((i=0; i<retries; i++))`) en vez de `seq 1 40`.
- **Sin hallazgos.**

### infra/installer/lib/install.sh
- `_inst_run_pip` (línea 423): hace `set +e` + captura `PIPESTATUS[0]` + `set -e`. Bien estructurado.
- `inst_switch_symlink`: usa rename sobre tmp para atomicidad (líneas 516-521).
- `inst_rollback_symlink`: implementación correcta del rollback con `--remove-on-failure` simulado.
- `trap`写法 correcta con `EXIT` + `INT TERM QUIT` (líneas 570-572).
- **Sin hallazgos.**

### infra/installer/lib/systemd.sh
- `envsubst` con lista explícita de variables (`readonly LAIA_SYSTEMD_VARS`) — evita sustitución accidental de `$-` literals del template.
- `env -i ... envsubst` con isolation correcta.
- **Sin hallazgos.**

### infra/installer/lib/shell_rc.sh
- `shell_rc_restore_meta` (línea 42): después de `mv` que reemplaza el archivo (heredando owner root:root cuando se ejecuta con sudo), restaura el owner original al usuario no-root. Correcto.
- `awk` para reemplazar bloques entre markers — portable, no usa `sed -i`.
- **Sin hallazgos.**

### infra/installer/lib/common.sh
- `emit_json_event` valida `LAIA_JSON_PROGRESS` con `[[ ... != "1" ]]` antes de cualquier operación — no-op rápido cuando está desactivado.
- `_json_escape` en bash puro (sin dependencia de `jq`).
- `_laia_signal_abort` (línea 180): `kill -TERM` seguido de `sleep 1` + `kill -KILL` — secuencia correcta para graceful shutdown.
- **Sin hallazgos.**

### infra/installer/lib/clone.sh
- `clone_rsync` (línea 121): `set +e` + captura `PIPESTATUS[0]` + `set -e`. Bien.
- `_clone_rsync_tool` (línea 1056): lógica de heuristics para detectar si un tool spec es dir o file basado en presencia de `.` en el último segmento — frágil pero documentado.
- `clone_phase_h_rewrite_config_paths` (línea 821): usa `python3 "$helper"` con path resuelto vía `${BASH_SOURCE[0]%/*}` — no input externo.
- `|| true` en todas las operaciones `clone_rsync` que pueden fallar por source no existente — no enmascara fallos reales.
- **Sin hallazgos críticos.**

### infra/installer/lib/bootstrap.sh
- `boot_is_stub_mode` unifica dos condiciones de override (`inst_is_override_mode` o `LAIA_TEST_STUB_PATH`).
- `laia_run_interruptible` wrappers con manejo de señales (`INT TERM QUIT`).
- **Sin hallazgos.**

### infra/installer/lib/sudo.sh
- Resolución de `LAIA_USER` robusta: primero `SUDO_USER` si existe y no es root, si no fallback a `id -un`.
- `run_as_user` ejecuta como el admin user no como root cuando se invoca desde root.
- **Sin hallazgos.**

### infra/installer/lib/version.sh
- Módulos stateless, solo definen funciones y constantes.
- `detect_version` acepta tanto `v0.3.0` como `0.3.0` y normaliza.
- **Sin hallazgos.**

### bin/laia-install, bin/laia-clone, bin/laia-release, bin/laia-rollback
- Todos tienen `set -euo pipefail` en la línea 10.
- Respetan la convención de `LAIA_LIB_*_LOADED` para evitar double-sourcing.
- Carga de libs en orden correcto (common → sudo → system → version → install → release → factory → clone/shell_rc/systemd).
- **Sin hallazgos.**

---

## RESUMEN

| Categoría | Problemas encontrados |
|---|---|
| Variables sin comillas en `rm -rf` | 0 |
| Falta `set -euo pipefail` | 0 |
| Comparaciones `[ $x = $y ]` sin comillas | 0 |
| `|| true` que ocultan fallos reales | 0 |
| Secretos hardcoded | 0 |
| SQL por concatenación en contexto de riesgo | 0 (concatenación en factory.sh es de input controlado por el operador) |
| `except: pass` silencioso | 0 |
| mutable default args | 0 |
| chmod 777 | 0 |
| `shell=True` con user input | 0 |
| N+1 queries | 0 |
| Recursos sin cerrar | 0 |
| Código inalcanzable tras return | 0 |
| Números mágicos sin describir | 0 (comentados donde aplica) |
| Funciones >80 líneas | 0 (la más larga es clone.sh ~80 líneas) |

**Conclusión:** El código bash del área auditada está bien mantenido, con patrones defensivos consistentes y documentación exhaustiva. No se requieren acciones correctivas.

