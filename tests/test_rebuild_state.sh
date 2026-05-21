#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MOCK="$TMP/bin"
HOME_DIR="$TMP/home"
STATE="$HOME_DIR/.laia/state"
mkdir -p "$MOCK" "$STATE"

cat > "$MOCK/lxc" <<'SH'
#!/usr/bin/env bash
if [[ "$1 $2" == "info laia-agora" ]]; then
  exit 0
fi
if [[ "$1" == "list" && "$3" == "-c" ]]; then
  [[ "$2" == "agent-jorge-dev" ]] && echo RUNNING || echo RUNNING
  exit 0
fi
if [[ "$1" == "list" && "$3" == "--format" ]]; then
  if [[ "$2" == "laia-agora" ]]; then
    echo '[{"state":{"network":{"eth0":{"addresses":[{"family":"inet","address":"10.99.0.96"}]}}}}]'
  else
    echo '[{"state":{"network":{"eth0":{"addresses":[{"family":"inet","address":"10.99.0.105"}]}}}}]'
  fi
  exit 0
fi
if [[ "$1 $2 $3" == "config show laia-agora" ]]; then
  cat <<EOF
devices:
  agora-api:
    connect: tcp:127.0.0.1:8000
    listen: tcp:0.0.0.0:8088
    type: proxy
  agora-auth:
    source: /home/laia-hermes/.laia/auth.json
    type: disk
  agora-data:
    source: /srv/laia/agora
    type: disk
EOF
  exit 0
fi
if [[ "$1 $2 $3" == "exec laia-agora --" ]]; then
  printf 'jorge-dev\tuser_jorge-dev\tagent_abc\tagent-jorge-dev\t10.99.0.105\ttok123\n'
  exit 0
fi
if [[ "$1 $2 $3" == "exec agent-jorge-dev --" ]]; then
  echo 9091
  exit 0
fi
exit 0
SH
chmod +x "$MOCK/lxc"

PATH="$MOCK:/usr/bin:/bin" \
HOME="$HOME_DIR" \
LAIA_STATE_DIR="$STATE" \
LAIA_ROOT="$TMP/repo" \
bash "$ROOT/infra/dev/rebuild-state.sh" >"$TMP/rebuild-state.out" 2>&1

test -f "$STATE/laia-agora-state.json"
test -f "$STATE/laia-state-jorge-dev.json"
jq -e '.host_port == 8088 and .container_port == 8000' "$STATE/laia-agora-state.json" >/dev/null
jq -e '.username == "jorge-dev" and .container == "agent-jorge-dev" and .api_port == 9091 and .password == "chattest"' "$STATE/laia-state-jorge-dev.json" >/dev/null
echo "test_rebuild_state.sh: ok"
