# Problems log

Bitácora de problemas descubiertos durante el desarrollo. Se anotan AL DESCUBRIRLOS
aunque no se arreglen en ese momento. Sin esto, los problemas se olvidan.

## Cuándo escribir aquí

- Bug visible (algo no funciona como debería).
- Documentación que contradice al código.
- Decisión de arquitectura que parece equivocada (con argumentación).
- UX confuso (preguntas sin contexto suficiente, defaults raros).
- Performance que duele.

## Formato

```
## <slug-corto> (estado)

- **Descubierto**: 2026-MM-DD por <agente>.
- **Síntoma**: qué se ve, dónde.
- **Causa raíz sospechada**: si se sabe; "desconocida" si no.
- **Reproducción**: pasos mínimos.
- **Workaround**: si existe.
- **Owner**: persona/agente, o "sin asignar".
- **Estado**: open | in-progress | blocked | resolved.
```

Cuando un problema se resuelve, no se borra — se marca `(resolved)` en el título y se
añade una línea `- **Resuelto**: 2026-MM-DD en commit <hash>`.

---

## install-wizard-ui-tests-stale (resolved)

- **Descubierto**: 2026-05-25 por codex durante la implementación del runner de
  integridad.
- **Síntoma**: `tests/wizard/test_ui_*.py` y
  `tests/installer/test_wizard_yesno_input.sh` fallan al importar
  `laia_cli.install_wizard.ui`.
- **Causa raíz**: los tests unitarios atacaban internals (`_ask_yesno`,
  `_NavigationSentinel`, `Prompt.ask`) de la capa rich `install_wizard.ui`
  que se borró en Fase 4 del remake del wizard (commit del flip a Textual).
  La cobertura equivalente vive ahora en `.laia-core/tests/test_tui_app.py`
  contra el FormScreen Textual.
- **Resuelto**: 2026-05-25 — borrados los 4 archivos de test obsoletos
  (`tests/installer/test_wizard_yesno_input.sh`,
  `tests/wizard/test_ui_components.py`, `tests/wizard/test_ui_render.py`,
  `tests/wizard/test_ui_progress.py`) junto con la capa rich que testeaban.
- **Verificación**: `tests/installer/run_all.sh` 29/29 verde tras la
  limpieza; `pytest tests/wizard/` baja a 159/160 (la failure restante
  `test_clone_security::test_clone_execute_aborts_on_ssh_setup_mode` es
  pre-existente y testea comportamiento intencional que NO es parte del
  remake — ver entrada propia abajo).

## clone-ssh-setup-mode-continues (open)

- **Descubierto**: 2026-05-25 por claude-code al correr `pytest tests/wizard/`
  durante Fase 4. La falla es pre-existente; el test viene del commit
  `5e786ac5` (codex añadiendo asserts de seguridad).
- **Síntoma**: `tests/wizard/test_clone_security.py::test_clone_execute_aborts_on_ssh_setup_mode`
  asserta que cuando `ssh_auth_mode='setup'` el flow `execute()` debe yieldar
  `step_error` ANTES de invocar `bin/laia-clone`. El código actual hace el
  setup SSH y luego sí continúa al clone, contradiciendo el test.
- **Causa raíz sospechada**: divergencia entre intent (la sesión de "sólo
  setup" debería ser una pasada separada, no fold-into-clone) y la
  implementación heredada en `flows/clone.py:402-408` que continúa.
- **Reproducción**: `cd .laia-core && PYTHONPATH=. venv/bin/python -m pytest
  ../tests/wizard/test_clone_security.py -k aborts_on_ssh_setup -o addopts=""`.
- **Workaround**: usar `ssh_auth_mode='existing'` después del setup manual,
  o no marcar la opción setup si quieres clonar en la misma ejecución.
- **Owner**: sin asignar — decisión de Jorge sobre si la semántica correcta
  es "abort después de setup" o "encadenar setup + clone".
- **Estado**: open.

## wizard-clone-tty (resolved)

- **Descubierto**: 2026-05-25 por claude-code durante prueba en VM Ubuntu 26.04 arm64.
- **Síntoma**: `infra/installer/lib/clone.sh: line 225: /dev/tty: No such device or address`
  al ejecutar el wizard vía `curl | sudo bash` en modo clone, durante el preflight
  cuando el SSH key auth falla y se intenta SSH password.
- **Causa raíz**: `clone_prompt_ssh_password()` en `clone.sh` leía de `/dev/tty`
  directamente como fallback cuando key auth fallaba, ignorando el mecanismo
  `--ssh-pass-file` que Python ya implementaba correctamente vía
  `_secret_to_tempfile` + `bin/laia-clone::resolve_ssh_pass_file`. En `curl|sudo bash`
  bajo subprocess, ese `/dev/tty` no estaba disponible aunque el wizard Python tuviera
  su propio reattach.
- **Resuelto**: 2026-05-25 — borrada la función `clone_prompt_ssh_password()` y el
  fallback que la llamaba. Cuando key auth falla sin `--ssh-pass-file`, `clone.sh`
  ahora `die`'s con código 3 y mensaje claro apuntando al wizard para reintentar
  con password mode. Bash nunca más promptea — todo secreto entra por el path
  `--ssh-pass-file` (Python escribe tempfile 0600, bash lo lee y lo unlinkea).
  Además, el reattach `/dev/tty` redundante en `bin/laia-wizard:86-89` se eliminó;
  el único reattach vive en `install.sh` (curl|bash hand-off) y la red de seguridad
  `_reattach_tty()` en `__main__.py`. Commits asociados en rama `feat/installer-wizard`.
- **Verificación**: `tests/installer/test_clone_ssh_no_password_fallback.sh` —
  stubea ssh para que falle, invoca `bin/laia-clone --source user@unreachable.invalid
  --yes` sin `--ssh-pass-file`, asserts: exit 3, mensaje claro, sin mención a
  `/dev/tty` en la salida. La suite completa `tests/installer/run_all.sh` pasa.

## env-laia-home-stale (resolved)

- **Descubierto**: 2026-05-25 por claude-code al lanzar `scripts/sync-workspace-markdown.py`.
- **Síntoma**: scripts que leen `LAIA_HOME` fallan apuntando a
  `/home/laia-hermes/laia-partial-install.02XwlG/LAIA-ARCH` en vez de a `~/.laia`.
  Error visible: `ERROR: /home/laia-hermes/laia-partial-install.02XwlG/LAIA-ARCH/workspaces no existe`.
- **Causa raíz**: bloque `# >>> laia >>> / <<< laia <<<` en `~/.bashrc` (líneas
  157-160) añadido por `laia-install` durante un clone interrumpido, que sobreescribía
  el export bueno de la línea 154.
- **Reproducción**: `echo $LAIA_HOME` en una shell nueva → devolvía la ruta fantasma.
- **Resuelto**: 2026-05-25 — bloque retirado de `~/.bashrc`, sustituido por un comentario
  que apunta a esta entrada. La línea 154 (`export LAIA_HOME="$HOME/.laia"`) sigue siendo
  la única autoritativa.
- **Verificación**: shell nueva → `echo $LAIA_HOME` devuelve `/home/laia-hermes/.laia`.
  Systemd unit `laia-docs-sync.service` declara `Environment=LAIA_HOME=/home/laia-hermes/.laia`
  explícitamente como cinturón y tirantes.
- **Pendiente relacionado**: la carpeta `~/laia-partial-install.02XwlG/` que motivó el
  bloque sigue existiendo en el home. Decisión sobre borrarla, abierta — ver changelog.

## wizard-prompts-sin-contexto (open)

- **Descubierto**: 2026-05-25 por Jorge durante prueba del wizard.
- **Síntoma**: prompts del wizard con defaults raros o sin default sin explicación
  suficiente. Ejemplos:
  - "Límite de ancho de banda rsync (opcional)" con default `50M` — no se explica qué
    pasa si lo dejas vacío vs si lo cambias.
  - "¿Mantener sesión de admin del viejo?" sin default y sin pista de qué teclear.
  - "¿Modo --resume (saltar fases ya completadas)?" sin default visible.
- **Causa raíz sospechada**: los prompts del wizard no han sido revisados con UX como
  objetivo. Heredados del modo CLI no-interactivo donde se asume conocimiento previo.
- **Reproducción**: lanzar `laia-wizard` en cualquier modo, prestar atención a los
  prompts.
- **Workaround**: dejar todo en default y rezar.
- **Owner**: sin asignar.
- **Estado**: open.
