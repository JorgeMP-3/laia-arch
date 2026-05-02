#!/usr/bin/env bash
# status-web.sh — Genera una página HTML con el estado del proyecto workhard

set -euo pipefail

WORKHARD_ROOT="${WORKHARD_ROOT:-$HOME/.openclaw/workspace/workhard}"
CURRENT_PROJECT_FILE="$WORKHARD_ROOT/CURRENT_PROJECT"
OUTPUT_FILE="$WORKHARD_ROOT/status.html"

get_session_field() {
  local field="$1"
  local session_file="$2"
  grep -E "^${field}: " "$session_file" 2>/dev/null | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

get_todo_rows() {
  local todo_file="$1"
  if [[ ! -f "$todo_file" ]]; then
    echo "<tr><td colspan='5'>Sin archivo TODO</td></tr>"
    return
  fi
  grep "^|" "$todo_file" 2>/dev/null | tail -n +4 | sed '$d' | while read line; do
    # Parsear cada línea de la tabla: | # | descripción | tipo | riesgo | estado |
    echo "$line" | awk -F'|' '{
      num=$2; desc=$3; tipo=$4; riesgo=$5; estado=$6;
      gsub(/^[ \t]+|[ \t]+$/, "", num);
      gsub(/^[ \t]+|[ \t]+$/, "", desc);
      gsub(/^[ \t]+|[ \t]+$/, "", tipo);
      gsub(/^[ \t]+|[ \t]+$/, "", riesgo);
      gsub(/^[ \t]+|[ \t]+$/, "", estado);
      if (estado=="✅") { cls="done"; icon="✅"; }
      else if (estado=="🔄") { cls="wip"; icon="🔄"; }
      else if (estado=="⏳") { cls="pending"; icon="⏳"; }
      else if (estado=="⏸") { cls="paused"; icon="⏸"; }
      else if (estado=="❌") { cls="error"; icon="❌"; }
      else { cls="other"; icon=estado; }
      printf "<tr class=\"%s\"><td>%s</td><td>%s</td><td><code>%s</code></td><td><span class=\"risk risk-%s\">%s</span></td><td>%s</td></tr>\n", cls, num, desc, tipo, riesgo, riesgo, icon;
    }'
  done
}

get_summary() {
  local todo_file="$1"
  if [[ ! -f "$todo_file" ]]; then
    echo '<span class="stat">—</span>'
    return
  fi
  local done=$(grep -c "✅" "$todo_file" 2>/dev/null || echo 0)
  local wip=$(grep -c "🔄" "$todo_file" 2>/dev/null || echo 0)
  local pending=$(grep -c "⏳" "$todo_file" 2>/dev/null || echo 0)
  local paused=$(grep -c "⏸" "$todo_file" 2>/dev/null || echo 0)
  local error=$(grep -c "❌" "$todo_file" 2>/dev/null || echo 0)
  echo "<span class='stat done'>✅ $done</span>"
  echo "<span class='stat wip'>🔄 $wip</span>"
  echo "<span class='stat pending'>⏳ $pending</span>"
  echo "<span class='stat paused'>⏸ $paused</span>"
  echo "<span class='stat error'>❌ $error</span>"
}

# Detectar proyecto activo
if [[ -f "$CURRENT_PROJECT_FILE" ]]; then
  PROJECT_DIR="$(<"$CURRENT_PROJECT_FILE")"
  PROJECT_NAME="$(basename "$PROJECT_DIR")"
  SESSION_FILE="$PROJECT_DIR/SESSION.md"
  TODO_FILE="$PROJECT_DIR/TODO.md"
  LOG_FILE="$PROJECT_DIR/LOG.md"

  if [[ -f "$SESSION_FILE" ]]; then
    OBJECTIVE=$(get_session_field "objective" "$SESSION_FILE")
    PHASE=$(get_session_field "phase" "$SESSION_FILE")
    STATUS=$(get_session_field "status" "$SESSION_FILE")
    MODE=$(get_session_field "mode" "$SESSION_FILE")
    IA=$(get_session_field "ia_mode" "$SESSION_FILE")
    CREATED=$(get_session_field "created_at" "$SESSION_FILE")
    UPDATED=$(get_session_field "updated_at" "$SESSION_FILE")
  else
    OBJECTIVE="Sin datos"
    PHASE="—"; STATUS="—"; MODE="—"; IA="—"; CREATED="—"; UPDATED="—"
  fi

  TODO_ROWS=$(get_todo_rows "$TODO_FILE")
  SUMMARY=$(get_summary "$TODO_FILE")

  # Últimas acciones del log
  if [[ -f "$LOG_FILE" ]]; then
    LAST_ACTIONS=$(grep "^|" "$LOG_FILE" 2>/dev/null | tail -n 5 | while read line; do
      echo "$line" | awk -F'|' '{
        ts=$2; fase=$3; accion=$4; resultado=$5; notas=$6;
        gsub(/^[ \t]+|[ \t]+$/, "", ts);
        gsub(/^[ \t]+|[ \t]+$/, "", fase);
        gsub(/^[ \t]+|[ \t]+$/, "", accion);
        gsub(/^[ \t]+|[ \t]+$/, "", resultado);
        gsub(/^[ \t]+|[ \t]+$/, "", notas);
        printf "<li><code>%s</code> [%s] %s — %s %s</li>\n", ts, fase, accion, resultado, notas;
      }'
    done | tr '\n' ' ')
  else
    LAST_ACTIONS="<li>Sin historial</li>"
  fi
else
  PROJECT_NAME="Ningún proyecto activo"
  OBJECTIVE="Inicia uno con /workhard [objetivo]"
  PHASE="—"; STATUS="—"; MODE="—"; IA="—"; CREATED="—"; UPDATED="—"
  TODO_ROWS="<tr><td colspan='5'>Sin proyecto activo</td></tr>"
  SUMMARY="<span class='stat'>—</span>"
  LAST_ACTIONS="<li>Sin historial</li>"
fi

cat > "$OUTPUT_FILE" << EOF
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Workhard Status</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e6edf3; min-height: 100vh; padding: 2rem; }
  .container { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #58a6ff; }
  h2 { font-size: 1rem; color: #8b949e; margin: 1.5rem 0 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
  .stat { display: inline-block; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.875rem; font-weight: 600; }
  .done { background: #1f3a2a; color: #3fb950; }
  .wip { background: #2a2a10; color: #d29922; }
  .pending { background: #1f2937; color: #58a6ff; }
  .paused { background: #2a2030; color: #a371f7; }
  .error { background: #3a1f1f; color: #f85149; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; color: #8b949e; font-size: 0.75rem; text-transform: uppercase; border-bottom: 1px solid #30363d; padding: 0.5rem 0.75rem; }
  td { padding: 0.6rem 0.75rem; border-bottom: 1px solid #21262d; }
  tr:last-child td { border-bottom: none; }
  .risk { padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
  .risk-low { background: #1f3a2a; color: #3fb950; }
  .risk-medium { background: #2a2a10; color: #d29922; }
  .risk-high { background: #3a1f1f; color: #f85149; }
  .risk-critical { background: #3a1f1f; color: #f85149; }
  code { color: #79c0ff; }
  ul { list-style: none; }
  ul li { padding: 0.3rem 0; color: #8b949e; font-size: 0.85rem; }
  ul li code { color: #58a6ff; }
  .footer { text-align: center; color: #484f58; font-size: 0.75rem; margin-top: 2rem; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge-active { background: #1f3a2a; color: #3fb950; }
  .badge-paused { background: #2a2030; color: #a371f7; }
  .badge-complete { background: #1f3a2a; color: #3fb950; }
  .badge-aborted { background: #3a1f1f; color: #f85149; }
</style>
</head>
<body>
<div class="container">
  <h1>🐧 Workhard — Estado del proyecto</h1>

  <div class="card">
    <h2>Datos del proyecto</h2>
    <div class="grid">
      <div><span class="stat">📁 $(echo "$PROJECT_NAME" | cut -c1-20)</span></div>
      <div><span class="stat">📍 Fase $PHASE/5</span></div>
      <div><span class="badge badge-${STATUS:-unknown}">${STATUS:-—}</span></div>
      <div><span class="stat">⚙️ $MODE · $IA</span></div>
    </div>
    <p style="color:#8b949e;font-size:0.875rem;margin-bottom:0.5rem;">Objetivo:</p>
    <p style="font-size:0.9rem;line-height:1.5;">$OBJECTIVE</p>
  </div>

  <div class="card">
    <h2>Resumen de pasos</h2>
    <div class="grid">$SUMMARY</div>
  </div>

  <div class="card">
    <h2>Pasos</h2>
    <table>
      <thead><tr><th>#</th><th>Descripción</th><th>Tipo</th><th>Riesgo</th><th>Estado</th></tr></thead>
      <tbody>$TODO_ROWS</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Últimas acciones</h2>
    <ul>$LAST_ACTIONS</ul>
  </div>

  <div class="footer">
    Generado: $(date '+%Y-%m-%d %H:%M:%S') · Workhard · ~/.openclaw/skills/workhard/scripts/status-web.sh
  </div>
</div>
</body>
</html>
EOF

echo "✅ HTML generado: $OUTPUT_FILE"
echo "   Abre en navegador: file://$OUTPUT_FILE"
