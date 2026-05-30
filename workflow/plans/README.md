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

## Estado actual del ecosistema

- [`2026-05-30-estado-roadmap-integraciones.md`](2026-05-30-estado-roadmap-integraciones.md)
  — **Snapshot consolidado**: estado tras la estabilización + release `v0.2.0`, siguientes
  pasos (ventana de prod: migrar v1→v2 → deploy → B2) y posibles integraciones (canales,
  MCP, skills). **Empieza por aquí** para saber dónde está el proyecto. Owner: claude-code / Jorge.

## Mega-proyecto activo

- [`estabilizacion/`](estabilizacion/) — **Estabilización de LAIA-ARCH + entorno de
  desarrollo (VM)**. ✅ **Completada** (slices B1–D2 mergeados, release `v0.2.0` en `stable`,
  D2 verde validado en la VM). Bundle: idea/estrategia, plan técnico, auditoría, snapshot del
  servidor, runbook de migración C3 y checklist [`slices.md`](estabilizacion/slices.md).
  Pendiente: **ventana de prod** (HITL) — ver el snapshot de estado de arriba. Owner: claude-code / Jorge.

## Planes activos

- [`2026-05-25-installer-textual-remake.md`](2026-05-25-installer-textual-remake.md)
  — Remake del wizard de instalación/clonado con Textual. **En curso** (Fases 1-4
  hechas; Fase 5 pendiente: headless TOML + pirámide de tests). Owner: claude-code.
- [`2026-05-25-installer-vm-smoke.md`](2026-05-25-installer-vm-smoke.md)
  — Guía para validar install + clone en VM real. Owner: jorge (operador),
  claude-code (autor).
- [`atlas-remaining-work-phases-2026-05-27.md`](atlas-remaining-work-phases-2026-05-27.md)
  — Fases ⏳ pendientes de adopción de Atlas (1-4), estructura `/opt` (5) y cosmético
  (6). La herramienta Atlas v2 ya está completa. Owner: por asignar.

## Archivados (`archive/`)

Trabajo completado o superseded — histórico, no tocar: Atlas v2 (`atlas-audit-report`,
`atlas-v2-implementation-report`, `atlas-visualize-fix`, componentes en `atlas-v2/`),
`dev-stable-versioning` (superseded por `release-flow.md`), y la limpieza GitHub/Hermes.
