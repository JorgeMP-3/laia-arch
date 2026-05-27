---
name: handoff
description: "Cierre de turno — Resumir la sesión para que otra IA continúe; en LAIA, actualizar workflow/changelog.md. Use when compacting the conversation into a handoff for a fresh agent."
argument-hint: "What will the next session be used for?"
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

<!-- LAIA:START — no es upstream. Todo lo de arriba es de mattpocock/skills; al re-vendorizar, reemplaza solo lo de arriba y conserva este bloque. -->
## LAIA context

> **Dev tooling de LAIA** — skill de workflow para las IAs que construyen LAIA. NO es una skill del Marketplace ni se expone a usuarios/PA-AGORA.

En LAIA el handoff canónico **no** es un fichero temporal: es la **memoria compartida en git**. Al cerrar turno, actualiza lo que aplique (`workflow/02-how-to-work.md` §Cierre de turno, y `03-multi-ai-coordination.md` §Handoff):

- `workflow/changelog.md` — qué se hizo, qué quedó abierto, qué vale saber mañana (todo cambio material).
- `workflow/problems.md` — si descubriste un problema (aunque no lo arregles).
- `workflow/security.md` — si tocaste credenciales, permisos, red o secrets.
- Plan completado/abandonado → mueve `workflow/plans/<plan>.md` a `workflow/plans/archive/`.

El doc temporal de upstream es opcional y complementario; la fuente de verdad del handoff es el `changelog.md`.
<!-- LAIA:END -->

