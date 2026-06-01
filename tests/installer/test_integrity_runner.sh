#!/usr/bin/env bash
# Regression guard for tests/integration/run_integrity.sh. Uses a synthetic
# test root so it never depends on LXD or the live ecosystem.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
RUNNER="$LAIA_ROOT/tests/integration/run_integrity.sh"

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

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-integrity-runner.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
ROOT="$TMPDIR_TEST/tests"
mkdir -p "$ROOT"

cat >"$ROOT/test_fast_ci.sh" <<'SH'
#!/usr/bin/env bash
# integrity:id=fast_ci
# integrity:name=Fast CI contract
# integrity:level=unit
# integrity:layers=host
# integrity:profiles=ci,host,vm
printf 'fast ok\n'
exit 0
SH
chmod +x "$ROOT/test_fast_ci.sh"

cat >"$ROOT/test_host_only.sh" <<'SH'
#!/usr/bin/env bash
# integrity:id=host_only
# integrity:name=Host only contract
# integrity:level=integration
# integrity:layers=lxd
# integrity:profiles=host,vm
# integrity:requires=lxd
printf 'should not run in ci\n'
exit 0
SH
chmod +x "$ROOT/test_host_only.sh"

echo "→ CI profile selects fast tests and reports host-only skips"
if "$RUNNER" --root "$ROOT" --profile ci --json "$TMPDIR_TEST/ci.json" >"$TMPDIR_TEST/ci.out" 2>&1; then
  assert "runner exits 0 when selected CI tests pass" 0
else
  assert "runner exits 0 when selected CI tests pass" 1
fi

if python3 - "$TMPDIR_TEST/ci.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
tests = {t["id"]: t for t in doc["tests"]}
assert doc["profile"] == "ci"
assert doc["summary"]["passed"] == 1, doc["summary"]
assert doc["summary"]["skipped"] == 1, doc["summary"]
assert doc["summary"]["failed"] == 0, doc["summary"]
assert tests["fast_ci"]["status"] == "pass"
assert tests["host_only"]["status"] == "skip"
assert "profile" in tests["host_only"]["reason"]
PY
then
  assert "CI JSON report has pass/skip taxonomy" 0
else
  assert "CI JSON report has pass/skip taxonomy" 1
fi

cat >"$ROOT/test_fails_ci.sh" <<'SH'
#!/usr/bin/env bash
# integrity:id=fails_ci
# integrity:name=Failing CI contract
# integrity:level=unit
# integrity:layers=host
# integrity:profiles=ci
printf 'intentional failure\n' >&2
exit 7
SH
chmod +x "$ROOT/test_fails_ci.sh"

echo
echo "→ Failing selected test makes runner exit non-zero"
set +e
"$RUNNER" --root "$ROOT" --profile ci --json "$TMPDIR_TEST/fail.json" >"$TMPDIR_TEST/fail.out" 2>&1
rc=$?
set -e
assert "runner exits 1 when any selected test fails (got $rc)" \
  "$([[ "$rc" == "1" ]] && echo 0 || echo 1)"

if python3 - "$TMPDIR_TEST/fail.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
tests = {t["id"]: t for t in doc["tests"]}
assert doc["summary"]["failed"] == 1, doc["summary"]
assert tests["fails_ci"]["status"] == "fail"
assert tests["fails_ci"]["exit_code"] == 7
assert "intentional failure" in tests["fails_ci"]["stderr"]
PY
then
  assert "failure JSON preserves exit code and stderr" 0
else
  assert "failure JSON preserves exit code and stderr" 1
fi

rm -f "$ROOT/test_fails_ci.sh"
cat >"$ROOT/test_skips_ci.sh" <<'SH'
#!/usr/bin/env bash
# integrity:id=skips_ci
# integrity:name=Skipping CI contract
# integrity:level=unit
# integrity:layers=host
# integrity:profiles=ci
printf 'not applicable here\n'
exit 77
SH
chmod +x "$ROOT/test_skips_ci.sh"

echo
echo "→ Test-requested skip is reported as skip, not pass"
if "$RUNNER" --root "$ROOT" --profile ci --json "$TMPDIR_TEST/skip.json" >"$TMPDIR_TEST/skip.out" 2>&1; then
  assert "runner exits 0 when selected tests pass or skip" 0
else
  assert "runner exits 0 when selected tests pass or skip" 1
fi

if python3 - "$TMPDIR_TEST/skip.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
tests = {t["id"]: t for t in doc["tests"]}
assert doc["summary"]["passed"] == 1, doc["summary"]
assert doc["summary"]["runtime_skipped"] == 1, doc["summary"]
assert tests["skips_ci"]["status"] == "skip"
assert tests["skips_ci"]["exit_code"] == 77
assert tests["skips_ci"]["reason"] == "test requested skip"
PY
then
  assert "skip JSON preserves exit 77 and reason" 0
else
  assert "skip JSON preserves exit 77 and reason" 1
fi

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  echo
  echo "Runner output:"
  cat "$TMPDIR_TEST/ci.out" "$TMPDIR_TEST/fail.out" 2>/dev/null || true
  exit 1
fi
exit 0
