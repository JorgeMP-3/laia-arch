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
  echo "No hay proyecto para reanudar." >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
todo_file="$project_dir/TODO.md"
responses_file="$project_dir/QUESTIONNAIRE_RESPONSES.md"

session_field() {
  local key="$1"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

mode="$(session_field mode)"
status="$(session_field status)"
phase="$(session_field phase)"

if [[ "$status" == "aborted" ]]; then
  echo "La sesión está abortada. No se reanuda automáticamente."
  exit 1
fi

if [[ "$mode" == "super" && -f "$responses_file" && "$phase" -le 2 ]]; then
  "$script_dir/questionnaire.sh" --project-dir "$project_dir" --synthesize
fi

if [[ ! -f "$todo_file" ]]; then
  "$script_dir/plan.sh" "$project_dir"
fi

"$script_dir/execute.sh" "$project_dir"
