#!/usr/bin/env bash
# Dispatcher passthrough spec (ARCH-usable S1, 2026-06-04):
#   - `laia <non-host-op>` forwards verbatim to the .laia-core Python CLI
#     (python -m laia_cli.main <args>) — chat, setup, login, model, skills, …
#   - `laia` with NO args drops into the agent CLI (interactive chat).
#   - Host-op subcommands (status, install, …) keep their precedence.
#   - `laia --help` stays on the dispatcher (never forwarded).
#   - Missing .laia-core/laia_cli → clear error, exit 4.
# Guard for problems.md::dispatcher-v020-sin-passthrough-al-cli-python.
# Stub-based: copies bin/laia into a tmp tree with a fake venv python, so it
# runs host-free (no laia-core deps, no network) — CI-safe.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"

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

TMP="$(mktemp -d "${TMPDIR:-/tmp}/laia-dispatcher.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# Minimal tree the dispatcher expects around itself.
mkdir -p "$TMP/bin" "$TMP/infra/installer/lib" "$TMP/.laia-core/laia_cli" \
         "$TMP/.laia-core/venv/bin"
cp "$LAIA_ROOT/bin/laia" "$TMP/bin/laia"
cp "$LAIA_ROOT/infra/installer/lib/common.sh" "$TMP/infra/installer/lib/"
cp "$LAIA_ROOT/infra/installer/lib/version.sh" "$TMP/infra/installer/lib/"

# Stub venv python: prints how it was invoked and exits 0.
cat > "$TMP/.laia-core/venv/bin/python" <<'EOF'
#!/usr/bin/env bash
echo "STUB-PY $*"
EOF
chmod +x "$TMP/.laia-core/venv/bin/python"

# Stub host-op binary to verify precedence.
cat > "$TMP/bin/laia-status" <<'EOF'
#!/usr/bin/env bash
echo "HOST-OP status $*"
EOF
chmod +x "$TMP/bin/laia-status"

echo "-> forwarding de subcomandos del agente"
out="$("$TMP/bin/laia" setup --help 2>&1)"
assert "laia setup → python -m laia_cli.main setup" \
  "$(grep -q '^STUB-PY -m laia_cli.main setup --help$' <<<"$out" && echo 0 || echo 1)"

out="$("$TMP/bin/laia" chat hola mundo 2>&1)"
assert "laia chat <args> → forwarded verbatim" \
  "$(grep -q '^STUB-PY -m laia_cli.main chat hola mundo$' <<<"$out" && echo 0 || echo 1)"

out="$("$TMP/bin/laia" skills list 2>&1)"
assert "laia skills → forwarded" \
  "$(grep -q '^STUB-PY -m laia_cli.main skills list$' <<<"$out" && echo 0 || echo 1)"

echo
echo "-> sin args → agent CLI (chat interactivo)"
out="$("$TMP/bin/laia" </dev/null 2>&1)"
assert "laia (no args) → python -m laia_cli.main" \
  "$(grep -q '^STUB-PY -m laia_cli.main$' <<<"$out" && echo 0 || echo 1)"

echo
echo "-> precedencia de host-ops intacta"
out="$("$TMP/bin/laia" status 2>&1)"
assert "laia status → laia-status (host-op, no forwarded)" \
  "$(grep -q '^HOST-OP status' <<<"$out" && echo 0 || echo 1)"

out="$("$TMP/bin/laia" --help 2>&1)"
assert "laia --help → dispatcher help (no forwarded)" \
  "$(grep -q 'USAGE' <<<"$out" && ! grep -q 'STUB-PY' <<<"$out" && echo 0 || echo 1)"

echo
echo "-> sin .laia-core → error claro, exit 4"
rm -rf "$TMP/.laia-core/laia_cli"
"$TMP/bin/laia" setup >/dev/null 2>"$TMP/err.txt"; rc=$?
assert "exit 4 cuando falta laia_cli" "$([[ "$rc" -eq 4 ]] && echo 0 || echo 1)"
assert "el error menciona cómo recuperar (install/release)" \
  "$(grep -qi 'install' "$TMP/err.txt" && echo 0 || echo 1)"

echo
echo "=================================================="
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo; echo "Failures:"; printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
exit 0
