#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/test_ci_workflow.sh
#
# Guard del CI (Track B · B1): verifica que .github/workflows/ci.yml sigue
# alineado con la realidad del repo. No corre el workflow (eso lo hace GitHub);
# protege contra drift silencioso:
#   - que el job de backend siga apuntando a services/agora-backend + pytest,
#   - que el job installer siga llamando a un run_all.sh que EXISTE,
#   - que el floor de Python del CI == el floor real del installer
#     (require_python_min), para que el CI no deje de probar la mínima soportada,
#   - que el SKIP de D2 (LXD) quede documentado (no silent cap).
#
# Host-free: sólo lee ficheros. Run:
#   bash tests/test_ci_workflow.sh
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/.." && pwd)"
CI="$LAIA_ROOT/.github/workflows/ci.yml"
README="$LAIA_ROOT/.github/workflows/README.md"

PASS=0
FAIL=0
FAILURES=()

assert_true() {
  local desc="$1"; shift
  if "$@"; then
    PASS=$((PASS + 1)); printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1)); FAILURES+=("$desc"); printf '  ✗ %s\n' "$desc"
  fi
}

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1)); printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc — expected '$expected', got '$actual'")
    printf '  ✗ %s (expected %s, got %s)\n' "$desc" "$expected" "$actual"
  fi
}

echo "→ Workflow file presente y bien formado"
assert_true "ci.yml existe" test -f "$CI"
assert_true "README de workflows existe" test -f "$README"
assert_true "se dispara en PR a main" grep -q 'pull_request:' "$CI"
assert_true "rama main como target" grep -Eq 'branches:\s*\[main\]' "$CI"
assert_true "permisos read-only (contents: read)" grep -q 'contents: read' "$CI"

echo
echo "→ Job backend coherente con el repo"
assert_true "apunta a services/agora-backend" grep -q 'services/agora-backend' "$CI"
assert_true "corre pytest" grep -q 'pytest tests/' "$CI"
assert_true "instala requirements.txt" grep -q 'requirements.txt' "$CI"
assert_true "el dir agora-backend existe" test -d "$LAIA_ROOT/services/agora-backend"
assert_true "requirements.txt existe" test -f "$LAIA_ROOT/services/agora-backend/requirements.txt"

echo
echo "→ Job backend resuelve workspace_store vía LAIA_ROOT"
assert_true "backend exporta LAIA_ROOT" grep -q 'LAIA_ROOT:' "$CI"

echo
echo "→ Job installer coherente con el repo"
assert_true "llama a tests/installer/run_all.sh" grep -q 'tests/installer/run_all.sh' "$CI"
assert_true "run_all.sh existe y es ejecutable por bash" test -f "$LAIA_ROOT/tests/installer/run_all.sh"

echo
echo "→ Exclusión de tests no-host-free documentada (no silent cap)"
assert_true "ci.yml usa INSTALLER_SKIP" grep -q 'INSTALLER_SKIP:' "$CI"
assert_true "run_all.sh soporta INSTALLER_SKIP" \
  grep -q 'INSTALLER_SKIP' "$LAIA_ROOT/tests/installer/run_all.sh"
assert_true "ci.yml nombra los 2 tests excluidos (native_layout)" \
  grep -q 'test_install_native_layout.sh' "$CI"
assert_true "ci.yml nombra los 2 tests excluidos (clone_hardening)" \
  grep -q 'test_clone_hardening.sh' "$CI"
assert_true "README documenta la exclusión" \
  grep -q 'INSTALLER_SKIP' "$README"

echo
echo "→ Floor de Python del CI == floor real del installer (anti-drift)"
# Floor declarado por el installer (p.ej. 'require_python_min 3.11').
floor_real="$(grep -rhoE 'require_python_min[[:space:]]+[0-9]+\.[0-9]+' \
  "$LAIA_ROOT/infra/installer/lib/" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)"
assert_true "se encontró require_python_min en el installer" test -n "$floor_real"
assert_true "el CI incluye el floor real ($floor_real) en la matriz" \
  grep -q "'$floor_real'" "$CI"

echo
echo "→ SKIP de D2 documentado (no silent cap)"
assert_true "ci.yml menciona el SKIP de D2/integrity" \
  grep -q 'test_ecosystem_integrity.sh' "$CI"
assert_true "ci.yml justifica el SKIP con LXD" grep -qi 'LXD' "$CI"
assert_true "README documenta el SKIP de D2" \
  grep -q 'test_ecosystem_integrity.sh' "$README"

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
