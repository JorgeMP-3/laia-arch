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
> `laia-agora`. Aquí (espejo) copiamos el `auth.json` **real** del host a la VM
> (`lxc file push … /home/laia-arch/.laia/auth.json`) antes de re-ejecutar. *(Implica a C4
> install-native: el flujo limpio es install → `laia auth` → provision.)*

### 4.3 — Verificación (criterio de B1)

```bash
lxc exec laia-dev -- runuser -u laia-arch -- bash -lc 'lxc list'        # laia-agora RUNNING (LXD anidado)
lxc exec laia-dev -- curl -fsS http://localhost:8088/api/health         # health del cerebro
```

## 5. Snapshot crear + restaurar  — PENDIENTE

## 6. Operación (arrancar/parar/borrar, autostart)  — PENDIENTE

---

## Anexo — Recursos host creados por este runbook (para limpiar si se descarta)

- Storage pool LXD `laia-dev` (dir → `/mnt/data/lxd-laia-dev`).
- Red LXD `laiadev0` (10.123.0.1/24) + 2 reglas UFW (`allow in` / `route allow in`).
- Perfil LXD `laia-dev`.
- Instancia VM `laia-dev`.
