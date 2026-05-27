# Atlas / Migración — Plan por Fases del Trabajo Restante

**Fecha:** 2026-05-27
**Base:** `atlas-audit-report-2026-05-27.md` (108 ocurrencias) + verificación en disco 2026-05-27.

## Lectura honesta del estado

El audit cuenta **ocurrencias**, no **bugs accionables**. Tras verificar en disco:

- **Herramienta Atlas: COMPLETA y estable** (versionada, auto-sanación `init`/`doctor --fix`/`repair_hint`,
  scanner `consumers`, consumo resiliente, 68 tests). Es el *vehículo* para arreglar el resto.
- **`laia-hermes` en código ejecutable: RESUELTO.** Las 29 ocurrencias restantes son fixtures de
  tests (rewrite cross-user), ejemplos en comentarios o comentarios legacy → **no son bugs**.
- **Adopción real de Atlas: 0** fuera del puente `scripts/_laia_runtime_paths.py`. Aquí está el grueso.
- Quedan **críticos funcionales autónomos** (no dependen de Atlas) y **deuda estructural de infra**.

El nº de bugs reales es muy inferior a 108. Lo accionable se agrupa abajo por fases ordenadas
por **riesgo↑ / dependencia**. Cada fase es independiente; elige el orden.

---

## FASE 0 — Críticos funcionales autónomos (no necesitan Atlas)

Bugs que rompen arranque/funcionalidad y se arreglan solos, sin tocar el modelo de refs.

| # | Problema | Archivos | Acción |
|---|---|---|---|
| 0.1 | Import `laia_paths` sin try/except → tumba el daemon si `.laia-core` no está en path | `infra/pathd/server.py:27`, `notifier.py:19`, `cli.py:17` | Envolver en try/except con fallback claro |
| 0.2 | Identidad legacy en context engine | `scripts/_doc_context_engine.py:789-790` (`HERMES_AGENT_ROOT/PYTHON`), `:833` (`familiamp`) | Renombrar a rutas `laia`/Atlas; eliminar `familiamp` |
| 0.3 | `ai.hermes.gateway` (launchctl macOS) en código vivo | `scripts/workspace-switch.py:250`, `create-workspace.py:266,420,635` | Parametrizar el label del gateway (env/const) |
| 0.4 | `.laia-core/venv` ausente → `bin/laia` no arranca el agente CLI | `bin/laia` espera `.laia-core/venv/bin/{laia,python}` | **Diagnóstico primero**: ¿es esperado en dev? ¿se crea en install? Decidir crear venv o ajustar `bin/laia` |

**Riesgo:** bajo (cambios locales, con tests). **Dependencia:** ninguna.
**Nota 0.4:** requiere decisión tuya — puede ser intencional en dev (el agente corre en contenedor).

---

## FASE 1 — Adopción de Atlas: capa de servicios (rutas)

Reemplazar coordenadas físicas por `atlas.get()` donde es seguro (defaults env-configurables ya existen).
El scanner `atlas consumers` lista los candidatos.

| Grupo | Ejemplos (audit) | Estrategia |
|---|---|---|
| Rutas `/opt/laia/...` y `/srv/laia/...` en agora-backend | `admin.py`, `main.py`, `storage.py`, `orchestrator.py`, `config.py` | Añadir refs a `atlas.yaml`; consumir vía `atlas.get_path()` con el default actual como fallback |
| Rutas en laia-executor | `services/laia-executor/src/config.py`, `tools/*` | Igual; mantener defaults `/etc/laia`, `/var/lib/laia` |

**Riesgo:** medio (toca backend; algunas rutas son *internas del contenedor* y NO deben cambiar —
solo centralizar las que el host resuelve). **Dependencia:** Atlas (listo).
**Importante:** rutas dentro del contenedor (`/opt/laia/runtime/...` que solo existen en el LXD) NO
se migran a refs del host — se documentan como "container-internal", fuera del scope de Atlas-host.

---

## FASE 2 — Adopción de Atlas: puertos y endpoints

| Grupo | Ejemplos | Estrategia |
|---|---|---|
| Puerto AGORA `:8088` | `start.sh:6`, `Makefile`, `infra/dev/*`, `admin.py:427,430` (`:9091`) | Leer de `atlas.get("agora_api")` / env; un único origen |
| URLs healthcheck agente `:9090/:9091` | `infra/orchestrator/lxd.py:370,465` | Ref `executor_api` |

**NO migrar:** `nginx/*.conf` (proxy_pass necesita literal), systemd units (`Environment=`),
profiles LXD — esos consumen el valor en build/deploy, no en runtime Python. Para ellos: generar
el valor desde Atlas en el instalador (`atlas get` → render), no `atlas.get()` en caliente.

**Riesgo:** medio. **Dependencia:** Atlas + Fase 1 (mismo patrón).

---

## FASE 3 — Adopción de Atlas: contenedores LXD

~156 líneas con `laia-agora`/`laia-employee`/`laia-agent` hardcodeados.

**Matiz crítico:** el nombre del contenedor en `lxc launch`/`create` es un **valor de creación**,
no una coordenada a resolver en caliente. Atlas debe ser la **fuente** que esos scripts leen al
arrancar (vía `atlas get agora_container`), no algo que reemplace el literal en cada `lxc exec`.

| Grupo | Ejemplos | Estrategia |
|---|---|---|
| Scripts de build/rebuild de imágenes | `infra/lxd/image-build/*`, `infra/lxd/scripts/rebuild-*` | Cabecera `CONTAINER="$(atlas get agora_container)"` y usar la variable |
| Orquestador Python | `infra/orchestrator/config.py:30-34`, `lxd.py` | Refs Atlas para image/profile/network/pool |
| Instalador | `infra/installer/lib/{clone,bootstrap}.sh` | Leer de Atlas en vez de literal |

**Riesgo:** alto (toca aprovisionamiento; un error rompe el deploy de contenedores).
**Dependencia:** Atlas + validación en VM/entorno de prueba antes de tocar producción.

---

## FASE 4 — Configuración central de env vars

~42 `AGORA_*` + varias `LAIA_*` operan solo con defaults en código; sin punto único.

| Acción | Detalle |
|---|---|
| Crear `.env` canónico documentado | Plantilla versionada con TODAS las `AGORA_*`/`LAIA_*` y su default |
| Resolver las **sin default** (riesgo real) | `AGORA_ADMIN_HOST_AUTH_JSON`, `AGORA_ARCH_AUTH_JSON`, `AGORA_ADMIN_HOST_LAIA_DIR` (posible typo `AGORAA_`) |
| Inconsistencia de nombres | `AGORA_TELEGRAM_TOKEN` vs `TELEGRAM_BOT_TOKEN` en `.env` |

**Límite de scope (tu visión):** Atlas **NO** es gestor de secretos. Este `.env` vive aparte;
Atlas solo declara *dónde* está (`env_file` ref `agora_env`, ya existe) y verifica sus keys.
**Riesgo:** bajo-medio. **Dependencia:** ninguna (paralela a todo).

---

## FASE 5 — Deuda estructural de infraestructura

| # | Problema | Decisión requerida |
|---|---|---|
| 5.1 | `/opt/laia/{current,versions,data}` (layout §8.1) no existe — volcado plano del repo | ¿Adoptar layout versionado o ajustar la spec a la realidad dev? |
| 5.2 | Runtime de ARCH en `~/.laia` y `LAIA-ARCH/` en vez de `/srv/laia/arch/` (§8.2/8.4) | ¿Migrar runtime o actualizar la spec? |

**Riesgo:** alto (mueve datos vivos). **Dependencia:** decisión de arquitectura tuya.
Probablemente la spec (`LAIA_ECOSYSTEM.md`) deba reconciliarse con dev, no al revés.

---

## FASE 6 — Limpieza cosmética / legacy (baja prioridad)

- Comentarios con `laia-hermes` en `infra/lxd/scripts/*` y `infra/scripts/backup-state.sh`.
- `scripts/hermes-backup.py`, `scripts/check-hardcoded-paths.py` (auto-contradictorio), `show-injected.py:158`.
- Tabla/tags "Hermes" en `workspace_store/__init__.py` (código vivo, revisar si es dato o etiqueta).

**NO TOCAR (no son bugs):** fixtures `tests/installer/*`, `tests/wizard/*` que usan `laia-hermes`
a propósito para probar el rewrite cross-user; ejemplo en `install.sh:14`.

**Riesgo:** mínimo. **Dependencia:** ninguna.

---

## Recomendación de orden

1. **Fase 0** (críticos autónomos, rápido, alto valor, bajo riesgo) — empezar aquí.
2. **Fase 4** en paralelo (env central, desbloquea diagnósticos).
3. **Fase 1 → 2** (adopción servicios + puertos, mismo patrón, valida el modelo Atlas en uso real).
4. **Fase 5** (decisión de arquitectura — conviene resolverla antes de Fase 3).
5. **Fase 3** (contenedores, alto riesgo, requiere entorno de prueba).
6. **Fase 6** (cosmético, cuando convenga).

Cada fase: rama/commit propio, tests verdes, y `atlas consumers` antes/después para medir adopción.
```
