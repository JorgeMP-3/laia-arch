---
name: grill-me
description: "FASE 1 — Interrogar a fondo una idea o plan ANTES de tocar código, resolviendo cada rama del árbol de decisión hasta alinearse. Use when stress-testing a plan, getting grilled on a design, mentions 'grill me', or before starting any LAIA feature."
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

<!-- LAIA:START — no es upstream. Todo lo de arriba de este marcador es de mattpocock/skills; al re-vendorizar, reemplaza solo lo de arriba y conserva este bloque. -->
## LAIA context

> **Dev tooling de LAIA** — skill de workflow para las IAs que construyen LAIA. NO es una skill del Marketplace ni se expone a usuarios/PA-AGORA.

Equivale a la **FASE 1 ("Grill me")** del protocolo de ingeniería de LAIA. Al aplicarla en este repo, el interrogatorio DEBE cubrir como mínimo:

- **Encaje canónico:** ¿la idea encaja en `LAIA_ECOSYSTEM.md`? Si lo contradice, bloquéala — el documento es canónico (regla absoluta 1).
- **Muerte y estado:** ¿qué pasa si el container muere a media operación? ¿cómo se maneja el estado? ¿es idempotente (principios Hermes Agent)?
- **Permisos y separación:** ¿qué implica para los permisos root en `PA-AGORA` y la separación LAIA-ARCH / LAIA-AGORA?
- **Escalabilidad / deuda:** ¿escala? ¿genera deuda técnica?

No se pasa a planificar (skill `to-prd`) hasta resolver todas las ramas del árbol de decisión y estar 100% alineados con Jorge.
<!-- LAIA:END -->
