#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_systemd_render.sh
#
# Verifies the envsubst-based systemd template rendering:
#   - Every LAIA_* placeholder gets substituted with the expected value.
#   - No literal ${LAIA_*} remains in the rendered output.
#   - Other $-vars in Environment= lines (e.g. $HOME) are PRESERVED so systemd
#     can expand them at runtime (envsubst with explicit list, not bare).
#
# Tests each template under infra/installer/systemd/*.service.tmpl.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"

export LAIA_LOG_FILE="$(mktemp)"
export NO_COLOR=1

# shellcheck source=../../infra/installer/lib/common.sh
source "$LIB/common.sh"
# shellcheck source=../../infra/installer/lib/sudo.sh
source "$LIB/sudo.sh"

# shellcheck source=../../infra/installer/lib/install.sh
source "$LIB/install.sh"
# shellcheck source=../../infra/installer/lib/systemd.sh
source "$LIB/systemd.sh"

# Set test values AFTER sourcing install.sh (which resets these globals).
# systemd.sh reads LAIA_USER and LAIA_USER_HOME from the environment, plus
# DATA_DIR + INST_PREFIX as install.sh globals.
LAIA_USER="testuser"
LAIA_USER_HOME="/home/testuser"
DATA_DIR="/home/testuser/LAIA-ARCH"
INST_PREFIX="/opt/laia"
export LAIA_USER LAIA_USER_HOME

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc")
    printf '  ✗ %s\n' "$desc"
  fi
}

# ── Pre-check: envsubst available ──────────────────────────────────────────
if ! command -v envsubst >/dev/null 2>&1; then
  echo "✗ envsubst not installed; skipping (install with: apt install gettext-base)"
  exit 0
fi

TMP_OUT="$(mktemp)"
trap 'rm -f "$TMP_OUT" "$LAIA_LOG_FILE"' EXIT

# ── List templates ─────────────────────────────────────────────────────────
TEMPLATE_DIR="$(systemd_template_dir)"
echo "→ Templates discovered:"
mapfile -t TEMPLATES < <(find "$TEMPLATE_DIR" -maxdepth 1 -type f -name '*.service.tmpl' | sort)
for t in "${TEMPLATES[@]}"; do
  printf '    %s\n' "$(basename "$t")"
done

assert "at least one template exists" \
  "$([[ "${#TEMPLATES[@]}" -ge 1 ]] && echo 0 || echo 1)"

# ── Per-template assertions ────────────────────────────────────────────────
for tmpl in "${TEMPLATES[@]}"; do
  name="$(basename "$tmpl" .tmpl)"
  echo
  echo "→ Render: $name"

  systemd_render "$tmpl" "$TMP_OUT"
  assert "  render exits 0" "$?"
  assert "  output file exists and non-empty" \
    "$([[ -s "$TMP_OUT" ]] && echo 0 || echo 1)"

  # Substituted variables — check by direct match (each appears at least once).
  if grep -q '\${LAIA_USER}' "$tmpl"; then
    assert "  \${LAIA_USER} substituted to '$LAIA_USER'" \
      "$(grep -q "$LAIA_USER" "$TMP_OUT" && echo 0 || echo 1)"
  fi
  if grep -q '\${LAIA_USER_HOME}' "$tmpl"; then
    assert "  \${LAIA_USER_HOME} substituted to '$LAIA_USER_HOME'" \
      "$(grep -q "$LAIA_USER_HOME" "$TMP_OUT" && echo 0 || echo 1)"
  fi
  if grep -q '\${LAIA_HOME}' "$tmpl"; then
    assert "  \${LAIA_HOME} substituted to '$DATA_DIR'" \
      "$(grep -q "$DATA_DIR" "$TMP_OUT" && echo 0 || echo 1)"
  fi
  if grep -q '\${LAIA_INSTALL_PREFIX}' "$tmpl"; then
    assert "  \${LAIA_INSTALL_PREFIX} substituted to '$INST_PREFIX'" \
      "$(grep -q "$INST_PREFIX" "$TMP_OUT" && echo 0 || echo 1)"
  fi

  # No leftover LAIA placeholders.
  assert "  no leftover \${LAIA_*} in rendered output" \
    "$(! grep -q '\${LAIA_' "$TMP_OUT" && echo 0 || echo 1)"
done

# ── Variable list contains exactly the four documented vars ────────────────
echo
echo "→ LAIA_SYSTEMD_VARS sanity"
assert "LAIA_SYSTEMD_VARS contains LAIA_USER" \
  "$(grep -q 'LAIA_USER' <<<"$LAIA_SYSTEMD_VARS" && echo 0 || echo 1)"
assert "LAIA_SYSTEMD_VARS contains LAIA_USER_HOME" \
  "$(grep -q 'LAIA_USER_HOME' <<<"$LAIA_SYSTEMD_VARS" && echo 0 || echo 1)"
assert "LAIA_SYSTEMD_VARS contains LAIA_HOME" \
  "$(grep -q 'LAIA_HOME' <<<"$LAIA_SYSTEMD_VARS" && echo 0 || echo 1)"
assert "LAIA_SYSTEMD_VARS contains LAIA_INSTALL_PREFIX" \
  "$(grep -q 'LAIA_INSTALL_PREFIX' <<<"$LAIA_SYSTEMD_VARS" && echo 0 || echo 1)"

# ── Targeted: preservation of $-vars NOT in the substitution list ──────────
# Create a synthetic template that contains both a known LAIA var and a non-LAIA
# $-var; verify only the LAIA one is substituted.
echo
echo "→ Preservation of non-LAIA \$-variables"

SYNTH_IN="$(mktemp)"
SYNTH_OUT="$(mktemp)"
cat >"$SYNTH_IN" <<'EOF'
[Service]
Environment=HOME=$HOME
Environment=PATH=$PATH:/extra
WorkingDirectory=${LAIA_INSTALL_PREFIX}/sub
EOF

systemd_render "$SYNTH_IN" "$SYNTH_OUT"

assert "LAIA_INSTALL_PREFIX substituted in synthetic template" \
  "$(grep -q 'WorkingDirectory=/opt/laia/sub' "$SYNTH_OUT" && echo 0 || echo 1)"
assert "literal \$HOME preserved (not substituted to current shell HOME)" \
  "$(grep -q 'HOME=\$HOME' "$SYNTH_OUT" && echo 0 || echo 1)"
assert "literal \$PATH preserved" \
  "$(grep -q '\$PATH:/extra' "$SYNTH_OUT" && echo 0 || echo 1)"

rm -f "$SYNTH_IN" "$SYNTH_OUT"

# ── Summary ────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  exit 1
fi
exit 0
