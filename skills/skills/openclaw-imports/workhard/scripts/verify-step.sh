#!/usr/bin/env bash

set -euo pipefail

project_dir=""
step_id=""
result=""
note=""

usage() {
  echo "Uso: verify-step.sh --project-dir DIR --step N --result success|failure|paused [--note TXT]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      project_dir="${2:-}"
      shift 2
      ;;
    --step)
      step_id="${2:-}"
      shift 2
      ;;
    --result)
      result="${2:-}"
      shift 2
      ;;
    --note)
      note="${2:-}"
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

if [[ -z "$project_dir" || -z "$step_id" || -z "$result" ]]; then
  usage >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
todo_file="$project_dir/TODO.md"
log_file="$project_dir/LOG.md"
timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

emoji="✅"
status="active"
completed="$timestamp"
case "$result" in
  success)
    emoji="✅"
    status="active"
    ;;
  failure)
    emoji="❌"
    status="paused"
    completed="-"
    ;;
  paused)
    emoji="⏸"
    status="paused"
    completed="-"
    ;;
  *)
    echo "Resultado inválido: $result" >&2
    exit 1
    ;;
esac

python3 - "$todo_file" "$step_id" "$emoji" "$completed" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
step_id = sys.argv[2]
emoji = sys.argv[3]
completed = sys.argv[4]
lines = path.read_text(encoding="utf-8").splitlines()
rows = []

def parse_row(line):
    parts = [part.strip() for part in line.strip().strip("|").split("|")]
    if len(parts) < 6 or not parts[0].isdigit():
        return None
    return {
        "id": parts[0],
        "description": parts[1],
        "command": parts[2],
        "risk": parts[3],
        "status": parts[4],
        "completed": parts[5],
    }

out = []
for line in lines:
    row = parse_row(line)
    if row and row["id"] == step_id:
        row["status"] = emoji
        row["completed"] = completed
        line = "| {id} | {description} | {command} | {risk} | {status} | {completed} |".format(**row)
    out.append(line)
    row = parse_row(line)
    if row:
        rows.append(row)

if emoji in {"⏸", "❌"}:
    next_row = next((row for row in rows if row["id"] == step_id), None)
else:
    next_row = next((row for row in rows if row["status"] in {"⏳", "🔄"}), None)
replacement = [
    "## SIGUIENTE PASO",
    "",
]
phase_value = "4"
if next_row:
    replacement.extend([
        f"**Número:** {next_row['id']}",
        f"**Descripción:** {next_row['description']}",
        f"**Riesgo:** {next_row['risk']}",
    ])
else:
    phase_value = "5" if emoji == "✅" else "4"
    replacement.extend([
        "**Número:** -",
        "**Descripción:** Todo completado",
        "**Riesgo:** -",
    ])

text = "\n".join(out)
text = re.sub(r"\*\*Fase actual:\*\* .*", f"**Fase actual:** {phase_value}", text, count=1)
text = re.sub(r"## SIGUIENTE PASO\s+.*$", "\n".join(replacement), text, flags=re.S)
path.write_text(text.rstrip() + "\n", encoding="utf-8")
PY

if [[ "$result" == "paused" || "$result" == "failure" ]]; then
  next_step="$step_id"
else
  next_step="$(python3 - "$todo_file" <<'PY'
import sys
from pathlib import Path

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    parts = [part.strip() for part in line.strip().strip("|").split("|")]
    if len(parts) >= 6 and parts[0].isdigit() and parts[4] in {"⏳", "🔄"}:
        print(parts[0])
        break
PY
)"
fi

if [[ -z "$next_step" && "$result" == "success" ]]; then
  status="complete"
fi

phase="4"
if [[ "$status" == "complete" ]]; then
  phase="5"
fi

python3 - "$session_file" "$phase" "${next_step:-0}" "$status" "$timestamp" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
phase, current_step, status, updated_at = sys.argv[2:]
updates = {
    "phase": phase,
    "current_step": current_step,
    "status": status,
    "updated_at": updated_at,
}
lines = path.read_text(encoding="utf-8").splitlines()
out = []
for line in lines:
    done = False
    for key, value in updates.items():
        if line.startswith(f"{key}: "):
            out.append(f"{key}: {value}")
            done = True
            break
    if not done:
        out.append(line)
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY

safe_note="${note//|//}"
printf '| %s | FASE 4 | Verificación paso %s | %s | %s |\n' "$timestamp" "$step_id" "$emoji" "$safe_note" >> "$log_file"
echo "Paso $step_id actualizado a $emoji"
