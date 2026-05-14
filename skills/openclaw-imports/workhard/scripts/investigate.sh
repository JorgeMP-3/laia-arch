#!/usr/bin/env bash

set -euo pipefail

script_dir="$(python3 - "$0" <<'PY'
import os, sys
print(os.path.dirname(os.path.realpath(sys.argv[1])))
PY
)"
skill_dir="$(cd "$script_dir/.." && pwd)"
openclaw_root="$(cd "$skill_dir/../.." && pwd)"

project_dir="${1:-}"
objective="${2:-}"

if [[ -z "$project_dir" ]]; then
  echo "Uso: investigate.sh <project_dir> [objective]" >&2
  exit 1
fi

session_file="$project_dir/SESSION.md"
context_file="$project_dir/CONTEXTO.md"
investigation_file="$project_dir/INVESTIGATION.md"

session_field() {
  local key="$1"
  grep -E "^${key}:" "$session_file" | head -n 1 | cut -d: -f2- | sed 's/^ //'
}

update_session() {
  local updated_at="$1"
  python3 - "$session_file" "$updated_at" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
updated_at = sys.argv[2]
updates = {"phase": "2", "status": "researching", "updated_at": updated_at}
lines = path.read_text(encoding="utf-8").splitlines()
out = []

for line in lines:
    matched = False
    for key, value in updates.items():
        if line.startswith(f"{key}: "):
            out.append(f"{key}: {value}")
            matched = True
            break
    if not matched:
        out.append(line)

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

if [[ -z "$objective" ]]; then
  objective="$(session_field objective)"
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
project_name="$(session_field project_name)"
update_session "$timestamp"

python3 - "$objective" "$investigation_file" "$project_name" "$timestamp" <<'PY'
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

objective, investigation_path, project_name, timestamp = sys.argv[1:]
text = objective.lower()

queries = [
    objective,
    f"{objective} best practices",
    f"{objective} examples",
]

results = []
for query in queries:
    try:
        encoded = urllib.parse.quote(query)
        req = urllib.request.Request(
            f"https://html.duckduckgo.com/html/?q={encoded}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        body = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        for raw_href, raw_title in re.findall(r'result__a" href="(.*?)".*?>(.*?)</a>', body):
            href = html.unescape(raw_href)
            parsed = urllib.parse.urlparse(href)
            if "duckduckgo.com" in parsed.netloc:
                qs = urllib.parse.parse_qs(parsed.query)
                href = qs.get("uddg", [href])[0]
            title = re.sub(r"<.*?>", "", html.unescape(raw_title)).strip()
            if not title:
                continue
            item = {"query": query, "title": title, "url": href}
            if item not in results:
                results.append(item)
            if len(results) >= 6:
                break
        if len(results) >= 6:
            break
    except Exception:
        continue

best_practices = []
if "python" in text:
    best_practices.extend([
        "Mantener una entrada simple y ejecutable con python3.",
        "Usar nombres de archivo claros y evitar dependencias innecesarias.",
        "Validar la ejecución real del script como parte del flujo.",
    ])
if any(word in text for word in ["api", "rest", "web", "frontend", "backend"]):
    best_practices.extend([
        "Definir alcance mínimo verificable antes de añadir extras.",
        "Separar implementación, verificación y documentación.",
    ])
if not best_practices:
    best_practices.extend([
        "Dividir el trabajo en pasos pequeños con una salida verificable.",
        "Documentar decisiones antes de ejecutar cambios medianos o altos.",
        "Mantener el entregable en estado limpio tras cada paso.",
    ])

lines = [
    f"# INVESTIGATION — {project_name}",
    "",
    f"**Generado:** {timestamp}",
    f"**Objetivo:** {objective}",
    "",
    "## Hipótesis inicial",
    "",
    "- El trabajo necesita un plan ejecutable y verificable.",
    "- La investigación previa debe reducir ambigüedad antes de planificar.",
    "",
    "## Mejores prácticas sugeridas",
    "",
]
for item in best_practices:
    lines.append(f"- {item}")

lines.extend(["", "## Búsqueda web inicial", ""])
if results:
    for item in results:
        lines.append(f"- [{item['title']}]({item['url']})")
else:
    lines.append("- No se pudieron recuperar resultados web desde este entorno compartido.")

lines.extend([
    "",
    "## Recomendación",
    "",
    "Usar el cuestionario para resolver supuestos sobre alcance, restricciones y definición de hecho.",
])

Path(investigation_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY

python3 - "$context_file" "$investigation_file" <<'PY'
import sys
from pathlib import Path

context_path = Path(sys.argv[1])
investigation_file = Path(sys.argv[2]).name
text = context_path.read_text(encoding="utf-8")
replacement = f"## INVESTIGACIÓN\n\nVer resumen inicial en `{investigation_file}`.\n"

if "## INVESTIGACIÓN" in text:
    head, _, tail = text.partition("## INVESTIGACIÓN")
    if "\n## DECISIONES DE DISEÑO" in tail:
        _, _, rest = tail.partition("\n## DECISIONES DE DISEÑO")
        text = head + replacement + "\n## DECISIONES DE DISEÑO" + rest
    else:
        text = head + replacement
else:
    text = text.rstrip() + "\n\n" + replacement

context_path.write_text(text.rstrip() + "\n", encoding="utf-8")
PY

echo "Investigación guardada en $investigation_file"
