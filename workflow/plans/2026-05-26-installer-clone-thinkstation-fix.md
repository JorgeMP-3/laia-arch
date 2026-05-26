# Fix installer/clonador — egress preflight rompe clone en Thinkstation

- **Fecha**: 2026-05-26
- **Owner**: claude-code (con aprobación de Jorge)
- **Estado**: aprobado — en-curso

## Contexto

Jorge corrió en el Thinkstation:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
  | sudo bash -s -- --mode clone --source laia-hermes@100.73.36.92 --yes
```

La instalación cae en el paso `1.5/4 Verificar red LXD hacia internet` con:

```
▸ lanzando prueba temporal laia-egress-check-223219-initial (ubuntu:24.04, profile laia-employee, timeout 180s)
Terminated                 LAIA_ROOT="$LAIA_ROOT" bash "$script"
✗ rebuild-2-images.sh failed → tail /tmp/build-base.log /tmp/build-agora.log
```

### Diagnóstico

- `bootstrap.sh::boot_build_images` (línea 134) ejecuta
  `LAIA_ROOT=... bash rebuild-2-images.sh` en foreground.
- `rebuild-2-images.sh::ensure_lxd_egress` → `lxd_probe_egress` lanza
  `lxc launch ubuntu:24.04 -p default -p laia-employee &` con un watchdog
  de 180 s (`rebuild-2-images.sh:107-131`).
- El log se interrumpe ANTES del primer heartbeat (que se emite cada 15 s).
  La línea `Terminated  LAIA_ROOT="$LAIA_ROOT" bash "$script"` es bash
  reportando que su hijo recibió **SIGTERM externo** mientras esperaba a
  `lxc launch`.
- No aparece `Interrupted by SIG...` (de `_laia_signal_abort` en
  `common.sh:171`), por lo que el SIGTERM no llegó al laia-clone padre —
  llegó **directo** al bash hijo. Sospechosos: systemd-oomd matando el
  cgroup mientras `lxc launch` descarga ubuntu:24.04 (~300 MB), un
  reinicio de snap.lxd.daemon a mitad de descarga, o algún watchdog
  intermedio de sudo.

### Regresión

Los 4 commits de hoy introdujeron el preflight + sucesivos workarounds:

- `23e4ba5e fix(lxd): preflight container egress before image build` ← introduce el bug
- `ce121756 fix(lxd): auto-repair bridge egress preflight`
- `111d4a02 fix(lxd): timeout egress probe launch`
- `c933ab59 fix(lxd): watchdog hung egress launches`

Antes de hoy el installer funcionaba (la imagen se construía y el
`build-base-image.sh` ya hacía sus propias verificaciones de red de forma
natural durante apt-get update). El preflight intentaba dar pista
temprana, pero convirtió un fallo no-fatal en un `die` que aborta toda
la instalación, y encima depende de descargar 300 MB de imagen pública —
lo más caro y frágil de toda la operación.

### Outcome buscado

El clone Thinkstation← laia-hermes@100.73.36.92 debe completar al menos
hasta la fase de construcción de imágenes LXD. Si la red está realmente
rota, queremos que `build-base-image.sh` lo diga con un error claro;
NO queremos que un preflight cosmético tire la instalación.

## Plan

### Fase 1 — Reescribir `ensure_lxd_egress` (rebuild-2-images.sh)

**Decisión bisagra**: el preflight es informativo, no bloqueante.

1. **Check host-level (rápido, < 5 s, primario)**:
   - `ip link show lxdbr0` activo + tiene la IP esperada.
   - `iptables -t nat -L POSTROUTING` contiene MASQUERADE para `$subnet`.
   - `curl --max-time 5 -sSf https://archive.ubuntu.com -o /dev/null` (host).
   - `lxc image list ubuntu: 2>&1 | head` (control plane LXD responde).
   - Si todo pasa → `ok "egress LXD (host-level) verificado"` y `return 0`.
   - Si algún check falla → `warn` con el detalle pero **NO `die`**.

2. **Auto-repair NAT/forwarding** (igual que ahora, `lxd_apply_network_config`)
   se mantiene — útil y barato.

3. **Container probe (opt-in, deep check)**:
   - Sólo se ejecuta si `LAIA_LXD_DEEP_PROBE=1` o si el check host-level
     falló de forma "recuperable" (e.g., DNS roto pero ip route OK).
   - Captura stdout+stderr de `lxc launch` a `/tmp/laia-egress-probe.log`
     en vez de `>/dev/null 2>&1` — para que cuando falle el operador
     pueda inspeccionar.
   - Sigue siendo no-fatal: warn + continúa.

4. **El `die` final desaparece**: si todo lo anterior falló, log un mensaje
   con los diagnósticos y `return 0`. El siguiente paso (`build-base-image.sh`)
   ejecutará `lxc launch` real y si la red está rota dará error claro en
   ese momento (con stdout visible, no en /dev/null).

### Fase 2 — Mejor mensaje en `bootstrap.sh::boot_build_images`

- Si `bash $script` sale con código 143 (SIGTERM) o 137 (SIGKILL), imprimir
  hint específico: "el proceso fue terminado externamente (probablemente
  systemd-oomd o presión de memoria). Revisa `journalctl -k -n 100` y
  `journalctl -u systemd-oomd -n 50`. Re-intenta con menos carga en el
  servidor."
- Esto no es el fix raíz pero da al operador una pista accionable.

### Fase 3 — Verificación

1. **Smoke local en esta VM (laia-hermes)**:
   - Las imágenes `laia-agent`/`laia-agora` ya existen aquí → bootstrap.sh
     skip rebuild-2-images. Para probar el nuevo `ensure_lxd_egress`
     directamente: `LAIA_ROOT=/home/laia-hermes/LAIA sudo -E bash -c
     'source infra/lxd/scripts/rebuild-2-images.sh nop' ` — no, mejor:
     extraer la función a un test directo o invocarla con la imagen
     borrada temporalmente.
   - Plan B: borrar temporal de la imagen `laia-agent` y correr
     `bash infra/lxd/scripts/rebuild-2-images.sh` — pero hay riesgo de
     romper el state actual del usuario. **NO hacer sin confirmación.**
   - Plan C: ejecutar SOLO `ensure_lxd_egress` extrayéndola a un script
     temporal `/tmp/test-egress.sh` con `set +e`, y ver que (a) no hace
     `die` cuando los checks pasan, (b) emite warning y continúa cuando
     simulamos un fallo (e.g., bloqueando temporalmente lxdbr0).
   - **Plan elegido**: Plan C (sin riesgo de tocar imágenes reales).

2. **Smoke en el Thinkstation (lo que Jorge va a re-correr)**:
   - Mismo comando de arriba (`curl | sudo bash -- --mode clone ...`).
   - Esperamos: `▸ asegurando forwarding/NAT/DNS`,
     luego `✓ egress LXD (host-level) verificado` (o un `⚠` warning),
     luego pasa a `2/4 Borrar imágenes previas` y `3/4 Construir imagen
     laia-agent`.
   - Si el build de imagen también falla, **entonces** sabremos que el
     problema es de red real y no del preflight — y el error vendrá con
     stdout visible.

### Fase 4 — Documentar y cerrar

- Anotar en `workflow/changelog.md`.
- Añadir entrada en `workflow/problems.md` resuelta apuntando al commit.

## Files críticos

- `/home/laia-hermes/LAIA/infra/lxd/scripts/rebuild-2-images.sh:41-264`
  — refactor de `ensure_lxd_egress` y helpers internos.
- `/home/laia-hermes/LAIA/infra/installer/lib/bootstrap.sh:115-136`
  — añadir hint en `boot_build_images` para exits 143/137.

## Riesgos

1. **El check host-level "pasa" pero el container probe real sí fallaría**:
   Es teóricamente posible que la NAT esté rota sólo para el bridge LXD,
   no para el host. Mitigación: en ese caso `build-base-image.sh` fallará
   con error claro de apt-get inside container. El usuario sabrá que es
   red real, no el preflight.

2. **Si el SIGTERM externo era un síntoma de un problema mayor** (e.g.,
   el servidor está realmente bajo memoria), el fix lo enmascara
   temporalmente. Mitigación: la Fase 2 añade un mensaje específico para
   exits 143/137 con instrucción de revisar journalctl. El operador
   tendrá la información para diagnosticar más a fondo.

3. **`LAIA_LXD_DEEP_PROBE=1` opt-in puede no ser conocido**: si alguien
   quiere el comportamiento antiguo, podría perderlo. Mitigación: documentar
   en el banner del wizard y en el README del script.

## Verificación de aceptación

- Re-correr en Thinkstation: el comando del Contexto debe pasar de la
  sección `1.5/4` sin errores fatales (warning aceptable). Debe seguir a
  `2/4` y posteriores.
- Si el clone llega a la fase de rsync de datos, el objetivo del usuario
  ("clonar mi proyecto actual de esta VM en el servidor Thinkstation")
  está cubierto.

## Notas

- No vamos a tocar `clone.sh` ni el motor del wizard. El fix vive en
  el bootstrap LXD. Mínima superficie.
- Mantenemos `auto-repair` de iptables/sysctl porque es barato y útil
  en máquinas frescas donde nunca se ha tocado el bridge LXD.
