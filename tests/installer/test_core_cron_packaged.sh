#!/usr/bin/env bash
# Guard for PROBLEMS.md::laia-core-cron-package-gitignored-lost-in-migration:
# the .laia-core/cron package is PRODUCT CODE and must (a) be present in every
# checkout — so `laia release` ships it natively, no .pth workarounds — and
# (b) never be re-swallowed by the wholesale .laia-core/ gitignore (that is
# exactly how it got lost in the laia-hermes -> laia-arch migration).
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

echo "-> el paquete cron viaja en el checkout (release lo incluye nativo)"
for f in __init__.py jobs.py scheduler.py; do
  assert "cron/$f presente" \
    "$([[ -f "$LAIA_ROOT/.laia-core/cron/$f" ]] && echo 0 || echo 1)"
done

echo
echo "-> el gitignore ya no se traga ficheros nuevos del paquete"
if command -v git >/dev/null 2>&1 && git -C "$LAIA_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  if git -C "$LAIA_ROOT" check-ignore -q .laia-core/cron/some_new_module.py 2>/dev/null; then
    assert "fichero NUEVO en .laia-core/cron NO ignorado" 1
  else
    assert "fichero NUEVO en .laia-core/cron NO ignorado" 0
  fi
else
  printf '  SKIP check-ignore (sin git/repo en este entorno)\n'
fi

echo
echo "=================================================="
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo; echo "Failures:"; printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
exit 0
