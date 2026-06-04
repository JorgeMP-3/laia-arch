#!/usr/bin/env bash
# Diagnose/setup packaging spec (ARCH-usable S2, 2026-06-04). Guards for
# problems.md::laia-diagnose-v020-degradado:
#   - vm-smoke.sh ships INSIDE the installed tree (infra/dev/), with a compat
#     shim at its legacy tests/installer/ path.
#   - The installer provisions the core venv WITH the install_wizard extra
#     (textual), so wizard/diagnose/setup get the full TUI.
#   - The diagnose flow looks for vm-smoke at the packaged path.
#   - vm-smoke resolves the AGORA API: explicit AGORA_API is probed (never a
#     green it did not check); without it, falls back to the container IP.
# Stub-based (fake lxc/curl on PATH): host-free, no network, CI-safe.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
SMOKE="$LAIA_ROOT/infra/dev/vm-smoke.sh"
SHIM="$LAIA_ROOT/tests/installer/vm-smoke.sh"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1)); printf '  PASS %s\n' "$desc"
  else
    FAIL=$((FAIL + 1)); FAILURES+=("$desc"); printf '  FAIL %s\n' "$desc"
  fi
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/laia-diagnose-pkg.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"

echo "-> empaquetado"
assert "vm-smoke.sh vive en infra/dev (arbol instalado)" \
  "$([[ -x "$SMOKE" ]] && echo 0 || echo 1)"
assert "shim de compatibilidad en tests/installer" \
  "$([[ -f "$SHIM" ]] && grep -q 'infra/dev/vm-smoke.sh' "$SHIM" && echo 0 || echo 1)"
assert "bash -n de ambos" \
  "$(bash -n "$SMOKE" && bash -n "$SHIM" && echo 0 || echo 1)"
assert "installer pide el extra install_wizard (textual) para el core venv" \
  "$(grep -q '_inst_pip_install_pkg .*\.laia-core" "install_wizard"' "$LAIA_ROOT/infra/installer/lib/install.sh" && echo 0 || echo 1)"
assert "diagnose.py busca vm-smoke en infra/dev" \
  "$(grep -q '"infra" / "dev" / "vm-smoke.sh"' "$LAIA_ROOT/.laia-core/laia_cli/install_wizard/flows/diagnose.py" && echo 0 || echo 1)"

# ── Stubs: lxc sano (container RUNNING, IP 10.1.2.3) y curl selectivo ──
cat > "$TMP/bin/lxc" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  info) exit 0 ;;
  list)
    if [[ "$*" == *"-c4"* ]]; then echo "10.1.2.3 (eth0)"; else echo "RUNNING"; fi
    exit 0 ;;
esac
exit 0
EOF
# curl stub: only the magic host 10.1.2.3:8000 (and AGORA_API=...good...) answer.
cat > "$TMP/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  [[ "$a" == *"10.1.2.3:8000"* || "$a" == *"good"* ]] && exit 0
done
exit 22
EOF
chmod +x "$TMP/bin/lxc" "$TMP/bin/curl"
STUB_PATH="$TMP/bin:$PATH"

echo
echo "-> resolución del API"
out="$(PATH="$STUB_PATH" AGORA_DB=/nonexistent bash "$SMOKE" 2>&1)"; rc=$?
assert "sin AGORA_API: cae a la IP del container (:8000)" \
  "$(grep -q '10.1.2.3:8000' <<<"$out" && echo 0 || echo 1)"

out="$(PATH="$STUB_PATH" AGORA_API="http://good:9" AGORA_DB=/nonexistent bash "$SMOKE" 2>&1)"; rc=$?
assert "AGORA_API explícito alcanzable: se usa" \
  "$([[ "$rc" -eq 0 ]] && grep -q 'http://good:9' <<<"$out" && echo 0 || echo 1)"

out="$(PATH="$STUB_PATH" AGORA_API="http://bad:9" AGORA_DB=/nonexistent bash "$SMOKE" 2>&1)"; rc=$?
assert "AGORA_API explícito INALCANZABLE: falla loud (no verde sin comprobar)" \
  "$([[ "$rc" -ne 0 ]] && grep -qi 'unreachable' <<<"$out" && echo 0 || echo 1)"

echo
echo "-> el shim ejecuta el script real"
out="$(PATH="$STUB_PATH" AGORA_API="http://good:9" AGORA_DB=/nonexistent bash "$SHIM" 2>&1)"; rc=$?
assert "shim → mismo comportamiento (exit 0 vía good)" \
  "$([[ "$rc" -eq 0 ]] && echo 0 || echo 1)"

echo
echo "=================================================="
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo; echo "Failures:"; printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
exit 0
