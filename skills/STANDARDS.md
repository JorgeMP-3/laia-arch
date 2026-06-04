# Estándares de autoría — skills de PRODUCTO (Marketplace)

Reglas para toda skill nueva o modernizada en `skills/` (las skills que el Marketplace de
LAIA-AGORA distribuye a los PA-AGORA). Adaptadas del estándar HARDLINE de Hermes upstream
(2026-06-02) a la realidad de este catálogo (114 skills auditadas). Los reviewers rechazan
PRs que las violen.

> NO confundir con las skills de DESARROLLO (`~/laia-developers/skills/`, para las IAs que
> construyen LAIA). Estas son las del producto.

## Límites duros (los aplica el validador de `.laia-core`)

El loader (`agent/skill_utils.py`) y el validador (`tools/skill_manager_tool.py`) exigen:
frontmatter YAML válido entre `---`, `name` (≤64 chars, lowercase-con-guiones), `description`
presente (≤1024 chars techo técnico) y cuerpo no vacío (≤100k chars). Una skill que no parsea
**no se carga** (caso real: `mlx-local-servers`, sin frontmatter → invisible; ver PROBLEMS).

## Estándares de autoría (revisión humana/IA)

1. **`description`: UNA frase, en INGLÉS, ≤120 caracteres, termina en punto.** El techo
   técnico es 1024, pero las descripciones largas diluyen la atención del modelo cuando hay
   100+ skills cargadas. Di la *capacidad*, no la implementación. Sin marketing ("powerful",
   "comprehensive", "seamless"). No repitas el nombre de la skill. Nada de descripciones
   multilínea (`>`).
   - ✅ `Search arXiv papers by keyword, author, category, or ID.`
   - ❌ descripción de 392 chars contando la historia del proyecto (caso real).
   - Verifica: `python3 -c "import re,pathlib;d=re.search(r'^description: (.*)$', pathlib.Path('skills/<cat>/<skill>/SKILL.md').read_text(), re.M).group(1);assert len(d)<=120, len(d)"`

2. **Frontmatter mínimo completo:** `name`, `description`, `version` (semver sin comillas),
   `author`, `license`, y `metadata.laia.tags` + `metadata.laia.related_skills`.
   - **El namespace es `metadata.laia`** — `metadata.hermes` es legacy del fork (15 skills
     pendientes de migrar); no crear skills nuevas con él.
   - `tags:` top-level está **deprecated** (quedan 6) — siempre bajo `metadata.laia.tags`.

3. **Idioma: INGLÉS** en frontmatter y cuerpo (política de código 2026-06-01). Hoy hay 2
   skills en español — no añadir más; migrar al tocarlas.

4. **Cuerpo con el orden de secciones moderno** (capitalización EXACTA — hoy conviven
   "When to Use" y "When to use"):
   `# <Skill> Title` → intro de 2-3 frases (qué hace y qué NO) → `## When to Use` →
   `## Prerequisites` → `## Quick Reference` → `## Procedure` → `## Pitfalls` →
   `## Verification`. Objetivo: ~100 líneas una skill simple, ~200 una compleja.

5. **Ficheros auxiliares con criterio:** lógica no trivial (parsers, walkers, setup) va en
   `scripts/`; documentación de apoyo en `references/`; plantillas en `templates/`. Regla
   práctica: si el cuerpo pasa de ~15k chars, parte a `references/` (caso real a evitar:
   una skill de 103k chars en el cuerpo).

6. **`platforms:` auditado contra lo que los scripts importan de verdad** (`[linux]`,
   `[macos]`…). Si usa primitivas POSIX-only o herramientas de un solo OS, decláralo;
   si se puede hacer cross-platform con stdlib, hazlo cross-platform.

7. **`author` acredita primero al humano** si la skill viene de una contribución; el agente
   que ayudó va segundo.

8. **`related_skills` reales:** nombres que existen en el catálogo (no inventar).

## Checklist del reviewer (rechazar si falla)

- [ ] Frontmatter parsea y pasa el validador (cárgala en un agente de prueba).
- [ ] `description` ≤120, inglés, una frase, punto final, sin marketing.
- [ ] `metadata.laia.*` (no `hermes`, no `tags` top-level).
- [ ] Secciones en el orden y capitalización del punto 4.
- [ ] Cuerpo ≤~15k chars o partido a `references/`.
- [ ] `platforms` coherente con los imports de `scripts/`.

## Deuda conocida del catálogo (no bloquea skills nuevas)

Inventariada el 2026-06-02 (114 skills): 1 sin frontmatter (no carga), 4 con campos
malformados, 4 con descripción vacía/truncada, 15 en `metadata.hermes`, 6 con `tags`
top-level, 2 en español, headings con capitalización mixta. Registrada en
`~/laia-developers/workflow-main/PROBLEMS.md` (`marketplace-skills-deuda-formato`).
La migración se hace **al tocar cada skill**, no en un big-bang.
