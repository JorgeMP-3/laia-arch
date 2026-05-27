# Evidencia — Integración skills de dev (mattpocock) · 2026-05-27

Verificación de la integración de skills de workflow de desarrollo para Claude Code, Codex
y OpenCode. Upstream `mattpocock/skills` @ `0288510`.

## 1. Descubrimiento estructural (reproducible, sin coste)

13 skills en `.claude/skills/`, todas con frontmatter válido (`name` + `description`) y
`name` == nombre de carpeta (requisito de invocación correcta):

```
diagnose, git-guardrails, grill-me, grill-with-docs, handoff,
improve-codebase-architecture, setup-matt-pocock-skills, tdd, to-issues,
to-prd, triage, write-a-skill, zoom-out   → todas name=OK desc=ok
```

Symlinks de Codex (`.codex/skills/`) almacenados por git como mode **120000** (link, no
copia) y resolviendo al `SKILL.md` real:

```
git ls-files -s .codex/skills  →  12 entradas 120000
readlink .codex/skills/to-prd  →  ../../.claude/skills/to-prd  (frontmatter name: to-prd)
```

`git-guardrails` correctamente **ausente** de `.codex/skills/` (es solo-Claude: instala un
hook `PreToolUse`). No se ha activado: `.claude/settings.json` intacto.

`git check-ignore` confirma que `.claude/skills/` y `.codex/skills/` **no** están
gitignored (`.gitignore` solo ignora `.skills_prompt_snapshot.json` y `archived-skills/`).

## 2. Compatibilidad de paths por herramienta (según docs oficiales)

| Herramienta | Path leído | Estado |
|---|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` | ✅ archivos reales; resuelve vía `/skill-name` (confirmado en `claude --help`) |
| OpenCode | `.claude/skills/` (compat nativa) | ✅ mismos archivos reales |
| Codex | `.codex/skills/<name>/SKILL.md` | ✅ symlinks 120000 → SKILL.md real |

## 3. Invocación viva (paso manual — no auto-ejecutado)

Ninguna de las 3 CLIs expone un subcomando offline para "listar skills", y una invocación
viva llama al modelo (consume auth/créditos). Por eso la invocación real se deja como
comprobación manual de Jorge:

- **Claude Code:** abrir `claude` en `~/LAIA` y teclear `/grill-me` (debe autocompletar y cargar).
- **Codex:** abrir `codex` en `~/LAIA`, `/skills` lista el catálogo; `$grill-me ...` lo invoca.
- **OpenCode:** abrir `opencode` en `~/LAIA`; la skill se auto-activa por `description` o vía comando.

> Nota honesta: la verificación automatizada cubre descubrimiento e integridad (secciones
> 1-2). La invocación viva end-to-end no se ejecutó automáticamente para no gastar
> auth/créditos de las 3 CLIs; los comandos de arriba la reproducen en segundos.
