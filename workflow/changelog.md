# Changelog del trabajo cooperativo

Bitácora de cambios materiales en el repo. Se actualiza al CIERRE de cada sesión.
**No** es release notes del producto — es la memoria operativa del trabajo cooperativo.

Formato:

```
## 2026-MM-DD — <una línea con lo importante> (agente)

- Qué se hizo (bullets).
- Qué quedó abierto.
- Qué se descubrió.
```

---

## 2026-05-25 (cont. 3) — Plan remake installer + Fase 1 (matar bug TTY) (claude-code)

- **Plan aprobado**: `~/.claude/plans/atomic-giggling-shore.md` — remake del
  instalador/wizard en 5 fases. Engine Python (`engine.py`/`flows/`/`contract.py`,
  motor UI-agnóstico) se mantiene; reescribimos sólo la capa UI (`ui/*.py`, 959 LOC)
  hacia Textual. Bash en `infra/installer/lib/` se queda como librería de "acciones
  puras" (sin prompts). Decisiones: 2 modos (install/clone) + 2 subcomandos
  (`laia diagnose`, `laia reset`); todo bajo sudo desde `install.sh`; single branch
  con flag `LAIA_UI=textual|rich`; config headless en TOML (`tomllib` stdlib).
  Referencia inspecting: Hermes Agent (`NousResearch/hermes-agent`) — bash thin que
  invoca wizard Python separado, mismo patrón que LAIA ya tiene pero con mejor
  ejecución.

- **Fase 1 cerrada** — bug `wizard-clone-tty` resuelto:
  - Borrado `clone_prompt_ssh_password()` en `infra/installer/lib/clone.sh` (15 LOC).
    Bash ya no abre `/dev/tty` directamente para preguntar password SSH.
  - Reescrito el fallback de preflight SSH (clone.sh:256-263): si key auth falla
    sin `--ssh-pass-file`, `die` con código 3 y mensaje claro apuntando al wizard.
    Si key auth falla CON `--ssh-pass-file`, también die (el password era erróneo).
  - Eliminado el reattach `/dev/tty` redundante en `bin/laia-wizard:86-89`. Capa
    única: `install.sh` reattach en hand-off (para `curl|bash`) + Python
    `__main__._reattach_tty()` como red de seguridad para invocaciones standalone.
  - Nuevo test: `tests/installer/test_clone_ssh_no_password_fallback.sh` (4 asserts,
    pasa). Regression guard contra el bug.
  - **Suite completa `tests/installer/run_all.sh`: 30/30 verde** tras los cambios.
  - Files tocados: `infra/installer/lib/clone.sh`, `bin/laia-wizard`,
    `tests/installer/test_clone_ssh_no_password_fallback.sh` (nuevo),
    `workflow/problems.md` (cerrado wizard-clone-tty).

- **Pendiente Fase 2**: contrato JSON line-delimited de progreso bash→Python
  (`log_step`/`log_substep` emiten JSON cuando `LAIA_JSON=1`; `JsonEventParser` en
  `_subprocess.py`). El bug `wizard-prompts-sin-contexto` se atacará en Fase 3
  con la capa Textual (los `help_text` ya existen en los `Field`s; el problema es
  la presentación de `rich.prompt`).

- **Checkpoint previo**: commit `36c92fc5` archivó 18 docs hand-written a
  `docs/archived/old-handwritten/` y 3 root-level a `docs/archived/old-root-md/`,
  más 118 archivos auto-generados en `docs/db-export/` desde `workspace.db`.
  `docs/README.md` reescrito como índice minimal.

## 2026-05-25 — Inicio del workflow cooperativo y refresh de LAIA_ECOSYSTEM (claude-code)

- `LAIA_ECOSYSTEM.md` actualizado a v1.2: header con regla anti-alucinación que declara
  el documento canónico sobre la DB; nueva §6.4 "Subsistemas en detalle" (Agent Areas,
  Soul, AgentPool, Tool Forwarder, Command Center, Control Center, DevOps); nota de
  transición HOME en §8.3.
- Creada estructura `workflow/`: `00-start-here.md`, `01-canonical-sources.md`,
  `02-how-to-work.md`, `03-multi-ai-coordination.md`, `changelog.md`, `security.md`,
  `problems.md`, `plans/README.md`.
- Sembrado `problems.md` con los 2 bugs del wizard descubiertos hoy en prueba real
  (wizard-clone-tty, wizard-prompts-sin-contexto) para que no se pierdan.
- Creado `AGENTS.md` (entry para Codex/OpenCode/Aider) y `CLAUDE.md` (entry mínimo
  para Claude Code que apunta a `AGENTS.md`). Ambos en la raíz.
- Añadida regla en `00-start-here.md` y `02-how-to-work.md`: **toda integración
  necesita su test en `~/LAIA/tests/`**; antes de declarar "hecho" se corre la
  suite completa. Sección detallada en `02-how-to-work.md` "Tests (obligatorio)".
- Primer export real de `workspace.db` → `~/LAIA/docs/db-export/` con
  `scripts/sync-workspace-markdown.py`. **118 archivos generados**. Fuente: la DB en
  `~/.laia/workspaces/laia-ecosystem/workspace.db`.
## 2026-05-25 (cont. 3) — Linger activado, db-export "siempre actualizado" (jorge + claude-code)

- Jorge ejecutó `sudo loginctl enable-linger laia-hermes`.
- Verificado: `Linger=yes`, `State=active`. El user manager systemd persiste tras logout
  y arranca en boot.
- `laia-docs-sync.service` queda corriendo en watch indefinidamente. `docs/db-export/`
  se mantiene sincronizado con `workspace.db` sin intervención manual.

---

## 2026-05-25 (cont. 2) — Archive de docs viejos y refs (claude-code)

- Movidos a `docs/archived/old-root-md/` (con `git mv` para preservar historia):
  `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` (los 3 de raíz).
- Movidos a `docs/archived/old-handwritten/` (18 archivos): `AGORA_AGENTS.md`,
  `API.md`, `ARCHITECTURE.md`, `CLI.md`, `CLONE.md`, `CONTROL_CENTER.md`, `DEPLOY.md`,
  `DEVELOPMENT.md`, `INSTALL.md`, `INTEGRATIONS.md`, `MARKETPLACE.md`, `OPERATIONS.md`,
  `PATH_REGISTRY.md`, `RELEASE.md`, `SERVIDOR_CONTEXTO.md`, `WIZARD.md`,
  `WIZARD_BACKEND.md`, `WIZARD_THEMING.md`.
- `docs/` ahora contiene sólo: `README.md` (índice nuevo minimal), `db-export/`,
  `archived/`, y los diagramas `map.drawio` / `map.svg`.
- `~/LAIA/` raíz ahora contiene sólo `AGENTS.md`, `CLAUDE.md`, `LAIA_ECOSYSTEM.md` como
  archivos canónicos `.md`. (Resto: `Makefile`, código, carpetas.)
- Limpiadas 4 referencias rotas a los archivos archivados en `workflow/changelog.md`,
  `workflow/01-canonical-sources.md`, `workflow/02-how-to-work.md`, `workflow/security.md`.
  Inlineadas las reglas de estilo en `02-how-to-work.md` (antes apuntaban a CONTRIBUTING.md).
- `docs/README.md` reescrito como índice minimal del nuevo `docs/`.

---

## 2026-05-25 (cont.) — Limpieza, auto-sync activo, AGENTS.md raíz (claude-code)

- **Auto-sync activo**: systemd user unit `laia-docs-sync.service` ejecutando
  `scripts/sync-workspace-markdown.py --watch --interval 2.0` con `LAIA_HOME` y
  `PYTHONUNBUFFERED=1` declarados en el unit. Verificado: `touch workspace.db`
  → re-export en <4s. Log en `~/.laia/logs/laia-docs-sync.log`.
- **Git policy**: `docs/db-export/` añadido a stage. 118 archivos, 1.3 MB, +31030 líneas.
  Pendiente el commit (decisión de Jorge sobre el mensaje y el momento). `.gitignore`
  no excluye `docs/db-export/`, así que el tracking quedará permanente.
- **`LAIA_HOME` fix**: retirado el bloque malo de `~/.bashrc` (líneas 157-160) que
  apuntaba al partial-install. La línea 154 sigue siendo la única autoritativa.
  Bug `env-laia-home-stale` cerrado en `problems.md`.
- **`docs/README.md` actualizado**: ahora explica el orden canónico (AGENTS.md →
  LAIA_ECOSYSTEM.md → workflow/ → docs/ → docs/db-export/). No se mueven los
  `docs/*.md` viejos a `archived/` — son guías hand-written distintas del export
  técnico, NO redundantes.
- **Pendiente para próxima sesión** (decisión de Jorge):
  - Borrar `/home/laia-hermes/laia-partial-install.02XwlG/` (huérfano del clone
    interrumpido, ya no hay nada que apunte a él). Contiene `auth.json`, `state.db`,
    `SOUL.md` viejos — verificar primero que `~/.laia/` tiene lo equivalente o más nuevo.
  - Activar `loginctl enable-linger laia-hermes` si quieres que `laia-docs-sync` siga
    corriendo aunque cierres sesión SSH.
  - Hacer el commit con todo: `LAIA_ECOSYSTEM.md` v1.2, `workflow/`, `AGENTS.md`,
    `CLAUDE.md`, `docs/db-export/`, `docs/README.md`.
