#!/usr/bin/env bash
# Exercise laia-init.sh in --dry-run + --non-interactive modes. Verify the
# wizard:
#   (a) prints the section banners in order
#   (b) does NOT touch lxc / sudo when --dry-run is active
#   (c) fails when --non-interactive is requested without required env vars

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MOCK="$TMP/bin"
HOME_DIR="$TMP/home"
mkdir -p "$MOCK" "$HOME_DIR/.laia" "$TMP/srv-agora"
touch "$HOME_DIR/.laia/auth.json"

for tool in lxc jq curl python3 sudo; do
  cat > "$MOCK/$tool" <<SH
#!/usr/bin/env bash
echo "[mock-$tool] should not be called in --dry-run" >&2
exit 0
SH
  chmod +x "$MOCK/$tool"
done

# Case 1: --dry-run --non-interactive with all env vars → exit 0, banners present.
OUT="$TMP/out1"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
LAIA_ROOT="$ROOT" \
HOST_DATA_DIR="$TMP/srv-agora" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
AGORA_ADMIN_USERNAME=jorge \
AGORA_ADMIN_PASSWORD=secret \
AGORA_LLM_PROVIDER=openai-codex \
AGORA_FIRST_SLUG=jorge-dev \
bash "$ROOT/infra/dev/laia-init.sh" --dry-run --non-interactive \
    >"$OUT" 2>&1 || { echo "expected exit 0 in dry-run"; cat "$OUT"; exit 1; }
for needle in "1/8 Preflight" "2/8 LXD" "4/8 Configuración" "5/8 Build" "8/8 Verificación"; do
  grep -q "$needle" "$OUT" || { echo "missing section: $needle"; cat "$OUT"; exit 1; }
done
grep -qF "[dry-run]" "$OUT" || { echo "missing dry-run markers"; cat "$OUT"; exit 1; }
grep -q "Listo" "$OUT" || { echo "wizard didn't finish"; cat "$OUT"; exit 1; }
# Regression: ANSI escapes must NOT leak as literal text. If '\033' appears
# in the output, color codes are being stringified instead of rendered.
if grep -qF '\033' "$OUT"; then
  echo "FAIL: literal ANSI escape sequences in wizard output"
  cat "$OUT"; exit 1
fi

# Case 2: --non-interactive without required env vars → exit 1.
OUT="$TMP/out2"
set +e
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
LAIA_ROOT="$ROOT" \
HOST_DATA_DIR="$TMP/srv-agora" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
AGORA_ADMIN_USERNAME="" \
AGORA_ADMIN_PASSWORD="" \
AGORA_LLM_PROVIDER="" \
AGORA_FIRST_SLUG="" \
bash "$ROOT/infra/dev/laia-init.sh" --dry-run --non-interactive \
    >"$OUT" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "expected exit 1, got $RC"; cat "$OUT"; exit 1; }
grep -q "requerido en modo" "$OUT" || { echo "missing missing-env error"; cat "$OUT"; exit 1; }

# Case 3: with telegram token, dry-run should mention the .env write.
OUT="$TMP/out3"
PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
LAIA_ROOT="$ROOT" \
HOST_DATA_DIR="$TMP/srv-agora" \
AUTH_JSON_HOST="$HOME_DIR/.laia/auth.json" \
AGORA_ADMIN_USERNAME=jorge \
AGORA_ADMIN_PASSWORD=secret \
AGORA_LLM_PROVIDER=openai-codex \
AGORA_FIRST_SLUG=jorge-dev \
AGORA_TELEGRAM_TOKEN=fake:token \
bash "$ROOT/infra/dev/laia-init.sh" --dry-run --non-interactive \
    >"$OUT" 2>&1 || { echo "expected exit 0 with token"; cat "$OUT"; exit 1; }
grep -q "escribiría TELEGRAM_TOKEN" "$OUT" || {
  echo "wizard didn't announce .env write"; cat "$OUT"; exit 1; }

echo "test_laia_init.sh: ok"
