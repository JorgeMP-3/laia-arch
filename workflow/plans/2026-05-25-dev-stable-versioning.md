# Dev + Stable Versioning Runbook

- **Fecha**: 2026-05-25
- **Owner**: próxima IA implementadora, con Jorge aprobando cambios materiales
- **Estado**: aprobado para implementación
- **Topología objetivo**: VM QEMU en Mac para desarrollo + Lenovo ThinkStation Ubuntu para producción
- **Datos**: totalmente aislados por máquina
- **Promote**: manual, sin CI/CD

## Objetivo

Dejar LAIA con una separación clara entre:

- `main`: desarrollo activo, usado por la VM de Jorge.
- `stable`: producción, usado por el ThinkStation.
- tags `vX.Y.Z`: puntos reproducibles de release, creados solo sobre `stable`.

La implementación debe permitir que un `curl|bash` sin opciones instale la versión estable,
mientras que Jorge pueda seguir probando desarrollo con `--branch main` o ramas `feat/*`.

## Contexto Obligatorio

Antes de tocar código, la IA implementadora debe leer:

1. `AGENTS.md`
2. `LAIA_ECOSYSTEM.md`
3. `workflow/00-start-here.md`
4. `workflow/02-how-to-work.md`
5. `workflow/changelog.md` últimas entradas de 2026-05-25
6. Este plan completo

Reglas importantes:

- No editar `LAIA_ECOSYSTEM.md` sin consentimiento explícito de Jorge. Este plan propone una edición mínima ahí, pero la IA debe pedir confirmación antes de hacerla.
- Toda integración nueva necesita test en `tests/`.
- Al cerrar, actualizar `workflow/changelog.md`.
- Si se descubre un problema, actualizar `workflow/problems.md`.
- Si se toca seguridad, permisos, red, sudo, secrets o despliegue productivo, actualizar `workflow/security.md`.

## Estado Actual Que Motiva El Cambio

Hallazgos ya verificados:

- `install.sh` tiene `DEFAULT_BRANCH="feat/installer-wizard"`. Eso es correcto para la fase actual, pero no para producción.
- No existe una convención documentada dev/prod.
- `bin/laia-release`, `bin/laia-rollback` e `infra/installer/lib/release.sh` ya implementan versionado en `/opt/laia-vX.Y.Z` con symlink `/opt/laia`.
- `/srv/laia/` contiene datos y está separado de `/opt/laia/`, así que dev y prod quedan aislados si viven en máquinas distintas.
- Los containers LXD se reconstruyen por máquina; hoy no hay versionado separado de imágenes LXD.

## Resultado Deseado

Al terminar:

- Existe una rama remota `stable`.
- Existe un tag inicial en `stable` (`v0.1.0`, salvo que Jorge indique otro).
- `install.sh` usa `stable` como rama por defecto.
- Hay documentación clara en `workflow/release-flow.md`.
- `workflow/02-how-to-work.md` explica el flujo `main`/`stable`.
- `AGENTS.md` avisa a futuras IAs de la política de ramas.
- Hay tests que cubren el nuevo default y, si se añade, `--channel`.
- La suite relevante pasa.
- La implementación queda commiteada y pusheada a la rama de trabajo que Jorge indique.

## Decisión De Diseño

Usar branching simple:

```text
feat/* or wip/*  -> trabajo temporal de IA o Jorge
main             -> integración/dev validada en VM Mac
stable           -> producción del ThinkStation
tags vX.Y.Z      -> releases reproducibles sobre stable
```

No introducir CI/CD todavía. El promote es manual para mantener control y simplicidad.

No cambiar el layout `/srv/laia/`, `/opt/laia/` ni el mecanismo actual de `laia-release`.

## Alcance

Implementar solo esto:

1. Cambiar default de instalación a `stable`.
2. Crear/documentar el flujo de release manual.
3. Crear la rama `stable` y tag inicial.
4. Añadir o ajustar tests mínimos.
5. Actualizar documentación operativa.

No implementar en esta tarea:

- CI/CD.
- Versionado de imágenes LXD.
- Backups borg/restic.
- Refactor profundo de `laia-release`.
- Cambios de layout en `/srv/laia/arch`, `/srv/laia/agora` o `/srv/laia/users`.
- Migración de datos reales al ThinkStation.

## Fase 0 — Preparación

Crear rama de trabajo:

```bash
cd /home/laia-hermes/LAIA
git status --short
git switch -c wip/<agente>/dev-stable-versioning
```

Si el worktree tiene cambios ajenos, no revertirlos. Leerlos y trabajar alrededor.

Ver estado actual:

```bash
git branch --show-current
git remote -v
git log --oneline -5
rg 'DEFAULT_BRANCH=' install.sh
rg 'feat/installer-wizard|stable|main' install.sh workflow AGENTS.md
```

## Fase 1 — Crear Rama Stable Y Tag Inicial

Confirmar con Jorge el tag inicial. Si no responde y ya aprobó este plan, usar `v0.1.0`.

Comandos esperados:

```bash
cd /home/laia-hermes/LAIA
git fetch origin
git switch feat/installer-wizard
git pull origin feat/installer-wizard
git switch -c stable
git tag -a v0.1.0 -m "release v0.1.0"
git push origin stable v0.1.0
git switch wip/<agente>/dev-stable-versioning
```

Si `stable` ya existe:

```bash
git fetch origin stable --tags
git branch --list stable origin/stable
```

No sobrescribir ni force-pushear. Si diverge, parar y explicárselo a Jorge.

## Fase 2 — Cambiar Default De `install.sh`

Editar `install.sh`:

```bash
DEFAULT_BRANCH="stable"
```

Mantener soporte existente de `--branch`. No romper instalaciones que pasen una rama explícita.

Opcional solo si es muy pequeño y queda testeado: añadir `--channel`:

- `--channel stable` equivale a `--branch stable`
- `--channel dev` equivale a `--branch main`
- si se pasan `--channel` y `--branch` juntos, `--branch` debe ganar o el script debe fallar con mensaje claro. Elegir una conducta y documentarla.

Recomendación: no añadir `--channel` en la primera implementación salvo que el código ya lo facilite. `--branch` es suficiente.

## Fase 3 — Documentar Flujo De Release

Crear `workflow/release-flow.md` con este contenido mínimo:

- Roles de ramas: `main`, `stable`, `feat/*`, `wip/*`.
- Dónde corre cada rama:
  - VM Mac QEMU dev: `main` o `feat/*`, datos sintéticos.
  - ThinkStation prod: `stable`, datos reales.
- Cómo hacer promote manual.
- Cómo desplegar en prod.
- Cómo hacer rollback.
- Qué hacer si un cambio toca backend o `.laia-core`: reconstruir imágenes LXD manualmente hasta que exista versionado de imágenes.
- Cómo hacer hotfix.
- Criterios mínimos antes de tag:
  - tests verdes
  - install/clone smoke en VM dev
  - changelog actualizado

Comandos de promote que deben aparecer en el documento:

```bash
# En dev
cd /home/jorge/LAIA
git switch main
git pull origin main
bash tests/installer/run_all.sh

git switch stable
git pull origin stable
git merge --ff-only main
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push origin stable vX.Y.Z

# En prod
cd /home/jorge/LAIA
git fetch --all --tags
git switch stable
git pull origin stable
sudo laia-release
```

Rollback:

```bash
sudo laia-rollback
readlink -f /opt/laia
```

Hotfix:

```bash
git switch -c fix/<area> stable
# commit fix + tests
git switch stable
git merge --ff-only fix/<area>
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push origin stable vX.Y.Z
git switch main
git merge --ff-only stable
git push origin main
```

## Fase 4 — Actualizar Documentación Operativa

Actualizar `workflow/02-how-to-work.md`:

- Mantener la regla de no commitear directo a `main` para trabajo normal.
- Añadir:
  - `main` es integración/dev.
  - `stable` es producción.
  - no se trabaja directo en `stable`.
  - `stable` solo recibe merges fast-forward desde `main` o hotfixes aprobados.
  - tags semver solo en `stable`.

Actualizar `AGENTS.md` con una sección breve, por ejemplo:

```markdown
## Branching operativo

- `main` es desarrollo/integración.
- `stable` es producción. El instalador por defecto debe apuntar a `stable`.
- No hagas commits directos a `stable` salvo hotfix aprobado por Jorge.
- Los tags `vX.Y.Z` se crean solo sobre `stable`.
```

No editar `LAIA_ECOSYSTEM.md` sin confirmación explícita de Jorge. Si Jorge confirma, añadir una frase mínima en la sección de instalación/versionado indicando que `/opt/laia -> /opt/laia-vX.Y.Z` en producción se alimenta desde `stable`.

Actualizar `workflow/plans/README.md` para incluir este plan en "Planes activos" si no está.

## Fase 5 — Tests

Añadir o actualizar tests en `tests/installer/`.

Cobertura mínima:

1. `install.sh` default branch es `stable`.
2. `--branch <x>` sigue sobreescribiendo el default.
3. Si se implementa `--channel`, testear `stable`, `dev` y el conflicto con `--branch`.

Buscar patrón existente antes de crear test nuevo:

```bash
rg 'DEFAULT_BRANCH|--branch|install.sh' tests/installer
```

Si no hay test adecuado, crear uno con el estilo de `tests/installer/test_*.sh` y registrarlo en `tests/installer/run_all.sh` si el runner no lo detecta automáticamente.

## Fase 6 — Verificación Local

Ejecutar:

```bash
bash -n install.sh
bash tests/installer/run_all.sh
```

Si se tocó documentación solamente además de `install.sh`, estos dos comandos bastan como verificación mínima.

Si se tocó `bin/laia-release`, `bin/laia-install`, `bin/laia-clone` o librerías de `infra/installer/lib/`, ejecutar además:

```bash
make test
```

Si alguna prueba falla por causa preexistente, no ocultarlo. Registrar en `workflow/problems.md` con el comando exacto y el error.

## Fase 7 — Verificación En VM Dev

En la VM dev de Jorge:

```bash
cd /home/jorge/LAIA
git fetch --all --tags
git switch main
sudo laia-install --from-local /home/jorge/LAIA --version v0.0.0-dev
sudo /usr/local/bin/laia diagnose
```

Verificar que la instalación dev usa código local y no toca la rama `stable`.

## Fase 8 — Verificación Tipo Prod

En una VM limpia o en el ThinkStation cuando Jorge lo permita:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
  | sudo -E bash -s -- --mode install --yes
```

Verificar:

```bash
cd /home/jorge/LAIA
git branch --show-current
git describe --tags --exact-match || true
readlink -f /opt/laia
sudo /usr/local/bin/laia diagnose
```

Resultado esperado:

- rama local `stable`
- `/opt/laia` apunta a `/opt/laia-v...`
- diagnose pasa

## Criterios De Hecho

La tarea no está terminada hasta que todo esto sea cierto:

- `install.sh` default apunta a `stable`.
- `--branch` sigue funcionando.
- `workflow/release-flow.md` existe y tiene comandos copy-pasteables.
- `AGENTS.md` y `workflow/02-how-to-work.md` explican `main`/`stable`.
- `workflow/plans/README.md` referencia este plan.
- Hay test para el default `stable`.
- `bash -n install.sh` pasa.
- `bash tests/installer/run_all.sh` pasa o cualquier fallo queda documentado como preexistente.
- `workflow/changelog.md` actualizado.
- `git status --short` revisado antes de cerrar.
- La IA explica a Jorge qué quedó hecho, qué comandos corrió y qué queda pendiente.

## Riesgos Y Mitigaciones

- Riesgo: `curl|bash` antiguo dependía de `feat/installer-wizard`.
  Mitigación: crear `stable` antes de cambiar `DEFAULT_BRANCH`; documentar que dev debe usar `--branch main` o rama explícita.

- Riesgo: `stable` diverge de `main`.
  Mitigación: usar `git merge --ff-only`; si falla, parar y escalar. No usar `push --force`.

- Riesgo: release nuevo cambia backend o `.laia-core` pero no reconstruye LXD.
  Mitigación: documentar en `workflow/release-flow.md` que esos cambios requieren `infra/lxd/scripts/rebuild-2-images.sh` en la máquina destino.

- Riesgo: datos reales en prod sin backup.
  Mitigación: antes de mover datos reales al ThinkStation, Jorge debe configurar backup de `/srv/laia/`. Esto queda fuera de esta tarea.

- Riesgo: una IA edita `LAIA_ECOSYSTEM.md` sin permiso.
  Mitigación: este plan lo prohíbe salvo confirmación explícita de Jorge.

## Notas Para La IA Implementadora

- No asumas que el branch actual es correcto; compruébalo.
- No hagas `git reset --hard`, `git clean -fd` ni `push --force`.
- No toques `/srv/laia/` ni permisos de producción para esta tarea.
- No borres planes existentes.
- Usa `apply_patch` o editor equivalente para cambios pequeños y revisables.
- Mantén los commits pequeños:
  - `docs: add dev/stable release flow`
  - `fix: default installer branch to stable`
  - `test: cover installer default branch`
- Si Jorge pide commit + push, pushea la rama de trabajo o la rama que él indique. No cambies default branch de GitHub desde CLI salvo orden explícita.
