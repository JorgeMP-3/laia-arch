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

## backend-suite-laia-chat-test-leak (open)

- **Descubierto**: 2026-05-25 por codex durante `tests/run_integrity.py --tier unit`
  fuera del sandbox.
- **Síntoma**: la suite completa de `services/agora-backend/tests/` falla en
  `test_laia_chat_endpoint_employee_uses_base_toolset` y
  `test_laia_chat_endpoint_admin_streams`. El SSE devuelve
  `worker crashed: test_session_id_defaults_to_user_scoped.<locals>._capture()
  got an unexpected keyword argument 'mode'`.
- **Causa raíz sospechada**: fuga de monkeypatch/callback entre tests del chat
  engine y tests de LAIA coordinator, o singleton de AgentPool/chat worker no
  reseteado entre casos.
- **Reproducción**:
  `cd services/agora-backend && .venv/bin/python -m pytest tests/ -q`.
- **Workaround**: ejecutar los ficheros afectados de forma aislada para diagnosis;
  la suite completa sigue siendo roja hasta resetear el estado compartido.
- **Owner**: sin asignar.
- **Estado**: open.

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

## wizard-prompts-sin-contexto (resolved)

- **Descubierto**: 2026-05-25 por Jorge durante prueba del wizard.
- **Síntoma**: prompts del wizard con defaults raros o sin default sin explicación
  suficiente. Ejemplos:
  - "Límite de ancho de banda rsync (opcional)" con default `50M` — no se explica qué
    pasa si lo dejas vacío vs si lo cambias.
  - "¿Mantener sesión de admin del viejo?" sin default y sin pista de qué teclear.
  - "¿Modo --resume (saltar fases ya completadas)?" sin default visible.
- **Causa raíz**: doble — la prosa de `help_text` era escasa, y la UI legacy
  `rich.prompt` no renderizaba `help_text` de manera prominente aunque
  estuviera. La data estaba ahí; la presentación no la mostraba.
- **Resuelto**: 2026-05-25 — combinación de cambios en Fase 3 y Fase 4 del
  remake del wizard:
  - Fase 3 part 2 (commit `b31287b8`): `help_text` reescrito para los 3
    campos en `flows/clone.py::_OPTIONS_SCREEN`. De 50-100 chars a 200-330
    chars cada uno con guía explícita: bwlimit explica WAN vs LAN y qué
    pasa con vacío; keep_session deja claro que `No` es recomendado y
    describe el flujo de credenciales; resume tiene "primera vez? `No`"
    up-front.
  - Fase 4 part 1 (commit `58b6e88e`): la UI Textual es default; renderiza
    `help_text` inline bajo el label de cada campo con estilo `field-help`
    (color muted, padding consistente). La UI rich legacy se borró.
- **Verificación**: cualquier `Field` con `help_text` ahora muestra ese texto
  bajo el input en la UI Textual. Probar con `laia wizard --mode clone` y
  ver las pantallas de opciones.
- **Workaround**: dejar todo en default y rezar.
- **Owner**: sin asignar.
- **Estado**: open.

## backend-jwt-secret-regenerates-on-restart (open)

- **Descubierto**: 2026-05-26 por claude opus 4.7 durante T.14.4.
- **Síntoma**: cada restart del agora-backend invalida todos los tokens
  emitidos previamente. F.5.4 falló con `401 invalid signature` después de
  un restart del backend que normalmente debería ser transparente.
- **Causa raíz**: `services/agora-backend/app/config.py:64` —
  `self.jwt_secret = os.environ.get("AGORA_JWT_SECRET", secrets.token_hex(32))`.
  Si `AGORA_JWT_SECRET` no está en env, genera un random nuevo cada boot.
  El systemd unit template (`agora-backend.service.tmpl`) no setea esa
  var, ni el `.env` de `/srv/laia/agora/`.
- **Reproducción**: login → obtener token → restart backend → token
  rechazado.
- **Workaround**: re-login en cada restart.
- **Fix sugerido**: generar `AGORA_JWT_SECRET` una vez durante install y
  persistirlo en `/srv/laia/agora/.env` (o systemd unit drop-in). Verify
  no se commitea.
- **Owner**: sin asignar.
- **Estado**: open.

## create-agent-slug-_-dash-mismatch (resolved)

- **Descubierto**: 2026-05-26 por claude opus 4.7 durante T.14.3.
- **Síntoma**: `create-agent.sh verify_bob` falla con
  `Invalid instance name "agent-verify_bob": Name can only contain
  alphanumeric and hyphen characters` (LXD restriction).
- **Causa raíz**: `infra/lxd/scripts/create-agent.sh:43` validaba slugs con
  `_` permitido pero LXD lo prohíbe en container names.
- **Resuelto**: 2026-05-26 — `CONTAINER="${AGENT_CONTAINER_PREFIX:-agent-}${SLUG//_/-}"`
  mapea `_ → -` solo en el container name. El slug (DB, host paths) se
  preserva.
- **Pendiente**: `/api/agents/register` valida slug con `^[a-z0-9][a-z0-9-]{1,30}$`
  (no acepta `_`). `/api/users` SÍ acepta `_`. Hay drift de validación.
  Hacer que `/api/users` rechace `_` también, o que `/api/agents/register`
  lo permita.
- **Owner**: sin asignar.
- **Estado**: parcial — fix en create-agent.sh; drift en API queda open.

## create-agent-uid-offset-100000-vs-1000000 (resolved)

- **Descubierto**: 2026-05-26 por claude opus 4.7 durante T.14.4.
- **Síntoma**: bind mount `/srv/laia/users/<slug>/home → /home/user`
  dentro del agent container muestra `nobody:nogroup`, root inside no
  puede escribir. write_file desde el agente devuelve "permiso denegado".
- **Causa raíz**: `infra/lxd/scripts/create-agent.sh:41` tenía
  `LXD_UID_OFFSET=100000` por default, pero la idmap real de LXD usa
  `1000000` (per `/etc/subuid`). Files owned by 100000 en host caen fuera
  del rango mapeado y aparecen como nobody.
- **Resuelto**: 2026-05-26 — default cambiado a 1000000.
- **Workaround para containers ya creados con UID 100000**:
  `sudo chown -R 1000000:1000000 /srv/laia/users/<slug>/`.
- **Estado**: resolved.

## pm2-agora-backend-errored-shadowing-container (open)

- **Descubierto**: 2026-05-26 por claude opus 4.7 durante T.14.4.
- **Síntoma**: `pm2 list` muestra `agora-backend` en estado `errored` con
  5322+ restarts. Pero `http://127.0.0.1:8088/api/health` responde porque
  la version REAL del backend corre dentro del container `laia-agora`
  (LXD proxia `host:8088 → laia-agora:8000`).
- **Causa raíz**: dual setup — el PM2 spec del host intenta arrancar
  uvicorn local pero el container ya lo sirve via LXD proxy. PM2 falla
  porque el puerto está ocupado y entra en restart loop.
- **Workaround**: ignorar PM2 (no afecta funcionalidad real).
- **Fix sugerido**: decidir un único deployment path:
  - Opción A: eliminar PM2 agora-backend, dejar el container `laia-agora`
    como la única fuente del backend.
  - Opción B: parar el container `laia-agora`, mover el backend a host
    via PM2 limpiamente (requiere ajustes de permisos en `/srv/laia/agora/`).
- **Owner**: sin asignar.
- **Estado**: open.

## laia-ui-server-stale-LAIA_HOME (open)

- **Descubierto**: 2026-05-26 por claude opus 4.7 durante T.14.12.
- **Síntoma**: tras la migración a `~/LAIA-ARCH`, `~/.laia/` se repuebla
  con stubs (SOUL.md, state.db, sessions/, workspaces/, logs/) porque
  `laia-ui-server` (PID inicial 1426, arranque 07:58) y `laia-docs-sync`
  tienen `LAIA_HOME=/home/laia-hermes/.laia` en su env de runtime.
- **Causa raíz**: el shell que los lanzó (pre-migración) tenía LAIA_HOME
  legacy. No hay systemd unit que respete el env del bashrc actualizado;
  el bind se hizo en boot del shell que arrancó esos procesos.
- **Workaround inmediato**:
  `kill <pid>; LAIA_HOME=~/LAIA-ARCH nohup ./laia-ui-server ... &`
  o crear systemd --user unit con `Environment=LAIA_HOME=...`.
- **Fix sugerido**: convertir `laia-ui-server` y `laia-docs-sync` en
  systemd user units (template equivalente al de `laia-pathd.service`)
  que lean LAIA_HOME del environment o de un .env.paths.
- **Estado**: open.
