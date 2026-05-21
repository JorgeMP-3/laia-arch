# Plan: Sincronización profesional de LAIA con upstream Hermes Agent

## Context

LAIA es un fork de **Hermes Agent v0.11.0** (Nous Research, MIT). Desde que LAIA hizo el fork (commit `120bf10`, 2026-05-13), upstream ha publicado **tres releases mayores** (v0.12, v0.13, v0.14 — última 2026-05-16, ayer). El usuario quiere saber:

1. ¿Es rentable integrar esas actualizaciones?
2. Si lo es, cómo hacerlo **de forma profesional, aislada y rollback-friendly**, sin parar el ecosistema en funcionamiento (agente `laia-jorge` está en producción).

### Hechos clave de la divergencia

| Aspecto | Estado |
|---|---|
| Versión upstream actual | **v0.14.0** (2026-05-16) — "The Foundation Release" |
| Versión upstream del fork | v0.11.0 (2026-04-23) |
| Versiones publicadas en medio | v0.12 (Curator), v0.13 (Tenacity), v0.14 (Foundation) |
| Mantenimiento upstream | Activo (8.640 commits, release hace 1 día) |
| Estructura del fork LAIA | **NO es un fork git real**: bulk-copy con renombrado masivo. Sin remote `upstream`. `.laia-core/` vive dentro del repo monolito `JorgeMP-3/laia-private` |
| Renombrado | `hermes`→`laia`, `HERMES_HOME`→`LAIA_HOME` (1.346 referencias). 99,9% completo |
| Código LAIA-only en `.laia-core/` | `laia_paths.py` (242), `laia_state.py` (2.094), `laia_constants.py` (295), `laia_logging.py`, `laia_time.py`, `cli.py` con 518KB personalizado, `laia_cli/`, `laia-ui-server/`, plus environments LAIA |
| Cambios sin commitear actualmente | **29 ficheros modificados** (cli.py, agent/prompt_builder.py, model_tools.py, etc.) en rama `feat/agora-redesign-centralized-brain` |
| Espacio libre en disco | 22 GB |

### Cambios en upstream v0.12 → v0.14 (resumen ejecutivo)

| Categoría | Cambios |
|---|---|
| **Arquitectura** | Browser tooling refactorizado de monolítico a **provider registry pattern** (`tools/browser_providers/` reestructurado). ABC templates para providers |
| **Features** | Multi-provider browser (Browserbase + browser-use + Firecrawl), X/XAI search auto-detect, 22 plataformas mensajería, Matrix con clock-skew, Telegram con typing indicators |
| **Seguridad** | Shell hook block enforcement reforzado, validación SSH mejorada, type safety en security handlers, guard contra memory provider vacío |
| **Bug fixes** | Detección de fallback de context-length, robustez en inicialización |

---

## Veredicto sobre rentabilidad

**Sí, parcialmente rentable** — pero **NO** mediante `git merge` (es inviable por la divergencia de renombres). La vía profesional es:

- **Alto ROI** (debería portarse): security hardening (shell hook, SSH, type safety), guard memory provider vacío, fallback context-length, provider registry pattern para browser (LAIA tiene `.laia-core/tools/browser_providers/` ya).
- **ROI medio** (evaluar): multi-provider browser concretos (Browserbase/Firecrawl), X/XAI search auto-detect — útil si los agentes LXD van a navegar web.
- **ROI bajo** (probablemente saltar): 22 plataformas mensajería, Matrix, Telegram UX — LAIA usa AGORA UI propia, no necesita estos canales.

El coste: **no es un merge automático**. Cada feature requiere triage manual porque los renombres masivos y los ficheros LAIA-only (`laia_state.py` reemplaza estructuras que upstream sigue evolucionando bajo otro nombre) impiden cualquier merge ciego.

---

## Arquitectura propuesta: el modelo "vendor branch + worktree paralelo"

Este es el patrón estándar de la industria para forks con renombres divergentes (es lo que hace AWS con Linux, Sourcegraph con LSIF, etc.):

```
JorgeMP-3/laia-private (repo actual)
│
├── main / feat/agora-redesign-centralized-brain   ← producción intacta
│   └── .laia-core/   ← LAIA con sus renombres
│
├── vendor/hermes-pristine                          ← nueva rama "vendor"
│   └── .laia-core/   ← réplica pristina de upstream Hermes (sin renombrar)
│                       solo se actualiza con `git fetch upstream`
│
└── feat/upstream-sync-vX                           ← rama de trabajo
    └── .laia-core/   ← integración selectiva: cherry-pick + adaptación renombrada

Worktree separado:
/home/laia-hermes/LAIA-sync/   ← git worktree de feat/upstream-sync-vX
   → permite que el agente jorge siga corriendo en /home/laia-hermes/LAIA
     mientras se prueba la sincronización en este directorio paralelo
```

**Aislamiento garantizado por tres capas:**

1. **Git worktree**: el sync se hace en `/home/laia-hermes/LAIA-sync/`, independiente del directorio de producción.
2. **Snapshot LXD** del agente `laia-jorge` antes de tocar runtime (`laiactl snapshot laia-jorge pre-sync-v0.14`).
3. **Systemd parallel slot**: backend AGORA y gateway corren con `LAIA_HOME=/home/laia-hermes/.laia` (producción). Para validar, se levanta una instancia paralela con `LAIA_HOME=/tmp/laia-sync-home` y puertos no conflictivos (`AGORA_PORT=8089`, `GATEWAY_PORT=...+1`). Verificas y solo entonces se hace cutover.

**Rollback en < 60 segundos**: `git switch feat/agora-redesign-centralized-brain` + `laiactl restore laia-jorge pre-sync-v0.14`.

---

## Fase 1 — Análisis + infraestructura (lo que el usuario pidió primero)

Objetivo: entregar al usuario un **informe triage feature-by-feature** y dejar la infraestructura preparada para que las siguientes fases sean ejecutables sin fricción.

### 1.1 Configurar el remote upstream (read-only)

```bash
cd /home/laia-hermes/LAIA
git remote add hermes-upstream https://github.com/NousResearch/hermes-agent.git
git config remote.hermes-upstream.fetch '+refs/tags/*:refs/tags/hermes/*'
git config --add remote.hermes-upstream.fetch '+refs/heads/main:refs/remotes/hermes-upstream/main'
git fetch hermes-upstream --no-tags
git fetch hermes-upstream 'refs/tags/v0.11.0:refs/tags/hermes/v0.11.0' \
                         'refs/tags/v0.12.0:refs/tags/hermes/v0.12.0' \
                         'refs/tags/v0.13.0:refs/tags/hermes/v0.13.0' \
                         'refs/tags/v0.14.0:refs/tags/hermes/v0.14.0'
```

Tags prefijados (`hermes/v0.14.0`) evitan colisión con cualquier tag local. Remote read-only por convención: nunca se hace push.

### 1.2 Crear la rama `vendor/hermes-pristine`

Esta rama almacena el código de upstream **sin renombrar**, en una raíz aparte (`vendor/hermes/`) para no chocar con `.laia-core/`. Se usa solo como fuente de verdad para diffs y cherry-picks:

```bash
git checkout --orphan vendor/hermes-pristine
git rm -rf .  # limpiar working tree
git read-tree --prefix=vendor/hermes/ hermes/v0.14.0
git checkout -- vendor/hermes/
git commit -m "vendor: snapshot hermes-agent v0.14.0 pristine"
git push -u origin vendor/hermes-pristine
```

Resultado: rama `vendor/hermes-pristine` con un único directorio `vendor/hermes/` que contiene Hermes v0.14.0 tal cual. Cuando upstream saque v0.15.0, se actualiza esta rama con `git read-tree --prefix=vendor/hermes/ hermes/v0.15.0` y se commitea — esto produce un único commit con todo el diff entre versiones, ideal para revisar.

### 1.3 Generar el inventario triage

Crear `/home/laia-hermes/LAIA/.plans/upstream-sync/feature-matrix.md` con esta estructura, una fila por feature/cambio significativo de upstream:

| ID | Feature | Release | Ficheros upstream | Equivalente LAIA | Renombre necesario | Conflicto con LAIA-only | Valor para LAIA | Esfuerzo | Decisión |
|---|---|---|---|---|---|---|---|---|---|
| F01 | Browser provider registry pattern | v0.12 | `tools/browser_providers/registry.py` + `tools/browser_*.py` | `.laia-core/tools/browser_providers/`, `.laia-core/tools/browser_*.py` | Sí (imports) | Bajo (LAIA no tocó esta capa) | Alto | M | Pendiente |
| F02 | Browserbase provider | v0.12 | `tools/browser_providers/browserbase.py` | (no existe) | Sí | Ninguno | Medio | S | Pendiente |
| F03 | Firecrawl provider | v0.13 | `tools/browser_providers/firecrawl.py` | (no existe) | Sí | Ninguno | Medio | S | Pendiente |
| F04 | X/XAI search auto-detect | v0.13 | `agent/...` (TBD) | `.laia-core/agent/...` | Sí | Verificar | Medio | S | Pendiente |
| F05 | Shell hook block enforcement | v0.13 | `gateway/...` (TBD) | `.laia-core/gateway/...` | Sí | Verificar | Alto | S | Pendiente |
| F06 | SSH validation | v0.13 | TBD | TBD | Sí | Verificar | Alto | S | Pendiente |
| F07 | Type safety en security handlers | v0.14 | TBD | TBD | Sí | Verificar | Alto | XS | Pendiente |
| F08 | Empty memory provider guard | v0.14 | `agent/memory_*.py` | `.laia-core/agent/memory_manager.py`, `memory_provider.py` | Sí | **Alto** (LAIA bundleó workspace-context como built-in en commit b934c9b) | Alto | M | Pendiente |
| F09 | Context-length fallback detection | v0.14 | `agent/context_*.py` | `.laia-core/agent/context_engine.py`, `context_compressor.py` | Sí | Medio | Alto | S | Pendiente |
| F10 | Matrix clock-skew | v0.14 | `tools/matrix_*.py` | (LAIA no usa Matrix) | N/A | Ninguno | **Nulo** | — | **Saltar** |
| F11 | Telegram typing indicators | v0.13 | `tools/telegram_*.py` | (LAIA no usa Telegram) | N/A | Ninguno | **Nulo** | — | **Saltar** |
| F12 | 22 plataformas mensajería | v0.12-14 | varios | (irrelevante) | N/A | Ninguno | **Nulo** | — | **Saltar** |

> Esta tabla se completa ejecutando el script de inventario (siguiente paso). Estimación inicial: ~40-60 features tras desglose completo.

### 1.4 Script de inventario automatizado

Crear `/home/laia-hermes/LAIA/.plans/upstream-sync/scripts/build_feature_matrix.sh`:

```bash
#!/usr/bin/env bash
# Por cada release upstream, vuelca:
#   - commits con su shortlog y autor
#   - lista de ficheros tocados
#   - clasifica cada fichero: ¿existe en .laia-core con nombre equivalente?
#   - heatmap de conflicto: ¿ese fichero LAIA tiene cambios LAIA-only?

OUT=/home/laia-hermes/LAIA/.plans/upstream-sync
mkdir -p "$OUT/raw"

for from_to in "v0.11.0..v0.12.0" "v0.12.0..v0.13.0" "v0.13.0..v0.14.0"; do
  rel=$(echo "$from_to" | sed 's/.*\.\.//')
  git log --pretty=format:'%h %s (%an)' "hermes/$from_to" > "$OUT/raw/$rel-commits.txt"
  git diff --name-only "hermes/$from_to" > "$OUT/raw/$rel-files.txt"
  # Para cada fichero upstream, encontrar el equivalente LAIA
  while read f; do
    candidate=".laia-core/$f"
    if [ -e "$candidate" ]; then
      echo "MATCH: $f → $candidate"
    else
      echo "NEW: $f"
    fi
  done < "$OUT/raw/$rel-files.txt" > "$OUT/raw/$rel-mapping.txt"
done
```

Output: tres ficheros de mapping (uno por release) que alimentan la tabla triage manualmente (con criterio humano sobre valor/esfuerzo).

### 1.5 Comparación quirúrgica por feature

Cuando un feature está en la triage tabla y se quiere evaluar a fondo, se usa este patrón:

```bash
# Ver el diff exacto de upstream para una feature
git log hermes/v0.13.0..hermes/v0.14.0 -- agent/memory_manager.py
git show <commit> -- agent/memory_manager.py

# Comparar con el archivo LAIA equivalente
diff <(git show hermes/v0.14.0:agent/memory_manager.py) \
     .laia-core/agent/memory_manager.py
```

### 1.6 Entregable de la Fase 1

Un único informe en `/home/laia-hermes/LAIA/.plans/upstream-sync/TRIAGE_REPORT.md` con:

1. Tabla matriz completa (todas las features de v0.12→v0.14).
2. **Recomendaciones** por feature (portar / saltar / decidir más tarde) con justificación de una línea.
3. Estimación total de esfuerzo si se acepta la recomendación.
4. Lista de **riesgos altos identificados** (conflictos con LAIA-only, breaking changes en LAIA APIs).
5. Apéndice: comandos exactos preparados para Fase 2 (cherry-pick / patch / port manual) para cada feature aceptada.

**Decisión del usuario aquí.** Marca columna "Decisión" (Portar/Saltar/Aplazar) en la tabla. Solo entonces se procede a Fase 2.

---

## Fase 2 — Protocolo de integración por feature (referencia, no se ejecuta aún)

Una vez el usuario apruebe features concretas en la Fase 1, cada una sigue este protocolo. Documentado aquí para que el plan sea completo:

### 2.1 Setup del worktree paralelo (una sola vez)

```bash
cd /home/laia-hermes/LAIA
git checkout -b feat/upstream-sync-v0.14 feat/agora-redesign-centralized-brain
git worktree add /home/laia-hermes/LAIA-sync feat/upstream-sync-v0.14
```

Resultado: `/home/laia-hermes/LAIA-sync/` es un working tree independiente. El agente `laia-jorge` y AGORA siguen ejecutando contra `/home/laia-hermes/LAIA/` sin enterarse.

### 2.2 Snapshot pre-cambio

```bash
# Snapshot del agente en producción
laiactl snapshot laia-jorge pre-sync-v0.14
# Snapshot de la config de runtime
cp -a /home/laia-hermes/.laia /home/laia-hermes/.laia.pre-sync-v0.14
```

### 2.3 Por cada feature aprobada — un commit atómico

```bash
cd /home/laia-hermes/LAIA-sync
# Caso A: fichero nuevo (no toca código LAIA)
git checkout hermes/v0.14.0 -- tools/browser_providers/firecrawl.py
mv tools/browser_providers/firecrawl.py .laia-core/tools/browser_providers/
# aplicar renombres hermes→laia con script
.plans/upstream-sync/scripts/rename_hermes_to_laia.sh \
    .laia-core/tools/browser_providers/firecrawl.py
git add .laia-core/tools/browser_providers/firecrawl.py
git commit -m "feat(browser): port Firecrawl provider from hermes v0.13"

# Caso B: modificación a fichero existente
# 1. Generar parche desde upstream
git format-patch -1 <commit_upstream> --stdout -- agent/memory_manager.py > /tmp/p.patch
# 2. Editar paths y renombres en el .patch
sed -i 's|^--- a/agent/|--- a/.laia-core/agent/|; s|^+++ b/agent/|+++ b/.laia-core/agent/|' /tmp/p.patch
sed -i 's/HERMES_HOME/LAIA_HOME/g; s/hermes/laia/g' /tmp/p.patch
# 3. Aplicar con 3-way merge (deja conflictos marcados si los hay)
git apply --3way /tmp/p.patch
# 4. Resolver conflictos manualmente, ejecutar tests, commit
```

Convención de commit: `port(hermes-vX.Y): <descripción> [F0N]` donde F0N referencia el ID de la matriz triage.

### 2.4 Validación en paralelo (la clave del aislamiento)

Antes de mergear, se levanta una instancia paralela:

```bash
# Backend AGORA paralelo en :8089
export LAIA_HOME=/tmp/laia-sync-home
export LAIA_ROOT=/home/laia-hermes/LAIA-sync
export AGORA_PORT=8089
cd /home/laia-hermes/LAIA-sync/services/agora-backend
./scripts/run-dev.sh

# En otra shell, validaciones:
curl localhost:8089/api/health         # debe responder
pytest .laia-core/tests/ -x            # tests del core
pytest services/agora-backend/tests/   # 69 tests del backend
```

Producción en `:8088` sigue intacta. Solo cuando todo pasa en `:8089` se hace cutover.

### 2.5 Cutover

```bash
# Mergear la rama en producción
cd /home/laia-hermes/LAIA
git switch feat/agora-redesign-centralized-brain
git merge --no-ff feat/upstream-sync-v0.14
# Reiniciar servicios
sudo systemctl restart laia-agora-backend laia-gateway laia-ui-server
# Verificar
laiactl status laia-jorge
curl localhost:8088/api/health
```

### 2.6 Rollback (si algo falla post-cutover)

```bash
git revert -m 1 <merge_commit_sha>
sudo systemctl restart laia-agora-backend laia-gateway
laiactl restore laia-jorge pre-sync-v0.14
cp -a /home/laia-hermes/.laia.pre-sync-v0.14/* /home/laia-hermes/.laia/
```

---

## Ficheros críticos involucrados

| Ruta | Razón |
|---|---|
| `/home/laia-hermes/LAIA/.laia-core/agent/memory_manager.py`, `memory_provider.py` | Punto caliente: LAIA bundleó workspace-context como built-in (commit b934c9b). Cualquier port de memoria upstream necesita reconciliación. |
| `/home/laia-hermes/LAIA/.laia-core/agent/context_engine.py`, `context_compressor.py` | Probable conflicto con context-length fallback de v0.14 |
| `/home/laia-hermes/LAIA/.laia-core/tools/browser_providers/` | Capa que upstream refactorizó completa en v0.12. LAIA tiene esta carpeta — verificar si está sin tocar |
| `/home/laia-hermes/LAIA/.laia-core/cli.py` | 518KB con customizaciones LAIA. Riesgo alto de conflicto. Probablemente NO portar cambios de upstream a este fichero salvo bugs críticos |
| `/home/laia-hermes/LAIA/.laia-core/gateway/` | Hooks de seguridad (shell block enforcement) viven aquí |
| `/home/laia-hermes/LAIA/.laia-core/laia_state.py` | 2.094 líneas LAIA-only. Ignorar upstream para este fichero |
| `/home/laia-hermes/LAIA/.laia-core/laia_paths.py` | Path Registry LAIA, sin equivalente upstream. Ignorar |

## Utilidades existentes a reutilizar

- `laiactl snapshot/restore` — ya implementado en `infra/laiactl` (Agente 1). Lo usamos para snapshots LXD pre-sync.
- Tests del backend AGORA (69 tests, mencionados en CHANGELOG 2.0.0 §Backend) — se ejecutan en el slot paralelo.
- `conftest.py` ya configura env vars antes del import (commit `0285a3e`) — compatible con la validación paralela.
- `infra/scripts/backup-state.sh` (Agente 6) — backup adicional antes de cutover.

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Conflicto en `memory_manager.py` rompe workspace-context bundleado | Alta | Alto | F08 marcado como "decisión cuidadosa" en triage. Tests dedicados antes de cutover |
| Provider registry de browser rompe el plugin `workspace-context` o las skills LAIA | Media | Medio | Validar en worktree con suite completa de skills antes de mergear |
| 29 ficheros modificados sin commitear se pierden al crear worktree | Alta | Medio | **Antes de todo**, hacer commit o stash de los cambios actuales en `feat/agora-redesign-centralized-brain` |
| Cambios en `cli.py` upstream chocan con personalización LAIA | Alta | Alto | Política: no portar cambios upstream a `cli.py` excepto fixes de seguridad puntuales |
| Renombres incompletos en patches portados causan ImportError | Media | Alto | Script `rename_hermes_to_laia.sh` ejecutado siempre + `python -c "import laia_..."` smoke test |
| Agente `laia-jorge` afectado por cambios de runtime | Baja | Crítico | Snapshot LXD pre-cambio. Servicio `laia-runtime` dentro del contenedor solo se actualiza tras validación |

---

## Verificación end-to-end

Una vez ejecutada la Fase 1 (análisis), la validación es trivial:

```bash
# 1. Upstream remote configurado
cd /home/laia-hermes/LAIA && git remote -v | grep hermes-upstream
git tag | grep ^hermes/   # debe listar hermes/v0.11.0..v0.14.0

# 2. Rama vendor existe
git branch -a | grep vendor/hermes-pristine
git show vendor/hermes-pristine:vendor/hermes/agent/memory_provider.py | head -5

# 3. Informe triage generado
ls /home/laia-hermes/LAIA/.plans/upstream-sync/
cat /home/laia-hermes/LAIA/.plans/upstream-sync/TRIAGE_REPORT.md | head -50
```

Cuando empiece la Fase 2 (port real), la validación incluye:

```bash
# Por cada port:
cd /home/laia-hermes/LAIA-sync
pytest .laia-core/tests/ -x
pytest services/agora-backend/tests/ -x
# Backend paralelo respondiendo:
curl http://localhost:8089/api/health
# Agente runtime smoke test (en LXD aislado de test, no en jorge):
laiactl provision-agent laia-synctest && laiactl verify laia-synctest
```

---

## Resumen de decisiones para el usuario

Este plan **no toca código LAIA todavía**. La Fase 1 entrega:
- Remote upstream configurado (lectura).
- Rama `vendor/hermes-pristine` con código pristino de v0.14.0.
- Informe triage con recomendación feature-por-feature.

Solo cuando apruebes el informe se procede a la Fase 2 (port real) con el modelo worktree + parallel runtime + snapshots descrito.

**Tiempo estimado Fase 1**: 3-5 horas de análisis + redacción del informe.
**Tiempo estimado Fase 2** (depende de tu decisión sobre cuántas features portar): rango 1 día (solo seguridad crítica) a 2 semanas (todo lo aplicable).
