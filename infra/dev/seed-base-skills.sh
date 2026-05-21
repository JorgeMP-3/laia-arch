#!/usr/bin/env bash
# seed-base-skills.sh — publish + approve a curated set of base skills into
# the AGORA marketplace skill_registry.
#
# The set is fixed (10 skills picked from LAIA/skills/) and biased toward
# user-facing productivity: each new user that runs rebuild-4 auto-installs
# them unless --no-base-skills is passed.
#
# Idempotent: re-running skips skills whose slug already exists.
#
# Usage:
#   bash infra/dev/seed-base-skills.sh                    # uses default API + admin token
#   AGORA_API=http://127.0.0.1:8088 bash seed-base-skills.sh
#   AGORA_TOKEN=<admin-bearer> bash seed-base-skills.sh

set -euo pipefail

# Resolve REPO_ROOT: explicit env > git toplevel > script location (../..)
if [[ -z "${REPO_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if REPO_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    REPO_ROOT="$(cd "$_script_dir/../.." && pwd)"
  fi
  unset _script_dir
fi
[[ -d "$REPO_ROOT/skills" ]] || { echo "REPO_ROOT $REPO_ROOT has no skills/ dir — pass REPO_ROOT explicitly" >&2; exit 1; }

SKILLS_DIR="${SKILLS_DIR:-$REPO_ROOT/skills}"
CLI="$REPO_ROOT/infra/dev/laia-marketplace.py"
API="${AGORA_API:-http://127.0.0.1:8088}"
TOKEN="${AGORA_TOKEN:-dev-admin-token}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
err()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; }

# Curated catalog: <slug>:<relative-path-from-skills-dir>
SKILLS=(
  "google-workspace:productivity/google-workspace"
  "notion:productivity/notion"
  "linear:productivity/linear"
  "airtable:productivity/airtable"
  "nano-pdf:productivity/nano-pdf"
  "ocr-and-documents:productivity/ocr-and-documents"
  "arxiv:research/arxiv"
  "github-issues:github/github-issues"
  "workspace-read:workspace/workspace-read"
  "maps:productivity/maps"
)

# 1. Check the API is reachable.
if ! curl -fsS "$API/api/health" >/dev/null 2>&1; then
  err "AGORA backend no responde en $API. Arranca el container laia-agora primero."
  exit 1
fi

# 2. Pull the current catalog once so we can skip already-approved slugs
#    instead of hammering the API on each iteration.
EXISTING=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$API/api/skills/catalog" \
           | jq -r '.[] | .slug' 2>/dev/null || true)

CREATED=0
SKIPPED=0
FAILED=0

for entry in "${SKILLS[@]}"; do
  slug="${entry%%:*}"
  rel="${entry#*:}"
  src="$SKILLS_DIR/$rel/SKILL.md"

  if [[ ! -f "$src" ]]; then
    warn "$slug: SKILL.md not found at $src (skipping)"
    FAILED=$((FAILED+1))
    continue
  fi

  if grep -qx "$slug" <<<"$EXISTING"; then
    ok "$slug ya está en el catálogo (skip)"
    SKIPPED=$((SKIPPED+1))
    continue
  fi

  log "publicando $slug ← $rel"
  # Authenticate explicitly via AGORA_TOKEN so the CLI uses the admin
  # token (owner_user_id=user_jorge by virtue of dev-admin-token).
  if ! AGORA_TOKEN="$TOKEN" python3 "$CLI" --api "$API" \
       skill publish "$src" --skill-slug "$slug" --publish >/dev/null 2>&1; then
    err "$slug: publish failed"
    FAILED=$((FAILED+1))
    continue
  fi

  # The publish CLI doesn't print the skill id when it succeeds in --publish
  # mode (it prints the upload + publish JSON). Look it up via the admin
  # pending list and approve.
  sid=$(curl -fsS -H "Authorization: Bearer $TOKEN" \
        "$API/api/admin/marketplace/pending" \
        | jq -r --arg s "$slug" '.skills[] | select(.slug==$s) | .id' | head -1)
  if [[ -z "$sid" || "$sid" == "null" ]]; then
    warn "$slug: publicado pero no aparece en pending (posible doble-approve)"
    SKIPPED=$((SKIPPED+1))
    continue
  fi
  if ! curl -fsS -X POST -H "Authorization: Bearer $TOKEN" \
       "$API/api/admin/skills/$sid/approve" >/dev/null; then
    err "$slug ($sid): approve failed"
    FAILED=$((FAILED+1))
    continue
  fi
  ok "$slug aprobado (id=$sid)"
  CREATED=$((CREATED+1))
done

# v0.3 AGORA-native skills — auto-edit / learning / scheduler / delegation +
# doyouwin reference. Single-file manifests (no SKILL.md folder structure).
# Same publish+approve flow.
AGORA_SKILLS=(
  "agent-self-edit:$REPO_ROOT/examples/marketplace/skills/agent-self-edit.md"
  "agent-learning:$REPO_ROOT/examples/marketplace/skills/agent-learning.md"
  "agent-scheduler:$REPO_ROOT/examples/marketplace/skills/agent-scheduler.md"
  "agent-delegation:$REPO_ROOT/examples/marketplace/skills/agent-delegation.md"
  "doyouwin-reference:$REPO_ROOT/examples/marketplace/skills/doyouwin-reference.md"
)

# Refresh existing-slug list — we may have just added some above.
EXISTING=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$API/api/skills/catalog" \
           | jq -r '.[] | .slug' 2>/dev/null || true)

for entry in "${AGORA_SKILLS[@]}"; do
  slug="${entry%%:*}"
  src="${entry#*:}"

  if [[ ! -f "$src" ]]; then
    warn "$slug: manifest not found at $src (skipping)"
    FAILED=$((FAILED+1))
    continue
  fi

  if grep -qx "$slug" <<<"$EXISTING"; then
    ok "$slug ya está en el catálogo (skip)"
    SKIPPED=$((SKIPPED+1))
    continue
  fi

  log "publicando $slug ← $(basename "$src")"
  if ! AGORA_TOKEN="$TOKEN" python3 "$CLI" --api "$API" \
       skill publish "$src" --skill-slug "$slug" --publish >/dev/null 2>&1; then
    err "$slug: publish failed"
    FAILED=$((FAILED+1))
    continue
  fi
  sid=$(curl -fsS -H "Authorization: Bearer $TOKEN" \
        "$API/api/admin/marketplace/pending" \
        | jq -r --arg s "$slug" '.skills[] | select(.slug==$s) | .id' | head -1)
  if [[ -z "$sid" || "$sid" == "null" ]]; then
    warn "$slug: publicado pero no aparece en pending (posible doble-approve)"
    SKIPPED=$((SKIPPED+1))
    continue
  fi
  if ! curl -fsS -X POST -H "Authorization: Bearer $TOKEN" \
       "$API/api/admin/skills/$sid/approve" >/dev/null; then
    err "$slug ($sid): approve failed"
    FAILED=$((FAILED+1))
    continue
  fi
  ok "$slug aprobado (id=$sid)"
  CREATED=$((CREATED+1))
done

printf "\n  ${GRN}%d${RST} creadas  ${YEL}%d${RST} ya presentes  ${RED}%d${RST} fallidas\n" \
  "$CREATED" "$SKIPPED" "$FAILED"
exit $(( FAILED > 0 ? 1 : 0 ))
