#!/usr/bin/env bash
# Gate de supply-chain (doctrina: ~/laia-developers/AGENTS.md §Reglas de diseño;
# adoptado de Hermes upstream, 2026-06-02):
#   1) deps PyPI con cota superior en requirements*.txt (`>=floor,<techo` o `==exacto`)
#   2) GitHub Actions pineadas por SHA de 40 hex (los tags son refs mutables)
# Grep-based: barato, corre en CI (job doctrine-gates) y en local.
# Excluye archived/ (histórico inmutable) y .laia-core/ (upstream Hermes VENDORIZADO:
# sus deps/tests los gobierna el CI de upstream, no el nuestro — no divergimos del vendor).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail=0

# ── 1) requirements*.txt: toda spec >= necesita techo ,< ──────────────────────
while IFS= read -r f; do
  lineno=0
  while IFS= read -r line; do
    lineno=$((lineno + 1))
    [[ "$line" =~ ^[[:space:]]*(#|$|-r) ]] && continue
    [[ "$line" == *"=="* ]] && continue
    if [[ "$line" == *">="* && "$line" != *",<"* ]]; then
      echo "FAIL [deps] $f:$lineno: '$line' sin cota superior (usa >=floor,<techo)"
      fail=1
    fi
  done <"$f"
done < <(git ls-files '*requirements*.txt' | grep -v -e '^archived/' -e '^\.laia-core/')

# ── 2) workflows: uses: owner/action@<sha40>  # vX ───────────────────────────
while IFS= read -r m; do
  f=${m%%:*}; rest=${m#*:}; lineno=${rest%%:*}; content=${rest#*:}
  ref=$(sed -E 's/.*uses:[[:space:]]*[^@]+@([^[:space:]#]+).*/\1/' <<<"$content")
  if ! [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
    echo "FAIL [actions] $f:$lineno: $(echo "$content" | xargs) — pinea por SHA de 40 hex (+ '# vX' de comentario)"
    fail=1
  fi
done < <(git grep -n -E '^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*[^./][^[:space:]]*@' -- '.github/workflows/*.yml' 2>/dev/null || true)

if [ "$fail" -eq 0 ]; then
  echo "OK supply-chain: deps con techo + actions por SHA"
fi
exit "$fail"
