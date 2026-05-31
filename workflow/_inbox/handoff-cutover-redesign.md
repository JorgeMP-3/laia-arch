# Handoff — Rediseño + re-test del cutover de prod v1→v2

> **Para:** la IA (otra cuenta de Claude Code) que ejecuta el rediseño del cutover.
> **De:** Claude Opus 4.8 (rol Lead), sesión 2026-05-31. **Autoriza:** Jorge.
> **Estado:** briefing operativo. Léelo entero + los artefactos que referencia antes de actuar.

---

## 0. Antes de nada (orden de lectura)

1. `CLAUDE.md` (raíz) — reglas operativas de las IAs de LAIA. **Obligatorio.**
2. `LAIA_ECOSYSTEM.md` — qué es LAIA. Canónico. **Obligatorio.**
3. Este briefing.
4. Artefactos que **NO** repito aquí (léelos por path):
   - PRD del cutover (fallido, referencia histórica): `workflow/_inbox/prd-LEAD-prod-cutover-v1v2.md`
   - Post-mortem del outage: `workflow/changelog.md` (entrada 2026-05-30; commit `97c5c6c3`)
   - Bug abierto: `workflow/problems.md` → `## migrate-v1-to-v2-prod-outage (open)`
   - Runbook + ensayo en VM: `workflow/plans/estabilizacion/c3-migration-runbook.md`
   - Script a arreglar: `infra/lxd/scripts/migrate-v1-to-v2.sh` (449 líneas)
   - Sub-script que invoca: `infra/lxd/scripts/rebuild-3b-fix-authjson.sh`

## 1. Misión y alcance

**Misión:** dejar el cutover v1→v2 **re-ejecutable con seguridad**, arreglando los 4 bugs + el
auto-rollback, **validado contra una réplica FIEL del prod real** (no una sintética).

**EN ALCANCE (esto es lo que haces, todo AFK-safe en la VM):**
- **Step 1** — construir una réplica fiel del prod v1 en la VM `laia-dev` y una línea base verde.
- **Step 2** — reproducir el fallo y arreglar los 4 bugs *test-first*; empaquetar el ciclo como
  test de regresión.

**FUERA DE ALCANCE (NO lo hagas):**
- ❌ **Re-ejecutar `migrate-v1-to-v2.sh` en PROD.** Prohibido hasta que Jorge abra una ventana HITL
  *después* de que esto pase. El cutover real es un paso supervisado por Jorge, no AFK.
- ❌ Tocar/mutar el container `laia-agora` de prod, sus datos, o `/srv/laia/*` del host (salvo
  **lectura**). Todo el trabajo destructivo ocurre **dentro de la VM `laia-dev`**.
- ❌ Borrar el snapshot `pre-v2-migration-20260530T182010Z` (es oro — ver §3).

## 2. Prerrequisito de entorno

Esto **requiere correr en el host LAIA (el ThinkStation)** con acceso a `lxc` (sin sudo: el user
está en el grupo lxd) y a la VM `laia-dev` (LXD anidado, Tailscale). Si tu cuenta **no** tiene ese
acceso, **párate y avisa a Jorge** — sin la VM no puedes hacer Step 1.

## 3. Estado REAL de prod (descubierto 2026-05-31 — esto es lo que no está escrito en otro sitio)

> ⚠️ **Re-verifícalo tú mismo** antes de actuar (puede haber drift). Comandos read-only:
> `lxc config show laia-agora`, `lxc config device show laia-agora`, `lxc info laia-agora`.

**Container `laia-agora` (prod, RUNNING):**
- **`raw.idmap`: NO está puesto.** Usa el idmap por defecto (`volatile.idmap.current` con
  Hostid 1000000, Nsid 0, range 1e9). El uid `agora` (999 dentro) mapea a `1000999` en el host.
- **2 devices** (¡no hay device de secretos!):
  - `agora-api` — proxy `tcp:0.0.0.0:8088` → `tcp:127.0.0.1:8000`.
  - `agora-data` — disk, `source=/srv/laia/agora` → `path=/opt/agora/data`.
- **El backend lee `auth.json` de `/opt/agora/data/auth.json`** = host **`/srv/laia/agora/auth.json`**
  (dentro del propio mount de datos). **NO** lo lee de `~/.laia` ni de un device aparte.
- Hay **1 snapshot: `pre-v2-migration-20260530T182010Z`** → foto del prod v1 justo antes del
  intento fallido. **Es la réplica fiel para Step 1; cópiala, no la borres.**

> ⚠️ **Snapshot vs prod-vivo-hoy:** el snapshot es el v1 *limpio* pre-incidente (ideal para el
> banco de pruebas). El prod **vivo de hoy** está en un estado *recuperado a mano* que difiere algo
> (el post-mortem dejó `auth.json` como **copia** en `/srv/laia/agora`, no bind-mount — riesgo de
> drift anotado en `workflow/security.md`). Para Step 1 usa el snapshot. Pero cuando Jorge abra la
> ventana real (fuera de alcance), el cutover debe re-baselinarse contra el prod **vivo** de ese
> momento, no contra el snapshot.

**Host (lado v1, ahora mismo):**
- `/srv/laia/agora` → `owner=UNKNOWN:UNKNOWN mode=700`. El uid/gid real (confirmado por el
  post-mortem) es **`1000999:1000988`** = el agora user del container (999:988) shifteado por el
  idmap por defecto. Es el valor que el auto-rollback DEBE preservar (grabó `0:0` → bug #3).
  Re-confírmalo en vivo: `stat -c %u:%g /srv/laia/agora`.
- `~/.laia` → `laia-arch:laia-arch mode=755` (layout v1, presente).
- `/srv/laia/arch/secrets` → existe, `laia-arch:laia-arch mode=700` (creado por un intento previo).
- `/opt/agora/data` → no existe en el host (es la ruta *dentro* del container vía el mount).

**VM `laia-dev`:** install limpio v0.2.0 (layout v2), D2 verde (9/0). Tiene su propio snapshot.
Es donde montas la réplica y ensayas.

## 4. Por qué falló (el delta synthetic-vs-real, mapeado a los 4 bugs)

El ensayo de C3 se validó contra una réplica **sintética** (runbook §4: device `arch-laia` desde
`~/.laia` 0755 + `auth.json` 644, `/srv/laia/agora` con owner del default-map). **El prod real no
es así** → los 4 bugs son exactamente ese delta:

| Bug | Causa concreta (con el estado real) |
|---|---|
| **#2 swap no surte efecto** | `rebuild-3b` añade device `arch-laia`→`/var/lib/laia-host` + `AGORA_ARCH_AUTH_JSON`, pero el backend era-Hermes (v0.11.0) lee `/opt/agora/data/auth.json` y **ignora** el device nuevo. |
| **#3 auto-rollback graba owner 0:0** | `record_rollback_state` (`migrate...sh:129`) hace `stat /srv/laia/agora`; el script asume un owner que no es el real (uid shifteado) → rollback deja el dir inaccesible al agora user → restart falla. **Un rollback que rompe es lo peor.** |
| **#1 borra el mountpoint auth.json** | al quitar/recrear el device de auth, el path `auth.json` (que vive *dentro* de `agora-data`) se ve afectado. |
| **#4 bind anidado frágil** | montar un fichero dentro de un mount idmapped no es fiable (ARM/LXD). |

**Causa raíz de fondo:** se testeó contra un install fresco, no contra la **migración de un
container EXISTENTE en marcha**. Step 1 corrige justo eso.

## 5. Step 1 — réplica fiel en la VM (recomendado)

1. `lxc export laia-agora/pre-v2-migration-20260530T182010Z` → tarball.
2. Importarlo en la VM `laia-dev` como container de pruebas.
3. **Recrear el lado-host del bind-mount:** el export trae el rootfs pero **no** `/srv/laia/agora`
   (es externo). Lleva una copia de ese árbol a la VM (contiene `agora.db` + `auth.json`) y re-añade
   el device `agora-data` apuntando ahí.
4. **Línea base verde:** arrancar → `/api/health` `ok:true` + `auth_json_ready:true`. Confirma que la
   réplica es fiel **antes** de migrar. (Si no da verde, la réplica no sirve — arréglala primero.)
5. Banco listo: `migrate --dry-run` → `migrate` (debe **reproducir el fallo = RED**) → diagnóstico →
   fix → **GREEN** → `--rollback` → verde de nuevo.

## 6. Step 2 — arreglar los 4 bugs (test-first, por gravedad)

1. **Auto-rollback (#3)** primero — captura el owner **real** del data dir (numérico, leído en
   vivo), nunca asumido. Un rollback debe dejar el sistema *exactamente* como estaba.
2. **Auth-path (#2)** — que la migración apunte/escriba donde el backend **realmente** lee
   (`/opt/agora/data/auth.json` dentro del mount), no a un device que ignora. Decidir si el modelo
   v2 (secretos 0600 + raw.idmap) es compatible con cómo lee este backend, o si hay que tocar también
   el backend / la forma de servir auth.
3. **Mountpoint (#1)** y **bind anidado (#4)** — replantear el swap para no destruir el `auth.json`
   vivo ni depender de un file-mount anidado frágil.
4. Empaquetar **baseline verde → migrate → verify → rollback → verde** como **test de regresión**
   en `~/LAIA/tests/` (alimenta Track T; ver `workflow/_inbox/prd-T-regression-suite.md`).

## 7. Guardarraíles específicos de esta tarea

- **NUNCA** `migrate-v1-to-v2.sh` contra prod. Todo en la VM.
- Sobre prod: **solo lectura** (`lxc config show/device show/info`, `stat`, `find`). Nada que mute.
- **No borres** el snapshot `pre-v2-migration-20260530T182010Z`.
- Branch `wip/claude/<slug>` (p.ej. `wip/claude/cutover-redesign`). Nunca commit directo a `main`.
  Conventional Commits. Corre la suite antes de declarar "hecho".
- Secretos: si copias `auth.json` real a la VM sacas tokens OAuth de prod → **preferible un
  `auth.json` dummy** (forma correcta + 0600); la migración no necesita tokens válidos. Si tocas
  credenciales/permisos/red, anótalo en `workflow/security.md`.
- Al cerrar: actualiza `workflow/changelog.md`, y la entrada `migrate-v1-to-v2-prod-outage` de
  `workflow/problems.md` con el progreso. Cuando el PRD del cutover deje de ser "fallido", reescríbelo
  (vía `to-prd`) y muévelo de `_inbox/` a `plans/`.

## 8. Decisiones recomendadas (confírmalas con Jorge si dudas; en la VM son AFK-safe)

| Decisión | Recomendación del Lead | Por qué |
|---|---|---|
| Dónde corre la réplica | **VM `laia-dev`** | Aislada; ensayar un script que muta layout pegado a prod es el riesgo que nos quemó. |
| Cómo se construye | **Desde el snapshot real** | La lección entera: testear contra lo real, no sintético. |
| Datos/secretos | **`auth.json` dummy** + copia de `agora.db` | No sacar tokens OAuth reales a la VM; la migración no los necesita. |
| Alcance de la réplica | Solo `laia-agora` | La migración no toca los `agent-*`. |

## 9. Suggested skills (en orden)

- **`grill-with-docs`** o **`grill-me`** — interroga este plan con Jorge ANTES de tocar la VM
  (sobre todo las 3 decisiones de §8 y el modelo de auth de §6.2). FASE 1.
- **`diagnose`** — para los 4 bugs: reproducir → causa raíz → fix → test. FASE 4.
- **`tdd`** — el ciclo red-green del Step 2 y el test de regresión. FASE 3.
- **`to-prd`** — reescribir el PRD del cutover una vez rediseñado y sacarlo de `_inbox/`.
- **`handoff`** — al cerrar tu turno.

## 10. Estado git al entregar (sesión 2026-05-31)

- Branch `wip/claude/tracker-hygiene` (commit `374f5aaa`, **sin pushear**): cerró 2 entradas stale
  de `problems.md` (shell_rc + cron, ya estaban resueltas en git; eran inexactitudes del tracker).
  No bloquea nada; Jorge decide si pushear/mergear.
- `main`: limpio salvo `skills/.curator_state` + `.usage.json` (estado auto-generado, no commitear)
  y 5 drafts en `workflow/_inbox/` (incluido este y los PRDs B/C/D/T pendientes de OK de Jorge).
- Step 0 del plan (commits de shell_rc/cron) resultó **ya hecho** — el tracker estaba desactualizado.
