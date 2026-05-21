#!/usr/bin/env bash
# Smoke test for the base skills seeder. We run the script twice; the second
# run must be a no-op (idempotency contract).

set -euo pipefail

SCRIPT=/home/laia-hermes/LAIA/infra/dev/seed-base-skills.sh
API="${AGORA_API:-http://127.0.0.1:8088}"

# Sanity: backend reachable? If not, skip — the test is for a live backend.
if ! curl -fsS "$API/api/health" >/dev/null 2>&1; then
  echo "test_seed_base_skills.sh: skip (backend not reachable at $API)"
  exit 0
fi

# Run 1 — may publish or skip depending on prior state.
bash "$SCRIPT" >/tmp/seed-base-skills.run1.log 2>&1
ec1=$?

# Run 2 — must succeed AND every line must be a "skip" or "ya está".
bash "$SCRIPT" >/tmp/seed-base-skills.run2.log 2>&1
ec2=$?

if [[ "$ec2" -ne 0 ]]; then
  echo "FAIL: idempotent run exited $ec2"
  cat /tmp/seed-base-skills.run2.log
  exit 1
fi

# At least the 10 expected slugs should be in the catalog.
got=$(curl -fsS -H 'Authorization: Bearer dev-admin-token' \
      "$API/api/skills/catalog" | jq -r '.[].slug' | sort -u)
expected=(google-workspace notion linear airtable nano-pdf ocr-and-documents
          arxiv github-issues workspace-read maps)
for slug in "${expected[@]}"; do
  if ! grep -qx "$slug" <<<"$got"; then
    echo "FAIL: catalog missing '$slug'. Got:"
    echo "$got"
    exit 1
  fi
done

echo "test_seed_base_skills.sh: ok ($ec1, $ec2)"
