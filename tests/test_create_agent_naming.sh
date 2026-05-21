#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MOCK="$TMP/bin"
USER_ROOT="$TMP/users"
mkdir -p "$MOCK" "$USER_ROOT/jorge-dev/home" "$USER_ROOT/jorge-dev/plugins" "$USER_ROOT/jorge-dev/workspace"

cat > "$MOCK/lxc" <<'SH'
#!/usr/bin/env bash
case "$*" in
  "info agent-jorge-dev") exit 1;;
  "profile show laia-employee") exit 0;;
  "image info laia-agent") exit 0;;
  init\ laia-agent\ agent-jorge-dev*) exit 0;;
  "start agent-jorge-dev") exit 0;;
  "list agent-jorge-dev --format=csv -c4") echo "10.99.0.42"; exit 0;;
  config\ device\ add\ agent-jorge-dev*) exit 0;;
  exec\ agent-jorge-dev\ --*) cat >/dev/null || true; exit 0;;
esac
exit 0
SH
chmod +x "$MOCK/lxc"

cat > "$MOCK/curl" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$MOCK/curl"

OUT="$(
  PATH="$MOCK:/usr/bin:/bin" \
  HOST_USER_ROOT="$USER_ROOT" \
  bash "$ROOT/infra/lxd/scripts/create-agent.sh" jorge-dev laia-agent
)"

JSON="$(printf '%s\n' "$OUT" | tail -1)"
printf '%s' "$JSON" | jq -e '.slug == "jorge-dev" and .container == "agent-jorge-dev" and .ipv4 == "10.99.0.42" and .api_port == 9091' >/dev/null
echo "test_create_agent_naming.sh: ok"
