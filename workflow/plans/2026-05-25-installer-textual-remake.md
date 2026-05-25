# Remake del instalador/wizard con Textual

- **Fecha**: 2026-05-25
- **Owner**: claude-code (con aprobación explícita de Jorge)
- **Estado**: en-curso (Fases 1-3 completadas, 4-5 pendientes)
- **Plan original (Claude Code plan-mode artifact)**: `~/.claude/plans/atomic-giggling-shore.md`

## Contexto

El instalador (`laia-install`) y el wizard de clonado (`laia-clone`) son la
herramienta que Jorge usa desde LAIA-ARCH para desplegar la plataforma en un
host nuevo o migrarla. El estado al arrancar la sesión era **frágil y opaco**:

- **4.910 LOC Python** (`.laia-core/laia_cli/install_wizard/`) sobre
  `rich.prompt`. UI plana: prompts apilados sin progressive disclosure ni
  contexto, defaults sin explicación.
- **2.837 LOC bash** (`infra/installer/lib/`) hacía el trabajo real.
  **Bash seguía promptando** desde sus propias rutinas (`clone.sh:218-232`,
  `clone_prompt_ssh_password`) leyendo `/dev/tty` directamente — esto rompía
  en `curl|sudo bash` cuando el wizard Python ya había hecho reattach (bug
  abierto `wizard-clone-tty`).
- **Reattach TTY en 3 capas** (bash wrapper, Python startup, herencia a
  subprocess) — frágil y duplicado.
- **Prompts sin contexto** (bug abierto `wizard-prompts-sin-contexto`):
  bwlimit `50M`, `keep_session`, `--resume` sin pistas.
- **3.267 LOC tests shell** vs **91 LOC Python** — pirámide invertida.
  Validar requiere VM.

Referencia que usamos: Hermes Agent (`NousResearch/hermes-agent`) — bash
thin (~1.800 LOC) que invoca wizard Python como módulo separado al final.
La arquitectura ya era la correcta en LAIA — falla la ejecución.

**Outcome buscado:** wizard usable sin frustración. Bug TTY estructuralmente
imposible. UI navegable con teclado (Textual). Tests pytest sin VM excepto 2
smoke E2E. Net delta esperado: **−1.500 LOC**.

## Plan

### Decisiones bisagra confirmadas por Jorge

1. **Alcance**: Textual sobre motor existente (`engine.py`/`flows/`/`contract.py`
   se quedan; `ui/*.py` se reescribe). NO rewrite total.
2. **Sudo**: todo bajo sudo desde `install.sh`. Textual corre como root.
   Mitigaciones: `umask(0o077)` en `App.on_mount`, no exponer shell-escape.
3. **Modos**: 2 (`install`, `clone`) en el menú + subcomandos standalone
   `laia diagnose` / `laia reset`. Connectivity pasa a ser paso opcional
   dentro de install/clone.
4. **Branch**: single branch (`feat/installer-wizard`) + flag
   `LAIA_UI=textual|rich`. Flip y borrado en Fase 4.
5. **Config headless**: TOML (`tomllib` stdlib, cero deps nuevas).

### Arquitectura objetivo

```
install.sh (bash, ~250 LOC)        # bootstrap thin: sudo + sanitize + deps + venv + invoke
  └─> python -m laia_cli.install_wizard
        ├─ engine.py + flows/ + contract.py + validators.py + state.py   (se quedan)
        ├─ tui/ (Textual)        ← nuevo, render dinámico de WizardScreen
        ├─ headless.py            ← --config wizard.toml, --yes
        └─ _subprocess.py        ← JSON line-delimited contract con bash
              └─> infra/installer/lib/*.sh   ← funciones puras, sin prompts, JSON events
```

**Regla dura:** `bash NUNCA promptea`. Todos los secretos y elecciones vienen
de Python por `--ssh-pass-file` (ya existe `_secret_to_tempfile` en
`clone.py:259-272`), env vars o args. Bash sólo lee. Esto cierra
`wizard-clone-tty` estructuralmente.

### Fases

#### Fase 1 — Matar bug TTY y sanear boundary (COMPLETADA 2026-05-25)

Commit: `11ba61f0` · Bug `wizard-clone-tty` cerrado.

- Borrado `clone_prompt_ssh_password()` en `infra/installer/lib/clone.sh:218-232`.
- Reescrito el fallback de preflight SSH: si key auth falla sin
  `--ssh-pass-file`, `die` exit 3 con mensaje claro apuntando al wizard.
- Eliminado el reattach `/dev/tty` redundante en `bin/laia-wizard:86-89`.
  Único reattach vive en `install.sh` (curl|bash hand-off) +
  `__main__._reattach_tty()` como red de seguridad.
- Nuevo test: `tests/installer/test_clone_ssh_no_password_fallback.sh`
  (4 asserts, pasa). Regression guard.

#### Fase 2 — Contrato JSON line-delimited (COMPLETADA 2026-05-25)

Commit: `6172a80f`. Más adelantada de lo previsto — el contrato ya estaba
implementado; el gap real era el acoplamiento `log_step` ↔ `emit_json_event`.

- `common.sh::log_step` ahora acepta `step_id` opcional como 2º arg y
  auto-emite `step_start` cuando `LAIA_JSON_PROGRESS=1`. Si no se da id,
  se deriva slug del label.
- Nuevo `common.sh::log_step_done` para cerrar simétricamente la fase.
- Colapsados 9 pares redundantes `log_step` + `emit_json_event step_start`
  adyacentes en `clone.sh` (−9 LOC, mismo comportamiento).
- `tests/installer/test_json_progress.sh` extendido con 4 asserts nuevos
  (10 total). Pasa.

#### Fase 3 — Textual UI sobre el motor existente (COMPLETADA 2026-05-25)

Commits: `3ecd44c4` (skeleton) + `b31287b8` (menú + help_text).

- `.laia-core/pyproject.toml`: nuevo extra `install_wizard = ["textual>=0.50,<10"]`.
- Nueva carpeta `.laia-core/laia_cli/install_wizard/tui/`:
  - `app.py` (~670 LOC): `LaiaWizardApp`, `FormScreen`, `ExecuteScreen`.
  - `__init__.py`: exporta `run_textual_wizard()` y `is_textual_available()`.
- **Threading model**: engine sync corre en `run_worker(thread=True)`;
  cada `push_screen` cruza al main thread via
  `call_from_thread(push_screen_wait)`. Engine + flows sin cambios.
- Render dinámico de todos los `Field.type`: text, password, choice,
  checklist, yesno, path, info. `depends_on` honrado.
- `umask(0o077)` en `App.on_mount` (mitigación sudo).
- Opt-in via `LAIA_UI=textual` env var; legacy rich UI sigue como default.
- `__main__.py` dispatch añadido: si `LAIA_UI=textual` y textual instalado,
  short-circuita a `tui.run_textual_wizard()`.
- `MODE_SELECT_SCREEN` (engine.py) reducido a 2 choices: install / clone.
  connectivity/diagnose/reset siguen funcionando via `--mode`.
- `help_text` reescrito en `flows/clone.py` para `bwlimit`, `keep_session`,
  `resume`. De ~100 chars a 200-330 chars cada uno con guía explícita.
- Tests: `.laia-core/tests/test_tui_app.py` con 7 smoke tests usando
  `App.run_test()`. Cobre composición, value collection, `depends_on`,
  back/quit, ExecuteScreen con todos los `ProgressEvent` types. **7/7 verde.**

#### Fase 4 — Flip default + borrado legacy + subcomandos (PENDIENTE, ~2 días)

- Flip `LAIA_UI=textual` como default en `__main__.py`.
- Borrar `ui/__init__.py`, `ui/components.py`, `ui/console.py`,
  `ui/progress.py`, `ui/theme.py` (~959 LOC).
- Decidir destino de `_headless_ui.py` y `_dev_ui.py`:
  - Si Fase 5 cubre headless via TOML → borrar.
  - Si no, mover `headless.py` a top-level y borrar `_dev_ui.py`.
- Mover `flows/diagnose.py` → `.laia-core/laia_cli/diagnose.py`
  (subcomando `laia diagnose`, Textual single-screen).
- Mover `flows/reset.py` → `.laia-core/laia_cli/reset.py`
  (subcomando `laia reset`, Textual modal con doble confirmación).
- Borrar `bin/laia-wizard`; el shim único es `bin/laia` que despacha a
  subcomandos.
- Borrar `flows/connectivity.py`; inlinear el step como sub-screen opcional
  dentro de `flows/install.py` y `flows/clone.py`. **Decisión abierta**:
  ¿se pregunta siempre, o sólo si `ssh-keyscan` detecta que no hay key
  válida al origen?
- Actualizar `Makefile` y `install.sh` para no referenciar binarios borrados.
- Cerrar bug `wizard-prompts-sin-contexto` en `workflow/problems.md`.

#### Fase 5 — Modo headless + pirámide de tests (PENDIENTE, ~2-3 días)

- Implementar `headless.py`: lee TOML con `tomllib`, valida con
  `validators.py`, ejecuta flow sin Textual, stream JSON a stdout.
- Env vars override: `LAIA_<FIELD_UPPER>=value` setea `Field(name=field)`.
- `install.sh` añade flags `--skip-setup`, `--config FILE`, `--yes`
  (siguiendo patrón Hermes).
- Tests pytest nuevos:
  - `test_headless_install.py` — TOML válido/inválido, dry-run mock.
  - `test_validators.py` — los 232 LOC sin cobertura.
  - `test_secret_tempfile.py` — 0600, cleanup en SIGINT.
  - `test_tui_screens.py` — flows enteros con `App.run_test()` + mocks
    de subprocess.
- E2E en VM reducido a 2 (`vm-install-e2e.sh`, `vm-clone-e2e.sh`).
- Cobertura Python: subir de ~0% a >60%.

## Files críticos

- `/home/laia-hermes/LAIA/install.sh` — bootstrap thin (Fase 1 + 5).
- `/home/laia-hermes/LAIA/bin/laia-wizard` — **borrar en Fase 4**.
- `/home/laia-hermes/LAIA/bin/laia` — shim único de subcomandos (Fase 4).
- `/home/laia-hermes/LAIA/infra/installer/lib/clone.sh` — limpio (Fase 1+2).
- `/home/laia-hermes/LAIA/infra/installer/lib/common.sh` — `log_step` JSON (Fase 2).
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/engine.py` —
  `MODE_SELECT_SCREEN` recortado (Fase 3).
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/contract.py` —
  contrato UI-agnóstico que no cambia.
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/flows/_subprocess.py` —
  `_json_progress_event` parser (Fase 2).
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/flows/clone.py` —
  help_text + matar prompts shell (Fase 1, 3).
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/tui/` (Fase 3).
- `/home/laia-hermes/LAIA/.laia-core/laia_cli/install_wizard/headless.py` —
  **nuevo** (Fase 5).

## Funciones a reutilizar (no reescribir)

- `_secret_to_tempfile` en `flows/clone.py:259-272`.
- `_target_user_context` y `_as_operator` en `flows/clone.py:275-295`.
- `validators.py` (232 LOC, hoy sin cobertura) — reusar tal cual.
- `state.WizardState` y `contract.{Field,WizardScreen,Action,Choice,ProgressEvent}` —
  diseñados UI-agnóstico desde el inicio.
- `flows/_subprocess.py:_kill_tree` — limpieza correcta de procesos.

## Verificación

**Fase 1**: `tests/installer/test_clone_with_install.sh` + nuevo
`test_clone_ssh_no_password_fallback.sh`. En VM Ubuntu limpio:
`curl -fsSL ./install.sh | sudo bash` → modo clone con clave SSH inválida
→ debe pedir password en Python (no en bash) y NO colgarse en `/dev/tty`.
✅ Hecho.

**Fase 2**: `LAIA_JSON_PROGRESS=1 bash -c 'source common.sh; log_step "Phase H"; log_step_done'`
produce JSON parseable. `tests/installer/test_json_progress.sh` (10 asserts).
✅ Hecho.

**Fase 3**: `pytest .laia-core/tests/test_tui_app.py` (7 asserts, todos verdes).
En VM real (PENDIENTE de validación humana): `LAIA_UI=textual laia install`
arranca, navega con teclado, completa instalación factory. `LAIA_UI=rich`
sigue funcionando idéntico al estado anterior.

**Fase 4**: `laia install`, `laia clone`, `laia diagnose`, `laia reset` cada
uno responde como subcomando. `git diff --stat` muestra ~1.500 LOC de delta
negativo. Tests E2E verdes en ambos modos UI durante ventana de gracia, luego
sólo Textual.

**Fase 5**: `laia install --config tests/fixtures/install.toml --yes` corre
sin TTY. `pytest` cubre validators, secret tmpfile, TUI screens. E2E reducido
a 2 tests en VM. Cobertura Python >60%.

## Riesgos

1. **Textual + sudo + curl|bash**: tres interacciones que podrían pelearse.
   Mitigación: Fase 1 ya garantizó que bash no abre `/dev/tty` por su cuenta;
   Textual en root con `umask 0o077`; install.sh hace el único reattach.
   Si hay sorpresas, se ven en la primera ejecución real en VM.

2. **Codex trabaja en paralelo**: branch separado
   `wip/codex/integrity-tests`. Conflictos potenciales en
   `workflow/changelog.md` y `Makefile`. Mitigación: commits focalizados,
   re-check de `git branch` antes de cada commit, no usar `git add .`.

3. **Borrado de 959 LOC del rich UI en Fase 4**: irreversible vía git
   `revert` (los archivos vuelven, pero la integración con Textual ya está
   asentada). Mitigación: hacer la Fase 4 en una sola sesión, verificar VM
   antes de borrar, mantener `LAIA_UI=rich` como flag de emergencia durante
   1-2 días de ventana de gracia.

4. **Fase 5 cobertura Python >60%**: ambiciosa para 2-3 días. Mitigación:
   priorizar validators y _subprocess.py (las dos zonas críticas); aceptar
   <60% si las críticas están cubiertas.

## Notas

- El plan original aprobado vive intacto en
  `~/.claude/plans/atomic-giggling-shore.md` (Claude Code plan-mode artifact);
  este archivo en `workflow/plans/` es la copia que sigue la convención del
  repo + estado actualizado tras Fases 1-3.
