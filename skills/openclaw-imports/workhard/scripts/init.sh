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
work_root="$workspace_root/WORK"
current_project_file="$workspace_root/CURRENT_PROJECT"

mkdir -p "$work_root"

mode=""
ia_mode=""
objective=""
project_name=""
subcommand=""

usage() {
  echo "Uso:"
  echo "  init.sh --objective \"texto\" [--mode normal|super] [--ia single|dual] [--name slug]"
  echo "  init.sh resume|status|abort|log"
}

slugify() {
  python3 - "$1" <<'PY'
import re
import sys
text = sys.argv[1].strip().lower()
text = re.sub(r"[^a-z0-9]+", "-", text)
text = re.sub(r"-{2,}", "-", text).strip("-")
print(text or "workhard-project")
PY
}

session_field() {
  local key="$1"
  local session_file="$2"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    resume|status|abort|log)
      subcommand="$1"
      shift
      ;;
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    --ia)
      ia_mode="${2:-}"
      shift 2
      ;;
    --objective)
      objective="${2:-}"
      shift 2
      ;;
    --name)
      project_name="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$objective" ]]; then
        objective="$1"
      else
        objective="$objective $1"
      fi
      shift
      ;;
  esac
done

if [[ -n "$subcommand" ]]; then
  case "$subcommand" in
    resume)
      exec "$script_dir/resume.sh"
      ;;
    status)
      exec "$script_dir/status.sh"
      ;;
    log)
      if [[ -f "$current_project_file" ]]; then
        current_dir="$(<"$current_project_file")"
        tail -n 30 "$current_dir/LOG.md"
      else
        echo "No hay proyecto activo."
      fi
      exit 0
      ;;
    abort)
      if [[ ! -f "$current_project_file" ]]; then
        echo "No hay proyecto activo."
        exit 0
      fi
      project_dir="$(<"$current_project_file")"
      session_file="$project_dir/SESSION.md"
      timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
      python3 - "$session_file" "$timestamp" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
timestamp = sys.argv[2]
updates = {"status": "aborted", "updated_at": timestamp}
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
      printf '| %s | FASE %s | Sesión abortada | ⏸ | Abort solicitado |\n' \
        "$timestamp" \
        "$(session_field phase "$session_file")" >> "$project_dir/LOG.md"
      rm -f "$current_project_file"
      echo "Sesión abortada en $project_dir"
      exit 0
      ;;
  esac
fi

if [[ -z "$objective" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "$mode" || -z "$ia_mode" ]]; then
  menu_args=()
  if [[ -n "$mode" ]]; then
    menu_args+=(--mode "$mode")
  fi
  if [[ -n "$ia_mode" ]]; then
    menu_args+=(--ia "$ia_mode")
  fi
  menu_output="$("$script_dir/menu.sh" "${menu_args[@]}")"
  mode="$(printf '%s\n' "$menu_output" | sed -n 's/^MODE=//p' | head -n 1)"
  ia_mode="$(printf '%s\n' "$menu_output" | sed -n 's/^IA_MODE=//p' | head -n 1)"
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

if [[ -z "$project_name" ]]; then
  project_name="$(slugify "$objective")"
fi

project_dir="$work_root/$project_name"
if [[ -d "$project_dir" ]]; then
  project_dir="$work_root/${project_name}-$(date '+%Y%m%d%H%M%S')"
fi

mkdir -p "$project_dir"
timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

cat > "$project_dir/SESSION.md" <<EOF
# SESSION — $project_name

project_name: $project_name
objective: $objective
mode: $mode
ia_mode: $ia_mode
phase: 1
current_step: 0
status: active
created_at: $timestamp
updated_at: $timestamp
work_dir: $project_dir

## Notes

- Sesión creada por WORKHARD.
EOF

cat > "$project_dir/CONTEXTO.md" <<EOF
# CONTEXTO — $project_name

**Fecha inicio:** $timestamp
**Última actualización:** $timestamp
**Fase:** 1
**Modo:** $mode
**IA:** $ia_mode

---

## OBJETIVO

$objective

## SCOPE

**DENTRO:**
- Entregar el objetivo principal.

**FUERA:**
- Cambios no solicitados.

## RESTRICCIONES

- Mantener pasos pequeños y verificables.
- Respetar approval gates por riesgo.

## INVESTIGACIÓN

Pendiente.

## DECISIONES DE DISEÑO

1. Persistir el trabajo en Markdown.
2. Usar TODO.md como contrato de ejecución.

## RECURSOS

- SESSION.md
- LOG.md
EOF

cat > "$project_dir/LOG.md" <<EOF
# LOG — $project_name

**Iniciado:** $timestamp
**Objetivo:** $objective

---

| Timestamp | Fase | Acción | Resultado | Notas |
|-----------|------|--------|-----------|-------|
| $timestamp | FASE 1 | Proyecto inicializado | ✅ | Configuración base creada |
EOF

cat > "$project_dir/NOTES.md" <<EOF
# NOTES — $project_name

## $timestamp — Inicio

- Objetivo recibido: $objective
- Modo: $mode
- IA: $ia_mode
EOF

printf '%s\n' "$project_dir" > "$current_project_file"

if [[ "$mode" == "super" ]]; then
  "$script_dir/investigate.sh" "$project_dir" "$objective"
  "$script_dir/questionnaire.sh" --project-dir "$project_dir"
  echo "Modo super preparado en $project_dir"
  echo "Responde QUESTIONNAIRE_RESPONSES.md y usa resume.sh para continuar."
  exit 0
fi

"$script_dir/plan.sh" "$project_dir"
"$script_dir/execute.sh" "$project_dir"

echo "Proyecto inicializado en $project_dir"
