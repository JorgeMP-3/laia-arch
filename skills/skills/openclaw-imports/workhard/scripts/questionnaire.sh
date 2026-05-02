#!/usr/bin/env bash

set -euo pipefail

script_dir="$(python3 - "$0" <<'PY'
import os, sys
print(os.path.dirname(os.path.realpath(sys.argv[1])))
PY
)"

project_dir=""
mode="generate"

usage() {
  echo "Uso: questionnaire.sh --project-dir DIR [--synthesize]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      project_dir="${2:-}"
      shift 2
      ;;
    --synthesize)
      mode="synthesize"
      shift
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

if [[ -z "$project_dir" ]]; then
  usage >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
context_file="$project_dir/CONTEXTO.md"
questionnaire_file="$project_dir/QUESTIONNAIRE.md"
responses_file="$project_dir/QUESTIONNAIRE_RESPONSES.md"

session_field() {
  local key="$1"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

update_session_status() {
  local status="$1"
  local updated_at="$2"
  python3 - "$session_file" "$status" "$updated_at" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
status = sys.argv[2]
updated_at = sys.argv[3]
updates = {"phase": "2", "status": status, "updated_at": updated_at}
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
}

objective="$(session_field objective)"
timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

if [[ "$mode" == "synthesize" ]]; then
  if [[ ! -f "$responses_file" ]]; then
    echo "No existe $responses_file" >&2
    exit 1
  fi

  python3 - "$context_file" "$responses_file" <<'PY'
import sys
from pathlib import Path

context_path = Path(sys.argv[1])
responses_path = Path(sys.argv[2])
responses = responses_path.read_text(encoding="utf-8").strip()
text = context_path.read_text(encoding="utf-8")
block = "## INVESTIGACIÓN\n\n### Respuestas sintetizadas\n\n" + responses + "\n"

if "## INVESTIGACIÓN" in text:
    head, _, tail = text.partition("## INVESTIGACIÓN")
    if "\n## DECISIONES DE DISEÑO" in tail:
        _, _, rest = tail.partition("\n## DECISIONES DE DISEÑO")
        text = head + block + "\n## DECISIONES DE DISEÑO" + rest
    else:
        text = head + block
else:
    text = text.rstrip() + "\n\n" + block

context_path.write_text(text.rstrip() + "\n", encoding="utf-8")
PY

  update_session_status "active" "$timestamp"
  echo "Respuestas sintetizadas en $context_file"
  exit 0
fi

python3 - "$objective" "$questionnaire_file" <<'PY'
import sys
from pathlib import Path

objective = sys.argv[1]
output_path = Path(sys.argv[2])
text = objective.lower()

questions = [
    "¿Cuál es el resultado mínimo que considerarías completo?",
    "¿Qué parte del trabajo está explícitamente fuera de alcance?",
    "¿Hay archivos, carpetas o tecnologías que deban respetarse sí o sí?",
    "¿Cómo vas a validar que el resultado es correcto?",
    "¿Hay dependencias o integraciones obligatorias?",
    "¿Qué riesgos o cambios prefieres evitar?",
]

if "python" in text:
    questions.extend([
        "¿Qué versión de Python quieres asumir?",
        "¿El script debe aceptar argumentos o solo ejecutarse tal cual?",
    ])
elif any(word in text for word in ["api", "web", "frontend", "backend"]):
    questions.extend([
        "¿Debe exponerse una interfaz o endpoint concreto?",
        "¿Hay requisitos de seguridad, despliegue o rendimiento?",
    ])
else:
    questions.extend([
        "¿Qué ejemplo concreto representaría un resultado correcto?",
        "¿Hay un formato de entrega preferido?",
    ])

lines = [
    "# QUESTIONNAIRE",
    "",
    f"**Objetivo:** {objective}",
    "",
    "Responde debajo de cada pregunta para continuar el modo super.",
    "",
]

for idx, question in enumerate(questions[:8], start=1):
    lines.extend([
        f"## {idx}. {question}",
        "",
        "_Respuesta:_",
        "",
    ])

output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY

update_session_status "waiting_input" "$timestamp"
echo "Cuestionario guardado en $questionnaire_file"
