# Saneamiento de GitHub: unificar LAIA, archivar Hermes y experimentos orphan

- **Fecha**: 2026-05-28
- **Owner**: claude-opus (autor del plan); Jorge aprueba y ejecuta los pasos en GitHub UI; Claude ejecuta los pasos de git CLI tras aprobación
- **Estado**: aprobado, en-curso (Fase 1 ✓ · Fase 2 ✓ · Fase 3 pendiente Jorge)

## Principio rector (Jorge, 2026-05-28)

**No integrar sin verificar.** Cada fase que reintegre trabajo (cherry-pick, push,
rename, archivado) **DEBE** cerrar con un bloque de verificación. Si la verificación
falla, NO se avanza a la siguiente fase — se diagnostica y se arregla primero. La
integración de las skills de dev (mattpocock + las 3 IAs Claude/Codex/OpenCode) tiene
una verificación específica obligatoria (Fase 7 bis).

## Contexto

`JorgeMP-3/laia-arch` arrastra **6 historias paralelas orphan** sin ancestro común:

1. `main` — **Hermes Agent upstream** (proyecto de Nous Research por Teknium; 6.625 commits desde julio 2025) + tus parches de installer encima.
2. `stable` — **snapshot orphan de LAIA** (1 commit, 26-may, 2.574 archivos).
3. `feat/installer-cloner-v2` — LAIA orphan vieja (49 commits, hasta 21-may, SIN AGENTS.md/CLAUDE.md/workflow).
4. `feat/installer-wizard` — LAIA orphan intermedia (92 commits, hasta 25-may).
5. `wip/codex/dev-stable-versioning` — **base oficial de LAIA-ARCH** (95 commits, hasta 25-may, **contiene los tags v0.1.0/0.1.1/0.1.2** = releases).
6. `local-customizations` — customizaciones viejas pre-LAIA sobre Hermes.

Más, en local (no pusheadas todavía):
- `wip/jorge/recent-fixes` — 7 commits sobre `stable` orphan (atlas v2, fix migration, fix clone, recover cron, fix installer, docs ecosystem, fix wrappers). Trabajo de los últimos 2 días.
- `wip/jorge/cleanup-and-trio` — 3 commits (trío docs canónicos + chore claude + trace LAIA_TRACE).
- `wip/claude/mattpocock-dev-skills` — 1 commit grande (skills + doctrina FASE/right-size).

**Realidad operativa**: la "verdad" actual de LAIA es `wip/codex/dev-stable-versioning` (más historia, releases tageados, AGENTS/CLAUDE/workflow completos). Stable orphan + recent-fixes es trabajo divergente de los últimos 2 días que hay que reintegrar a esa base. Las dos `feat/installer-*` son experimentos viejos previos al versionado.

Doc actual (`workflow/02-how-to-work.md`) dice `main=dev / stable=prod`, pero la realidad es opuesta: main es Hermes upstream. Ninguna IA o humano puede orientarse en este estado.

## Objetivo

Tras el saneamiento, el repo en GitHub tendrá esta estructura limpia y coherente con la doc:

```
JorgeMP-3/laia-arch
├── main              ← LAIA-ARCH (la rama de Codex con tags) — DEFAULT BRANCH
├── stable            ← LAIA-ARCH release tip (creada desde main)
├── wip/jorge/recent-fixes-on-main         (los 7 commits de stable orphan reintegrados)
├── wip/jorge/cleanup-and-trio-on-main     (los 3 commits reintegrados)
├── wip/claude/mattpocock-dev-skills-on-main  (skills + doctrina reintegrados)
├── archive/hermes-upstream                (la antigua `main`)
├── archive/hermes-local-customizations    (`local-customizations`)
├── archive/laia-pre-versioning-cloner-v2  (`feat/installer-cloner-v2`)
├── archive/laia-pre-versioning-wizard     (`feat/installer-wizard`)
├── archive/laia-stable-orphan-snapshot    (el `stable` orphan de 26-may)
└── tags v0.1.0, v0.1.1, v0.1.2            (siguen apuntando a sus commits dentro de main)
```

## Prerequisitos (bloqueantes)

1. **Auth SSH a GitHub funcionando**. Jorge añade la clave pública (ya generada) en https://github.com/settings/keys.
2. **Verificar protecciones de branch** en GitHub. Si `main` está protegida (rules en Settings → Branches), Jorge las relaja temporalmente o las migra a la nueva main al final.
3. **Snapshot/backup conceptual**: el archivo de Hermes y de los orphans EN GITHUB es la red de seguridad. Si algo falla, se puede revertir desde los `archive/*`.

## Plan por fases

### Fase 0 — Prerequisitos (Jorge)

- Añadir la clave SSH a GitHub (Settings → SSH and GPG keys → New SSH key).
- Avisar a Claude para verificar `ssh -T git@github.com` y cambiar el remote a SSH.

### Fase 1 — Backups y push de wips locales (Claude, sin destruir nada)

1. Cambiar remote a SSH: `git remote set-url origin git@github.com:JorgeMP-3/laia-arch.git`.
2. Verificar auth: `ssh -T git@github.com` debe saludar por nombre.
3. Push de las 3 wips locales NO pusheadas (cap. 4 original):
   ```bash
   git push -u origin wip/jorge/recent-fixes
   git push -u origin wip/jorge/cleanup-and-trio
   git push -u origin wip/claude/mattpocock-dev-skills
   ```
4. Esto NO afecta a ninguna rama existente; sube las 3 wips como ramas nuevas.

### Fase 2 — Archivar Hermes y orphans viejas (Claude, push a nuevas ramas archive/*)

Por cada rama a archivar, hacer un push que copie su contenido bajo `archive/`:

```bash
git push origin refs/remotes/origin/main:refs/heads/archive/hermes-upstream
git push origin refs/remotes/origin/local-customizations:refs/heads/archive/hermes-local-customizations
git push origin refs/remotes/origin/feat/installer-cloner-v2:refs/heads/archive/laia-pre-versioning-cloner-v2
git push origin refs/remotes/origin/feat/installer-wizard:refs/heads/archive/laia-pre-versioning-wizard
git push origin refs/remotes/origin/stable:refs/heads/archive/laia-stable-orphan-snapshot
```

**Verificación intermedia**: las 5 nuevas ramas `archive/*` aparecen en GitHub. NO se ha borrado nada todavía.

### Fase 3 — Promover `wip/codex/dev-stable-versioning` a la nueva `main` (Jorge en GitHub UI)

Cambiar el default branch del repo a `wip/codex/dev-stable-versioning`:
- GitHub repo → Settings → General → Default branch → cambiar a `wip/codex/dev-stable-versioning` (botón con icono de doble flecha).
- Confirmar el aviso.

Tras esto, el default ya no es `main` (Hermes); es la rama de Codex. Esto desbloquea poder borrar `main`.

### Fase 4 — Borrar la `main` antigua y renombrar la de Codex a `main` (Claude)

```bash
# 1. Borrar main (Hermes) — ya está copiada en archive/hermes-upstream
git push origin --delete main

# 2. Renombrar la rama de Codex a 'main' (en remoto)
git push origin refs/remotes/origin/wip/codex/dev-stable-versioning:refs/heads/main
git push origin --delete wip/codex/dev-stable-versioning
```

### Fase 5 — Restablecer `main` como default y limpiar (Jorge en GitHub UI)

- GitHub repo → Settings → General → Default branch → cambiar a `main`.
- Verificar que los tags v0.1.0/0.1.1/0.1.2 siguen apuntando a commits accesibles desde main.

### Fase 6 — Reintegrar los 7 commits de `recent-fixes` sobre la nueva main (Claude, **operación delicada**)

Los 7 commits de `wip/jorge/recent-fixes` están sobre `stable` orphan y NO sobre la nueva main. Hay que reaplicarlos.

Estrategia recomendada: **cherry-pick uno a uno**, resolviendo conflictos si los hay (los archivos suelen existir en ambas con estructura similar).

```bash
git switch main
git pull origin main
git switch -c wip/jorge/recent-fixes-on-main

for sha in b2a99a04 8b927318 9894e977 85dc7c9c e4e2847c 314a69f2 80aa0c6d; do
  git cherry-pick $sha
  # si hay conflicto: resolverlo, git add, git cherry-pick --continue
done

git push -u origin wip/jorge/recent-fixes-on-main
```

(Las wips originales `wip/jorge/recent-fixes` quedan en GitHub como referencia hasta que se decida archivarlas.)

**Verificación post-Fase 6 (gate obligatorio):**
- `git log --oneline main..wip/jorge/recent-fixes-on-main` muestra 7 commits con los mismos mensajes que los originales.
- Para cada commit reintegrado, comprobar que su cambio principal está aplicado:
  - `e4e2847` feat(atlas): `bin/atlas` o el código del registro universal v2 está presente en disco.
  - `9894e977` fix(laia-core): el paquete `cron/` y `SOUL.md` están presentes.
  - `85dc7c9c` fix(clone): la lógica de rewrite estructural de config.yaml.
  - `8b927318` fix(installer): shell_rc restore.
  - `314a69f2` fix(migration): rutas legacy.
  - `b2a99a04` fix(clone): wrappers bin/.
  - `80aa0c6d` docs(ecosystem): separación visión/detalle.
- Si algún commit no aplica limpio (skip por duplicado/irrelevante), documentarlo en el changelog.
- **STOP si algo falla** — diagnosticar antes de seguir.

### Fase 7 — Reintegrar `cleanup-and-trio` y `mattpocock-dev-skills` sobre la nueva main

Mismo procedimiento que Fase 6:

```bash
git switch -c wip/jorge/cleanup-and-trio-on-main main
git cherry-pick 2e6e893e 1d0f4120 d38e729c
git push -u origin wip/jorge/cleanup-and-trio-on-main

git switch -c wip/claude/mattpocock-dev-skills-on-main main
git cherry-pick 444db36c
git push -u origin wip/claude/mattpocock-dev-skills-on-main
```

**Verificación post-Fase 7 (gate obligatorio) — cleanup-and-trio:**
- Trío docs (`LAIA_ECOSYSTEM.md` §8, `arch-layout.md`, `project-map.md`) tienen las refinaciones visión/spec/realidad.
- `.claude/settings.json` no tiene entradas a `familiamp/.hermes`/`laia-hermes`.
- `.laia-core/run_agent.py` tiene las 3 líneas de trace LAIA_TRACE.

**Verificación post-Fase 7 (gate obligatorio) — mattpocock-dev-skills (DEV SKILLS PARA LAS 3 IAs):**

Esta es la verificación más importante. La integración SOLO se considera buena si pasa
TODO esto:

```bash
git switch wip/claude/mattpocock-dev-skills-on-main

# 1. Las 13 skills existen en .claude/skills/ con frontmatter valido y name==carpeta
python3 - <<'PY'
import glob, yaml, sys
ok=0
for f in sorted(glob.glob(".claude/skills/*/SKILL.md")):
    fm = yaml.safe_load(open(f, encoding="utf-8").read().split("---",2)[1])
    name = fm.get("name"); desc = fm.get("description")
    folder = f.split("/")[-2]
    assert name == folder, f"{f}: name '{name}' != folder '{folder}'"
    assert desc, f"{f}: description vacia"
    ok += 1
assert ok == 13, f"esperadas 13 skills, encontradas {ok}"
print(f"OK: 13 skills con frontmatter valido y name==carpeta")
PY

# 2. .codex/skills/ tiene 12 symlinks (git-guardrails NO porque es Claude-only)
test "$(git ls-files -s .codex/skills | awk '$1==120000' | wc -l)" -eq 12

# 3. Symlinks resuelven a SKILL.md reales
for s in diagnose grill-me grill-with-docs handoff improve-codebase-architecture \
         setup-matt-pocock-skills tdd to-issues to-prd triage write-a-skill zoom-out; do
  test -f ".codex/skills/$s/SKILL.md" || { echo "BROKEN: $s"; exit 1; }
done

# 4. git-guardrails NO esta en .codex (es Claude-only, sin symlink)
test ! -e .codex/skills/git-guardrails

# 5. AGENTS.md tiene §Agent skills + right-size + guardarrailes
grep -q "## Agent skills" AGENTS.md
grep -q "right-size" AGENTS.md
grep -q "Siempre" AGENTS.md && grep -q "Pregunta primero" AGENTS.md && grep -q "Nunca" AGENTS.md

# 6. CLAUDE.md es stub
test "$(wc -l < CLAUDE.md)" -lt 30

# 7. workflow/ai-mindset.md y .claude/skills/README.md y .claude/skills/UPSTREAM.md existen
test -f workflow/ai-mindset.md
test -f .claude/skills/README.md
test -f .claude/skills/UPSTREAM.md

# 8. (Opcional, requiere reinicio de Claude Code) `/grill-me` autocompleta en Claude Code
echo "MANUAL: reabre 'claude' en el repo y teclea /grill-me — debe autocompletar."
echo "MANUAL: reabre 'codex' y teclea /skills — debe listar las 12."
```

Si CUALQUIERA de los checks 1-7 falla → **STOP**, diagnosticar el cherry-pick (probablemente
conflicto mal resuelto), corregir y revalidar.

### Fase 8 — Crear nueva `stable` desde `main` (Claude)

`stable` queda como el tip de producción. Inicialmente igual a main; conforme se vayan mergeando PRs y se haga release, se promueve.

```bash
git push origin main:refs/heads/stable-new
# y luego en GitHub UI:
# - Borrar la 'stable' actual (orphan, ya archivada en archive/laia-stable-orphan-snapshot)
# - Renombrar 'stable-new' a 'stable'
# (alternativa CLI con `--force` y permisos):
# git push --force-with-lease origin main:stable
```

### Fase 9 — Abrir PRs de las 3 wips reintegradas (Jorge en GitHub UI o Claude con gh si se instala)

3 Pull Requests, todas contra `main`:
- `wip/jorge/recent-fixes-on-main` → `main`
- `wip/jorge/cleanup-and-trio-on-main` → `main`
- `wip/claude/mattpocock-dev-skills-on-main` → `main`

Jorge revisa cada uno y mergea con un click.

### Fase 10 — Limpieza final de las wips originales (orphan-based)

Tras mergear las PRs, archivar las wips originales (basadas en stable orphan):

```bash
git push origin refs/remotes/origin/wip/jorge/recent-fixes:refs/heads/archive/wip-jorge-recent-fixes-orphan
git push origin --delete wip/jorge/recent-fixes

git push origin refs/remotes/origin/wip/jorge/cleanup-and-trio:refs/heads/archive/wip-jorge-cleanup-and-trio-orphan
git push origin --delete wip/jorge/cleanup-and-trio

git push origin refs/remotes/origin/wip/claude/mattpocock-dev-skills:refs/heads/archive/wip-claude-mattpocock-orphan
git push origin --delete wip/claude/mattpocock-dev-skills
```

### Fase 11 — Actualizar docs para reflejar la nueva realidad

En la nueva `main`, actualizar:
- `workflow/02-how-to-work.md`: la descripción de main/stable ya es correcta — solo añadir nota de que el saneamiento del 2026-05-28 unificó las historias orphan.
- `AGENTS.md`: actualizar §"A dónde ir" y §"Si encuentras una contradicción" si procede.
- `workflow/changelog.md`: entrada del saneamiento (qué se hizo, qué se archivó).
- `workflow/01-canonical-sources.md`: confirmar que `LAIA_ECOSYSTEM.md` sigue siendo canónico.

Commit como `docs(repo): registrar saneamiento de ramas y archivado de Hermes (2026-05-28)`.

### Fase 12 — Verificación final

```bash
git fetch origin --prune
git branch -r
```

Comprobar que:
- ✓ `origin/main` existe y es LAIA (con tags v0.1.x accesibles).
- ✓ `origin/stable` existe.
- ✓ 5 ramas `archive/*` con el contenido legado.
- ✓ 3 PRs mergeadas o pendientes según se haya decidido.
- ✓ Default branch en GitHub es `main`.
- ✓ Ninguna rama "huérfana" con contenido perdido.

### Fase 13 — Documentación de git+github para el proyecto (Claude)

**Audiencia split** (regla LAIA: AI-facing terso, Jorge-facing explicado):

**13.1 — Para Jorge (human-facing, explicada):** crear `workflow/git-github-guide.md` con:
- Modelo mental git+GitHub (local vs remoto, branches, fetch/pull/push, refspec, PR).
- El historial real de saneamiento del 2026-05-28 (cómo era el lío, cómo se ordenó).
- Operaciones frecuentes con comandos exactos y explicación: clonar, traer cambios, crear branch, commitear, push, abrir PR, mergear, sincronizar tras merge, archivar branch.
- Cómo añadir una clave SSH (es la entrada al sistema).
- Mapa visual del repo tras el saneamiento (qué es `main`, `stable`, `archive/*`, `wip/<agente>/...`).
- Errores típicos y cómo salir: working tree sucio, branch desfasada, push rechazado, cherry-pick conflictivo.
- Cuándo escalar a una IA y cuándo no.

**13.2 — Para las IAs (AI-facing, denso):** extender `AGENTS.md` con una sección
`## Git workflow` corta (~30 líneas), con:
- El modelo (`main`=dev LAIA, `stable`=prod LAIA, `archive/*` = histórico inmutable, `wip/<agente>/<tarea>` = trabajo en curso).
- Reglas imperativas (no commit directo a `main` ni `stable`; PR como puerta; cherry-pick si vienen de orphan; no force-push a ramas compartidas).
- Comandos canónicos de cada operación.
- Pointer a `workflow/git-github-guide.md` para el porqué.

**13.3 — Reflejar en el índice:** actualizar `workflow/00-start-here.md` y
`workflow/01-canonical-sources.md` para que apunten a la nueva guía.

**Commit:** `docs(git): añadir guía de git+github + extensión AGENTS.md §Git workflow`.

## Verificación de éxito

- **Cualquier IA o humano que clone el repo** ve `main` como rama por defecto, con LAIA-ARCH.
- **Los tags v0.1.0/0.1.1/0.1.2** siguen apuntando a commits accesibles desde main.
- **El historial de Hermes** está preservado en `archive/hermes-upstream` (no se ha perdido nada upstream).
- **Tu trabajo local** de los últimos días está integrado vía PRs en la nueva main.
- **Docs y realidad** coinciden por primera vez en semanas.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Conflictos en cherry-pick (Fase 6) por archivos distintos entre orphans | Resolver uno a uno; si un commit es irrelevante en la nueva estructura, se `--skip`. |
| Branch protections de GitHub impidan `--delete main` o push a `main` | Jorge desactiva temporalmente en Settings → Branches; reactiva al final. |
| Default branch no se cambia antes de borrar main | El plan lo pide explícitamente en Fase 3. Sin eso, `--delete main` falla. |
| Push --force destructivo | Se evita en todo el plan; solo se usan creación de nuevas ramas y `--delete` tras backup en archive/. |
| Codex u otra IA pierda referencia a `wip/codex/dev-stable-versioning` | La nueva `main` ES esa rama renombrada — sus commits son los mismos SHAs. |
| Tag v0.1.x se vuelve "huérfano" (sin rama que lo contenga) | Tras Fase 4, los tags siguen siendo descendientes de la nueva main; verificar en Fase 12. |
| CI/workflows de `.github/` de Hermes ya no aplican | LAIA no tiene CI configurado actualmente; quedan en `archive/hermes-upstream` para referencia. |

## Rollback

Si en cualquier fase algo va mal:

- **Antes de Fase 4** (borrar Hermes main): todo es reversible. Las copias ya están en `archive/*`.
- **Después de Fase 4**: para restaurar Hermes main, `git push origin archive/hermes-upstream:main` (desde Claude tras desactivar default-branch temp). Mismo patrón para cualquier otra rama archivada.
- **Si cherry-pick rompe** en Fase 6/7: `git cherry-pick --abort` y reconsiderar la estrategia (volver a la original wip y traer cambios manualmente).
