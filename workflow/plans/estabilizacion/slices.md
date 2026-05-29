# Estabilización — Vertical slices (checklist de ejecución)

> Desglose del [plan técnico](2026-05-29-estabilizacion-plan-tecnico.md) en trozos
> independientes y comprobables (tracer bullets). Orden por dependencias (A → B → C → D).
> **Tipo:** HITL = necesita decisión/revisión de Jorge · AFK = una IA lo hace y lo deja listo.
>
> El bug de los 2 tests (slice A2) vive en [`workflow/problems.md`](../../problems.md)
> (`agora-backend-test-pool-contamination`). El cierre del agujero de `auth.json` (644→0600)
> **no es un slice aparte**: se hace dentro de **C2** vía `raw.idmap` (decisión de Jorge,
> 2026-05-29 — el servidor es solo suyo, riesgo bajo, evita hacer el idmap dos veces).

Estado de cada slice: `[ ]` pendiente · `[~]` en curso · `[x]` hecho.

---

## [ ] B1 · Provisionar VM de desarrollo `laia-dev`  — HITL · prioridad

**Bloqueado por:** ninguno.

VM de **LXD** (`lxc launch --vm`) dentro del host, con LXD anidado (`security.nesting=true`),
~8 GiB RAM / 6–8 vCPU, disco en pool sobre `/mnt/data`, Tailscale unido al tailnet, repo
clonado y `laia-install` corriendo **dentro** para un LAIA fiel (laia-agora + 1 agente).
Layout idéntico a producción.

- [ ] `lxc list` muestra `laia-dev` RUNNING con nesting.
- [ ] Accesible desde el Mac por Tailscale (terminal/editor), sin IP en la LAN.
- [ ] Dentro: `laia-install` termina OK y `/api/health` responde.
- [ ] Snapshot creado y restaurado OK (prueba de "volver atrás en segundos").

## [ ] B2 · `~/LAIA` del host → checkout pristino de `stable`  — HITL

**Bloqueado por:** B1.

Tras mover el desarrollo a la VM, reconvertir el `~/LAIA` del host a un checkout limpio de
`stable` (sin branch wip ni estado sin commitear), que es lo que `laia-release` necesita.

- [ ] Todo lo pendiente commiteado/pusheado antes (cero pérdida).
- [ ] `~/LAIA` del host en `stable`, `git status` limpio.
- [ ] `laia-release` funciona desde ese checkout.

## [ ] C1 · Repuntar anclas de path a `/srv/laia/arch`  — AFK

**Bloqueado por:** B1 (se ensaya en la VM). **Módulo:** M2.

Cambiar los anclas (defaults de env) para que el runtime del ARCH lea/escriba en
`/srv/laia/arch`: `config.yaml`, `.env.paths`, `pathd`, `LAIA_STATE_ROOT` (orchestrator),
`EnvironmentFile` de systemd. Sin reescribir hardcodes (ya está parametrizado).

- [ ] `atlas doctor` resuelve a `/srv/laia/arch` sin refs rotas.
- [ ] `pathd` arranca leyendo de `/srv/laia/arch` y escribe `.env.paths`/socket ahí (owner `laia-arch`).
- [ ] Tests del path-resolver verdes en la VM.

## [ ] C2 · Mount de secretos con `raw.idmap` + `auth.json` 0600  — HITL (prod-risk)

**Bloqueado por:** B1. **Módulo:** M3 · **núcleo T1.** *(Aquí se cierra el agujero del 644.)*

`rebuild-3`/`rebuild-3b` montan los secretos desde `/srv/laia/arch/secrets` en `laia-agora`
usando `raw.idmap` (mapear el uid de `agora` al de `laia-arch`), de modo que `auth.json`
queda **0600** y el container lo lee **sin** `chmod` world-readable.

- [ ] `auth.json` en 0600 (ya no legible por otros).
- [ ] `laia-agora` lee credenciales y `/api/health` OK tras restart.
- [ ] Ensayado en la VM antes de tocar prod.

## [ ] C3 · Script de migración in-place idempotente  — AFK (build) / HITL (aplicar a prod)

**Bloqueado por:** C1, C2. **Módulo:** M6 · **T2.**

Script que migra un host del layout viejo al nuevo **in-place**: backup one-shot → crear
`/srv/laia/arch{,/secrets}` con perms → rsync datos (origen intacto hasta verificar) →
repuntar anclas → **añadir** mount nuevo + `raw.idmap` + restart `laia-agora` + verificar
health (**add-before-remove**) → en verde: borrar mount viejo + `~/.laia`. Ensayo: replicar
el estado viejo **crudo** de prod en la VM y correr ahí el script.

- [ ] Re-ejecutable sin corromper (idempotente; markers de resume).
- [ ] Rollback probado (revertir device; `~/.laia` intacto hasta verde).
- [ ] Ensayo en VM con réplica cruda: AGORA verde tras migrar.
- [ ] Aplicado a prod con backup (paso HITL, ventana de reinicio planificada).

## [ ] C4 · Instalador "nace en el layout nuevo" (install-native)  — AFK

**Bloqueado por:** C1, C2. **Módulo:** M2/M3/M4 · **T3.**

`laia-install` crea `/srv/laia/arch{,/secrets}` con perms; el flujo `laia auth` escribe en
`/srv/laia/arch/secrets`; el provision (`rebuild-3`) monta desde ahí con `raw.idmap`. Toda
instalación nueva nace ordenada — una sola configuración en todas las máquinas.

- [ ] Install limpio en la VM produce el layout nuevo (sin `~/.laia`).
- [ ] `laia auth` escribe en `/srv/laia/arch/secrets`.
- [ ] `tests/installer/` actualizados y verdes.

## [ ] D1 · Sistema de backups permanente  — AFK

**Bloqueado por:** C (sobre el layout ya definitivo). **Módulo:** M1 · **D5.**

Reutilizar `infra/bin/laia-backup`: quitar `pg_dump arete` (muerto), añadir `/srv/laia/arch`,
alcance `agora.db` + `/srv/laia/users` + `/srv/laia/arch`, destino `/mnt/data/laia-backups`
(otro disco físico), systemd timer nocturno, retención 14 días. (Off-site = paso posterior.)

- [ ] `laia-backup all` deja artefactos en `/mnt/data/laia-backups`.
- [ ] Timer nocturno activo; `clean` borra >14 días.
- [ ] Test de backup verde.

## [ ] D2 · Suite de integridad de arriba a abajo  — AFK · gate final

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
