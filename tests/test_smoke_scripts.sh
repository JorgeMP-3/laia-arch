#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/infra/dev/smoke-test.sh" --help >/tmp/laia-smoke-help.out
grep -q "smoke-test.sh" /tmp/laia-smoke-help.out

bash "$ROOT/infra/dev/smoke-test.sh" --dry-run --slug jorge-dev >/tmp/laia-smoke-dry.out
grep -q "DRY RUN smoke-test" /tmp/laia-smoke-dry.out
grep -q "/api/agents/me/chat" /tmp/laia-smoke-dry.out

echo "test_smoke_scripts.sh: ok"
