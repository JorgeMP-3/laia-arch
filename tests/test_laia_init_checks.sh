#!/usr/bin/env bash
# Verify laia-init-checks.sh reports the expected statuses under controlled
# PATH overlays. Doesn't run anything destructive.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MOCK="$TMP/bin"
HOME_DIR="$TMP/home"
mkdir -p "$MOCK" "$HOME_DIR/.laia" "$TMP/srv-agora"

# Provide every tool the checks expect.
for tool in lxc jq curl python3 sudo; do
  cat > "$MOCK/$tool" <<SH
#!/usr/bin/env bash
exit 0
SH
  chmod +x "$MOCK/$tool"
done

# Case 1: auth.json present → exit 0, no warnings.
touch "$HOME_DIR/.laia/auth.json"
OUT="$TMP/out1"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
HOST_DATA_DIR="$TMP/srv-agora" \
bash "$ROOT/infra/dev/laia-init-checks.sh" >"$OUT" 2>&1
grep -q "LXD client" "$OUT" || { echo "missing LXD check"; cat "$OUT"; exit 1; }
grep -q "auth.json presente" "$OUT" || { echo "missing auth_json ok"; cat "$OUT"; exit 1; }

# Case 2: no auth.json → still exit 0 but warn.
rm "$HOME_DIR/.laia/auth.json"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
HOST_DATA_DIR="$TMP/srv-agora" \
bash "$ROOT/infra/dev/laia-init-checks.sh" >"$TMP/out2" 2>&1
grep -q "ausente" "$TMP/out2" || { echo "expected ausente warning"; cat "$TMP/out2"; exit 1; }

# Case 3: lxc missing → exit 1.
rm "$MOCK/lxc"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
HOST_DATA_DIR="$TMP/srv-agora" \
bash "$ROOT/infra/dev/laia-init-checks.sh" >"$TMP/out3" 2>&1 || RC=$?
RC="${RC:-0}"
if [[ "$RC" -ne 1 ]]; then
  echo "expected exit 1 when lxc missing, got $RC"; cat "$TMP/out3"; exit 1
fi
grep -q "LXD client no instalado" "$TMP/out3" || { echo "missing LXD blocker msg"; cat "$TMP/out3"; exit 1; }

# Case 4: --json mode emits a json object on stdout.
touch "$HOME_DIR/.laia/auth.json"
cat > "$MOCK/lxc" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$MOCK/lxc"
JSONOUT=$(PATH="$MOCK:/usr/bin:/bin" \
  HOME="$HOME_DIR" \
  AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
  HOST_DATA_DIR="$TMP/srv-agora" \
  bash "$ROOT/infra/dev/laia-init-checks.sh" --json)
echo "$JSONOUT" | grep -q '"lxd":"ok"' || { echo "json missing lxd ok: $JSONOUT"; exit 1; }

echo "test_laia_init_checks.sh: ok"
