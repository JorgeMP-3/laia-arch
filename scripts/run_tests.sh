#!/usr/bin/env bash
# Entrada ÚNICA para las suites de LAIA — con paridad CI (patrón run_tests.sh de Hermes,
# adoptado 2026-06-02). Llama a esto, no a pytest/run_all a pelo, antes de declarar "hecho".
#
# Uso:
#   scripts/run_tests.sh                   # todas las suites corribles en este entorno
#   scripts/run_tests.sh backend [args…]   # pytest de agora-backend (args → pytest)
#   scripts/run_tests.sh installer         # suite shell del instalador
#   scripts/run_tests.sh integrity         # runner de integridad (perfil $LAIA_TEST_PROFILE, def. ci)
#   scripts/run_tests.sh frontend          # typecheck de las UIs
#   scripts/run_tests.sh gates             # doctrine-gates (supply-chain + no-secrets)
#
# Por qué wrapper — deriva local-vs-CI que cierra (tabla):
#   |                   | sin wrapper             | con wrapper                  |
#   | TZ / LANG         | los del host            | UTC / C.UTF-8 (como CI)      |
#   | LAIA_ROOT         | a veces sin definir     | raíz del repo (como ci.yml)  |
#   | INSTALLER_SKIP    | a mano                  | igual que ci.yml cuando CI=1 |
#   | perfil integrity  | a mano                  | `ci` por defecto (CI-safe)   |
#   | venv del backend  | el que toque            | el del repo; en worktrees,   |
#   |                   |                         |   cae al del checkout ppal.  |
# Las suites que no pueden correr aquí se reportan como SKIP con motivo (no silent cap).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8
export LAIA_ROOT="$REPO"

declare -a RESULTS=()
note() { RESULTS+=("$1"); echo ">>> $1"; }

run_backend() {
  # Worktrees no llevan el .venv (untracked): probar el del checkout principal.
  local py
  for py in "$REPO/services/agora-backend/.venv/bin/python" \
            "$HOME/LAIA/services/agora-backend/.venv/bin/python"; do
    [ -x "$py" ] && break
  done
  if [ ! -x "$py" ]; then
    note "SKIP backend — sin venv (ni en el repo ni en ~/LAIA); créalo o corre en el checkout principal"
    return 0
  fi
  if (cd "$REPO/services/agora-backend" && "$py" -m pytest tests/ -q "$@"); then
    note "PASS backend"
  else
    note "FAIL backend"; return 1
  fi
}

run_installer() {
  local skip="${INSTALLER_SKIP:-}"
  # Paridad ci.yml: en runner pelado se excluye el test que no es host-free.
  [ "${CI:-0}" = "1" ] && [ -z "$skip" ] && skip="test_install_native_layout.sh"
  if (cd "$REPO" && INSTALLER_SKIP="$skip" bash tests/installer/run_all.sh); then
    note "PASS installer"
  else
    note "FAIL installer"; return 1
  fi
}

run_integrity() {
  local profile="${LAIA_TEST_PROFILE:-ci}" ci_env="${CI:-}"
  [ "$profile" = "ci" ] && ci_env=1   # el perfil ci fuerza el subset sin-LXD (como en CI)
  if (cd "$REPO" && CI="$ci_env" tests/integration/run_integrity.sh --profile "$profile"); then
    note "PASS integrity (perfil $profile)"
  else
    note "FAIL integrity (perfil $profile)"; return 1
  fi
}

run_frontend() {
  if [ ! -d "$REPO/laia-ui/node_modules" ]; then
    note "SKIP frontend — laia-ui sin node_modules (npm install primero)"
    return 0
  fi
  if (cd "$REPO/laia-ui" \
      && npx tsc --noEmit -p packages/arch-app/tsconfig.json \
      && npx tsc --noEmit -p packages/agora-app/tsconfig.json); then
    note "PASS frontend (typecheck)"
  else
    note "FAIL frontend (typecheck)"; return 1
  fi
}

run_gates() {
  if [ ! -x "$REPO/scripts/check-supply-chain.sh" ]; then
    note "SKIP gates — scripts/check-*.sh no presentes en esta branch"
    return 0
  fi
  if "$REPO/scripts/check-supply-chain.sh" && "$REPO/scripts/check-no-secrets.sh"; then
    note "PASS gates (supply-chain + no-secrets)"
  else
    note "FAIL gates"; return 1
  fi
}

suite="${1:-all}"; shift || true
rc=0
case "$suite" in
  backend)   run_backend "$@" || rc=1 ;;
  installer) run_installer    || rc=1 ;;
  integrity) run_integrity    || rc=1 ;;
  frontend)  run_frontend     || rc=1 ;;
  gates)     run_gates        || rc=1 ;;
  all)
    run_gates     || rc=1
    run_installer || rc=1
    run_integrity || rc=1
    run_backend   || rc=1
    run_frontend  || rc=1
    ;;
  *) echo "Uso: scripts/run_tests.sh [all|backend|installer|integrity|frontend|gates]"; exit 2 ;;
esac

echo
echo "═══ resumen ═══"
printf '%s\n' "${RESULTS[@]}"
exit "$rc"
