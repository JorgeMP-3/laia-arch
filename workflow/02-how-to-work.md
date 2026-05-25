# Cómo trabajar en LAIA

## Antes de empezar

1. Lee `LAIA_ECOSYSTEM.md` si nunca lo has hecho.
2. Comprueba `workflow/problems.md` — si tu tarea cae sobre un problema conocido,
   léelo antes.
3. Si tu tarea no es trivial, escribe primero un plan en `workflow/plans/` (ver
   plantilla en `plans/README.md`).

## Branches

- Trabaja siempre en una branch dedicada. **Nunca commits directos a `main`.**
- Convención: `wip/<agente>/<tarea-corta>`. Ejemplos:
  - `wip/claude/fix-clone-tty`
  - `wip/codex/agora-ui-marketplace-tab`
  - `wip/jorge/workflow-folder`
- Para PRs serios usa `feat/<area>` o `fix/<area>`.

## Commits

Conventional Commits:

- `feat:` funcionalidad nueva.
- `fix:` corrección de bug.
- `refactor:` reestructuración sin cambio de comportamiento.
- `security:` cambio con impacto de seguridad.
- `docs:` documentación.
- `chore:` mantenimiento (deps, configs).

Si el cambio cae sobre un problema de `workflow/problems.md`, referéncialo:
`fix: <síntoma>. Resuelve workflow/problems.md#<slug>.`

## Cierre de turno (obligatorio)

Antes de terminar tu sesión, actualiza lo que aplique:

1. **Cambio material en código** → entrada en `workflow/changelog.md` con qué se hizo
   y qué quedó abierto.
2. **Problema descubierto** → entrada en `workflow/problems.md`, aunque no lo arregles.
3. **Acción con impacto de seguridad** (credenciales, permisos, red, container escape,
   secrets en repo) → entrada en `workflow/security.md`.
4. **Plan completado o abandonado** → mueve `workflow/plans/<plan>.md` a
   `workflow/plans/archive/`.

## Detalles de código

- **Python**: PEP 8, type hints (`from __future__ import annotations`), `pydantic` para
  modelos de datos, `sqlite3` de stdlib (no ORM).
- **TypeScript / React**: componentes funcionales con hooks, tokens `--d-*` del design
  system, `@laia/ui` para componentes compartidos.
- **Shell**: `#!/usr/bin/env bash` + `set -euo pipefail`. Google Shell Style.
- **Commits**: Conventional Commits (ver sección "Commits" más arriba).

Antes de push: `make test` (backend) y `npx tsc --noEmit` (frontend) si aplica.

## Tests (obligatorio)

**Toda integración nueva debe tener su propio test en `~/LAIA/tests/`.** Sin test, la
integración no se considera terminada — aunque el código compile y aparente funcionar.

### Por qué

`~/LAIA/tests/` cumple dos funciones:

1. **Tests de integridad y estado del ecosistema** — verifican que LAIA está sano:
   containers vivos, servicios respondiendo, DBs accesibles, state files coherentes,
   permisos correctos. Ejemplos existentes: `test_preflight.sh`, `test_smoke_scripts.sh`,
   `test_rebuild_state.sh`, `installer/`, `wizard/`.
2. **Tests de regresión cross-sistema** — cuando integras algo nuevo, lanzar
   **toda la suite** garantiza que no rompiste otra cosa lejos de tu cambio.

### Regla operativa

- Cada vez que integras algo (feature nueva, plugin, skill, endpoint, refactor que cruza
  módulos), añades su test propio en `~/LAIA/tests/` siguiendo el naming existente
  (`test_<area>.{sh,py}`) o como subcarpeta si tiene varios archivos (ej. `tests/wizard/`).
- Antes de declarar el trabajo "hecho", corres la **suite completa**, no sólo el test
  que escribiste. Si algo distinto a tu cambio falla, lo arreglas tú o lo escalas como
  problema (entrada en `workflow/problems.md`).
- Si la integración requiere container vivo / red / `agora-backend` corriendo, los tests
  deben detectar esa dependencia y skip-eaer limpiamente cuando no se cumple
  (no fallar con error críptico).

### Cómo lanzar todo

```bash
# Suite backend (pytest)
cd ~/LAIA/services/agora-backend && .venv/bin/python -m pytest tests/ -v

# Suite shell (tests de host/container/orquestación)
cd ~/LAIA/tests && ./test_preflight.sh && ./test_smoke_scripts.sh

# Suite frontend (typecheck)
cd ~/LAIA/laia-ui && npx tsc --noEmit -p packages/arch-app/tsconfig.json && \
                     npx tsc --noEmit -p packages/agora-app/tsconfig.json
```

Si añades una integración que cruza host + container + UI, el test correspondiente
en `~/LAIA/tests/` debe ejercitar el camino end-to-end o documentar explícitamente
qué porción cubre y qué porción queda fuera.

## Qué NUNCA hacer sin permiso explícito de Jorge

- Editar `LAIA_ECOSYSTEM.md`. Es el contrato del proyecto.
- `git push --force` a ramas compartidas.
- Borrar archivos de `archived/`.
- Reset destructivo de `workspace.db` o `agora.db`.
- Cambiar permisos en `~/.laia/` o `/srv/laia/`.
- Commits con `--no-verify` (saltarse hooks).
- Aplicar comandos `rm -rf`, `git reset --hard`, `git clean -fd` sin confirmación.
