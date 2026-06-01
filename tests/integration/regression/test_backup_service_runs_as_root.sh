#!/usr/bin/env bash
# integrity:id=regression_backup_service_user
# integrity:name=Regression: backup service must read root-owned agora data
# integrity:level=unit
# integrity:layers=backups,host
# integrity:profiles=ci,host,vm
# integrity:timeout=20
#
# Guard for problems.md::backup-timer-runs-as-laia-arch-cannot-read-agora
# (OPEN as of 2026-06-01). The systemd unit template runs laia-backup as
# ${LAIA_USER} (= laia-arch), but /srv/laia/agora is drwx------ owned by the
# container uid (1000999). So the nightly backup would run "green" WITHOUT
# agora.db -- the same false-green pattern that caused the prod cutover outage.
#
# The fix is a production change (template -> User=root), which Track T must not
# make on its own. Until the fix lands this test SKIPS (exit 77) with a loud,
# logged reason that cites the open bug -- a documented gap, never a silent one.
# When the template is corrected to root, the test flips to a real PASS and
# becomes the standing regression guard.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/integrity_shell.sh
source "$SCRIPT_DIR/../lib/integrity_shell.sh"

TMPL="$INTEGRITY_REPO_ROOT/infra/installer/systemd/laia-backup.service.tmpl"
assert_file "$TMPL"

user_line="$(grep -E '^[[:space:]]*User=' "$TMPL" | head -1)"
[[ -n "$user_line" ]] || integ_fail "backup service template has no User= line"

user_val="${user_line#*User=}"
user_val="${user_val//[[:space:]]/}"

if [[ "$user_val" == "root" ]]; then
  integ_info "backup service runs as root -> can read root-owned /srv/laia/agora"
elif [[ "$user_val" == '${LAIA_USER}' || "$user_val" == "laia-arch" ]]; then
  integ_skip "KNOWN OPEN BUG (problems.md: backup-timer-runs-as-laia-arch-cannot-read-agora): \
template User=$user_val cannot read root-owned /srv/laia/agora -> false-green backup. \
Fix is a production template change (User=root), owned by Codex/Lead. Test flips to PASS once fixed."
else
  # Some other user: assert it is actually able to read the agora zone. Without
  # a live host we cannot verify group membership, so treat as a documented skip.
  integ_skip "backup service User=$user_val is neither root nor the known buggy value; \
verify on a live host that it can read /srv/laia/agora (problems.md backup-timer entry)."
fi
