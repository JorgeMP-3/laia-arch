#!/usr/bin/env bash
# integrity:id=regression_backend_hardcoded_plugin_paths
# integrity:name=Regression: backend tests must not hardcode dev-host plugin paths
# integrity:level=unit
# integrity:layers=agora,host
# integrity:profiles=ci,host,vm
# integrity:requires=git
# integrity:timeout=30
#
# Regression for problems.md::backend-tests-hardcodean-ruta-de-plugins-del-host-de-dev
# (resolved 2026-05-30). Six backend tests used to load their plugin from the
# dev host's absolute path (.../LAIA/.laia-core/plugins/<X>/__init__.py), which
# is gitignored and absent in a clean checkout -> green locally, FileNotFoundError
# in CI. The fix routes plugin resolution through tests/_laia_core.py. This guard
# fails if any tracked test source reintroduces such an absolute host path.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/integrity_shell.sh
source "$SCRIPT_DIR/../lib/integrity_shell.sh"

require_cmds git
cd "$INTEGRITY_REPO_ROOT" || integ_fail "cannot cd to repo root"

# Absolute home path that points into a checkout's .laia-core (the smell). We
# match /home/<user>/.../.laia-core or /Users/<user>/.../.laia-core inside test
# files. The portable helper uses LAIA_ROOT / __file__, never an absolute home.
PATTERN='(/home/[^"'"'"' ]+|/Users/[^"'"'"' ]+)/\.laia-core/'

# Scan tracked Python test files under services/ (where the bug lived).
mapfile -t hits < <(git grep -nE "$PATTERN" -- 'services/**/tests/**/*.py' 2>/dev/null)

if [[ "${#hits[@]}" -gt 0 ]]; then
  printf 'FAIL: hardcoded dev-host .laia-core path(s) in backend tests:\n' >&2
  printf '  %s\n' "${hits[@]}" >&2
  integ_fail "use tests/_laia_core.py to resolve plugins portably (see problems.md)"
fi

# Belt and braces: the portable helper must still exist.
assert_file "$INTEGRITY_REPO_ROOT/services/agora-backend/tests/_laia_core.py"

integ_info "no hardcoded dev-host plugin paths in backend tests"
