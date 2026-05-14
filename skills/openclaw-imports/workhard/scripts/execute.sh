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

if [[ -z "$project_dir" ]]; then
  echo "Uso: execute.sh <project_dir>" >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
todo_file="$project_dir/TODO.md"
log_file="$project_dir/LOG.md"

if [[ ! -f "$todo_file" ]]; then
  echo "No existe $todo_file" >&2
  exit 1
fi

update_session_active() {
  local step="$1"
  local updated_at="$2"
  python3 - "$session_file" "$step" "$updated_at" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
step = sys.argv[2]
updated_at = sys.argv[3]
updates = {
    "phase": "4",
    "current_step": step,
    "status": "active",
    "updated_at": updated_at,
}
lines = path.read_text(encoding="utf-8").splitlines()
out = []
for line in lines:
    replaced = False
    for key, value in updates.items():
        if line.startswith(f"{key}: "):
            out.append(f"{key}: {value}")
            replaced = True
            break
    if not replaced:
        out.append(line)
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

mark_in_progress() {
  local step_id="$1"
  python3 - "$todo_file" "$step_id" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
step_id = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
out = []
for line in lines:
    parts = [part.strip() for part in line.strip().strip("|").split("|")]
    if len(parts) >= 6 and parts[0].isdigit() and parts[0] == step_id:
        parts[4] = "🔄"
        line = "| " + " | ".join(parts[:6]) + " |"
    out.append(line)
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

next_step() {
  python3 - "$todo_file" <<'PY'
import sys
from pathlib import Path

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    parts = [part.strip() for part in line.strip().strip("|").split("|")]
    if len(parts) >= 6 and parts[0].isdigit() and parts[4] in {"⏳", "🔄"}:
        print("\t".join(parts[:5]))
        break
PY
}

confirm_risk() {
  local risk="$1"
  local description="$2"

  case "$risk" in
    low)
      return 0
      ;;
    medium)
      if [[ -t 0 ]]; then
        echo "Paso de riesgo medium: $description"
        printf 'Continuar? [y/N] '
        read -r answer
        [[ "$answer" == "y" || "$answer" == "Y" ]]
        return
      fi
      echo "Aviso: riesgo medium en modo no interactivo, se continúa automáticamente."
      return 0
      ;;
    high|critical)
      if [[ ! -t 0 ]]; then
        echo "Se requiere aprobación para riesgo $risk y no hay TTY."
        return 1
      fi
      echo "Approval gate para riesgo $risk: $description"
      printf 'Escribe "yes" para continuar: '
      read -r answer
      [[ "$answer" == "yes" ]]
      return
      ;;
    *)
      return 0
      ;;
  esac
}

while true; do
  step_line="$(next_step || true)"
  if [[ -z "$step_line" ]]; then
    echo "No quedan pasos pendientes."
    break
  fi

  IFS=$'\t' read -r step_id description command risk current_status <<<"$step_line"
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  update_session_active "$step_id" "$timestamp"
  mark_in_progress "$step_id"
  printf '| %s | FASE 4 | Inicio paso %s | 🔄 | %s |\n' "$timestamp" "$step_id" "${description//|//}" >> "$log_file"

  if ! confirm_risk "$risk" "$description"; then
    "$script_dir/verify-step.sh" --project-dir "$project_dir" --step "$step_id" --result paused --note "Esperando approval para riesgo $risk"
    exit 0
  fi

  if [[ "$command" == PROMPT:* ]]; then
    "$script_dir/verify-step.sh" --project-dir "$project_dir" --step "$step_id" --result paused --note "${command#PROMPT:}"
    echo "Paso $step_id pausado. Requiere intervención manual o de IA."
    exit 0
  fi

  shell_command="$command"
  if [[ "$shell_command" == SHELL:* ]]; then
    shell_command="${shell_command#SHELL:}"
  fi

  if (cd "$project_dir" && bash -lc "$shell_command"); then
    "$script_dir/verify-step.sh" --project-dir "$project_dir" --step "$step_id" --result success --note "Comando ejecutado correctamente"
    if ! "$script_dir/checkpoint.sh" "$project_dir" "$step_id" "$description"; then
      printf '| %s | FASE 4 | Checkpoint paso %s | ⚠️ | Falló el commit automático |\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$step_id" >> "$log_file"
    fi
  else
    "$script_dir/verify-step.sh" --project-dir "$project_dir" --step "$step_id" --result failure --note "Falló el comando: ${shell_command//|//}"
    exit 1
  fi
done

printf '| %s | FASE 5 | Ejecución finalizada | ✅ | Todo completado |\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$log_file"
echo "Ejecución completada."
