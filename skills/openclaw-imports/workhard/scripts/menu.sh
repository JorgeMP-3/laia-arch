#!/usr/bin/env bash

set -euo pipefail

script_dir="$(python3 - "$0" <<'PY'
import os, sys
print(os.path.dirname(os.path.realpath(sys.argv[1])))
PY
)"
skill_dir="$(cd "$script_dir/.." && pwd)"
openclaw_root="$(cd "$skill_dir/.." && pwd)"
workspace_root="${WORKHARD_WORKSPACE_ROOT:-$openclaw_root/workspace/workhard}"

project_dir=""
mode=""
ia_mode=""

usage() {
  echo "Uso: menu.sh [--project-dir DIR] [--mode normal|super] [--ia single|dual]"
}

update_session() {
  local session="$1"
  python3 - "$session" "$mode" "$ia_mode" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
mode = sys.argv[2]
ia = sys.argv[3]
text = path.read_text(encoding="utf-8") if path.exists() else ""
lines = text.splitlines()
updates = {"mode": mode, "ia_mode": ia}
out = []
seen = set()

for line in lines:
    replaced = False
    for key, value in updates.items():
        if line.startswith(f"{key}: "):
            out.append(f"{key}: {value}")
            seen.add(key)
            replaced = True
            break
    if not replaced:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}: {value}")

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      project_dir="${2:-}"
      shift 2
      ;;
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    --ia)
      ia_mode="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento no reconocido: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$mode" ]]; then
  if [[ -t 0 ]]; then
    echo "Selecciona modo:"
    echo "1) normal"
    echo "2) super"
    read -r choice
    case "$choice" in
      2) mode="super" ;;
      *) mode="normal" ;;
    esac
  else
    mode="normal"
  fi
fi

if [[ -z "$ia_mode" ]]; then
  if [[ -t 0 ]]; then
    echo "Selecciona configuración IA:"
    echo "1) single"
    echo "2) dual"
    read -r choice
    case "$choice" in
      2) ia_mode="dual" ;;
      *) ia_mode="single" ;;
    esac
  else
    ia_mode="single"
  fi
fi

case "$mode" in
  normal|super) ;;
  *)
    echo "Modo inválido: $mode" >&2
    exit 1
    ;;
esac

case "$ia_mode" in
  single|dual) ;;
  *)
    echo "IA inválida: $ia_mode" >&2
    exit 1
    ;;
esac

if [[ -n "$project_dir" ]]; then
  mkdir -p "$workspace_root/WORK"
  update_session "$project_dir/SESSION.md"
  echo "Configuración guardada en $project_dir/SESSION.md"
fi

echo "MODE=$mode"
echo "IA_MODE=$ia_mode"
