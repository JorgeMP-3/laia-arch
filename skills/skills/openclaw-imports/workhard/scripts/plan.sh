#!/usr/bin/env bash

set -euo pipefail

script_dir="$(python3 - "$0" <<'PY'
import os, sys
print(os.path.dirname(os.path.realpath(sys.argv[1])))
PY
)"

project_dir="${1:-}"
if [[ -z "$project_dir" ]]; then
  echo "Uso: plan.sh <project_dir>" >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
todo_file="$project_dir/TODO.md"
context_file="$project_dir/CONTEXTO.md"
notes_file="$project_dir/NOTES.md"

session_field() {
  local key="$1"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

project_name="$(session_field project_name)"
objective="$(session_field objective)"
mode="$(session_field mode)"
ia_mode="$(session_field ia_mode)"
timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

python3 - "$objective" "$project_name" "$mode" "$ia_mode" "$timestamp" "$todo_file" "$notes_file" <<'PY'
import json
import sys
from pathlib import Path

objective, project_name, mode, ia_mode, timestamp, todo_path, notes_path = sys.argv[1:]
text = objective.lower()

steps = []

if "python" in text and ("hola mundo" in text or "hello world" in text):
    steps = [
        {
            "description": "Crear el script principal hello_world.py",
            "command": """SHELL:python3 -c "from pathlib import Path; Path('hello_world.py').write_text('print(\\\"Hola Mundo\\\")\\n', encoding='utf-8')" """.strip(),
            "risk": "low",
        },
        {
            "description": "Ejecutar el script y validar la salida",
            "command": "SHELL:python3 hello_world.py",
            "risk": "low",
        },
        {
            "description": "Crear README mínimo con instrucciones de uso",
            "command": """SHELL:python3 -c "from pathlib import Path; Path('README.md').write_text('# Hola Mundo\\n\\nEjecuta: python3 hello_world.py.\\n', encoding='utf-8')" """.strip(),
            "risk": "low",
        },
    ]
elif "python" in text and "script" in text:
    steps = [
        {
            "description": "Definir el archivo Python principal para el entregable",
            "command": "PROMPT:Crear el archivo principal del script solicitado respetando el objetivo y el contexto del proyecto.",
            "risk": "low",
        },
        {
            "description": "Implementar la lógica principal del script",
            "command": "PROMPT:Implementar la funcionalidad pedida por el usuario y dejar el script ejecutable.",
            "risk": "medium",
        },
        {
            "description": "Ejecutar y verificar el comportamiento esperado",
            "command": "PROMPT:Ejecutar una verificación real del script y registrar el resultado en LOG.md.",
            "risk": "low",
        },
    ]
else:
    steps = [
        {
            "description": "Revisar el contexto y delimitar el cambio exacto",
            "command": "PROMPT:Inspeccionar el proyecto, archivos y restricciones antes de tocar nada.",
            "risk": "low",
        },
        {
            "description": "Implementar el cambio principal",
            "command": "PROMPT:Ejecutar el trabajo principal definido en CONTEXTO.md.",
            "risk": "medium",
        },
        {
            "description": "Verificar el resultado final",
            "command": "PROMPT:Comprobar que el resultado cumple el objetivo y actualizar notas y log.",
            "risk": "low",
        },
    ]

step_lines = []
for idx, step in enumerate(steps, start=1):
    step_lines.append(
        f"| {idx} | {step['description']} | {step['command']} | {step['risk']} | ⏳ | - |"
    )

todo = f"""# TODO — {project_name}

**Creado:** {timestamp}
**Modo:** {mode}
**IA:** {ia_mode}
**Fase actual:** 3

---

## PASOS

| # | Descripción | Comando/Prompt | Riesgo | Estado | Completado |
|---|-------------|----------------|--------|--------|------------|
{chr(10).join(step_lines)}

---

## SIGUIENTE PASO

**Número:** 1
**Descripción:** {steps[0]['description']}
**Riesgo:** {steps[0]['risk']}
"""

Path(todo_path).write_text(todo.rstrip() + "\n", encoding="utf-8")

with open(notes_path, "a", encoding="utf-8") as fh:
    fh.write(f"\n## {timestamp} — Plan generado\n")
    fh.write(f"- Objetivo: {objective}\n")
    fh.write(f"- Pasos creados: {len(steps)}\n")
    fh.write(f"- Modo: {mode} / {ia_mode}\n")
PY

python3 - "$session_file" "$timestamp" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
timestamp = sys.argv[2]
updates = {
    "phase": "3",
    "current_step": "1",
    "status": "planned",
    "updated_at": timestamp,
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

python3 - "$context_file" "$timestamp" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
timestamp = sys.argv[2]
text = path.read_text(encoding="utf-8")
lines = []
for line in text.splitlines():
    if line.startswith("**Fase:**"):
        lines.append("**Fase:** 3")
    elif line.startswith("**Última actualización:**"):
        lines.append(f"**Última actualización:** {timestamp}")
    else:
        lines.append(line)
path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY

echo "Plan generado en $todo_file"
