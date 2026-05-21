#!/usr/bin/env bash
# Verify rebuild-3-provision-agora.sh rewrites agora_api_url in every
# pre-existing per-user state file (laia-state-<slug>.json) when the
# laia-agora container gets a fresh IP. Regression test for the gap
# detected on 2026-05-19 when chat-with-deployed.sh kept hitting the
# old IP after a rebuild.
#
# We don't run rebuild-3 end-to-end (it touches LXD); we extract just
# the state-refresh block and feed it controlled inputs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

STATE_DIR="$TMP/state"
mkdir -p "$STATE_DIR"

# Two stale user state files plus a non-matching file that must NOT change.
cat > "$STATE_DIR/laia-state-alice.json" <<'JSON'
{"slug":"alice","agora_api_url":"http://10.99.0.1:8000","other":"keep"}
JSON
cat > "$STATE_DIR/laia-state-bob.json" <<'JSON'
{"slug":"bob","agora_api_url":"http://10.99.0.1:8000"}
JSON
cat > "$STATE_DIR/other-file.json" <<'JSON'
{"agora_api_url":"http://10.99.0.1:8000"}
JSON

# Run the same block as rebuild-3, isolated.
CONTAINER_IP="10.99.0.99"
CONTAINER_PORT=8000
ORIG_USER="$(id -un)"
NEW_AGORA_URL="http://${CONTAINER_IP}:${CONTAINER_PORT}"

shopt -s nullglob
USER_STATE_FILES=( "$STATE_DIR"/laia-state-*.json )
shopt -u nullglob

for f in "${USER_STATE_FILES[@]}"; do
  tmp="$f.tmp.$$"
  jq --arg url "$NEW_AGORA_URL" '.agora_api_url = $url' "$f" > "$tmp"
  mv "$tmp" "$f"
done

# Assertions.
got_alice=$(jq -r .agora_api_url "$STATE_DIR/laia-state-alice.json")
got_bob=$(jq -r .agora_api_url "$STATE_DIR/laia-state-bob.json")
got_other=$(jq -r .agora_api_url "$STATE_DIR/other-file.json")

[[ "$got_alice" == "$NEW_AGORA_URL" ]] || { echo "alice not updated: $got_alice"; exit 1; }
[[ "$got_bob"   == "$NEW_AGORA_URL" ]] || { echo "bob not updated: $got_bob"; exit 1; }
[[ "$got_other" == "http://10.99.0.1:8000" ]] || { echo "other-file got touched: $got_other"; exit 1; }

# Non-target field preserved on alice.
keep=$(jq -r .other "$STATE_DIR/laia-state-alice.json")
[[ "$keep" == "keep" ]] || { echo "alice lost sibling field: $keep"; exit 1; }

# And the script itself must contain the refresh logic — guards against
# someone deleting the block but forgetting this test.
grep -q "agora_api_url = .url" "$ROOT/infra/lxd/scripts/rebuild-3-provision-agora.sh" \
  || { echo "rebuild-3 missing agora_api_url refresh block"; exit 1; }

echo "test_rebuild3_state_refresh.sh: ok"
