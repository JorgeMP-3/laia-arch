# Git + GitHub en LAIA — guía explicada

> Documento human-facing, prosa explicativa. La versión densa para IAs vive en
> `AGENTS.md` §Git workflow.

Esta guía cubre cómo está organizado el repositorio `JorgeMP-3/laia-arch` en GitHub, cómo se
trabaja en él día a día, y cómo recuperarte cuando algo se tuerce. Si nunca has usado git en
serio, lee primero §1 (modelo mental) y §2 (operaciones). Si ya sabes pero no recuerdas algo
concreto de LAIA, salta directo a §3 (mapa del repo).

## 1. Modelo mental

**Analogía**: el proyecto es un libro que se escribe entre varios. Cada cambio es una "foto"
del libro completo en un momento concreto (un **commit**, identificado por un hash tipo
`be96536`). Las **branches** son borradores paralelos del libro: el borrador `main` es
desarrollo activo de LAIA, el `stable` es la versión publicada, y los `wip/<persona>/...`
son ensayos individuales antes de proponerse.

**Local vs GitHub**:

```
  TU MÁQUINA (~/LAIA/.git)        ←→        GITHUB (origin)
  ┌────────────────────────┐                ┌──────────────────────┐
  │ tu copia privada       │  git fetch ←── │ copia compartida     │
  │ trabajas aquí          │  git push  ──→ │ verdad para todos    │
  └────────────────────────┘                └──────────────────────┘
```

Tu repo en `~/LAIA/.git/` es **tu copia privada**. GitHub es **la copia compartida**. No
están conectados en tiempo real: tú decides cuándo subes (`push`) y cuándo bajas
(`fetch`/`pull`). Por eso es normal que difieran.

**Las 5 acciones básicas que tienes que dominar**:

| Acción | Qué hace | Cuándo |
|---|---|---|
| `git status` | Te dice qué has cambiado y no guardado | constantemente |
| `git add <archivo>` | Marca el archivo como "listo para commit" | antes de commitear |
| `git commit -m "msg"` | Guarda una "foto" de lo añadido en tu local | cuando terminas algo coherente |
| `git push` | Sube tu(s) commit(s) a GitHub | cuando quieres que viva en la nube |
| `git pull` | Baja los commits que otros (o tú desde otra máquina) subieron | al empezar a trabajar |

Y la gran herramienta de GitHub: el **Pull Request (PR)**. Es la "propuesta formal" para
fusionar el borrador `wip/...` en `main`. GitHub te enseña el diff, lo revisas como si
fuera el trabajo de otro, y mergeas con un botón.

## 2. Operaciones frecuentes (con comandos exactos)

### Empezar el día

Antes de tocar nada, asegúrate de tener lo último de GitHub:

```bash
cd ~/LAIA
git switch main
git pull            # baja los commits que haya en origin/main
```

Si tienes cambios sin commitear, git te avisará — los guardas (`git add` + `git commit`) o
los stasheas (`git stash`) antes del pull.

### Empezar una tarea nueva

Cada tarea no-trivial vive en su propia branch. La convención de LAIA: `wip/<agente>/<tarea>`.

```bash
git switch -c wip/jorge/mi-nueva-feature main
# … trabajas, modificas archivos …
git add <archivos-tocados>
git commit -m "feat(area): descripcion corta"
```

### Subir tu trabajo a GitHub

```bash
git push -u origin wip/jorge/mi-nueva-feature
```

El `-u` (alias de `--set-upstream`) le dice a tu local "esta branch ahora trackea esa del
remoto". Tras esto, futuros `git push` y `git pull` sin argumentos funcionarán.

### Abrir un Pull Request

GitHub te dará una URL al pushear, tipo:

```
https://github.com/JorgeMP-3/laia-arch/pull/new/wip/jorge/mi-nueva-feature
```

Ábrela, escribe un título y descripción, click "Create pull request". Después click "Merge"
cuando esté listo.

### Tras mergear un PR, limpieza

```bash
git switch main
git pull                                                # baja la versión mergeada
git branch -d wip/jorge/mi-nueva-feature                # borra la branch local
git push origin --delete wip/jorge/mi-nueva-feature     # borra la branch remota
```

### Stacked PRs: por qué NO

Un "stacked PR" es cuando abres PR-B con base = `wip/.../PR-A` en vez de `main`,
encadenando uno encima de otro. Suena cómodo (B continúa el trabajo de A) pero
**aquí rompe siempre**.

**Qué pasó el 2026-05-28**: Claude abrió 4 PRs para Atlas adoption — uno base
(#4 con refs nuevas) y tres encima (#5 agora-backend, #6 shell scripts, #7
changelog). Mergeé #4 con `--delete-branch`, que borró la branch base. **GitHub
auto-cerró #5 y #6 sin mergear** (porque ya no existía su branch base). Hubo que
reabrirlos como #8 y #9 contra main, perdiendo tiempo y generando ruido en el
historial.

**Regla**: 1 tarea coherente = 1 branch = 1 PR. Si tienes 3 cambios relacionados,
3 commits dentro de la **misma** branch. Solo abre PRs separados cuando son
**totalmente independientes** (mergeables en cualquier orden, sin tocar los
mismos archivos).

Si una IA te abre un PR con `--base wip/<otra-branch>` (no `--base main`), es
señal de stacked → pídele que fusione todo en uno solo.

### Cuándo `git pull` y cuándo `git fetch`

- **`git fetch`**: baja los commits de GitHub a tu local pero NO los aplica a tu branch.
  Útil para "espiar" qué hay nuevo sin tocarte.
- **`git pull`**: hace `fetch` + auto-merge en tu branch. Es lo que usas para "actualizar".

### Ver qué ha cambiado

```bash
git status                # qué archivos has tocado pero no commiteado
git diff                  # los cambios reales línea a línea
git log --oneline -10     # los 10 últimos commits
git branch -v             # todas tus branches locales con su último commit
git branch -r             # branches remotas (lo que hay en GitHub)
```

## 3. Mapa del repo `JorgeMP-3/laia-arch`

Tras el saneamiento del 2026-05-28, el repo en GitHub tiene esta estructura:

```
JorgeMP-3/laia-arch
├── main                    ← LAIA-ARCH desarrollo (default branch)
├── stable                  ← LAIA-ARCH producción (release tip)
│
├── wip/<agente>/<tarea>    ← Trabajo en curso. Una branch por tarea no-trivial.
│   convención: <agente> ∈ {jorge, claude, codex, opencode}
│
├── archive/hermes-upstream                    ← Hermes Agent (Nous Research). Fork upstream.
├── archive/hermes-local-customizations        ← Pre-LAIA Hermes customs.
├── archive/laia-pre-versioning-cloner-v2      ← Orphan LAIA antigua.
├── archive/laia-pre-versioning-wizard         ← Orphan LAIA intermedia.
├── archive/laia-stable-orphan-snapshot        ← Snapshot orphan de 26-may.
├── archive/wip-*-orphan                       ← Wips antiguas basadas en orphan.
│
└── tags vX.Y.Z             ← Releases sobre stable (v0.1.0, v0.1.1, v0.1.2 actualmente).
```

**Regla simple**:

- `main` es donde se trabaja activamente. No commits directos: siempre vía PR de una wip.
- `stable` es la rama estable, lo que el instalador apunta por defecto. Solo se promueve
  desde `main` cuando algo está bien probado.
- `archive/*` son ramas históricas inmutables. NUNCA se borran (son tu memoria del proyecto).

## 4. Autenticación SSH (entrada al sistema)

Para poder pushear necesitas que GitHub te reconozca esta máquina. Se hace con una clave
SSH (huella criptográfica única).

### Comprobar si ya funciona

```bash
ssh -T git@github.com
```

Si responde `Hi JorgeMP-3! You've successfully authenticated...` → todo OK.

### Si no funciona

1. **Genera la clave** (solo si no existe):
   ```bash
   ssh-keygen -t ed25519 -C "laia-arch@miel-maquina"
   ```
2. **Copia la clave pública**:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
3. **Añádela a GitHub** en https://github.com/settings/keys → "New SSH key".

### Cambiar el remote a SSH (mejor que HTTPS)

```bash
git remote set-url origin git@github.com:JorgeMP-3/laia-arch.git
```

## 5. Errores típicos y cómo salir

### "Your branch is ahead of 'origin/X' by N commits"

Tienes commits locales que no están en GitHub. Solución: `git push`. Si la branch es
protegida (`main`/`stable`), abre un PR en su lugar.

### "Your branch is behind 'origin/X' by N commits"

GitHub tiene commits que tu local no tiene. Solución: `git pull`. Si hay conflicto,
git te lo dice y los resuelves.

### "Please commit your changes or stash them before you switch branches"

Tienes cambios sin commitear y quieres cambiar de branch. Opciones:
- Si los cambios son buenos: `git add` + `git commit`.
- Si son WIP que no quieres perder: `git stash` (guardarlos en un "cajón" temporal). Luego
  `git stash pop` para recuperarlos.
- Si son basura: `git checkout -- <archivo>` para descartarlos (cuidado, irreversible).

### "Permission denied (publickey)" al pushear

Tu SSH key no está registrada en GitHub. Ver §4.

### Merge conflict tras `git pull` o `git merge`

Git pone marcadores `<<<<<<<` / `=======` / `>>>>>>>` en los archivos conflictivos. Tú
decides qué versión queda. Edita el archivo dejando solo el contenido correcto, borra los
marcadores, luego:

```bash
git add <archivo-resuelto>
git commit                  # si era un merge en curso
git rebase --continue       # si era un rebase
git cherry-pick --continue  # si era un cherry-pick
```

### "Detached HEAD"

Hiciste `git checkout <sha>` en vez de `git switch <branch>`. Estás fuera de cualquier
branch. Para volver: `git switch main` (o la que sea). Tus cambios sueltos: créate una
branch primero si quieres conservarlos (`git switch -c temp`).

## 6. El saneamiento del 2026-05-28 (qué pasó y por qué)

Para futuras referencias y para entender por qué el repo está como está:

**El lío**: el repositorio era un fork de Hermes Agent (Nous Research) que en algún
momento pivotó hacia LAIA-ARCH. La transición se hizo con múltiples ramas orphan
(branches creadas sin historia común con `git checkout --orphan`), lo que dejó **5
historias paralelas desconectadas** de LAIA en el mismo repo, más la `main` que seguía
siendo Hermes upstream. Tu doc decía "main = dev, stable = prod" pero la realidad era
opuesta.

**El saneamiento** (plan completo en `workflow/plans/archive/2026-05-28-github-cleanup-archive-hermes.md`):

1. Backup en `archive/*` de todo lo legado (Hermes upstream, customs antiguas, orphans).
2. Promoción de `wip/codex/dev-stable-versioning` (la rama con tags y más historia) a
   nueva `main`.
3. Reintegración via cherry-pick de los 10 commits dispersos en orphans (fixes recientes,
   doctrina, skills mattpocock).
4. Resolución de conflictos archivo a archivo.
5. Push de main unificado.
6. Archivado de las ramas obsoletas; preservación de los tags.

Resultado: una `main` única con 10 commits + 3 merges (todo el trabajo dev de Jorge +
Claude integrado), `stable` apuntando al tip pre-integración para producción, y todo el
histórico preservado en `archive/*` para consultable.

## 7. Cuándo escalar a una IA y cuándo no

**Hazlo tú** (rutinario):
- Pull diario.
- Crear una branch para una tarea, commitear, pushear, abrir PR.
- Mergear un PR ya aprobado.
- Resolver un conflicto pequeño en un archivo que conoces.

**Escala a una IA** (no rutinario o complejo):
- Conflictos en muchos archivos.
- Branches con historias divergentes (orphan).
- Necesitas cherry-pick o rebase de varios commits.
- Algo destructivo (force-push, reset --hard) que no estás seguro.
- Configuración del remote, refspec, hooks.

Las IAs en este repo siempre actúan sobre `AGENTS.md` §Git workflow (las reglas duras) y
este documento (el contexto explicado).
