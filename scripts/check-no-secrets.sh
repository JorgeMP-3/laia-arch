#!/usr/bin/env bash
# Gate anti-secretos: automatiza el criterio de release "no hay secretos nuevos en git"
# (workflow-main/release-flow.md §Criterios). Patrones de ALTA confianza para minimizar
# falsas alarmas; corre en CI (job doctrine-gates) y en local.
# Adoptado del patrón "doctrina ejecutable" de Hermes upstream (2026-06-02).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PATTERNS=(
  'ghp_[A-Za-z0-9]{36}'                       # GitHub PAT clásico
  'github_pat_[A-Za-z0-9_]{22,}'              # GitHub PAT fine-grained
  'AKIA[0-9A-Z]{16}'                          # AWS access key
  'sk-[A-Za-z0-9]{40,}'                       # OpenAI/Anthropic-style API key
  'xox[bpars]-[A-Za-z0-9-]{10,}'              # Slack token
  '\-\-\-\-\-BEGIN [A-Z ]*PRIVATE KEY\-\-\-\-\-'  # claves privadas PEM
)
# Excluye: histórico inmutable, upstream Hermes vendorizado (.laia-core — sus tests usan
# secretos-dummy a propósito), ejemplos documentales y este propio script.
EXCLUDES=(':!archived' ':!.laia-core' ':!*example*' ':!*.example' ':!scripts/check-no-secrets.sh')

fail=0
for p in "${PATTERNS[@]}"; do
  hits=$(git grep -nE "$p" -- "${EXCLUDES[@]}" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "FAIL [secrets] patrón '$p':"
    echo "$hits"
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "OK no-secrets: sin patrones de secretos en archivos trackeados"
fi
exit "$fail"
