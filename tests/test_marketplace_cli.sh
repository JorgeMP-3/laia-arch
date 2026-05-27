#!/usr/bin/env bash
# Smoke test for laia-marketplace.py CLI (Fase C).
# Verifies the script compiles, exposes the expected subcommands, and
# emits clear errors when auth/inputs are missing — no live backend needed.

set -euo pipefail

CLI="${LAIA_ROOT:-/home/laia-arch/LAIA}/infra/dev/laia-marketplace.py"
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

# 1) --help is reachable.
"$CLI" --help >/dev/null

# 2) Subcommand --help works for each top-level command.
for cmd in plugin skill mcp; do
    "$CLI" "$cmd" --help >/dev/null
done

# 3) plugin publish refuses a non-directory.
if "$CLI" --slug jorge-dev plugin publish /nope 2>&1 >/dev/null; then
    echo "FAIL: plugin publish accepted bogus path"
    exit 1
fi

# 4) plugin publish refuses dir without plugin.yaml.
empty="$TMP/empty"
mkdir -p "$empty"
if "$CLI" --slug jorge-dev plugin publish "$empty" 2>&1 >/dev/null; then
    echo "FAIL: plugin publish accepted dir without manifest"
    exit 1
fi

# 5) plugin publish refuses dir with manifest but no __init__.py.
nomanifest="$TMP/noinit"
mkdir -p "$nomanifest"
cat > "$nomanifest/plugin.yaml" <<EOF
slug: noinit
version: 0.1.0
EOF
if "$CLI" --slug jorge-dev plugin publish "$nomanifest" 2>&1 >/dev/null; then
    echo "FAIL: plugin publish accepted dir without __init__.py"
    exit 1
fi

# 6) Without any auth source, commands fail loudly.
unset AGORA_TOKEN AGORA_USERNAME AGORA_PASSWORD
unset LAIA_STATE_DIR  # ensure default path
export LAIA_STATE_DIR="$TMP/no-state"  # missing dir → forces clear error
if "$CLI" plugin list 2>&1 >/dev/null; then
    echo "FAIL: plugin list ran without auth"
    exit 1
fi

echo "test_marketplace_cli.sh: ok"
