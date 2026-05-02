#!/usr/bin/env bash

set -euo pipefail

project_dir="${1:-}"
step_number="${2:-}"
description="${3:-}"

if [[ -z "$project_dir" ]]; then
  echo "Uso: checkpoint.sh <project_dir> [step_number] [description]" >&2
  exit 1
fi

if ! git_root="$(git -C "$project_dir" rev-parse --show-toplevel 2>/dev/null)"; then
  echo "Sin repositorio git en $project_dir"
  exit 0
fi

if [[ "$git_root" != "$project_dir" ]]; then
  echo "El proyecto no es un repo git propio; se omite checkpoint ($git_root)"
  exit 0
fi

if [[ -z "$(git -C "$git_root" status --short)" ]]; then
  echo "Sin cambios para checkpoint en $git_root"
  exit 0
fi

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
message="[workhard] Step ${step_number:-?}: ${description:-checkpoint} - $timestamp"

git -C "$git_root" add -A
git -C "$git_root" commit -m "$message"

echo "Checkpoint creado en $git_root"
