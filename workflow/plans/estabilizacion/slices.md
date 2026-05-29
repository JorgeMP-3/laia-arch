# Estabilización — Vertical slices (checklist de ejecución)

> Desglose del [plan técnico](2026-05-29-estabilizacion-plan-tecnico.md) en trozos
> independientes y comprobables (tracer bullets). Orden por dependencias (A → B → C → D).
> **Tipo:** HITL = necesita decisión/revisión de Jorge · AFK = una IA lo hace y lo deja listo.
>
> El bug de los 2 tests (slice A2) vive en [`workflow/problems.md`](../../problems.md)
> (`agora-backend-test-pool-contamination`) — ✅ **resuelto** (PR #14, commit `9f7f7887`,
> mergeado a `main` el 2026-05-29; verificado por el Lead: RED en `main` → GREEN×2 con el fix).
> El cierre del agujero de `auth.json` (644→0600)
> **no es un slice aparte**: se hace dentro de **C2** vía `raw.idmap` (decisión de Jorge,
> 2026-05-29 — el servidor es solo suyo, riesgo bajo, evita hacer el idmap dos veces).

Estado de cada slice: `[ ]` pendiente · `[~]` en curso · `[x]` hecho.

---

## Roles de los agentes de IA (ejecución multi-agente)

> Asignación por **capacidad + riesgo de la tarea**. Coordinación según
> [`workflow/03-multi-ai-coordination.md`](../../03-multi-ai-coordination.md): cada agente en
> su branch `wip/<agente>/<slice>`, **un slice a la vez**, drafts de docs vivos a `_inbox/`,
> `changelog.md`/`problems.md` append-only.
>
> **Regla de oro multi-agente:** lo que toca **producción** lo revisa un **segundo agente
> fuerte + Jorge (HITL)** antes de mergear. Nada prod-risk se mergea con un solo par de ojos.

### Agentes, esfuerzo y si tocan código

| Agente | Modelo | Esfuerzo | ¿Escribe código? | Función |
|---|---|---|---|---|
| **Lead** (Claude Code, esta cuenta) | Opus | **`xhigh`** | **No** — dirige + revisa | Orquestador: planifica cada paso, escribe el **brief** para cada IA, **revisa TODO el código** antes de mergear, decide arquitectura. (Parche mínimo puntual solo si es más rápido que rebotarlo.) |
| **Coder-Opus** (Claude Code, cuenta 2) | Opus | **`high`** (·`xhigh` en C2/C3) | **Sí** | Escribe el código **difícil / prod-risk**. |
| **Coder-Codex** (Codex) | GPT-5.5 | **`high`** (reasoning) | **Sí** | Escribe el código **bien-especificado** (specs + criterios de aceptación). |
| **Minimax** (OpenCode) | Minimax 2.7 | su máximo disponible | **No** — read-only | Entender, **documentar** y **encontrar errores** (scouting/auditoría). Nunca toca código de producto. |

> **Regla de oro:** todo el código pasa por la **revisión del Lead** antes de mergear; lo
> prod-risk, además, por **Jorge (HITL)**. Nada se mergea con un solo par de ojos.

### Reparto del código entre los dos coders (por dificultad)

- **Coder-Opus (Claude #2)** — lo que exige razonamiento Opus mientras codea: **B1** (VM),
  **B2** (`~/LAIA`→stable), **C1** (anclas Atlas), **C2** (mount + `raw.idmap`), **C3**
  (migración in-place). `xhigh` para C2/C3 (prod-risk).
- **Coder-Codex (GPT-5.5)** — specs claros con criterios de aceptación: **A2** (tests),
  **C4** (install-native), **D1** (backups), **D2** (implementación de la integridad).

### Mapa slice → coder → revisor

| Slice | Coder | Revisa | Notas |
|---|---|---|---|
| **A2** tests | Codex | Lead | independiente, puede ir ya |
| **B1** VM | Coder-Opus | Lead + Jorge (HITL) | prioridad; habilita C |
| **B2** `~/LAIA`→stable | Coder-Opus | Lead + Jorge (HITL) | tras B1 |
| **C1** anclas Atlas | Coder-Opus | Lead | añade refs `/srv/laia/arch` a `atlas.yaml` |
| **C2** mount + idmap | Coder-Opus (`xhigh`) | Lead + Jorge (HITL) | prod-risk; cierra el 644 |
| **C3** migración in-place | Coder-Opus (`xhigh`) | Lead + Jorge (HITL) | ensaya en VM → prod con backup |
| **C4** install-native | Codex | Lead | instalador + flujo auth |
| **D1** backups | Codex | Lead | sobre layout final |
| **D2** integridad | Codex (impl) | Lead (diseña + revisa) | gate final |

### Minimax — apoyo read-only (a Jorge y al Lead)

- **Documentar** subsistemas y decisiones (docs, NO código de producto).
- **Scouting** continuo: escanear el sistema buscando errores nuevos (como hizo la auditoría).
- **Verificar** hallazgos y explicar zonas confusas. Sus docs/hallazgos los usan Lead/Jorge.

### Flujo de cada paso (cómo opera el Lead)

1. El **Lead** dice a Jorge la siguiente acción y a qué IA toca.
2. El **Lead** escribe un **brief copiable** para esa IA: rol, slice, criterios de aceptación,
   guardarraíles y branch (`wip/<agente>/<slice>`).
3. El **coder** implementa y abre PR.
4. El **Lead revisa el código**; si es prod-risk, además **Jorge (HITL)**.
5. Merge. Siguiente paso.

### Paralelismo

- **Ya, sin bloqueos:** Codex → **A2** · Coder-Opus → **B1**.
- Tras **B1**: Coder-Opus → **B2/C1/C2** (ensayando en la VM), guiado y revisado por el Lead.
- **C3/C4** tras C1+C2. **D1/D2** al final, sobre el layout ya migrado.
- **Minimax** hace scouting/docs **en cualquier momento** (no bloquea a nadie).

---

## [x] B1 · Provisionar VM de desarrollo `laia-dev`  — HITL · prioridad

**Bloqueado por:** ninguno. · **En curso** (Coder-Opus, branch `wip/claude/vm-laia-dev`, sin push aún).
**Runbook:** [`infra/dev/laia-dev-vm-runbook.md`](../../../infra/dev/laia-dev-vm-runbook.md).

VM de **LXD** (`lxc launch --vm`) dentro del host, con LXD anidado (`security.nesting=true`),
~8 GiB RAM / 6–8 vCPU, **disco en pool LXD sobre `/mnt/data` (HDD `sda`, 3.4 T libres)**,
Tailscale unido al tailnet, repo clonado y `laia-install` corriendo **dentro** para un LAIA
fiel (laia-agora + 1 agente). Layout idéntico a producción.

> **Disco — decidido (2026-05-29):** la VM va en el **HDD interno** (`/mnt/data`), **no** en el
> USB `VM-USB` (`/dev/sdb1`). Un USB para una VM viva da riesgo de desconexión→corrupción y
> desgaste de la flash por escrituras constantes. El NVMe root queda excluido (ahí vive prod).
> El USB `VM-USB` se reserva como **destino de backup removible** (off-site, paso de D5).

- [x] `lxc list` muestra `laia-dev` RUNNING con nesting (perfil `laia-dev`, 8 GiB/6 vCPU, disco `dir` en `/mnt/data`, red aislada `laiadev0` 10.123.0.x).
- [~] Accesible desde el Mac por Tailscale — pasos en el runbook; **pendiente** que Jorge autorice la URL de `tailscale up`.
- [~] Dentro: `laia-install` + `/api/health` — documentado con 3 gotchas; **pendiente marcar "verificado"** con la salida real (como §2.6 hizo con la red).
- [~] Snapshot creado y restaurado OK — snapshot `b1-base` **creado**; **falta probar el restore** (§5 del runbook = PENDIENTE).

### Hallazgos de la revisión del Lead (2026-05-29) — a cerrar antes del PR

- 🔴 **Seguridad: `auth.json` REAL de prod dentro de la VM.** El factory bootstrap exige creds
  LLM (Gotcha 3) y se copió el `auth.json` real del host (10403 B, **modo 644**, tokens OpenAI)
  a la VM; el snapshot `b1-base` (12:04) se tomó **después** (11:58) → **bakea los tokens reales**.
  La VM es el sandbox de romper cosas y no debe llevar creds de producción. **Remediar:** creds
  *throwaway*/dev en la VM → borrar `b1-base` → re-snapshot limpio. (Severidad final = decisión de Jorge.)
- 🟡 **Cambio a nivel host (UFW).** Se hizo `sudo ufw allow/route allow` para el bridge nuevo
  `laiadev0`. Aditivo y aislado (no toca `lxdbr0` de prod), riesgo bajo — registrado para conocimiento de Jorge.
- 🟡 **Disco `dir` (no zfs/btrfs).** zfs/btrfs no es viable sin root interactivo en este host;
  consecuencia: el snapshot es copia del `root.img` (sparse), no instantáneo. Decisión atribuida a
  Jorge (2026-05-29) — pendiente de confirmar por él.
- 🟢 **Hallazgo valioso (alimenta C3/C4):** UFW bloquea **todo** bridge LXD nuevo en este host
  (drop terminal en `FORWARD`/`INPUT`); un bridge nuevo necesita `ufw allow in` + `ufw route allow in`.
  → requisito incorporado en **C3** (migración) y **C4** (installer); ver más abajo.

**Pendiente para cerrar B1:** remediar el `auth.json` (creds throwaway + re-snapshot), confirmar
`laia-install`+`/api/health` verdes y marcarlo "verificado", §5 (restore del snapshot) y §6 (operación),
y Tailscale unido → entonces PR para revisión **Lead + Jorge (HITL)**.

## [ ] B2 · `~/LAIA` del host → checkout pristino de `stable`  — HITL

**Bloqueado por:** B1.

Tras mover el desarrollo a la VM, reconvertir el `~/LAIA` del host a un checkout limpio de
`stable` (sin branch wip ni estado sin commitear), que es lo que `laia-release` necesita.

- [ ] Todo lo pendiente commiteado/pusheado antes (cero pérdida).
- [ ] `~/LAIA` del host en `stable`, `git status` limpio.
- [ ] `laia-release` funciona desde ese checkout.

## [x] C1 · Repuntar anclas de path a `/srv/laia/arch`  — AFK

**Bloqueado por:** B1 (se ensaya en la VM). **Módulo:** M2.

Cambiar los anclas (defaults de env) para que el runtime del ARCH lea/escriba en
`/srv/laia/arch`: `config.yaml`, `.env.paths`, `pathd`, `LAIA_STATE_ROOT` (orchestrator),
`EnvironmentFile` de systemd. Sin reescribir hardcodes (ya está parametrizado).

- [ ] `atlas doctor` resuelve a `/srv/laia/arch` sin refs rotas.
- [ ] `pathd` arranca leyendo de `/srv/laia/arch` y escribe `.env.paths`/socket ahí (owner `laia-arch`).
- [ ] Tests del path-resolver verdes en la VM.

## [x] C2 · Mount de secretos con `raw.idmap` + `auth.json` 0600  — HITL (prod-risk)

**Bloqueado por:** B1. **Módulo:** M3 · **núcleo T1.** *(Aquí se cierra el agujero del 644.)*

`rebuild-3`/`rebuild-3b` montan los secretos desde `/srv/laia/arch/secrets` en `laia-agora`
usando `raw.idmap` (mapear el uid de `agora` al de `laia-arch`), de modo que `auth.json`
queda **0600** y el container lo lee **sin** `chmod` world-readable.

- [ ] `auth.json` en 0600 (ya no legible por otros).
- [ ] `laia-agora` lee credenciales y `/api/health` OK tras restart.
- [ ] Ensayado en la VM antes de tocar prod.

## [x] C3 · Script de migración in-place idempotente  — AFK (build) / HITL (aplicar a prod)

**Bloqueado por:** C1, C2. **Módulo:** M6 · **T2.**

Script que migra un host del layout viejo al nuevo **in-place**: backup one-shot → crear
`/srv/laia/arch{,/secrets}` con perms → rsync datos (origen intacto hasta verificar) →
repuntar anclas → **añadir** mount nuevo + `raw.idmap` + restart `laia-agora` + verificar
health (**add-before-remove**) → en verde: borrar mount viejo + `~/.laia`. Ensayo: replicar
el estado viejo **crudo** de prod en la VM y correr ahí el script.

- [ ] Re-ejecutable sin corromper (idempotente; markers de resume).
- [ ] Rollback probado (revertir device; `~/.laia` intacto hasta verde).
- [ ] Ensayo en VM con réplica cruda: AGORA verde tras migrar. (Nota B1: si el LXD anidado de
  la VM tiene UFW activo, su `lxdbr0` interno necesita las reglas `ufw allow/route allow` o el
  cerebro se queda sin red tras el restart.)
- [ ] Aplicado a prod con backup (paso HITL, ventana de reinicio planificada).

## [x] C4 · Instalador "nace en el layout nuevo" (install-native)  — AFK

**Bloqueado por:** C1, C2. **Módulo:** M2/M3/M4 · **T3.**

`laia-install` crea `/srv/laia/arch{,/secrets}` con perms; el flujo `laia auth` escribe en
`/srv/laia/arch/secrets`; el provision (`rebuild-3`) monta desde ahí con `raw.idmap`. Toda
instalación nueva nace ordenada — una sola configuración en todas las máquinas.

- [ ] Install limpio en la VM produce el layout nuevo (sin `~/.laia`).
- [ ] `laia auth` escribe en `/srv/laia/arch/secrets`.
- [ ] `tests/installer/` actualizados y verdes.
- [ ] **(B1)** Si la instalación crea un bridge LXD propio en un host con **UFW activo**,
  añade `ufw allow in on <bridge>` + `ufw route allow in on <bridge>` (o equivalente), o el
  cerebro/agentes se quedan sin DHCP/DNS/egress. Hallazgo del runbook de B1.

## [x] D1 · Sistema de backups permanente  — AFK

**Bloqueado por:** C (sobre el layout ya definitivo). **Módulo:** M1 · **D5.**

Reutilizar `infra/bin/laia-backup`: quitar `pg_dump arete` (muerto), añadir `/srv/laia/arch`,
alcance `agora.db` + `/srv/laia/users` + `/srv/laia/arch`, destino `/mnt/data/laia-backups`
(otro disco físico), systemd timer nocturno, retención 14 días. (Off-site = paso posterior.)

- [ ] `laia-backup all` deja artefactos en `/mnt/data/laia-backups`.
- [ ] Timer nocturno activo; `clean` borra >14 días.
- [ ] Test de backup verde.

## [x] D2 · Suite de integridad de arriba a abajo  — AFK · gate final

**Bloqueado por:** B1, C1, C2, C3, C4, D1. **Módulo:** M7.

Batería end-to-end en `tests/` que verifica el ecosistema completo: host → containers (LXD)
→ AGORA (`/api/health`, `agora.db` íntegra) → executor por-usuario → datos en su sitio
(modelo de 2 zonas) → Atlas (`doctor` sin refs rotas) → backups (artefactos presentes).

- [ ] La suite cubre las 6 capas y pasa en verde.
- [ ] Corre en la VM y en prod tras la migración.

---

## Resumen de dependencias

```
A2 (tests, en problems.md) ── independiente, ya
B1 (VM) ── prioridad
   └─ B2 (~/LAIA host → stable)
   └─ C1 (anclas) ─┐
   └─ C2 (mount+idmap, cierra 644) ─┤
                                    ├─ C3 (migración in-place) ── ensaya en VM → prod con backup
                                    └─ C4 (install-native)
                                          └─ D1 (backups) ── sobre layout final
                                                └─ D2 (integridad) ── gate final
```
