# AGENTS.md — Entry point para IAs agénticas en LAIA

Reglas operativas comunes a las 3 IAs de desarrollo (Claude Code, Codex, OpenCode).
**Léelo entero antes de actuar.** `CLAUDE.md` apunta aquí. El *porqué* y la mentalidad
(versión explicada) están en `workflow/ai-mindset.md`.

## Qué es LAIA

LAIA es un ecosistema de agentes de IA personales con dos expresiones: **LAIA-ARCH** (capa
de administración del host, sólo Jorge, invisible para usuarios) y **LAIA-AGORA** (la
plataforma multi-usuario en un container, lo que los usuarios llaman "LAIA"). Dentro de
LAIA-AGORA cada usuario tiene su agente personal (**PA-AGORA**) en un container privado
donde es root. Modelo completo en `LAIA_ECOSYSTEM.md` — documento canónico.

El operador y único dev de LAIA-ARCH es **Jorge Miralles Pérez**. Dirígete a él como Jorge.

## Cómo trabajar: right-size

**Ajusta el proceso a la tarea, no al revés.** Eres un ingeniero senior, no un robot de
proceso. Un typo se arregla y ya; una feature ambigua o multi-archivo pasa por el protocolo
completo. Sube el rigor con la ambigüedad, el riesgo y el nº de sistemas que tocas.

El **protocolo FASE es el *default* para trabajo no-trivial** (no un ritual obligatorio).
Cada fase es una skill (ver §Agent skills); salta las que no aporten a *esta* tarea:

| Fase | Skill |
|---|---|
| 1 — Grill (interrogar la idea antes de codear) | `grill-me` / `grill-with-docs` |
| 2 — Planificar (PRD + vertical slices, esperar OK) | `to-prd` → `to-issues` |
| 3 — TDD (Red-Green-Refactor, tests en `~/LAIA/tests/`) | `tdd` |
| 4 — Diagnóstico (reproducir, causa raíz, test primero) | `diagnose` / `triage` |
| Cierre de turno · contexto · arquitectura | `handoff` · `zoom-out` · `improve-codebase-architecture` |

Detalle de la mentalidad y cuándo subir/bajar el rigor: `workflow/ai-mindset.md`.

## Guardarraíles

### Siempre
- `LAIA_ECOSYSTEM.md` es canónico: si algo lo contradice, gana él.
- Toda integración nueva → su test en `~/LAIA/tests/`; corre la **suite completa** antes de declarar "hecho".
- Trabaja en branch `wip/<agente>/<tarea>` (nunca commits directos a `main`). Conventional Commits.
- Reutiliza lo que existe (código, skills, utilidades) antes de crear nuevo.
- Al cerrar turno, actualiza lo que aplique: `workflow/changelog.md` (cambio material), `workflow/problems.md` (bug descubierto), `workflow/security.md` (credenciales/permisos/red/secrets).

### Pregunta primero
- Acciones destructivas o difíciles de revertir: `push --force`, `reset --hard`, `clean -fd`, `rm -rf`, drop/reset de `agora.db`/`workspace.db`.
- Merge a `main`; cualquier cosa hacia `stable`.
- Cambios grandes a docs vivos (`workflow/*`): deja draft en `workflow/_inbox/` (ver `workflow/03-multi-ai-coordination.md`).
- Tocar permisos/credenciales en `~/.laia/` o `/srv/laia/`.

### Nunca
- Editar `LAIA_ECOSYSTEM.md` sin consentimiento explícito de Jorge.
- Inventar paths, endpoints o componentes: si no está en `LAIA_ECOSYSTEM.md` o `docs/db-export/`, no existe.
- Commits directos a `stable` (salvo hotfix aprobado); tags `vX.Y.Z` fuera de `stable`.
- `--no-verify` / saltarse hooks.

Detalle de "qué nunca sin permiso" en `workflow/02-how-to-work.md`. Runbook de release en `workflow/release-flow.md`.

## Git workflow

Modelo del repo `JorgeMP-3/laia-arch` tras el saneamiento del 2026-05-28:

- **`main`** = desarrollo activo de LAIA-ARCH. Default branch. **Nunca commit directo.**
- **`stable`** = producción (tip de release). El instalador apunta aquí. Solo se promueve desde `main`.
- **`wip/<agente>/<tarea>`** = trabajo en curso. Una branch por tarea no-trivial. Patrón obligatorio.
- **`archive/*`** = histórico inmutable (Hermes upstream, orphans previas, wips legados). **No tocar ni borrar.**
- **`tags vX.Y.Z`** = releases sobre `stable`.

Comandos canónicos:

```bash
# Empezar tarea
git switch -c wip/<agente>/<slug> main
# Trabajar, commitear (Conventional Commits)
git add <archivos>; git commit -m "feat(area): descripción"
# Publicar y abrir PR
git push -u origin wip/<agente>/<slug>     # GitHub muestra URL de PR; abrir contra main
# Tras merge: limpiar
git switch main; git pull
git branch -d wip/<agente>/<slug>
git push origin --delete wip/<agente>/<slug>
```

Reglas imperativas:
- **No** `git push --force` a `main`/`stable`/`archive/*`.
- **No** `git reset --hard` sin red de seguridad (branch de backup primero).
- **No** mergear PR sin que la suite (`workflow/02-how-to-work.md` §Tests) pase.
- Si los commits vienen de orphan disjoint, usar `cherry-pick`, no `merge`.
- Conflictos en docs append-only (`changelog.md`, `problems.md`, `security.md`) → combinar entradas chronológicamente.

### Cuántas branches / cuántos PRs por tarea

**Regla por defecto: 1 tarea = 1 branch = 1 PR.** LAIA es solo-dev — Jorge revisa
y mergea sin equipo. El patrón "muchos PRs pequeños stacked" del mundo corporativo
**aquí solo añade lío**, no seguridad.

| Caso | Patrón correcto |
|---|---|
| Tarea coherente, aunque toque varios archivos/áreas (ej. "adoptar Atlas v2" en agora-backend + scripts + docs) | **1 branch + 1 PR consolidado** con commits separados dentro para legibilidad (`feat: helper`, `feat: migrate config.py`, `test: regression`, `docs: changelog`). |
| Dos tareas **totalmente independientes** (sin orden de aplicación, distintos archivos) | 1 branch + 1 PR cada una. Mergeables en cualquier orden. |
| Trabajo en cadena (PR-B depende de PR-A no mergeado aún) | **NO usar stacked PRs.** 1 sola branch + 1 PR con los 2 commits en orden. |

**Por qué los stacked PRs rompen aquí (lección 2026-05-28):**
Al mergear el PR base con `gh pr merge --delete-branch`, GitHub **auto-cierra
sin mergear** los PRs que tienen esa branch como base. Los cambios "stacked
encima" se quedan huérfanos; hay que reabrir y rehacer el merge. Pasó con
PR #5 y #6 de Atlas adoption: se cerraron solos al borrar `wip/claude/atlas-refs-new`.

**Indicador de "estoy abriendo demasiados PRs":** si el segundo PR usa
`--base wip/<otra-branch>` en vez de `--base main`, está stacked → fusiona los
2 en uno solo antes de pushear.

Detalle del error histórico en `workflow/git-github-guide.md` §"Stacked PRs:
por qué no". El **porqué** general (modelo mental, errores típicos, cómo
recuperarse, historia del saneamiento) también ahí.

## Agent skills

Las IAs de desarrollo comparten un catálogo de skills de workflow en `.claude/skills/`
(Claude Code y OpenCode lo leen nativamente; Codex vía symlinks en `.codex/skills/`).
Guía de uso en `.claude/skills/README.md`; procedencia y actualización en `.claude/skills/UPSTREAM.md`.

> ⚠️ Son skills de **DESARROLLO** (para las IAs que construyen LAIA). NO confundir con las
> skills de **PRODUCTO** del Marketplace (`skills/` en la raíz del repo),.

Esta sección es la config que las skills de ingeniería esperan encontrar:

- **Issue tracker** — ficheros locales del repo, **no** GitHub/GitLab/Linear. Bugs y su
  estado → `workflow/problems.md`. PRDs y planes → `workflow/plans/`. (Lo consumen
  `to-issues`, `to-prd`, `triage`.)
- **Triage labels / estados** — la verdad del estado es el campo `Estado:` de
  `workflow/problems.md` (`open` | `in-progress` | `blocked` | `resolved`; ver su
  cabecera). **No inventes etiquetas nuevas.** Los roles de triaje de las skills (`triage`,
  `to-issues`) se expresan SOBRE ese formato, no aparte:
  - `needs-triage` → `Estado: open`, sin `Owner`.
  - `needs-info` → `Estado: open`, `Owner: <reporter>`, + nota "needs-info: esperando <qué>".
  - `ready-for-agent` → `Estado: open`, `Owner: <agente>`, con reproducción/brief completos.
  - `ready-for-human` → `Estado: open`, `Owner: Jorge`, + nota de por qué no es delegable.
  - en curso / bloqueado → `Estado: in-progress` / `blocked`.
  - `wontfix` → `Estado: resolved`, + nota "wontfix: <razón>".
- **Domain docs** — el glosario/dominio canónico es `LAIA_ECOSYSTEM.md` (en lugar de
  `CONTEXT.md`). Las decisiones de arquitectura ("ADRs") viven en `workflow/arch-layout.md`
  (en lugar de `docs/adr/`). No editar el canónico sin Jorge; drafts grandes a `workflow/_inbox/`.

**Catálogo:** `grill-me`, `grill-with-docs`, `to-prd`, `to-issues`, `tdd`, `triage`,
`diagnose`, `handoff`, `zoom-out`, `improve-codebase-architecture`, `write-a-skill`,
`setup-matt-pocock-skills`, y `git-guardrails` (solo-Claude, vendorizada pero **no activada**).

**Invocación:** Claude Code `/<skill>` · Codex `$<skill>` o `/skills` · OpenCode auto/comando.

## A dónde ir después

| Archivo | Cuándo |
|---|---|
| `LAIA_ECOSYSTEM.md` | Qué es LAIA. Documento canónico. |
| `workflow/ai-mindset.md` | Cómo pensar al trabajar (el porqué, mentalidad senior). |
| `workflow/git-github-guide.md` | Modelo mental git+GitHub, operaciones, errores típicos, historia del saneamiento. |
| `.claude/skills/` | Catálogo de skills de workflow (+ `README.md`, `UPSTREAM.md`). |
| `workflow/00-start-here.md` | Índice de los archivos operativos. |
| `workflow/01-canonical-sources.md` | Dónde vive la verdad para cada tema. |
| `workflow/02-how-to-work.md` | Branches, commits, tests, cierre de turno. |
| `workflow/03-multi-ai-coordination.md` | Sólo si trabajas en paralelo con otra IA. |
| `docs/db-export/` | Detalle técnico exhaustivo (auto-generado desde `workspace.db`). |

## Referencia rápida de paths

| Path | Qué contiene |
|---|---|
| `~/LAIA/` | Código del proyecto. |
| `~/.laia/` | Runtime de LAIA-ARCH: credenciales (`auth.json`, `.env`), config, atlas. |
| `/srv/laia/` | Datos factory: containers, workspaces de usuarios, agora.db. |
| `/opt/laia/` | Copia instalada de LAIA en producción (no se usa en dev). |
| `~/LAIA/tests/` | Tests del ecosistema. **Tu trabajo nuevo va aquí.** |
| `~/LAIA/workflow/` | Cooperación entre IAs: rules, changelog, problems, plans. |
| `~/LAIA/docs/db-export/` | Export auto-generado de `workspace.db`. |
| `~/.laia/workspaces/laia-ecosystem/workspace.db` | Base de conocimiento técnico exhaustivo. |

## Si encuentras una contradicción

Entre `LAIA_ECOSYSTEM.md` y otra fuente: gana el primero. Si te bloquea, **escala a Jorge
antes de actuar** — no decidas tú cuál tiene razón.

ANTES DE HACER NADA EN EL PROYECTO LAIA DEBES LEER Y ENTENDER `LAIA_ECOSYSTEM.md`.
