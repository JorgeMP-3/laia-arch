# 🪟 Guía de la ventana de migración v1 → v2 (para Jorge)

> **Qué es esto**: el guion paso a paso para migrar el servidor de producción del layout viejo
> (**v1**, era-Hermes `v0.11.0`, secretos en `~/.laia`) al nuevo (**v2**, `/srv/laia/arch`, v0.2.0)
> **sin perder nada**, con vuelta atrás en cada paso. Pensada para seguirla **contigo al mando** y
> Claude guiando en directo.
>
> **Fuentes canónicas** (detalle técnico): runbook `estabilizacion/c3-migration-runbook.md` y PRD
> `2026-05-31-prod-cutover-v1v2-redesigned.md`. Esta guía las **consolida en cristiano**, no las
> sustituye.
>
> **Estado**: borrador listo para usar. La secuencia está validada en la VM `laia-dev`. **NO ejecutada
> en prod todavía** — es el hito que cierra v2.

---

## Antes de nada: ¿qué es "la ventana"?

Un **rato reservado** (~30-45 min) para hacer la operación delicada cuando no hay nadie usando LAIA.
Durante la ventana se reinicia `laia-agora` unos segundos. Como **aún no hay usuarios reales**, hoy el
corte no afecta a nadie — pero el procedimiento es el mismo para cuando los haya.

## Prerequisitos (verde antes de abrir la ventana)

- [x] Reboot del host hecho (kernel `7.0.0-22`).
- [x] Seguridad P0 (SSH/firewall) aplicada.
- [x] Provisioning arreglado (tooling `laiactl` + idmap de zonas de datos) — los agentes nuevos y los
      existentes ya escriben en su zona de datos.
- [ ] **Tú**: elegir el hueco y tener una **sesión Tailscale viva** (`100.98.x`) que NO cierres durante
      la ventana (es la red de seguridad si el SSH directo fallara).
- [ ] **Tú**: confirmar que no hay nadie conectado.

> Todos los comandos se ejecutan **en el host de prod** (`doyouwin-server`), como tu usuario, con `sudo`
> donde se indique. Trabaja desde `~/LAIA`.

---

## Los pasos (cada uno: qué · comando · cómo sé que fue bien · vuelta atrás)

### Paso 0 — Foto de seguridad (backup + snapshot)

**Qué**: respaldo completo + snapshot del container, por si todo se tuerce.

```bash
sudo infra/bin/laia-backup all                 # backup one-shot a /mnt/data
sudo lxc snapshot laia-agora pre-ventana-$(date +%Y%m%d)
```
> Nota: el script de migración (paso 2) **también** hace su propio snapshot+tar automáticamente. Esto es
> un cinturón extra.

**Verificación**: el backup deja ficheros no vacíos en `/mnt/data` (el `agora.db` debe pesar ~36M, no 0);
`sudo lxc info laia-agora | grep -i snapshot` muestra el snapshot recién creado.

**Vuelta atrás**: nada que revertir; es solo respaldo.

---

### Paso 1 — Ensayo en seco (no cambia nada)

**Qué**: ver el plan de migración sin ejecutarlo.

```bash
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --dry-run --yes
```

**Verificación**: imprime las fases (preflight → backup → mkdirs → sync-runtime → sync-secrets → anchors
→ swap-mount → verify) sin tocar nada. Si dice "host ya en v2 — nada que migrar", el host ya estaba
migrado (parar y avisar).

**Vuelta atrás**: no aplica (no ejecuta nada).

---

### Paso 2 — Migración real (CONSERVANDO la v1)

**Qué**: aplicar v2 de verdad, pero **sin borrar `~/.laia`** todavía (para poder revertir al instante).

```bash
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --yes --no-cleanup
```
- Mueve secretos a `/srv/laia/arch/secrets` (0600), runtime a `/srv/laia/arch`, aplica `raw.idmap`,
  **reinicia `laia-agora`** (unos segundos), y deja `~/.laia` **intacto**.
- Si una fase falla, el script hace **auto-rollback** de ese paso solo.

**Verificación**: termina con "migración OK" y un mensaje tipo *"~/.laia CONSERVADO; para retirarlo:
... --resume --yes"*.

**Vuelta atrás**: `sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --rollback` → revierte idmap, owner y
mount al estado v1 (`~/.laia` sigue ahí → recuperación instantánea).

---

### Paso 3 — Verificar que AGORA sigue sano con los secretos nuevos

**Qué**: confirmar que el backend lee el secreto v2 (no un falso-verde).

```bash
curl -s http://127.0.0.1:8088/api/health | python3 -m json.tool
```

**Verificación**: `ok: true` **y** `auth_json_ready: true`. (Ojo: `auth_json_ready` ahora valida el
contenido real del `auth.json`, no solo que el fichero exista.)

**Vuelta atrás**: si sale rojo → `--rollback` (paso 2).

> 🔴 **Punto de no-retorno suave**: hasta aquí, revertir es instantáneo (`~/.laia` intacto). No sigas al
> paso 4 hasta tener este verde.

---

### Paso 4 — Desplegar la versión nueva (v0.2.0) + layout operacional

**Qué**: dejar `/opt/laia` apuntando a v0.2.0 y crear los dirs operacionales.

```bash
sudo laia-release                      # despliega v0.2.0 desde stable
                                       # si se queja del frontend: sudo laia-release --skip-frontend
sudo bash infra/scripts/setup-prod-dirs.sh
```

**Verificación**: `/opt/laia` resuelve a la versión `v0.2.0`; `setup-prod-dirs` deja
`/srv/laia/{state,users,...}` creados sin error.

**Vuelta atrás**: `laia-rollback` apunta al `/opt/laia` anterior (era-Hermes). El estado de datos no se
toca en este paso.

---

### Paso 5 — Prueba de fuego: suite de integridad + humo e2e

**Qué**: confirmar que el ecosistema entero está sano en prod.

```bash
# Suite de integridad (6 capas) en el host:
tests/integration/run_integrity.sh --profile host

# Humo e2e de un usuario (login + chat + tool-call):
bash infra/dev/smoke-test.sh
```

**Verificación**: la suite sale `fail=0`; el smoke completa login + chat con el PA + tool-call que ejecuta
en el container del usuario + chat con LAIA coordinador.

> Para validar el camino destructivo completo (provisionar→tool-call→desprovisionar) se usan los e2e
> T3/T6 con `LAIA_E2E_ALLOW_DESTRUCTIVE=1` — esos ya están **verdes en la VM**; en prod basta el smoke
> no destructivo salvo que quieras la prueba completa.

**Vuelta atrás**: si algo falla aquí, aún puedes `--rollback` (los datos v1 siguen archivados) o
`lxc restore laia-agora pre-ventana-*`.

---

### Paso 6 — Retirar la v1 (cerrar la migración)

**Qué**: solo cuando los pasos 3-5 estén verdes y tras un rato de observación, retirar `~/.laia`.

```bash
sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --resume --yes
```
- Archiva `~/.laia` → `~/.laia.v1-migrated-<fecha>` (no lo borra). Para borrarlo del todo más adelante:
  añade `--purge-old` (solo tras confirmar el backup permanente).

**Verificación**: `~/.laia` ya no existe como tal; el sistema sigue verde (repite el paso 3).

**Vuelta atrás (ya completada la migración)**: el rollback de dispositivo se rehúsa; recupera con
`lxc restore laia-agora pre-v2-migration-<ts>` o `mv ~/.laia.v1-migrated-<fecha> ~/.laia` o el tar de
`/mnt/data/laia-migration-backups/<ts>/`.

---

### Paso 7 — Cierre

- Reconvertir `~/LAIA` del host a un checkout limpio de `stable` (el desarrollo se hace en la VM).
- Actualizar `workflow/changelog.md` con el resultado de la ventana.
- 🎉 **V2 en producción.**

---

## Vuelta atrás de un vistazo

| Momento | Cómo revertir |
|---|---|
| Pasos 1-5 (antes de retirar `~/.laia`) | `sudo bash infra/lxd/scripts/migrate-v1-to-v2.sh --rollback` → instantáneo |
| Después del paso 6 | `lxc restore laia-agora pre-v2-migration-<ts>` · o `mv ~/.laia.v1-migrated-* ~/.laia` · o el tar de `/mnt/data/laia-migration-backups/` |
| Despliegue v0.2.0 (paso 4) | `laia-rollback` (vuelve al `/opt/laia` anterior) |

## Qué hacer si algo se atasca

- **No entres en pánico ni borres nada**: hasta el paso 6, todo es reversible y `~/.laia` está intacto.
- Reintento idempotente tras un fallo a mitad: añade `--resume` (salta las fases ya hechas).
- Si dudas, **para y pregunta a Claude** antes de tocar — esto es prod-risk (un intento previo el
  2026-05-30 tuvo un outage; por eso el script se rediseñó y se validó en VM).

## Notas (arreglado en la sesión 2026-06-01, ya en `main`)

- El **alta de usuarios** vía AGORA backend ya funciona (tooling `laiactl` reconciliado al cerebro central).
- Los **agentes escriben en su zona de datos** (fix idmap `shift=true`); los 3 agentes existentes ya
  remediados. → Tras la migración, un usuario real podrá usar su agente de verdad.
- `auth.json` ya a 0600; el cutover converge al modelo file-mount de `rebuild-3` (sin el `rebuild-3b`
  que causó el outage).
