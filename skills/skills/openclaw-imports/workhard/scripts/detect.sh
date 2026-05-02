#!/usr/bin/env bash
# detect.sh — Detecta el proyecto workhard activo y muestra su estado

set -euo pipefail

WORKHARD_ROOT="${WORKHARD_ROOT:-$HOME/.openclaw/workspace/workhard}"
CURRENT_PROJECT_FILE="$WORKHARD_ROOT/CURRENT_PROJECT"

show_help() {
  cat << 'EOF'
USO:
  detect.sh              → muestra estado del proyecto activo
  detect.sh --help       → esta ayuda
  detect.sh --raw        → salida minimal para scripts
  detect.sh --project    → solo el nombre del proyecto
  detect.sh --phase      → solo la fase actual
  detect.sh --status     → solo el estado
  detect.sh --next-step  → solo el siguiente paso
  detect.sh --summary    → resumen rápido (emoji style)

EJEMPLOS:
  detect.sh              # estado completo
  detect.sh --raw        # para parsing en scripts
  detect.sh --project    # solo nombre del proyecto

EXIT CODES:
  0 → proyecto activo encontrado
  1 → no hay proyecto activo
EOF
}

# Leer proyecto activo
get_project_dir() {
  if [[ -f "$CURRENT_PROJECT_FILE" ]]; then
    cat "$CURRENT_PROJECT_FILE"
  else
    echo "NO_ACTIVE_PROJECT"
  fi
}

get_session_field() {
  local field="$1"
  local session_file="$2"
  grep -E "^${field}: " "$session_file" 2>/dev/null | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

get_todo_summary() {
  local todo_file="$1"
  if [[ ! -f "$todo_file" ]]; then
    echo "sin TODO"
    return
  fi
  local done=$(grep -c "✅" "$todo_file" 2>/dev/null || echo 0)
  local wip=$(grep -c "🔄" "$todo_file" 2>/dev/null || echo 0)
  local pending=$(grep -c "⏳" "$todo_file" 2>/dev/null || echo 0)
  local paused=$(grep -c "⏸" "$todo_file" 2>/dev/null || echo 0)
  local error=$(grep -c "❌" "$todo_file" 2>/dev/null || echo 0)
  echo "✅ $done | 🔄 $wip | ⏳ $pending | ⏸ $paused | ❌ $error"
}

get_next_step() {
  local todo_file="$1"
  if [[ ! -f "$todo_file" ]]; then
    echo "sin pasos"
    return
  fi
  grep -n "⏳\|⏸" "$todo_file" 2>/dev/null | grep "^[^:]*:|" | head -n 1 | sed 's/|.*//' | cut -d: -f2-
}

# Parseo de argumentos
MODE="full"
if [[ $# -gt 0 ]]; then
  case "$1" in
    --help|-h) show_help; exit 0 ;;
    --raw) MODE="raw" ;;
    --project) MODE="project" ;;
    --phase) MODE="phase" ;;
    --status) MODE="status" ;;
    --next-step) MODE="next-step" ;;
    --summary) MODE="summary" ;;
    *) echo "Opción desconocida: $1"; show_help; exit 1 ;;
  esac
fi

PROJECT_DIR="$(get_project_dir)"

if [[ "$PROJECT_DIR" == "NO_ACTIVE_PROJECT" ]]; then
  case "$MODE" in
    raw) echo "NO_ACTIVE_PROJECT" ;;
    project|phase|status|next-step|summary) ;;
    full) echo "No hay proyecto workhard activo." ;;
  esac
  exit 1
fi

SESSION_FILE="$PROJECT_DIR/SESSION.md"
TODO_FILE="$PROJECT_DIR/TODO.md"

if [[ ! -f "$SESSION_FILE" ]]; then
  echo "ERROR: SESSION.md no encontrado en $PROJECT_DIR"
  exit 1
fi

PROJECT_NAME=$(get_session_field "project_name" "$SESSION_FILE")
OBJECTIVE=$(get_session_field "objective" "$SESSION_FILE")
MODE_SESSION=$(get_session_field "mode" "$SESSION_FILE")
IA_MODE=$(get_session_field "ia_mode" "$SESSION_FILE")
PHASE=$(get_session_field "phase" "$SESSION_FILE")
STATUS=$(get_session_field "status" "$SESSION_FILE")
CURRENT_STEP=$(get_session_field "current_step" "$SESSION_FILE")
CREATED=$(get_session_field "created_at" "$SESSION_FILE")
UPDATED=$(get_session_field "updated_at" "$SESSION_FILE")
SUMMARY=$(get_todo_summary "$TODO_FILE")
NEXT=$(get_next_step "$TODO_FILE")

# Truncar objetivo largo
if [[ ${#OBJECTIVE} -gt 80 ]]; then
  OBJECTIVE_SHORT="${OBJECTIVE:0:77}..."
else
  OBJECTIVE_SHORT="$OBJECTIVE"
fi

case "$MODE" in
  raw)
    echo "PROJECT_NAME=$PROJECT_NAME"
    echo "PHASE=$PHASE"
    echo "STATUS=$STATUS"
    echo "MODE=$MODE_SESSION"
    echo "IA=$IA_MODE"
    echo "CURRENT_STEP=$CURRENT_STEP"
    echo "CREATED=$CREATED"
    echo "UPDATED=$UPDATED"
    echo "NEXT_STEP=$NEXT"
    ;;
  project) echo "$PROJECT_NAME" ;;
  phase) echo "$PHASE" ;;
  status) echo "$STATUS" ;;
  next-step) echo "$NEXT" ;;
  summary)
    echo "🐧 $PROJECT_NAME | fase $PHASE | $STATUS | $SUMMARY"
    ;;
  full)
    cat << EOF

╔══════════════════════════════════════════════════════════════╗
║                   🐧 WORKHARD — Proyecto activo            ║
╚══════════════════════════════════════════════════════════════╝

  Proyecto:    $PROJECT_NAME
  Fase:        $PHASE / 5
  Estado:      $STATUS
  Modo:        $MODE_SESSION · $IA_MODE
  Creado:      $CREATED
  Actualizado: $UPDATED

  Objetivo:
  $OBJECTIVE_SHORT

  Resumen:
  $SUMMARY

  Siguiente paso:
  $NEXT

  Rout:
    /workhard status   → estado actual
    /workhard resume   → continuar proyecto
    /workhard log      → historial
    /workhard abort    → cancelar

  Archivos:
    SESSION.md · TODO.md · LOG.md · CONTEXTO.md

EOF
    ;;
esac
