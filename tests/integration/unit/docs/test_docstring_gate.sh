#!/usr/bin/env bash
# integrity:id=docstring_gate
# integrity:name=T-DOC English docstring gate
# integrity:level=unit
# integrity:layers=host
# integrity:profiles=ci,host,vm
# integrity:requires=python3
# integrity:timeout=60
#
# T-DOC (Track T). Two parts:
#   1. Self-test: prove the checker flags a missing docstring and a Spanish
#      docstring, and accepts a clean English one (fixture-driven, hermetic).
#   2. Real gate: run the checker over the production roots against the
#      committed baseline and require exit 0 (no NEW violations).
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

require_cmds python3

CHECKER="$INTEGRITY_REPO_ROOT/tests/integration/lib/check_docstrings.py"
BASELINE="$INTEGRITY_REPO_ROOT/tests/integration/docstrings-baseline.txt"
assert_file "$CHECKER"
assert_file "$BASELINE"

# ── Part 1: self-test with synthetic fixtures ────────────────────────────────
FIX="$(mktemp -d "${TMPDIR:-/tmp}/laia-tdoc-selftest.XXXXXX")"
trap 'rm -rf "$FIX"' EXIT
mkdir -p "$FIX/pkg"

# A module with one undocumented public function and one Spanish docstring.
cat >"$FIX/pkg/dirty.py" <<'PY'
"""Fixture module with documentation gaps."""


def undocumented_public():
    return 1


def spanish_doc():
    """Devuelve el número de usuario para cada contenedor."""
    return 2
PY

# A clean module: English docstrings everywhere public.
cat >"$FIX/pkg/clean.py" <<'PY'
"""Fixture module that is fully documented in English."""


def documented():
    """Return a constant for the documented-path test."""
    return 3
PY

selftest_json="$FIX/report.json"
python3 "$CHECKER" --repo-root "$FIX" --root pkg --json "$selftest_json" >/dev/null 2>&1
rc=$?
[[ "$rc" == "1" ]] || integ_fail "self-test: checker should exit 1 on undocumented fixtures (got $rc)"

python3 - "$selftest_json" <<'PY' || integ_fail "self-test: report did not flag the expected violations"
import json
import sys

doc = json.load(open(sys.argv[1], encoding="utf-8"))
violations = doc["new_violations"]
keys = {(v["qualname"], v["reason"]) for v in violations}

assert ("undocumented_public", "missing") in keys, keys
assert ("spanish_doc", "non-english") in keys, keys
# The clean module must not produce any violation.
clean = [v for v in violations if v["path"].endswith("clean.py")]
assert clean == [], clean
PY

# A baseline that lists the two known fixture violations makes the gate pass.
cat >"$FIX/baseline.txt" <<'EOF'
pkg/dirty.py::function::undocumented_public::missing
pkg/dirty.py::function::spanish_doc::non-english
EOF
if python3 "$CHECKER" --repo-root "$FIX" --root pkg --baseline "$FIX/baseline.txt" >/dev/null 2>&1; then
  integ_info "self-test: baseline suppresses known violations"
else
  integ_fail "self-test: full baseline should make the gate exit 0"
fi

# A new undocumented symbol NOT in the baseline must still fail (ratchet works).
cat >>"$FIX/pkg/dirty.py" <<'PY'


def newly_added_public():
    return 4
PY
if python3 "$CHECKER" --repo-root "$FIX" --root pkg --baseline "$FIX/baseline.txt" >/dev/null 2>&1; then
  integ_fail "self-test: a new undocumented symbol must fail even with a baseline"
else
  integ_info "self-test: ratchet catches new violations not in baseline"
fi

# ── Part 2: real gate over the production roots ──────────────────────────────
if python3 "$CHECKER" --baseline "$BASELINE" >"$FIX/real.out" 2>&1; then
  integ_info "production docstring gate is green against the committed baseline"
else
  printf '%s\n' "$(cat "$FIX/real.out")" >&2
  integ_fail "production docstring gate found NEW violations (see above); add English docstrings"
fi

integ_info "T-DOC gate OK"
