# workflow/ — Cómo trabajar en LAIA

Si eres una IA agéntica (Claude Code, Codex, OpenCode, Cursor, agentes propios) que va
a tocar algo en este repositorio, **lee esto primero**.

## Qué hay aquí

| Archivo | Lo que contiene |
|---|---|
| `00-start-here.md` | Este archivo. Punto de entrada. |
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
2. `01-canonical-sources.md` — dónde encontrar qué.
3. `02-how-to-work.md` — reglas duras.
4. `03-multi-ai-coordination.md` — sólo si vas a trabajar en paralelo con otra IA.

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
