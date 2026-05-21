# HANDOFF — Continuar Fase B (laia-install funcional)

> 📅 2026-05-20
> Estado: Fase A completa + Fase B parcialmente arrancada
> Para: la siguiente sesión de Claude Code (o Jorge directamente)

---

## 1. Contexto que SÍ o SÍ tienes que leer antes de tocar nada

Lee estos archivos **en orden**, no improvises:

1. **`/home/laia-hermes/LAIA/LAIA_ECOSYSTEM.md`** — la fuente de verdad del proyecto. Sin esto no entiendes qué es ARCH vs AGORA vs PA-AGORA, ni por qué los paths son como son.
2. **`/home/laia-hermes/LAIA/.plans/PLAN_INSTALLER_Y_CLONER_v1.md`** — el plan v1.1 aprobado por Jorge. Aquí están todas las decisiones bloqueadas: paths, versionado, alcance del installer/cloner, etc. **NO replantees nada de esto sin pedirle permiso a Jorge.**
3. **Este archivo (HANDOFF_FASE_B.md)** — qué quedó hecho de Fase B, qué falta, en qué estado están los archivos en el working tree.
4. Memoria de Claude: `/home/laia-hermes/.claude/projects/-home-laia-hermes/memory/project_laia_paths_v2.md` — la convención de paths v2 (datos visibles, código oculto, /opt versionado).

## 2. Decisiones ya tomadas — NO renegocies

Resumen de lo bloqueado en el plan (§0):

| Concepto | Valor |
|---|---|
| Programa instalado | `/opt/laia-vX.Y.Z/` + symlink `/opt/laia` |
| Datos del admin | `~/LAIA-ARCH/` (visible, LAIA_HOME) |
| Árbol de desarrollo | `~/.laia/` (oculto, git tree) |
| Comandos en PATH | `/usr/local/bin/laia*` (symlinks a `/opt/laia/bin/*`) |
| Versionado | symlink `/opt/laia` apunta a versión; convivencia de varias |
| Alcance installer | Solo LAIA-ARCH. NO LXD/AGORA bootstrap |
| Alcance clonador | LAIA-ARCH data + export LXD completo + `--with-tools` opcional |
| Compat `~/.laia` fallback en Hermes | NO refactorizar; son fallbacks que con `LAIA_HOME` exportado no disparan |

## 3. Estado del repo

```
Branch:  feat/installer-cloner-v2
Último commit en mi rama: 65fbadc feat(installer): scaffold laia-install / clone / release / rollback (Fase A)
Tip de main:              589694c (o donde esté actualmente)
```

**No hagas push.** Es una rama local. Cuando termines la fase, commit + nada más.

## 4. Qué quedó hecho en Fase A (commit 65fbadc)

```
bin/                              host-side entrypoints (todos chmod +x)
├── laia                          delegador → laia-<subcommand> (FUNCIONAL)
├── laia-install                  SCAFFOLD: parse_args + --help + --dry-run stub
├── laia-clone                    SCAFFOLD: parse_args + --help + --dry-run stub
├── laia-release                  SCAFFOLD: parse_args + --help + --dry-run stub
└── laia-rollback                 SCAFFOLD: parse_args + --help + --dry-run + --list FUNCIONA

infra/installer/lib/              shared bash helpers (FUNCIONALES)
├── common.sh                     log/colors/confirm/die/require_cmd
├── sudo.sh                       LAIA_USER, run_as_user, require_root
├── system.sh                     detect_os, require_ubuntu_min, require_python_min, ensure_disk_free_gb
└── version.sh                    detect_version, install_path_for_version, current_installed_version, list_installed_versions

infra/installer/systemd/          templates con placeholders ${LAIA_USER} ${LAIA_USER_HOME} ${LAIA_HOME} ${LAIA_INSTALL_PREFIX}
├── laia-gateway.service.tmpl
├── laia-pathd.service.tmpl
├── agora-backend.service.tmpl
├── laia-ui-server.service.tmpl
└── README.md

tests/installer/                  bash tests zero-deps, 50/50 passing
├── test_flags.sh                 24 asserts (--help, --version, --dry-run, bad args)
├── test_lib_common.sh            26 asserts (lib functions)
└── README.md
```

**Verifica que sigue verde antes de empezar:**
```bash
cd /home/laia-hermes/LAIA
bash tests/installer/test_flags.sh        # PASS 24
bash tests/installer/test_lib_common.sh   # PASS 26
```

## 5. Lo que YA he escrito en Fase B (UNTRACKED — NO commiteado)

Tres archivos `.sh` nuevos en `infra/installer/lib/`, sintaxis válida (`bash -n` pasa), pero NUNCA ejecutados ni testeados:

```
infra/installer/lib/install.sh    (428 líneas) — pipeline phases
infra/installer/lib/shell_rc.sh    (91 líneas) — .bashrc/.zshrc management
infra/installer/lib/systemd.sh     (99 líneas) — systemd template rendering
```

### 5.1 `install.sh` — funciones que ya escribí

| Función | Fase B | Estado | Notas |
|---|---|---|---|
| `inst_compute_paths` | — | OK | Sets INST_DEST, INST_PREFIX, INST_BIN_DIR, DATA_DIR, SYSTEMD_DIR con env overrides |
| `inst_is_override_mode` | — | OK | True si algún LAIA_*_OVERRIDE está set (tests) |
| `inst_preflight` | B.1 | OK | Ubuntu/kernel/python/disk/deps + require_root salvo en override mode |
| `inst_resolve_source` | B.2 | OK | Solo soporta `--from-local`. **Clone desde GitHub queda como TODO en Fase B.next** |
| `inst_resolve_version` | B.2 | OK | Delega a `detect_version` |
| `inst_resolve_paths` | B.3 | OK | Llama `inst_compute_paths` + log |
| `inst_check_existing_version` | B.3 | OK | Aborta si existe sin --force |
| `inst_copy_source_to_dest` | B.3 | OK | rsync con excludes definidos en `_inst_rsync_excludes`. Stampa `VERSION` file |
| `inst_create_venvs` | B.4 | OK | Crea dos venvs: `.laia-core/venv` + `services/agora-backend/.venv`. Hace pip install -e .laia-core y -r requirements.txt para agora |
| `inst_check_frontend` | B.4 | OK | Solo detecta `dist/`. Si falta, warn + continúa. **NO ejecuta `pnpm build` aún** |
| `inst_finalize_permissions` | B.3 | OK | chown root:root + chmod go-w (salvo override mode) |
| `inst_switch_symlink` | B.5 | OK | Atomic via tmpname + `mv -T` |
| `inst_install_wrappers` | B.6 | OK | Symlinks `/usr/local/bin/laia*` → `/opt/laia/bin/*` |
| `inst_ensure_data_dir` | B.7 | OK | Crea `~/LAIA-ARCH/` 700 si no existe |

### 5.2 `shell_rc.sh`

| Función | Fase B | Estado |
|---|---|---|
| `shell_rc_targets` | B.8 | OK — lista `.bashrc` + `.zshrc` (o `LAIA_SHELL_RC_OVERRIDE` para tests) |
| `shell_rc_render_block` | B.8 | OK — renderiza bloque con marcadores |
| `shell_rc_apply` | B.8 | OK — idempotente: si el bloque existe lo reemplaza, si no lo añade |
| `shell_rc_remove` | (futuro uninstall) | OK |

Marcadores: `# >>> laia >>>` / `# <<< laia <<<`

### 5.3 `systemd.sh`

| Función | Fase B | Estado |
|---|---|---|
| `systemd_template_dir` | B.9 | OK |
| `systemd_list_templates` | B.9 | OK |
| `systemd_render` | B.9 | OK — envsubst con lista explícita de vars (LAIA_SYSTEMD_VARS) |
| `systemd_install_all` | B.9 | OK — renderiza todos los .tmpl, chown root:root, `systemctl daemon-reload`. NO enable, NO start |

## 6. Lo que FALTA hacer en Fase B (tu trabajo)

### 6.1 CRÍTICO: Conectar las funciones al `bin/laia-install` (~1h)

Ahora mismo `bin/laia-install` tiene un `main()` stub que solo imprime "SCAFFOLD". Tienes que:

1. Añadir `source "$LIB_DIR/install.sh"`, `source "$LIB_DIR/shell_rc.sh"`, `source "$LIB_DIR/systemd.sh"` al top del script (después de los otros sources).
2. Añadir flags nuevos al `parse_args`: `--skip-pip`, `--skip-frontend`. (Ya hay `--no-systemd`, `--force`, `--version`, `--from-local`, `--yes`, `--dry-run`.) Mira `print_help` también para reflejarlos.
3. Reescribir `main()` para que llame al pipeline en orden:

```bash
main() {
  parse_args "$@"

  log_step "laia-install"
  inst_preflight

  inst_resolve_source
  inst_resolve_version
  inst_resolve_paths

  if [[ "$OPT_DRY_RUN" == true ]]; then
    log_warn "Dry-run mode — stopping before mutations."
    exit 0
  fi

  inst_check_existing_version

  if ! inst_is_override_mode; then
    ensure_sudo_cached
  fi

  inst_copy_source_to_dest
  inst_create_venvs
  inst_check_frontend
  inst_finalize_permissions
  inst_switch_symlink
  inst_install_wrappers
  inst_ensure_data_dir
  shell_rc_apply "$DATA_DIR"
  systemd_install_all

  inst_print_summary    # tienes que escribir esta
}
```

4. Escribir `inst_print_summary()` en `install.sh` — un bloque final que imprima:
   - Versión instalada
   - Path activo (`/opt/laia` → versión)
   - Comandos disponibles en `/usr/local/bin`
   - Cómo arrancar servicios (`sudo systemctl enable --now laia-gateway`)
   - Próximo paso sugerido: `laia clone <host>` o `laia init`

### 6.2 Tests (~3-4h)

Crear estos archivos en `tests/installer/`:

#### `test_shell_rc.sh` — idempotencia de markers

Cosas a verificar:
- Apply 2 veces → el archivo solo tiene UN bloque
- Apply con un valor distinto → reemplaza el bloque, no duplica
- Remove → quita el bloque sin tocar nada más
- Funciona con `LAIA_SHELL_RC_OVERRIDE` apuntando a un tmpfile

Plantilla (no la copies tal cual, ajusta):

```bash
#!/usr/bin/env bash
set -u
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"

source "$LIB/common.sh"
source "$LIB/sudo.sh"
export LAIA_SHELL_RC_OVERRIDE="$(mktemp)"
trap 'rm -f "$LAIA_SHELL_RC_OVERRIDE"' EXIT
source "$LIB/shell_rc.sh"

# ... aserts ...
```

#### `test_systemd_render.sh` — envsubst correctness

- Renderiza cada `.service.tmpl` con valores conocidos
- Verifica que las variables aparecen sustituidas
- Verifica que NO hay `$LAIA_` sin sustituir en el output
- Verifica que sí preserva otros `$HOME` o `$LAIACTL_PATH` que están en los Environment= y que systemd debe expandir

#### `test_install_e2e.sh` — end-to-end con tmpdir overrides

Este es el test más importante. Hace un install COMPLETO en un tmpdir, sin sudo, sin tocar producción.

```bash
#!/usr/bin/env bash
set -u
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR/usr-local-bin"
export LAIA_HOME_OVERRIDE="$TMPDIR/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR/bashrc-test"

touch "$LAIA_SHELL_RC_OVERRIDE"

# Run installer in test mode (no pip, no frontend — too slow/network)
"$LAIA_ROOT/bin/laia-install" \
  --from-local "$LAIA_ROOT" \
  --version v0.0.0-test \
  --skip-pip \
  --skip-frontend \
  --yes

# Verify outcomes:
test -d "$TMPDIR/opt/laia-v0.0.0-test"           # install dir exists
test -L "$TMPDIR/opt/laia"                        # symlink exists
[[ "$(readlink "$TMPDIR/opt/laia")" == "laia-v0.0.0-test" ]]
test -L "$TMPDIR/usr-local-bin/laia"              # wrapper exists
[[ "$(readlink "$TMPDIR/usr-local-bin/laia")" == "$TMPDIR/opt/laia/bin/laia" ]]
test -d "$TMPDIR/LAIA-ARCH"                       # data dir
[[ "$(stat -c %a "$TMPDIR/LAIA-ARCH")" == "700" ]]
grep -q 'LAIA_HOME=' "$LAIA_SHELL_RC_OVERRIDE"    # bashrc updated
test -f "$TMPDIR/systemd/laia-gateway.service"    # systemd rendered
grep -q "$TMPDIR/opt/laia/.laia-core" "$TMPDIR/systemd/laia-gateway.service"  # path substituted

# Re-run for idempotency:
"$LAIA_ROOT/bin/laia-install" --from-local "$LAIA_ROOT" --version v0.0.0-test --skip-pip --skip-frontend --yes --force
# Verify no duplicate block in bashrc:
[[ "$(grep -c '>>> laia >>>' "$LAIA_SHELL_RC_OVERRIDE")" == "1" ]]
```

### 6.3 Verificar manualmente el dry-run completo (~30 min)

```bash
cd /home/laia-hermes/LAIA
bin/laia-install --from-local "$PWD" --version v0.0.0-test --skip-pip --skip-frontend --dry-run
```

Debería:
- Pasar preflight (esta máquina sí cumple Ubuntu/Python/kernel/disk)
- Detectar la versión v0.0.0-test
- Calcular paths (`/opt/laia-v0.0.0-test`, etc.)
- Parar ANTES de cualquier mutación

Si pasa esto, la lógica está bien encadenada. **No hagas un install real fuera de override mode** — eso es trabajo de Fase C, no de Fase B.

### 6.4 Bug / mejora pendiente

Mira `install.sh:38-42`:
```bash
inst_compute_paths() {
  ...
  INST_DEST="${install_root}/laia-${OPT_VERSION#v}"
  [[ "$OPT_VERSION" =~ ^v ]] && INST_DEST="${install_root}/laia-${OPT_VERSION}"
```

Eso es feo (escribo dos veces y depende del orden). Simplifícalo:

```bash
local v="$OPT_VERSION"
[[ "$v" =~ ^v ]] || v="v$v"
INST_DEST="${install_root}/laia-${v}"
```

(Es exactamente el mismo patrón que `install_path_for_version` en `version.sh:32`.)

### 6.5 GitHub clone — DEJAR COMO TODO

El plan §3.1 menciona soporte para `curl ... | sudo -E bash` (bootstrap remoto desde GitHub privado vía `gh auth`). **No lo implementes en esta fase.** Déjalo como TODO claro en el código:

```bash
# inst_resolve_source actualmente solo soporta --from-local.
# TODO Fase B.next: si OPT_FROM_LOCAL está vacío, clonar de
#   gh repo clone JorgeMP-3/laia-arch /tmp/laia-build
# y hacer OPT_FROM_LOCAL="/tmp/laia-build". Requiere `gh auth status` previo.
```

Eso lo añade Jorge cuando despliegue a un servidor real. Por ahora `--from-local` cubre el caso interno.

### 6.6 Frontend build — DEJAR COMO TODO

Mismo razonamiento. `inst_check_frontend` actualmente solo detecta `dist/` y warns si falta. **No añadas `pnpm install + pnpm build` automatic en esta fase** — eso depende de pnpm/turbo instalados, network, y tarda 5+ min. Para Fase B basta con que el flag `--skip-frontend` exista y que se warn si no hay dist/. El build lo hace el dev manualmente antes de `laia-release` en Fase C.

### 6.7 Commit final

Cuando todo esté verde (los 5 archivos de test pasan), commit limpio:

```bash
git add bin/laia-install \
        infra/installer/lib/install.sh \
        infra/installer/lib/shell_rc.sh \
        infra/installer/lib/systemd.sh \
        tests/installer/test_install_e2e.sh \
        tests/installer/test_shell_rc.sh \
        tests/installer/test_systemd_render.sh

git commit -m "$(cat <<'EOF'
feat(installer): laia-install funcional con build a /opt (Fase B)

Conecta el scaffold de Fase A con un pipeline real que:
  - preflight: Ubuntu/kernel/python/disk/sudo
  - resuelve source tree (--from-local) y versión (git describe / VERSION)
  - rsync con excludes a /opt/laia-vX.Y.Z/
  - crea venvs Python (.laia-core + agora-backend) y pip install
  - detecta dist/ en laia-ui/ (no construye frontend, warn si falta)
  - aplica permisos root:root go-w
  - switch atómico de /opt/laia symlink
  - symlinks en /usr/local/bin/laia*
  - crea ~/LAIA-ARCH/ (700) si no existe
  - escribe LAIA_HOME en .bashrc/.zshrc entre marcadores
  - renderiza systemd units desde templates con envsubst
  - daemon-reload (NO enable, NO start)

Helpers nuevos en infra/installer/lib/:
  install.sh      pipeline phases (preflight, copy, venv, symlink, etc)
  shell_rc.sh     idempotent block management with markers
  systemd.sh      envsubst rendering with explicit variable list

Tests nuevos en tests/installer/ (zero-deps, no sudo, tmpdir overrides):
  test_install_e2e.sh        full pipeline en tmpdir (skip pip + frontend)
  test_shell_rc.sh           idempotencia de markers
  test_systemd_render.sh     correctness del envsubst

Tests pasan: 24 (flags) + 26 (lib_common) + N (e2e) + N (shell_rc) + N (systemd)

Lo que NO está en este commit (queda para fases siguientes):
  - clone de repo desde GitHub (--from-local sigue siendo obligatorio)
  - build automático del frontend con pnpm
  - tests E2E en VM Multipass limpia
  - laia-release (Fase C)
  - laia-clone (Fase D + E)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

## 7. Lo que NO debes hacer

- **NO** ejecutes `bin/laia-install` sin `--dry-run` y sin overrides en esta máquina. Eso es Fase C (migración real). Ahora mismo crearía `/opt/laia-v0.0.0-test` y tocaría tu `.bashrc` real.
- **NO** hagas push de la rama. Es trabajo en curso.
- **NO** mergees a main. Lo hace Jorge cuando todas las fases A-F estén verdes.
- **NO** toques `~/.laia/` ni `~/LAIA-ARCH/` directamente. La migración es Fase C.
- **NO** instales pnpm/node/turbo si no están. El installer detecta `dist/` y warn; eso basta para Fase B.
- **NO** modifiques `.laia-core/` (el fork de Hermes). Es código upstream, hay un plan separado para sync.

## 8. Si algo no encaja con el plan

Lee el plan otra vez. Si después de leerlo sigue sin encajar:
- **Pregunta a Jorge** antes de improvisar.
- Si tienes que pausar de nuevo, escribe otro HANDOFF al lado de éste (`HANDOFF_FASE_B_part2.md`) con el estado exacto y qué quedó pendiente.

## 9. Comandos útiles

```bash
# Verificar estado del repo:
cd /home/laia-hermes/LAIA
git status
git log --oneline -5
git branch --show-current        # debe ser feat/installer-cloner-v2

# Sintaxis check rápido:
for f in bin/laia* infra/installer/lib/*.sh; do bash -n "$f" || echo "FAIL: $f"; done

# Tests existentes (deben pasar antes y después de tu trabajo):
bash tests/installer/test_flags.sh
bash tests/installer/test_lib_common.sh

# Dry-run del installer (ahora mismo solo imprime SCAFFOLD; tras tu cambio debe imprimir el pipeline):
bin/laia-install --from-local "$PWD" --version v0.0.0-test --skip-pip --skip-frontend --dry-run
```

## 10. Archivos de Fase B en working tree (no commiteados)

```
infra/installer/lib/install.sh     (428 líneas)  sintaxis OK
infra/installer/lib/shell_rc.sh    (91 líneas)   sintaxis OK
infra/installer/lib/systemd.sh     (99 líneas)   sintaxis OK
```

Léelos COMPLETOS antes de modificar nada. La estructura ya está pensada para Fase C (laia-release reutiliza muchas funciones). No reescribas a tu gusto.

---

Buena suerte. Si necesitas el contexto del proyecto completo, las memorias de Claude están en `/home/laia-hermes/.claude/projects/-home-laia-hermes/memory/` — todas las relevantes empiezan por `project_laia_*`.
