# Plans

Planes activos y archivados de trabajo en LAIA. Un archivo Markdown por plan.

## Convención

- Nombre: `YYYY-MM-DD-<slug-corto>.md`.
- El plan vive aquí desde antes de empezar la tarea hasta que se ejecuta.
- Planes completados se mueven a `plans/archive/`.
- Planes obsoletos sin ejecutar también se archivan, prefijo `ABANDONED-`.

## Plantilla mínima

```markdown
# <título-corto>

- **Fecha**: 2026-MM-DD
- **Owner**: <agente-o-jorge>
- **Estado**: draft | aprobado | en-curso | completado | abandonado

## Contexto
Por qué se propone esto. El problema que resuelve. Qué se intenta conseguir.

## Plan
Pasos concretos. Archivos a tocar. Decisiones tomadas con su razón.

## Verificación
Cómo se sabe que está hecho. Tests, comandos, observaciones.

## Riesgos
Lo que puede salir mal y cómo mitigarlo.
```

## Planes activos

- [`2026-05-25-installer-textual-remake.md`](2026-05-25-installer-textual-remake.md)
  — Remake del wizard de instalación/clonado con Textual. **En curso**:
  Fases 1-3 completadas (bug TTY cerrado, contrato JSON, Textual opt-in);
  Fases 4-5 pendientes (flip default + borrado legacy; headless TOML +
  tests). Owner: claude-code.
- [`integrity-tests.md`](integrity-tests.md) — Runner de integridad por capas.
  Owner: codex.
