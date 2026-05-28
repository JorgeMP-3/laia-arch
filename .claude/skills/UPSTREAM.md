# Skills de dev — procedencia y mantenimiento

Estas skills (`.claude/skills/*/SKILL.md`) son **tooling de desarrollo** vendorizado desde
[mattpocock/skills](https://github.com/mattpocock/skills). Son para las IAs que
**construyen** LAIA (Claude Code, Codex, OpenCode). **No** tienen nada que ver con el
producto LAIA: no van al Marketplace (`skills/` en la raíz del repo), no se exponen a
PA-AGORA ni a usuarios.

## Versión vendorizada

- Upstream: `mattpocock/skills`
- Commit: `0288510dd61ff6ef7c2003834082ab8f2387e80e`
- Fecha vendor: 2026-05-27

## Fan-out a las 3 herramientas

- **Claude Code** y **OpenCode** leen `.claude/skills/` nativamente. Fuente de verdad.
- **Codex** lee `.codex/skills/`; ahí hay un **symlink relativo por skill** apuntando a
  `../../.claude/skills/<name>`. Las skills Claude-only (p.ej. las que instalan un hook de
  Claude Code) **no** llevan symlink en `.codex/`.

## Convención de adaptación LAIA (cómo re-vendorizar)

Cada `SKILL.md` conserva el **cuerpo** de upstream verbatim. Dos excepciones en el
frontmatter, documentadas: (a) el campo `description:` se localizó a español con prefijo de
FASE/categoría para que el diálogo `/skills` se lea claro — al re-vendorizar, re-aplica el
prefijo; (b) `git-guardrails` localizó su `name`. Las adaptaciones LAIA del cuerpo viven en
un bloque al final delimitado por:

```
<!-- LAIA:START ... -->
## LAIA context
...
<!-- LAIA:END -->
```

**Todo lo que está por encima de `<!-- LAIA:START -->` es upstream puro.** Para actualizar
una skill desde un nuevo commit de mattpocock: reemplaza todo lo de arriba del marcador con
el nuevo contenido upstream y conserva el bloque `LAIA:START…LAIA:END` intacto. Actualiza
el commit de arriba.

## Skills vendorizadas

| Skill | Origen upstream | Codex symlink | Adaptación LAIA |
|---|---|---|---|
| grill-me | productivity/grill-me | sí | FASE 1: ejes de interrogatorio LAIA |
| to-prd | engineering/to-prd | sí | FASE 2: PRD → `workflow/plans/`, OK de Jorge |
| tdd | engineering/tdd | sí | FASE 3: tests en `~/LAIA/tests/`, suite completa |
| triage | engineering/triage | sí | tracker = `workflow/problems.md` |
| diagnose | engineering/diagnose | sí | FASE 4: causa raíz en logs/`agora.db` |
| handoff | productivity/handoff | sí | cierre de turno = `changelog.md` (no /tmp) |
| to-issues | engineering/to-issues | sí | tracker local `problems.md`/`plans/` |
| git-guardrails | misc/git-guardrails-claude-code | **no** (Claude-only) | hook NO activado; `name` localizado |
| zoom-out | engineering/zoom-out | sí | dominio = `LAIA_ECOSYSTEM.md`/`project-map.md` |
| improve-codebase-architecture | engineering/improve-codebase-architecture | sí | ADRs→`arch-layout.md`; no editar canónico |
| grill-with-docs | engineering/grill-with-docs | sí | drafts a `workflow/_inbox/`, no editar canónico |
| write-a-skill | productivity/write-a-skill | sí | distingue skill dev vs Marketplace |
| setup-matt-pocock-skills | engineering/setup-matt-pocock-skills | sí | config en `AGENTS.md` §Agent skills, no `docs/agents/` |
