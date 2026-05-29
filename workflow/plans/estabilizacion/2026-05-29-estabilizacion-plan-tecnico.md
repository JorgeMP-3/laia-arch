# Plan técnico: Estabilización de LAIA-ARCH + Entorno de Desarrollo (VM)

- **Fecha**: 2026-05-29
- **Owner**: claude-code (autor) · Jorge (aprueba cambios materiales y docs canónicos)
- **Estado**: draft (pendiente de OK de Jorge para desglose en slices → `to-issues`)
- **Idea/estrategia origen**: [`estabilizacion-estrategia.md`](estabilizacion-estrategia.md)
- **Estado verificado del servidor**: [`estado-ecosistema-servidor.md`](estado-ecosistema-servidor.md)
- **Inventario de problemas**: [`auditoria-profunda-ecosistema.md`](auditoria-profunda-ecosistema.md)

> Este plan **convierte la idea en pasos técnicos**. Las decisiones de diseño se cerraron
> en un grill con Jorge (FASE 1). No reinventa la arquitectura: `LAIA_ECOSYSTEM.md` es
> canónico — **salvo en un punto donde Jorge consintió explícitamente evolucionarlo** (la
> eliminación de `~/.laia`, vía draft en `_inbox/` que él aprueba; ver Bloque C).

---

## Problem Statement

Desde la perspectiva de Jorge (operador y único dev de LAIA-ARCH):

- **Una sola máquina (ThinkStation P720) hace producción y desarrollo a la vez.** Un
  experimento puede rozar lo que da servicio. No hay un host limpio donde probar el
  instalador o una migración de forma fiel.
- **Los datos del agente están desordenados respecto a la spec**, y hay **secretos en el
  home** (`~/.laia/auth.json` en modo `644` con tokens reales de OpenAI) — superficie de
  exposición accidental en la carpeta donde operan a diario Jorge y sus herramientas.
- **No hay sistema de backups** (solo `.bak` viejos de `agora.db` en el mismo NVMe).
- **Cabos sueltos**: refs de Atlas rotas, un duplicado (`bin/atlas.py`), 2 tests que fallan,
  y `~/LAIA` del host arrastrando estado de desarrollo sin commitear.

Nada es grave por separado; juntos hacen el sistema frágil de evolucionar justo cuando se
va hacia **usuarios reales**.

## Solution

Cuatro bloques, con un orden que prioriza no romper producción y construye el "tejado"
(backups + integridad) **al final, sobre el layout ya definitivo**:

- **Bloque A — Orden y seguridad en el host (prod-real, ya):** cerrar el agujero de
  `auth.json` (`chmod 600`), diagnosticar los 2 tests, limpiar cruft trivial y commitear los
  docs de plan. **No** se monta aún el sistema de backups ni se tocan los artefactos de
  cohabitación dev/prod.
- **Bloque B — El taller (prioridad):** una **VM de LXD** dentro del host, con layout
  **idéntico a producción**, accesible por Tailscale desde el Mac, donde se prueban install,
  release y clone de forma fiel. Tras montarla, `~/LAIA` del host se reconvierte a checkout
  pristino de `stable`.
- **Bloque C — Casa del agente (ensayado en B, con backup one-shot):** migrar el estado
  **operacional** del ARCH a `/srv/laia/arch`, **eliminar `~/.laia`** consolidando secretos
  en `/srv/laia/arch/secrets/`, y dejar `LAIA_ECOSYSTEM.md` + docs alineados (vía draft).
- **Bloque D — Cierre, sobre el layout definitivo (último):** montar el **sistema de backups
  permanente** (ya conoce las rutas finales) y una **suite de integridad de arriba a abajo**
  en `tests/`. Se hace al final a propósito: configurar backups antes de fijar el layout sería
  "empezar por el tejado" (decisión de Jorge).

### Bucle de desarrollo y release (transporte = git, NO copiar carpetas)

```
VM:   editas ~/LAIA (main / feature) → laia-install·clone·release EN la VM → test ✓
      → git push (main)
              │
              ▼  promoción por git (no copia de carpetas)
Host: git switch stable → git merge --ff-only main → git tag vX.Y.Z
      → git pull → sudo laia-release        (ver release-flow.md)
```

- En la VM, `~/LAIA` es el **único sitio editable**; `/opt/laia` + containers son *output* de
  `laia-install`/`laia-release`. La VM tiene su **propio `/srv/laia` sintético**.
- A prod **no viaja la carpeta**, viajan los **commits/tags** por git. En el host,
  `laia-release` despliega **código** en `/opt/laia`; los **datos reales** (`/srv/laia`) se
  quedan. Regla: cada máquina su propio `/srv/laia`.

---

## Decisiones cerradas en el grill (referencia rápida)

| # | Decisión |
|---|---|
| **D1** | Migrar el estado **operacional** del ARCH a `/srv/laia/arch`; lo **interactivo** se queda en `~/LAIA-ARCH`. Eje = **volatilidad + sensibilidad**. `SOUL.md` → home (Jorge); `sandboxes/` → `/srv/laia/arch` (efímero). |
| **D2** | **`~/.laia/` desaparece.** Secretos (`auth.json`, `.env`) → `/srv/laia/arch/secrets/` (`0700`, files `0600`). El resto (`atlas.yaml`, `config.yaml`, `.env.paths`, `state/`) → `/srv/laia/arch`. `chmod 600` de `auth.json` **primero y siempre**. |
| **D3** | Taller = **VM de LXD** (`lxc launch --vm`), no libvirt. Un solo hipervisor + snapshots nativos. |
| **D4** | VM **mínima viable**: agora + 1 agente, **~8 GiB RAM / 6–8 vCPU**, disco en `/mnt/data`, nesting on. Escalable luego. |
| **D5** *(revisado)* | Backups = **Bloque D (último)**, no A: el sistema permanente se configura sobre el layout **ya definitivo** (*"no empezar por el tejado"*, Jorge). Reutiliza `infra/bin/laia-backup` (fuera `pg_dump arete`), alcance `agora.db` + `/srv/laia/users` + `/srv/laia/arch`, destino `/mnt/data/laia-backups`, cron nocturno, retención 14d. La migración de C se protege con un **backup one-shot** previo. Off-site = paso siguiente. |
| **D6** *(revisado)* | Orden: **A** (prod-real ya) → **B** (VM) → limpieza de cohabitación con B → **C** (migración, ensayada en B, con backup one-shot) → **D** (backups permanentes + integridad, sobre el layout final). |
| **D7** | `agent-verify-bob/carol` → **se quedan** por ahora. Draft `release-flow.md` → **aplicar**. Cruft → limpiar. Commitear docs de plan + PR. |
| **Layout VM** | **Idéntico a producción** (no carpeta única). Comodidad de dev = *repo único para editar* (`~/LAIA`) + *Atlas symlink farm* (`~/LAIA-ARCH/atlas/`) para navegar. |
| **`~/LAIA` host** | Tras la VM, **checkout pristino de `stable`** (solo para `laia-release`, que lo necesita). No se borra; se le quita el rol de dev. |

### Modelo de datos final del ARCH (2 zonas + cofre)

| Zona | Permisos | Contenido |
|---|---|---|
| `~/LAIA-ARCH/` | home `0700` | `workspaces`, `memories`, `skills`, `plugins`, `SOUL.md` |
| `/srv/laia/arch/` | `laia-arch:laia-arch 0750` · viaja en `laia-clone` | `state.db`, `response_store.db`, `sessions`, `atlas.yaml`, `config.yaml`, `.env.paths`, `cron`, `logs`, `orchestrator-runs`, `migration`, `platforms`, `whatsapp`, `sandboxes`, `state/`, `pathd.sock` |
| `/srv/laia/arch/secrets/` | `0700` · files `0600` | `auth.json`, `.env` |
| `~/.laia/` | — | ❌ **eliminado** |
| *efímeros* | — | `pathd.sock`, `auth.lock` → recreados por el daemon en la ubicación declarada |

### Decisiones técnicas del grill (2026-05-29) — T1/T2/T3

> Refinan M3/M6 y amplían el alcance del Bloque C tras explorar el código del bind-mount y del instalador.

- **T1 — Lectura de secretos por `laia-agora` (núcleo de M3).** El `644` de `auth.json` de hoy
  es un **hack deliberado** (`rebuild-3`/`rebuild-3b`) para que el container *unprivileged*
  lea el fichero por el bind-mount sin `raw.idmap`. v2 lo cierra de verdad con **`raw.idmap`
  shift**: se mapea el uid del usuario `agora` del container al uid de `laia-arch` (dueño de
  los secretos), de modo que el mount lee un `auth.json` **0600** sin `chmod` world-readable.
  Propiedad: `/srv/laia/arch` = `laia-arch:laia-arch`, `secrets/` `0700`. *(Los secretos NO
  pueden ser root-only: `laia`/`laia auth` corren como `laia-arch` sin sudo.)*
- **T2 — Migración en prod = script in-place idempotente (refina M6).** `laia-clone` se usa
  **solo para ensayar en la VM** (reconstruye containers; pensado para hosts nuevos). En
  PROD, un script in-place: backup one-shot → crear `/srv/laia/arch{,/secrets}` con perms →
  rsync datos (origen intacto hasta verificar) → repuntar anclas (`config.yaml`/`.env.paths`
  + `pathd` reload) → **añadir** device de mount nuevo + `raw.idmap` + restart `laia-agora` +
  verificar health (**add-before-remove**) → en verde: borrar mount viejo + `~/.laia`.
  Rollback en cualquier paso = revertir device + restart; `~/.laia` sigue intacto.
- **T3 — v2 install-native (amplía M2/M3/M4).** `laia-install` crea `/srv/laia/arch{,/secrets}`;
  el flujo `laia auth` (`infra/dev/laia-init.sh`, factory) escribe en `/srv/laia/arch/secrets`;
  `rebuild-3` monta desde ahí con `raw.idmap`. **Toda instalación/clone nace en v2** → una sola
  config en todas las máquinas. Touch-points extra: `infra/installer/lib/factory.sh` y el flujo
  de auth, además de los ya listados.

**Detalles de ingeniería (especificados, no son forks):**
- **Ensayo fiel en la VM:** replicar el estado v1 **crudo** de prod en la VM (rsync tal cual,
  *no* el clone que normaliza) y correr ahí el script in-place → ejercita la operación exacta.
- **`pathd`:** socket + `.env.paths` + `state/` en `/srv/laia/arch/` (owner `laia-arch`, escribe sin sudo).
- **Ventana de reinicio de `laia-agora`** planificada (el `raw.idmap` + swap de mount exige restart; segundos).

### Lentes del grill (cobertura)

- **Canónico (regla ⑦):** la VM es un host más; su `.laia-core` (ARCH) + el de `laia-agora` son legítimos; los agentes no llevan `.laia-core`. ✅
- **Separación ⑤/⑥:** el mount de secretos en `laia-agora` es read-only y ARCH es el único escritor (ya ocurre hoy). ✅
- **Muerte/estado:** T2 (add-before-remove, idempotente, rollback). ✅
- **Escalabilidad/deuda:** T3 (sin deuda de migrar máquina a máquina). ✅

---

## User Stories

**Bloque A — orden y seguridad**

1. Como operador, quiero que `auth.json` deje de ser legible por otros (`644→600`), para no exponer tokens reales.
2. Como dev, quiero que la suite de tests pase entera (los 2 del coordinador hoy fallan), para declarar "hecho" con confianza.
3. Como dev, quiero que `bin/atlas.py` (duplicado), `atlas.yaml.bak*` y `.curator_state` (ruido) desaparezcan, para no confundir versiones.
4. Como dev, quiero los docs de plan **commiteados y en un PR**, para no perder el trabajo de planificación.

**Bloque B — el taller (VM)**

5. Como dev, quiero una VM de desarrollo **dentro del host**, para construir y romper sin tocar producción.
6. Como dev, quiero que la VM tenga **su propio `/srv/laia`**, para que un experimento de datos no contamine los reales.
7. Como dev, quiero conectarme **desde el Mac por Tailscale** (solo terminal/editor), sin VM en el Mac ni IP en la LAN.
8. Como dev, quiero **snapshots de la VM** para volver atrás en segundos.
9. Como dev, quiero que dentro de la VM corra una **instalación fiel** (LXD anidado: `laia-agora` + 1 agente), para probar `laia-install` como un cliente.
10. Como dev, quiero desarrollar en `~/LAIA` de la VM y probar con **`laia-install`/`laia-release` en la propia VM**, para ver el comportamiento de producción antes de soltar la versión.
11. Como dev, quiero hacer un **`laia-clone` real prod→VM**, para validar la migración de punta a punta antes de tocar prod.
12. Como dev, quiero **layout idéntico a prod** en la VM, para no introducir bugs "funciona-en-dev-rompe-en-prod" ni reorganizar luego.
13. Como dev, quiero navegar el ecosistema disperso desde **una sola carpeta** (Atlas symlink farm), sin colapsar el layout físico.
14. Como operador, quiero llevar una versión validada a prod **por git** (`merge main→stable` + `laia-release` en el host), **no copiando carpetas**, para tener versionado, revisión y rollback.
15. Como operador, quiero que tras la VM, `~/LAIA` del host quede como **checkout pristino de `stable`**, para que `laia-release` siga funcionando sin que el repo de dev "moleste".

**Bloque C — casa del agente**

16. Como operador, quiero el **estado operacional** del ARCH (`state.db`, `sessions`…) en `/srv/laia/arch`, donde el código ya lo espera, para que `laia-clone` lo migre bien.
17. Como operador, quiero que el contenido que **curo a mano** (`workspaces`, `skills`, `SOUL.md`) se quede en `~/LAIA-ARCH`.
18. Como operador, quiero que **`~/.laia` desaparezca** y los secretos vivan en `/srv/laia/arch/secrets/` (root-owned), para reducir el radio de exposición accidental en mi home.
19. Como operador, quiero que la migración se **ensaye antes en la VM** y se haga **con backup one-shot**, para no arriesgar producción.
20. Como operador, quiero que la migración sea **idempotente y resumible**, para reintentarla sin corromper estado.
21. Como dev, quiero que `laia-agora` siga leyendo sus credenciales tras mover los secretos, para que el cerebro no se quede sin auth.
22. Como operador, quiero que `LAIA_ECOSYSTEM.md §8` + docs derivados reflejen el nuevo layout, **aprobando yo el cambio antes de aplicarlo**.
23. Como dev, quiero que `bin/atlas` y `atlas doctor` resuelvan a las **nuevas ubicaciones** sin refs rotas.

**Bloque D — cierre (último)**

24. Como operador, quiero el sistema de backups **configurado sobre el layout final** (`/srv/laia/arch`, secrets), para no reconfigurarlo dos veces.
25. Como operador, quiero que los backups corran solos cada noche a **otro disco físico** y se limpien tras 14 días, para no depender de acordarme.
26. Como operador, quiero una **suite de integridad de arriba a abajo** en `tests/` que se corra al terminar, para tener garantía de que todo el ecosistema quedó sano antes de usuarios reales.

## Implementation Decisions

> Convención LAIA: este plan **sí** nombra archivos y paths (es infra; los paths son el
> entregable). Se mantiene el guardarraíl de no editar `LAIA_ECOSYSTEM.md` ni docs vivos
> grandes sin pasar por draft en `_inbox/`.

### Módulos (deep modules, testables en aislamiento) — por bloque

**Bloque B**
- **M5 · Provisión de la VM (`infra/dev/` nuevo runbook/script)** — crea la VM LXD
  (`lxc launch --vm`, `security.nesting=true`, disco en pool sobre `/mnt/data`, ~8 GiB/6–8
  vCPU), instala Tailscale, clona el repo y corre `laia-install`. Reutiliza los scripts de
  install; no reinventa. Incluye el paso de reconvertir `~/LAIA` del host a checkout `stable`.

**Bloque C**
- **M2 · Relocalización de anclas de path** — el resolutor (pathd + `config.yaml` `paths:` +
  Atlas) ya es deep module **parametrizado por env** (`LAIA_HOME`, `LAIA_STATE_ROOT`,
  `LAIA_ARCH_CREDS_DIR_OVERRIDE`, `AUTH_JSON_HOST`…). La migración **repunta las anclas**, no
  reescribe hardcodes. Toca: `config.yaml` → `/srv/laia/arch/config.yaml`;
  `install-systemd-units.sh` (`EnvironmentFile`); `infra/orchestrator/config.py`
  (`LAIA_STATE_ROOT` → `/srv/laia/arch/state`).
- **M3 · Credenciales del cerebro (bind-mount LXD)** — `rebuild-3-provision-agora.sh` y
  `rebuild-3b-fix-authjson.sh`: fuente del mount `~/.laia` → `/srv/laia/arch/secrets`. **El de
  mayor riesgo** (ver Riesgos).
- **M4 · Contrato de clone (`infra/installer/lib/clone.sh`)** — ya implementa el split.
  Cambios: `clone_dest_arch_creds_dir()` → `/srv/laia/arch/secrets`; `SOUL.md` del set
  legacy-file al **interactivo** (D1); confirmar `sandboxes` operacional;
  `rewrite_config_paths.py` alineado al nuevo destino.
- **M6 · Migración operacional (reutiliza `laia-clone --source-dir`)** — **no es código
  nuevo**: `laia-clone` local ya parte los datos según el modelo. Se ensaya en la VM y se
  aplica en prod. Markers `.clone-state` → idempotencia/resume. El **backup one-shot** previo
  (tar/rsync de `/srv/laia` + `~/.laia` + `~/LAIA-ARCH` a `/mnt/data`, o `lxc snapshot` en la
  VM) es parte del runbook de C — **no** el sistema permanente.

**Bloque D (último)**
- **M1 · Sistema de backups permanente (`infra/bin/laia-backup`)** — interfaz simple y
  estable (`laia-backup <qué>`). Cambios: eliminar `backup_db()` (`pg_dump arete`, muerto);
  añadir `backup_arch()` (`/srv/laia/arch`); confirmar `backup_users()`/`backup_agora()`;
  default `LAIA_BACKUP_DIR=/mnt/data/laia-backups`; retención `clean N`; systemd timer (o
  cron) nocturno. **Se configura sobre el layout YA definitivo** (post-C).
- **M7 · Suite de integridad de arriba a abajo (`tests/`)** — batería end-to-end que verifica
  el ecosistema completo: host → containers (LXD) → AGORA (`/api/health`, agora.db íntegra) →
  executor por-usuario → datos en su sitio (modelo de 2 zonas) → Atlas (`doctor` sin refs
  rotas) → backups (artefactos presentes). Prior art: `tests/installer/`, `integrity-tests.md`
  (runner por capas, owner codex). Es el **gate final**.

### Decisiones arquitectónicas

- **Layout de la VM = idéntico a prod.** Colapsar a carpeta única rompería la fidelidad de
  install/clone/bind-mounts/idmaps (la razón de existir de la VM). Ergonomía vía: repo único
  editable (`~/LAIA`) + Atlas symlink farm (`~/LAIA-ARCH/atlas/`) para navegar.
- **Transporte VM→host = git, no copia de carpetas.** El repo (remoto `JorgeMP-3/laia-arch`)
  es la fuente de verdad; se promueve `main→stable` con `--ff-only` + tag, y el host hace
  `laia-release` desde su checkout `stable`. Despliega **código**; los **datos** de prod se
  quedan.
- **Backups y tests de integridad al final** (Bloque D), sobre el layout definitivo —
  *"no empezar por el tejado"*. La migración de C se protege con backup one-shot, no con el
  sistema permanente.
- **Evolución del canon (consentida).** Eliminar `~/.laia` contradice `LAIA_ECOSYSTEM.md §8`.
  Jorge consintió evolucionarlo **vía draft en `_inbox/`** que aprueba antes de aplicar. Docs:
  `LAIA_ECOSYSTEM.md §8`, `arch-layout.md §2.4`, `arch-data-layout.md`, `project-map.md`,
  `security.md`, `infra/docs/PATH_RESOLVER.md`.
- **Permisos `/srv` vs `laia-pathd`.** `/srv/laia` root-owned; pathd corre como `laia-arch`.
  Diseñar grupo/subdir escribible (registro, `.env.paths`, `state/`, socket reachable) en la
  slice de C; no bloqueante.

### Inventario de touch-points de `~/.laia` (verificado)

`infra/lxd/scripts/rebuild-3-provision-agora.sh`, `rebuild-3b-fix-authjson.sh`,
`infra/orchestrator/config.py`, `infra/scripts/backup-state.sh`, `infra/dev/preflight.sh`,
`infra/lxd/scripts/rebuild-4-first-user.sh`, `infra/dev/chat-with-deployed.sh`,
`infra/scripts/install-systemd-units.sh`, `infra/dev/smoke-test.sh`, `infra/dev/ctl/client.py`,
`infra/installer/lib/clone.sh` (`clone_dest_arch_creds_dir`), `infra/docs/PATH_RESOLVER.md`.
La mayoría usa `~/.laia` como **default de variable de entorno** → repuntar el ancla cubre el grueso.

## Testing Decisions

- **Qué es un buen test aquí:** verifica **comportamiento externo observable**, no detalles
  internos. Para infra: "tras X, el servicio responde / el artefacto existe / el path
  resuelve", no "se llamó a la función Y".
- **Tests fallando (Bloque A):** diagnosticar `test_laia_coordinator.py` (`mode` kwarg
  inesperado en `_capture()`); hipótesis = drift de firma de fixture / versión de
  `pytest-asyncio`. Reproducir → causa raíz → fix → verde. FASE 4 (`diagnose`).
- **M4 (clone):** extender `tests/installer/test_clone_*.sh` (override mode) para el nuevo
  `clone_dest_arch_creds_dir` y `SOUL.md` interactivo. Prior art: `test_clone_local.sh`,
  `test_clone_phase_h.sh`, `test_clone_config_rewrite.py`.
- **M5/M6 (VM):** runbook de smoke (prior art `2026-05-25-installer-vm-smoke.md`):
  `laia-install` OK, `/api/health` responde, `laia-clone --source-dir` prod→VM reconstruye con
  `agora.db` íntegra (`clone_phase_h_verify`).
- **M1 (backup, Bloque D):** test que corre `laia-backup all` con `LAIA_BACKUP_DIR` a tmp y
  asserta artefactos esperados + que `clean N` borra lo viejo. Prior art: bash en `tests/installer/`.
- **M7 (integridad):** la propia suite end-to-end es el entregable de test del cierre.
- **Regla LAIA:** toda integración nueva → su test en `~/LAIA/tests/`; la **suite completa**
  pasa antes de declarar "hecho".

## Verificación (por bloque)

- **A:** `stat -c %a ~/.laia/auth.json` = `600`; `make test` verde (2 tests arreglados); cruft
  ausente; PR de docs de plan abierto.
- **B:** `lxc list` muestra la VM RUNNING con nesting; `tailscale status` la ve desde el Mac;
  en la VM `laia-install`/`laia-release` + `/api/health` OK; `laia-clone` prod→VM verde;
  `~/LAIA` del host en `stable` limpio (`git status` clean; branch = `stable`).
- **C (primero en VM, luego prod con backup one-shot):** `~/.laia` no existe; secretos en
  `/srv/laia/arch/secrets/` (`0600`); `laia-agora` `/api/health` OK (credenciales nuevas);
  `atlas doctor` sin refs a `~/.laia`; `state.db`/`sessions` en `/srv/laia/arch`;
  `workspaces`/`SOUL.md` en `~/LAIA-ARCH`; suite verde; canon/docs con draft aprobado.
- **D:** `laia-backup all` deja artefactos en `/mnt/data/laia-backups` + timer activo +
  retención; **suite de integridad de arriba a abajo en verde**.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **Mover secretos rompe el bind-mount → AGORA sin auth (prod down).** | Ensayar **en la VM** (M3 end-to-end); aplicar en prod **con backup one-shot** y en **lockstep**; rollback = restaurar `~/.laia` desde backup + revertir mount. |
| **Editar el canon sin consentimiento.** | Draft en `_inbox/`; **no se aplica** hasta OK explícito de Jorge. |
| **Ventana sin backups programados hasta el Bloque D.** | Cada paso arriesgado (C) lleva backup one-shot + `lxc snapshot`; el sistema permanente llega justo después en D. Aceptado por decisión de orden ("no empezar por el tejado"). |
| **VM consume RAM de prod (límite real).** | ~8 GiB (cabe en ~21 libres); disco en `/mnt/data`; `verify-bob/carol` quedan (margen suficiente; retirarlos es palanca extra). |
| **Permisos `/srv` root vs pathd `laia-arch`.** | Diseñar grupo/subdir escribible; socket reachable; cubierto por smoke. |
| **Migración a medias = estado corrupto.** | `laia-clone` idempotente con markers `.clone-state` + verify de `agora.db`; correr con backup one-shot. |
| **Perder docs de plan sin commitear de `~/LAIA`.** | Commit + push **antes** de reconvertir `~/LAIA` a `stable`. |
| **Confundir "promover a prod" con copiar carpetas.** | Transporte = git (`merge --ff-only` + tag + `laia-release`); documentado en release-flow. |

## Out of Scope

- Off-site / 3-2-1 backups (paso siguiente tras D).
- Reorganizar `/opt/laia` (layout plano) y borrar `laia-v0.0.0-clone` (futuro).
- Encender integraciones de mensajería apagadas (gateway, whatsapp, feishu, bluebubbles).
- Mover secretos a una ubicación distinta de la decidida (`/srv/laia/arch/secrets`).
- UI nueva de LAIA-AGORA y LAIA OS (roadmap `LAIA_ECOSYSTEM.md §9`).
- Retirar `agent-verify-bob/carol` (D7: se quedan por ahora).

## Further Notes

- **Secuenciación (grafo de dependencias):**
  ```
  A-seguridad (chmod auth.json) ─┐
  A-tests (diagnose) ────────────┤── (en paralelo, ya)
  A-cruft + commit/PR docs ──────┘
              │
              ▼
  B (VM: M5) ── prioridad
     ├─ dev loop: editar ~/LAIA → laia-install/release EN la VM → test → git push
     ├─ limpieza de cohabitación (refs Atlas dev, etc.)
     └─ ~/LAIA host → checkout stable
              │
              ▼
  C (M2+M3+M4+M6) ── ensayado en B → prod, con backup one-shot previo
     └─ draft canon → OK Jorge → aplicar
              │
              ▼
  D (M1 backups permanentes + M7 integridad) ── sobre el layout YA definitivo
  ```
- **Por qué A no toca los artefactos de cohabitación ahora:** refs de Atlas a
  `agent-jorge-dev`, `workspaces/` vacíos, etc. son **síntomas** de dev+prod compartiendo
  host; se resuelven al separar con B.
- **Siguiente paso de proceso:** con el OK de Jorge, desglosar en vertical slices con
  `to-issues` (una slice por bloque/módulo, mergeables en el orden del grafo), registrando
  estado en `workflow/problems.md`.
