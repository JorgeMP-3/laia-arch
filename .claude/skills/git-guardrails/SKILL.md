---
name: git-guardrails
description: "Solo-Claude (NO activada en LAIA) — Instalar un hook que bloquea comandos git peligrosos (push, reset --hard, clean, branch -D). Use when adding git safety hooks or preventing destructive git operations."
---

# Setup Git Guardrails

Sets up a PreToolUse hook that intercepts and blocks dangerous git commands before Claude executes them.

## What Gets Blocked

- `git push` (all variants including `--force`)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

When blocked, Claude sees a message telling it that it does not have authority to access these commands.

## Steps

### 1. Ask scope

Ask the user: install for **this project only** (`.claude/settings.json`) or **all projects** (`~/.claude/settings.json`)?

### 2. Copy the hook script

The bundled script is at: [scripts/block-dangerous-git.sh](scripts/block-dangerous-git.sh)

Copy it to the target location based on scope:

- **Project**: `.claude/hooks/block-dangerous-git.sh`
- **Global**: `~/.claude/hooks/block-dangerous-git.sh`

Make it executable with `chmod +x`.

### 3. Add hook to settings

Add to the appropriate settings file:

**Project** (`.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

**Global** (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

If the settings file already exists, merge the hook into existing `hooks.PreToolUse` array — don't overwrite other settings.

### 4. Ask about customization

Ask if user wants to add or remove any patterns from the blocked list. Edit the copied script accordingly.

### 5. Verify

Run a quick test:

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | <path-to-script>
```

Should exit with code 2 and print a BLOCKED message to stderr.

<!-- LAIA:START — no es upstream. Todo lo de arriba es de mattpocock/skills; al re-vendorizar, reemplaza solo lo de arriba y conserva este bloque. (Excepción documentada: el `name` del frontmatter se localizó de `git-guardrails-claude-code` a `git-guardrails`.) -->
## LAIA context

> **Dev tooling de LAIA** — skill de workflow para las IAs que construyen LAIA. NO es una skill del Marketplace ni se expone a usuarios/PA-AGORA.

**Skill solo-Claude-Code** (instala un hook `PreToolUse`). NO se cablea en Codex/OpenCode — no lleva symlink en `.codex/`. Está **vendorizada pero NO activada**: no se ha tocado `.claude/settings.json`. Invócala explícitamente solo si Jorge quiere instalar el hook.

Los comandos que bloquea (`push`, `reset --hard`, `clean -f`, `branch -D`, `checkout .`) coinciden con la lista "NUNCA sin permiso de Jorge" de `workflow/02-how-to-work.md`. El modelo de ramas de LAIA (`main`=dev, `stable`=prod, tags solo en `stable`, una branch por IA `wip/<agente>/<tarea>`) vive en `workflow/02-how-to-work.md` y `workflow/release-flow.md`.
<!-- LAIA:END -->

