#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MOCK="$TMP/bin"
HOME_DIR="$TMP/home"
REPO="$TMP/repo"
STATE="$HOME_DIR/.laia/state"
mkdir -p "$MOCK" "$HOME_DIR/.laia" "$STATE" "$REPO/.git" "$TMP/srv-agora"
touch "$HOME_DIR/.laia/auth.json"
chmod 644 "$HOME_DIR/.laia/auth.json"
chmod 755 "$TMP/srv-agora"

cat > "$MOCK/lxc" <<'SH'
#!/usr/bin/env bash
if [[ "$1 $2 $3" == "image info laia-agora" ]]; then
  cat <<EOF
Timestamps:
    Created: 1970/01/01 00:10 UTC
    Uploaded: 1970/01/01 00:10 UTC
EOF
  exit 0
fi
if [[ "$1 $2" == "info laia-agora" ]]; then
  exit 0
fi
exit 0
SH
cat > "$MOCK/git" <<'SH'
#!/usr/bin/env bash
echo 2000
SH
cat > "$MOCK/systemctl" <<'SH'
#!/usr/bin/env bash
echo inactive
SH
cat > "$MOCK/pm2" <<'SH'
#!/usr/bin/env bash
echo '[]'
SH
cat > "$MOCK/ss" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$MOCK/"*

OUT="$TMP/preflight.out"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
LAIA_ROOT="$REPO" \
LAIA_STATE_DIR="$STATE" \
HOST_DATA_DIR="$TMP/srv-agora" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
LAIA_EXPECTED_OWNER="$(id -un):$(id -gn)" \
bash "$ROOT/infra/dev/preflight.sh" >"$OUT" 2>&1

grep -q "imagen desactualizada" "$OUT"
grep -q "laia-agora existe pero falta" "$OUT"
echo "test_preflight.sh: ok"
