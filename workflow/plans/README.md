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
  Fases 1-4 completadas (bug TTY cerrado, contrato JSON, Textual default,
  legacy rich borrado, unificado bajo `bin/laia`); 5 CRITICAL + 4 HIGH
  hardening fixes commiteados; Fase 5 pendiente (headless TOML + pirámide
  de tests). Owner: claude-code.
- [`2026-05-25-installer-vm-smoke.md`](2026-05-25-installer-vm-smoke.md)
  — Guía para validar install + clone en VM real antes de Fase 5.
  Comandos concretos para Multipass, qué verificar, dónde mirar si algo
  falla. Owner: jorge (operador), claude-code (autor).
- [`2026-05-25-dev-stable-versioning.md`](2026-05-25-dev-stable-versioning.md)
  — Runbook aprobado para separar desarrollo y producción: `main` para dev,
  `stable` para prod, tags semver sobre `stable`, promote manual y rollback.
  Owner: próxima IA implementadora, con Jorge aprobando cambios materiales.
- [`2026-05-25-ecosystem-e2e-verification.md`](2026-05-25-ecosystem-e2e-verification.md)
  — Migración IN-PLACE de ~/.laia/ al layout canónico post-`d02afcb0`
  (NO reinstala — preserva los 482 MB de data acumulada: workspaces,
  sessions, atlas, plugins, memorias) + verificación E2E con las 22
  secciones funcionales del ecosistema documentadas en
  `docs/db-export/nodes/`. 1 IA secuencial, esta misma VM, snapshot
  previo obligatorio. ~71 checks F.X.Y. Tiempo: 1-2 h. **Aprobado,
  listo para ejecutar.** Owner: próxima IA implementadora.
- [`integrity-tests.md`](integrity-tests.md) — Runner de integridad por capas.
  Owner: codex.
