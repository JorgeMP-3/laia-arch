# Runbook — Provisión de la VM de desarrollo `laia-dev` (slice B1)

> **Qué es esto:** los pasos EXACTOS para crear el "taller" de LAIA: una VM de LXD
> **dentro del host de producción** (`doyouwin-server`), con layout idéntico a prod, donde
> se ensaya `laia-install` / `laia-release` / `laia-clone` sin tocar lo que da servicio.
>
> Corresponde al **slice B1** de [`workflow/plans/estabilizacion/slices.md`](../../workflow/plans/estabilizacion/slices.md)
> y al módulo **M5** del [plan técnico](../../workflow/plans/estabilizacion/2026-05-29-estabilizacion-plan-tecnico.md).
> La migración del Bloque C (C3) se apoya en este documento.
>
> **Autor:** Coder-Opus (Claude Code) · **Fecha:** 2026-05-29 · **Host:** `doyouwin-server`
> **Revisión:** Lead + Jorge (HITL).

---

## 0. Decisiones de diseño (cerradas, no reabrir)

| # | Decisión | Por qué |
|---|---|---|
| VM | LXD `lxc launch --vm` (no libvirt) | un solo hipervisor + snapshots nativos |
| Recursos | **8 GiB RAM / 6 vCPU** | cabe en los ~21 GiB libres; CPU no es el límite |
| Disco | pool **`dir` sobre `/mnt/data`** (HDD, 3.4 T libres) | NO en el NVMe root (ahí vive prod); ext4 no hace CoW |
| Red | bridge **aislado `laiadev0`** (10.123.0.1/24, NAT) | aísla la VM del subnet de prod (10.99.0.0/24) |
| Nesting | `security.nesting=true` | dentro corre LXD anidado: `laia-agora` + 1 agente |
| Acceso | **Tailscale** (desde el Mac, sin IP en la LAN) | — |
| Layout interno | **idéntico a producción** | fidelidad install/clone/bind-mounts/idmaps |

> **Sobre el disco (zfs vs dir):** la intención inicial era un pool **zfs/btrfs** sobre
> `/mnt/data` para snapshots CoW instantáneos. **No es viable sin root interactivo:** LXD
> rechaza loop files en rutas custom (`Custom loop file locations are not supported`), el
> host no tiene `zpool`/`zfs` fuera del snap de LXD, y montar un loop manual exige
> `losetup`/`mount` (root) + persistencia en boot. Decisión de Jorge (2026-05-29): usar
> pool **`dir`** sobre `/mnt/data` — sin root, persistente, aislado del pool `default` de
> prod. Contra: el snapshot de VM es copia del `root.img` (sparse) → segundos-a-minutos en
> HDD, no instantáneo, pero cumple "crear y restaurar OK".

---

## ⚠️ HALLAZGO CRÍTICO — UFW bloquea los bridges LXD nuevos (importante para el Bloque C)

**Este host usa UFW**, que gestiona la tabla `ip filter` (iptables-nft) con
`chain FORWARD { ... policy drop; }` y `chain INPUT { ... policy drop; }`.

**Las reglas `accept` que LXD pone en su tabla `inet lxd` (`fwd.<bridge>`, `in.<bridge>`)
NO bastan:** ambas cadenas enganchan el mismo hook (`forward`/`input`, priority `filter`)
y en nftables un `drop` es terminal y gana sobre el `accept` de otra cadena. Por eso un
bridge LXD recién creado tiene **DHCP, DNS y egress TCP/UDP bloqueados** (solo pasa ICMP,
que `ufw-before-forward` acepta de forma genérica).

`lxdbr0` (el de prod) funciona **solo porque tiene reglas UFW explícitas** que lo permiten
(`iifname "lxdbr0" accept` en `ufw-user-input`, y reglas `lxdbr0↔eno2` en `FORWARD`).

**Por tanto, todo bridge LXD nuevo en este host necesita habilitarse en UFW:**

```bash
sudo ufw allow in on <bridge>          # input host (DHCP/DNS) — espejo de lxdbr0
sudo ufw route allow in on <bridge>    # forward → uplink (egress TCP/UDP)
```

> 🔧 **Implicación para la migración (Bloque C / C3) y para `laia-install`:** si la
> provisión crea un bridge LXD propio en una máquina con UFW activo, hay que añadir estas
> reglas o el cerebro/agentes se quedan sin red. Candidato a automatizar en el instalador.
> (En la VM `laia-dev`, el LXD *anidado* crea su propio `lxdbr0` interno; ver si UFW está
> activo también dentro de la VM — paso de instalación más abajo.)

---

## 1. Estado del host (verificado 2026-05-29)

- LXD **5.21.4 LTS**; usuario `laia-arch` en grupo `lxd` (opera `lxc` **sin sudo**).
- KVM presente (`/dev/kvm`). 40 vCPU. **30 GiB RAM (~21 libres)**.
- `/mnt/data` = `/dev/sda1` **ext4**, 3.4 T libres, owner `laia-arch`.
- Pool LXD previo: solo `default` (`dir`, en NVMe root). Red previa: solo `lxdbr0`
  (10.99.0.1/24). **No se tocan** — la VM es ADITIVA.
- Containers de prod intactos: `laia-agora`, `agent-jorge-dev`, `agent-verify-bob`,
  `agent-verify-carol`.

---

## 2. Pasos EXACTOS de provisión

### 2.1 — Storage pool `dir` sobre `/mnt/data`

```bash
mkdir -p /mnt/data/lxd-laia-dev                 # el driver dir exige que el source exista y esté vacío
lxc storage create laia-dev dir source=/mnt/data/lxd-laia-dev
```

### 2.2 — Red: bridge aislado `laiadev0`

```bash
lxc network create laiadev0 ipv4.address=10.123.0.1/24 ipv4.nat=true ipv6.address=none
```

➡️ **Inmediatamente después, habilitar el bridge en UFW** (ver hallazgo crítico arriba):

```bash
sudo ufw allow in on laiadev0
sudo ufw route allow in on laiadev0
```

### 2.3 — Perfil `laia-dev` (recursos + nesting + disco + NIC)

```bash
lxc profile create laia-dev
lxc profile set laia-dev limits.memory=8GiB
lxc profile set laia-dev limits.cpu=6
lxc profile set laia-dev security.nesting=true
lxc profile device add laia-dev root disk pool=laia-dev path=/ size=60GiB
lxc profile device add laia-dev eth0 nic network=laiadev0 name=eth0
```

### 2.4 — Lanzar la VM (Ubuntu 26.04 LTS, igual que prod)

```bash
lxc launch ubuntu:26.04 laia-dev --vm --profile laia-dev
```

> Se lanza SOLO con `--profile laia-dev` (no `default`) para garantizar disco en el pool
> nuevo y NIC en el bridge aislado, sin heredar el root/NIC del perfil `default`.

### 2.5 — Red estática dentro de la VM (IP determinista, sin depender de DHCP)

> El DHCP del bridge funciona tras el fix de UFW, pero se fija IP estática por ser un
> runbook determinista (IP conocida `10.123.0.50`) y robusto ante reboots.

```bash
lxc exec laia-dev -- sh -c 'cat > /etc/netplan/99-laia-dev.yaml <<EOF
network:
  version: 2
  ethernets:
    enp5s0:
      dhcp4: false
      addresses: [10.123.0.50/24]
      routes:
        - to: default
          via: 10.123.0.1
      nameservers:
        addresses: [1.1.1.1, 8.8.8.8]
EOF
chmod 600 /etc/netplan/99-laia-dev.yaml'
# Persistencia: que cloud-init no reescriba la red en reboots
lxc exec laia-dev -- sh -c 'echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg'
lxc exec laia-dev -- netplan apply
```

### 2.6 — Verificación de red

```bash
lxc list laia-dev                                   # IPV4 = 10.123.0.50
lxc exec laia-dev -- getent hosts archive.ubuntu.com # DNS OK
lxc exec laia-dev -- curl -sS -o /dev/null -w '%{http_code}\n' http://archive.ubuntu.com  # 200
```

Resultado verificado: `lxc list` muestra `laia-dev RUNNING` con IP `10.123.0.50`; DNS y
HTTP(S) salen a internet.

---

## 3. Tailscale (acceso desde el Mac, sin IP en la LAN)

```bash
lxc exec laia-dev -- sh -c 'curl -fsSL https://tailscale.com/install.sh | sh'
lxc exec laia-dev -- tailscale up --hostname=laia-dev --accept-dns=false
```

- `--accept-dns=false`: la VM mantiene su DNS determinista (1.1.1.1/8.8.8.8) y no depende del
  MagicDNS del host (que tiene un warning de DNS).
- `tailscale up` imprime una URL `https://login.tailscale.com/a/...` y **bloquea hasta que
  Jorge la autoriza** en el navegador (alternativa CI: `--auth-key tskey-...`).
- Tras autorizar: la VM aparece como **`laia-dev`** en el tailnet; desde el Mac
  `ssh laia-arch@laia-dev` o `lxc`/editor sobre esa IP `100.x`. (Para SSH, instalar
  `openssh-server` y la clave pública del Mac — paso de conveniencia, no de B1.)

## 4. `laia-install` dentro de la VM (LAIA fiel, como un cliente)

### 4.1 — Usuario owner = `laia-arch` (fidelidad a prod: paths `/home/laia-arch/...`)

```bash
lxc exec laia-dev -- bash -c '
  id laia-arch >/dev/null 2>&1 || useradd -m -s /bin/bash laia-arch
  usermod -aG sudo laia-arch
  echo "laia-arch ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-laia-arch
  chmod 440 /etc/sudoers.d/90-laia-arch'
```

> NOPASSWD es para que el install headless (`--yes`) no se bloquee pidiendo contraseña.
> En la VM `laia-arch` queda con uid **1001** (el `ubuntu` del cloud-image ocupa 1000); el
> número no importa para B1 — la migración (C3) remapea uids.

### 4.2 — Ejecutar el instalador (repo PÚBLICO `JorgeMP-3/laia-arch`, branch `stable`)

> ⚠️ **Gotcha:** el one-liner `curl … | sudo -E bash -s -- …` **anidado** dentro de
> `sudo -u laia-arch --login` se quedó en **no-op** (stdin de `bash -s` + doble sudo se
> comieron la ejecución; salió rc=0 sin crear nada). **Fiable:** descargar a fichero y
> `sudo bash` desde él.

```bash
lxc exec laia-dev -- runuser -u laia-arch -- bash -c '
  cd ~
  curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh -o install.sh
  sudo bash install.sh --mode install --yes'
```

`install.sh` (modo `install`, headless): instala prereqs apt → clona el repo en
`~/LAIA` → delega en `bin/laia-install` (que crea `/opt/laia-vX.Y.Z`, symlink `/opt/laia`,
wrappers en `/usr/local/bin`, `~/LAIA-ARCH/`, units systemd) → **factory bootstrap**:
LXD (snap) + container `laia-agora` + auth/admin/skills base.

> ⚠️ **Gotcha 2 — el handoff del bootstrap necesita TTY.** `install.sh` reabre `/dev/tty`
> antes de exec a `bin/laia-install` → bajo `lxc exec` sin terminal da
> `/dev/tty: No such device or address` y aborta el handoff (solo deja prereqs + clone).
> Por eso ejecutamos `bin/laia-install` directamente **envuelto en `script`** (provee pty).
>
> ⚠️ **Gotcha 3 — el factory bootstrap exige `auth.json` (credenciales LLM).**
> `rebuild-3-provision-agora.sh` aborta en pre-flight si no existe
> `~/.laia/auth.json` (`corre 'laia auth' … primero`), y `bin/laia-install` entonces
> **revierte `/opt/laia`**. Un install de fábrica necesita `laia auth` antes de provisionar
> `laia-agora`. *(Implica a C4 install-native: el flujo limpio es install → `laia auth`
> → provision.)*
>
> 🔐 **Enfoque CREDENCIALES en la VM = THROWAWAY (decisión Jorge, 2026-05-29).** El primer
> provisioning copió el `auth.json` **real de prod** a la VM para desbloquear el bootstrap,
> y eso **contaminó el snapshot `b1-base`** (creds de prod bakeadas). **La VM es el sandbox
> de romper cosas y NO debe llevar credenciales de producción.** Remediación aplicada:
>
> 1. Se sustituyó `/home/laia-arch/.laia/auth.json` por un **placeholder estructural** —
>    mismo esquema (`providers.openai-codex`, `credential_pool`, …) pero **tokens falsos**
>    (`DEV-PLACEHOLDER-NOT-REAL-*`). Cero secretos reales en la VM ni en el snapshot.
> 2. Se borró el snapshot contaminado `b1-base` y se creó uno limpio: **`golden`**.
>
> **Por qué un placeholder basta para B1:** tanto el pre-flight de `rebuild-3`
> (`[[ -f "$AUTH_JSON_HOST" ]]`) como `/api/health` (`agent_pool` solo comprueba que el
> fichero sea legible) **únicamente verifican que `auth.json` EXISTA y sea legible — no
> validan el token contra OpenAI.** Por eso la VM levanta verde (`auth_json_status:linked`)
> sin credenciales reales. La contrapartida: la VM **no puede chatear de verdad** con el LLM
> — irrelevante para su misión (ensayar `install`/`clone`/migración del Bloque C).
>
> ⚠️ **El fichero queda en 644 (world-readable DENTRO de la VM), NO 0600.** Es deliberado:
> `rebuild-3` lo deja 644 para que el uid mapeado del container `laia-agora` pueda leerlo
> por el bind-mount (sin `raw.idmap` aún). Endurecer a 0600 vía `raw.idmap` es **trabajo de
> C2**, no de B1. Un 644 sobre un token **falso** no tiene riesgo. Para reponer un
> placeholder si hiciera falta: escribir el JSON **in-place** (`cat > …`, conserva el inode
> del bind-mount file) y `chmod 0644`.
>
> 🚨 **Pendiente para Jorge (no de B1):** un fragmento del `access_token` real de prod
> (`openai-codex`) se expuso en logs durante la inspección. **Rotar/revocar esa credencial.**

### 4.3 — Verificación (criterio de B1) — ✅ VERIFICADO 2026-05-29

```bash
# laia-arch NO está en el grupo lxd dentro de la VM → el lxc anidado se invoca como root:
lxc exec laia-dev -- lxc list                                    # laia-agora RUNNING (LXD anidado)
lxc exec laia-dev -- curl -fsS http://localhost:8088/api/health  # health del cerebro
```

**Salida real capturada (2026-05-29, con el `auth.json` placeholder ya en su sitio):**

```text
$ lxc exec laia-dev -- lxc list
+------------+---------+--------------------+------+-----------+-----------+
|    NAME    |  STATE  |        IPV4        | IPV6 |   TYPE    | SNAPSHOTS |
+------------+---------+--------------------+------+-----------+-----------+
| laia-agora | RUNNING | 10.99.0.188 (eth0) |      | CONTAINER | 0         |
+------------+---------+--------------------+------+-----------+-----------+

$ lxc exec laia-dev -- curl -fsS http://localhost:8088/api/health
{"ok":true,"service":"agora-backend","version":"0.2.0","env":"dev",
 "data_dir":"/opt/agora/data","db":"sqlite","coordinator":true,
 "lxd_available":false,"laiactl_available":false,
 "auth_json_ready":true,"auth_json_status":"linked",
 "auth_json_path":"/opt/agora/data/auth.json",
 "default_llm_provider":"openai-codex","time":"2026-05-29T14:55:00Z"}
```

- ✅ `laia-agora` **RUNNING** en el LXD anidado (criterio "laia-install OK").
- ✅ `/api/health` responde `ok:true` con `auth_json_status:linked` (placeholder leído).
- ℹ️ `lxd_available:false` / `laiactl_available:false` son **esperados**: el health corre
  `lxc version` / busca `laiactl` **dentro del container `laia-agora`**, que no tiene socket
  LXD ni el binario del host. Informativo, no bloquea B1 (en prod la infra LXD la maneja el
  host/ARCH, no el cerebro). El campo del criterio es "`/api/health` responde" → cumplido.

## 5. Snapshot crear + restaurar — ✅ VERIFICADO 2026-05-29

> Demostración real del ciclo "volver atrás": crear snapshot → cambiar algo → restaurar →
> comprobar que el cambio desapareció y el cerebro vuelve solo. **El snapshot limpio se
> llama `golden`** (sustituye al `b1-base` contaminado, borrado en la remediación de creds).

### 5.1 — Crear el snapshot

```bash
lxc snapshot laia-dev golden        # snapshot NO stateful (solo disco)
lxc info laia-dev | sed -n '/Snapshots/,$p'
```

### 5.2 — Restaurar (rollback)

Un snapshot de VM **no stateful** exige la instancia **parada** para restaurar:

```bash
lxc stop laia-dev
lxc restore laia-dev golden
lxc start laia-dev
```

### 5.3 — Prueba real ejecutada (con resultados)

```bash
# 1) plantar un cambio que NO existe en golden
lxc exec laia-dev -- runuser -u laia-arch -- \
  bash -c 'echo cambio-post-golden > /home/laia-arch/SNAPSHOT-DEMO-MARKER.txt'
# 2) stop → restore golden → start  (ver tiempos abajo)
# 3) verificar
lxc exec laia-dev -- test -f /home/laia-arch/SNAPSHOT-DEMO-MARKER.txt && echo EXISTE || echo AUSENTE
lxc exec laia-dev -- lxc list laia-agora            # autostart lo levanta solo
lxc exec laia-dev -- curl -fsS http://localhost:8088/api/health
```

**Resultados (verificado):**
- ✅ `SNAPSHOT-DEMO-MARKER.txt` → **AUSENTE** tras el restore (disco revertido a `golden`).
- ✅ `auth.json` → sigue siendo el **placeholder** (lo que `golden` tiene). Sin creds de prod.
- ✅ `laia-agora` arrancó **solo** (boot: `STOPPED` → `RUNNING` en ~20 s por `boot.autostart`).
- ✅ `/api/health` → `ok:true, auth_json_status:linked` de nuevo.

### 5.4 — ⏱️ Tiempos reales medidos (importante — NO es "en segundos")

| Operación | Tiempo real (2026-05-29) |
|---|---|
| `lxc delete` snapshot | **0.3 s** |
| `lxc snapshot` (crear `golden`) | **16 m 31 s** |
| `lxc stop` | 21.8 s |
| `lxc restore golden` | **18 m 35 s** |
| `lxc start` (+ autostart del cerebro) | 1.1 s (+~20 s agora) |

> ⚠️ **El criterio del plan decía "volver atrás en segundos" — en este host son ~16-19 min,
> no segundos.** Causa: el pool es driver **`dir` sobre ext4 en HDD**, que **no tiene CoW**;
> cada snapshot/restore es una **copia byte-a-byte del `root.img` de 60 GiB** (~67 MB/s en el
> disco mecánico). Es la contrapartida ya aceptada en §0 (zfs/btrfs CoW no era viable sin root
> interactivo). **El mecanismo funciona y cumple "crear + restaurar OK"**, pero el rollback es
> de *minutos*, no instantáneo.
>
> 🔧 **Si en el futuro se quiere rollback rápido:** (a) **encoger el `root` a ~20-25 GiB**
> (la copia escala con el tamaño → ~5 min), o (b) migrar el pool a **btrfs/zfs** sobre
> `/mnt/data` (snapshots instantáneos; requiere una sesión con root de Jorge para montarlo).

## 6. Operación (arrancar/parar/borrar, autostart) — ✅ DOCUMENTADO 2026-05-29

> Todos los `lxc` de esta sección se ejecutan **en el host** como `laia-arch` (sin sudo;
> está en el grupo `lxd`). Los que operan el LXD **anidado** van prefijados con
> `lxc exec laia-dev -- lxc …` (dentro de la VM `laia-arch` **no** está en el grupo `lxd`,
> así que ahí el `lxc` anidado se invoca como root vía `lxc exec`).

### 6.1 — Arrancar / parar / estado de la VM

```bash
lxc start laia-dev                 # arrancar la VM
lxc stop  laia-dev                 # parada limpia (ACPI). --force si no responde
lxc restart laia-dev               # reiniciar
lxc list laia-dev                  # estado + IPs (IPV4 esperado: 10.123.0.50)
lxc info laia-dev                  # detalle + snapshots + uso de recursos
```

### 6.2 — Operar el LAIA anidado (cerebro) dentro de la VM

```bash
lxc exec laia-dev -- lxc list                      # estado del LXD anidado (laia-agora)
lxc exec laia-dev -- lxc start laia-agora           # arrancar el cerebro
lxc exec laia-dev -- lxc stop  laia-agora           # parar el cerebro
lxc exec laia-dev -- curl -fsS http://localhost:8088/api/health   # health del cerebro
```

### 6.3 — Autostart (sobrevivir a reinicios del host) — ✅ configurado

Para que tras un reboot del host la VM y el cerebro vuelvan solos:

```bash
lxc config set laia-dev boot.autostart=true                  # la VM arranca con el host
lxc exec laia-dev -- lxc config set laia-agora boot.autostart=true   # el cerebro arranca con la VM
```

Verificación (ambos devuelven `true`):

```bash
$ lxc config get laia-dev boot.autostart
true
$ lxc exec laia-dev -- lxc config get laia-agora boot.autostart
true
```

> Con esto, `host reboot` → VM `laia-dev` arranca → LXD anidado arranca `laia-agora` →
> `/api/health` verde sin intervención. (Verificado de forma equivalente por el ciclo de
> restore de §5, que cold-bootea la VM y deja el cerebro arriba solo.)

### 6.4 — Borrar la VM y limpiar TODOS los recursos del host

Si se descarta el taller, esto deja el host como antes de B1 (orden inverso a la creación):

```bash
lxc delete laia-dev --force                  # borra la VM y sus snapshots (incl. golden)
lxc profile delete laia-dev                  # perfil (recursos/nesting/disco/NIC)
lxc network delete laiadev0                  # bridge aislado
lxc storage delete laia-dev                  # storage pool (dir → /mnt/data/lxd-laia-dev)
sudo ufw delete allow in on laiadev0         # reglas UFW del bridge
sudo ufw route delete allow in on laiadev0
# y, ya vacío:  rm -rf /mnt/data/lxd-laia-dev
```

> ⚠️ Los containers de **producción** (`laia-agora`, `agent-jorge-dev`, `agent-verify-bob`,
> `agent-verify-carol`) y sus recursos (`default` pool, `lxdbr0`) **no se tocan** — la VM es
> aditiva. Borrar `laia-dev` no los afecta.

---

## Anexo — Recursos host creados por este runbook (para limpiar si se descarta)

- Storage pool LXD `laia-dev` (dir → `/mnt/data/lxd-laia-dev`).
- Red LXD `laiadev0` (10.123.0.1/24) + 2 reglas UFW (`allow in` / `route allow in`).
- Perfil LXD `laia-dev`.
- Instancia VM `laia-dev`.
