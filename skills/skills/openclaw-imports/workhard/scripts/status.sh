#!/usr/bin/env bash

set -euo pipefail

script_dir="$(python3 - "$0" <<'PY'
import os, sys
print(os.path.dirname(os.path.realpath(sys.argv[1])))
PY
)"
skill_dir="$(cd "$script_dir/.." && pwd)"
openclaw_root="$(cd "$skill_dir/../.." && pwd)"
workspace_root="${WORKHARD_WORKSPACE_ROOT:-$openclaw_root/workspace/workhard}"
current_project_file="$workspace_root/CURRENT_PROJECT"

project_dir="${1:-}"
if [[ -z "$project_dir" && -f "$current_project_file" ]]; then
  project_dir="$(<"$current_project_file")"
fi

if [[ -z "$project_dir" || ! -d "$project_dir" ]]; then
  echo "No hay proyecto activo."
  exit 0
fi

session_file="$project_dir/SESSION.md"
todo_file="$project_dir/TODO.md"
log_file="$project_dir/LOG.md"

session_field() {
  local key="$1"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

project_name="$(session_field project_name)"
objective="$(session_field objective)"
mode="$(session_field mode)"
ia_mode="$(session_field ia_mode)"
phase="$(session_field phase)"
current_step="$(session_field current_step)"
status="$(session_field status)"

counts="$(python3 - "$todo_file" <<'PY'
import sys
from pathlib import Path

counts = {"✅": 0, "🔄": 0, "⏳": 0, "❌": 0, "⏸": 0}
next_line = "Todo completado"
path = Path(sys.argv[1])
if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) >= 6 and parts[0].isdigit():
            counts[parts[4]] = counts.get(parts[4], 0) + 1
            if next_line == "Todo completado" and parts[4] in {"⏸", "⏳", "🔄"}:
                next_line = f"{parts[0]} - {parts[1]} ({parts[3]})"
print(f"{counts.get('✅',0)}|{counts.get('🔄',0)}|{counts.get('⏳',0)}|{counts.get('❌',0)}|{counts.get('⏸',0)}|{next_line}")
PY
)"

IFS='|' read -r done_count progress_count pending_count fail_count pause_count next_line <<<"$counts"

echo "WORKHARD STATUS"
echo "Proyecto: $project_name"
echo "Objetivo: $objective"
echo "Modo: $mode / $ia_mode"
echo "Fase: $phase"
echo "Estado: $status"
echo "Paso actual: $current_step"
echo "Ruta: $project_dir"
echo "Resumen TODO: ✅ $done_count | 🔄 $progress_count | ⏳ $pending_count | ❌ $fail_count | ⏸ $pause_count"
echo "Siguiente: $next_line"

if [[ -f "$log_file" ]]; then
  echo ""
  echo "Últimas acciones:"
  tail -n 5 "$log_file"
fi
