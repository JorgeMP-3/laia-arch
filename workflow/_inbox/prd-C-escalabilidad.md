# PRD (draft) — Track C · Escalabilidad (empresa de 10)

- **Fecha**: 2026-05-30
- **Owner**: Jorge (aprueba) · Coder-Opus (implementa, prod-risk) · Lead (diseña + revisa)
- **Estado**: draft (pendiente OK de Jorge)
- **Track**: C · **Agente**: Coder-Opus
- **Inputs de Jorge (2026-05-30)**: empresa de **10 personas**; cada usuario desarrolla en **su
  contenedor LXC** (es root), crea **plugins para su propio agente**, en sus áreas de trabajo.
  El modelo ya está documentado en `LAIA_ECOSYSTEM.md` (§①③, Marketplace, executor root).

## Contexto

El modelo multiusuario (1 PA-AGORA por usuario, container privado donde es root, plugins vía
Marketplace) **ya está diseñado y documentado** — esto NO lo rediseña. Lo que falta es
**endurecerlo para 10 usuarios concurrentes reales** sin que se pisen ni agoten el host.

**Techo real del P720 (medido 2026-05-30):**
- **RAM = 30 GiB → es el recurso que ata.** 10× `laia-employee` (2 GB) = 20 GB + `laia-agora`
  (3 GB) + host ≈ **al límite**. CPU (40 vCPU) y disco (398 G libres) sobran.
- Profiles ya existen con límites base: `laia-employee.yaml` (2 vCPU / 2 GB),
  `laia-agora.yaml` (2 vCPU / 3 GB).
- ⚠️ **Pool LXD = driver `dir` → NO soporta cuotas de disco** (`root.size` no se puede forzar).
  Un usuario podría llenar el NVMe y tumbar a todos.

## Objetivo

Que 10 empleados desarrollen y creen plugins en paralelo **sin que uno pueda agotar RAM/disco
del host ni afectar a otro**, y que provisionar/desprovisionar sea idempotente y limpio.

**Estrategia central de RAM — idle-eviction (decisión de Jorge, 2026-05-30):** en vez de reservar
2 GB fijos por usuario (10×2 = al límite de 30 GiB), **cargar el agente cuando se usa y liberar su
RAM cuando el usuario lleva mucho rato inactivo**. Como casi nunca están los 10 activos a la vez,
esto permite **overcommit seguro** → caben 10+ usuarios holgados. Dos niveles: (a) evictar sesiones
ociosas del **pool de AIAgent en `laia-agora`** (libera RAM del cerebro); (b) **congelar/parar**
(`lxc freeze`/`stop`) los contenedores per-usuario ociosos y re-despertarlos on-demand.

## No-objetivos

- Escalado horizontal / 2ª máquina (eso sería el escenario "50+", no elegido).
- Rediseñar el modelo de containers o el Marketplace (ya documentado).

## Slices (orden por dependencia)

- **C1 · Auditoría de capacidad + comportamiento idle** (read-only). Medir footprint real (RAM/disco)
  de `laia-agora` y de un agente/usuario; **¿el pool de AIAgent ya evicta sesiones ociosas?** (si
  sí, tunear su timeout; si no, hay que construirlo). Definir el presupuesto que cabe en 30 GiB con
  idle-eviction. Entregable: tabla de capacidad + diagnóstico del idle actual.
- **C2 · Idle-eviction** *(núcleo)*. Implementar/afinar la liberación de RAM en ocioso: (a) evictar
  sesiones ociosas del pool en `laia-agora` tras timeout; (b) `lxc freeze`/`stop` de contenedores
  per-usuario ociosos + wake-on-demand al volver el usuario. Sin pérdida de estado del usuario.
- **C3 · Cuotas/límites de seguridad** *(prod-risk)*. `limits.memory.enforce=hard` en todos los
  profiles + `limits.cpu.allowance`, para que un pico no OOM-ee el host. **Disco:** sin cuota dura
  (pool `dir` no la soporta) → **vigilar uso** y avisar en el dashboard de PRD-B (decisión: NO migrar
  el pool ahora, ver abajo). Que un usuario no pueda tumbar a otro.
- **C4 · Robustez de provisioning.** Crear/destruir N contenedores idempotente y limpio; aislar el
  flujo de "crear plugin" dentro del container del usuario; sin fugas de estado entre usuarios.
- **C5 · Smoke de carga.** Test que levanta ~10 agentes, los deja ociosos y verifica que **la RAM se
  libera** (idle-eviction funciona) y que al re-despertar siguen verdes; sin OOM. Extiende D2.

## Criterios de aceptación

- C1: footprint medido + nº de usuarios que caben con idle-eviction; diagnóstico del idle actual.
- C2: un agente ocioso N min libera su RAM (medido antes/después); al volver el usuario, re-despierta
  sin perder su estado/workspace.
- C3: un usuario no puede OOM-ear el host (enforce hard verificado); el uso de disco se ve en el dashboard.
- C4: provisionar/destruir 10 veces deja el host limpio (idempotente).
- C5: 10 agentes → ociosos → RAM liberada → re-despiertan verdes. Ensayado **en la VM** antes de prod.

## Riesgos / decisiones

- ✅ **RAM (resuelto):** idle-eviction + overcommit (decisión de Jorge). Es la estrategia central (C2).
- ✅ **Disco (recomendación del Lead, Jorge defirió):** **NO migrar el pool a btrfs/lvm ahora** —
  migrar containers de un prod vivo añade riesgo a cambio de poco (398 G libres, 11% usado). En su
  lugar: **vigilar uso de disco + alerta en el dashboard de PRD-B**; reevaluar la migración solo si
  el disco se vuelve un problema real. *(Objeta si prefieres cuota dura desde ya.)*
- 🟡 **Estado en freeze/stop:** congelar/parar un container per-usuario debe preservar su workspace y
  reanudar limpio — C2 debe probar el ciclo idle→wake sin pérdida.
