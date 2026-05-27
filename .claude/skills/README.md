# Skills de desarrollo — guía de uso (Jorge)

Catálogo de **skills de workflow** para las IAs que **construyen** LAIA (Claude Code, Codex,
OpenCode). Son atajos de proceso: ejecutan paso a paso el protocolo de ingeniería de LAIA.

> ⚠️ Esto NO es el Marketplace. Las skills de **producto** (capacidades de los PA-AGORA)
> viven en `skills/` (raíz del repo) y son otra cosa. Estas son solo para desarrollar.

## Cómo invocarlas

| Herramienta | Manual | Automático |
|---|---|---|
| **Claude Code** | `/grill-me` | la IA la elige sola por su `description` |
| **Codex** | `$grill-me` · o `/skills` para ver la lista | igual, auto por `description` |
| **OpenCode** | "usa la skill tdd" | igual, auto por `description` |

Fuente única en `.claude/skills/`; Codex las ve por symlinks en `.codex/skills/`. Tras
añadir/cambiar skills, **reinicia la herramienta** para que las relea.

## El flujo completo (tu protocolo FASE 1→4)

```
Idea ──▶ /grill-me ──▶ /to-prd ──▶ /to-issues ──▶ /tdd ──▶ (bug) /diagnose · /triage
        (interrogar)   (PRD)       (slices)        (código)        (cerrar) /handoff
```

## Qué hace cada una y cuándo usarla

### FASE 1 — Antes de tocar código
- **`/grill-me`** — Te interroga a fondo sobre una idea/plan hasta resolver todas las dudas.
  Úsala al proponer cualquier feature, ANTES de escribir nada.
- **`/grill-with-docs`** — Igual, pero contrastando con el dominio (`LAIA_ECOSYSTEM.md`) y
  afinando terminología. Úsala cuando el debate toca conceptos/arquitectura.

### FASE 2 — Planificar
- **`/to-prd`** — Convierte la conversación en un PRD técnico y lo guarda en `workflow/plans/`.
- **`/to-issues`** — Parte ese plan en trozos independientes (vertical slices), cada uno
  demostrable por sí solo, en `workflow/problems.md` / `workflow/plans/`.

### FASE 3 — Programar
- **`/tdd`** — Te guía en Red-Green-Refactor: un test → código mínimo → repetir. Los tests
  van a `~/LAIA/tests/`. Es el "innegociable" de tu protocolo.

### FASE 4 — Cuando hay bugs
- **`/diagnose`** — Disciplina para bugs difíciles: construir un loop de reproducción →
  causa raíz → fix → test de regresión. Para cuando "algo está roto" y no es obvio.
- **`/triage`** — Gestiona incidencias por estados en `workflow/problems.md` (clasificar,
  pedir info, marcar listo). Para ordenar la cola de problemas.

### Apoyo (en cualquier momento)
- **`/zoom-out`** — "No conozco esta zona": te da un mapa de módulos y llamadores.
- **`/improve-codebase-architecture`** — Busca refactors hacia módulos más profundos y
  testeables; genera un informe HTML. Para limpiar deuda técnica con criterio.
- **`/handoff`** — Cierre de turno: resume la sesión. En LAIA, la fuente de verdad es
  actualizar `workflow/changelog.md` (no un fichero temporal).

### Meta
- **`/write-a-skill`** — Crear una skill de desarrollo nueva (no de Marketplace).
- **`/setup-matt-pocock-skills`** — Configura tracker/labels/dominio. **Ya hecho en LAIA**
  (está en `AGENTS.md` §Agent skills); rara vez lo necesitarás.
- **`/git-guardrails`** — *(solo Claude Code, NO activada)* instala un hook que bloquea
  comandos git peligrosos. Invócala solo si quieres activar esa red de seguridad.

## Mantenimiento

- **Procedencia y cómo actualizar desde upstream**: `.claude/skills/UPSTREAM.md`.
- Cada `SKILL.md` tiene al final un bloque `## LAIA context` (entre `<!-- LAIA:START/END -->`)
  con la adaptación específica de LAIA. El resto es de mattpocock.
- Config que consumen las skills (tracker = ficheros locales, dominio = `LAIA_ECOSYSTEM.md`):
  `AGENTS.md` §Agent skills.
