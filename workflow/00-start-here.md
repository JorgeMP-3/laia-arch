# workflow/ — Cómo trabajar en LAIA

Si eres una IA agéntica (Claude Code, Codex, OpenCode, Cursor, agentes propios) que va
a tocar algo en este repositorio, **lee esto primero**.

## Qué hay aquí

| Archivo | Lo que contiene |
|---|---|
| `00-start-here.md` | Este archivo. Punto de entrada. |
| `ai-mindset.md` | Cómo pensar al trabajar (right-size, mentalidad senior, el porqué de los gates). |
| `01-canonical-sources.md` | Dónde vive la verdad. Qué fuentes son canónicas. |
| `02-how-to-work.md` | Reglas: branches, commits, cierre de turno, qué no hacer. |
| `03-multi-ai-coordination.md` | Cómo coordinar cuando hay varias IAs simultáneas. |
| `arch-data-layout.md` | Separación `/home/jorge/LAIA-ARCH` vs `/srv/laia/arch`. |
| `changelog.md` | Bitácora de cambios materiales. Se actualiza al cerrar turno. |
| `security.md` | Bitácora de hallazgos y acciones de seguridad. |
| `problems.md` | Bitácora de problemas descubiertos. Se anota AL DESCUBRIRLOS. |
| `release-flow.md` | Flujo dev/prod: `main`, `stable`, tags, promote, rollback. |
| `plans/` | Planes activos. Un archivo por plan. |

## Orden de lectura

1. `~/LAIA/LAIA_ECOSYSTEM.md` — qué es LAIA. **Es el documento canónico.**
2. `~/LAIA/AGENTS.md` — reglas operativas y guardarraíles (común a las 3 IAs).
   El porqué y la mentalidad (right-size, no ritual): `ai-mindset.md`.
3. `01-canonical-sources.md` — dónde encontrar qué.
4. `02-how-to-work.md` — reglas duras.
5. `03-multi-ai-coordination.md` — sólo si vas a trabajar en paralelo con otra IA.

El **protocolo de ingeniería** (FASE 1-4: grill, PRD, TDD, diagnóstico) se ejecuta vía
**skills de workflow** compartidas en `~/LAIA/.claude/skills/` (Codex vía `.codex/skills/`).
Catálogo y config en `AGENTS.md` §Agent skills; procedencia en `.claude/skills/UPSTREAM.md`.
No confundir con las skills de **producto** del Marketplace (`skills/` en la raíz).

## Reglas duras antes de cualquier acción

1. **No inventes paths, endpoints ni componentes.** Si no aparece en `LAIA_ECOSYSTEM.md`
   o en `docs/db-export/`, no existe.
2. **Si encuentras contradicciones** entre `LAIA_ECOSYSTEM.md` y otra fuente, gana
   `LAIA_ECOSYSTEM.md`. Si te bloquea, escala a Jorge.
3. **Toda integración nueva necesita su test en `~/LAIA/tests/`.** Sin test que la
   verifique contra el resto del ecosistema, la integración está incompleta. Antes
   de declarar "hecho" se corre la **suite entera** para confirmar que nada se rompió.
   Detalle en `02-how-to-work.md` sección "Tests".
4. **Antes de cerrar tu turno**, actualiza si aplica:
   - `changelog.md` si cambiaste algo material.
   - `problems.md` si descubriste un problema (aunque no lo arregles).
   - `security.md` si tocaste algo relacionado con seguridad.
5. **No edites `LAIA_ECOSYSTEM.md` sin consenso explícito de Jorge.** Es el contrato
   del proyecto.

## Quién es Jorge

Jorge Miralles Pérez es el desarrollador y único operador de LAIA-ARCH (la expresión
admin de LAIA, invisible para los usuarios finales). Es quien aprueba cambios materiales.
