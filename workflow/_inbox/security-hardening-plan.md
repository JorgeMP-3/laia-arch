# Plan de Hardening de Seguridad — host `doyouwin-server`

> **🔴 PRIORITARIO** — marcado importante por Jorge (2026-06-01). Tratar como track de primer
> nivel; los P0 (§0) son cuasi-prerequisito de la ventana de prod. Ver `roadmap-v2-to-production.md` §FASE S.
> **Estado:** DRAFT en `_inbox` (pendiente de revisión de Jorge antes de aplicar / promover).
> **Fecha:** 2026-06-01 · **Autor:** Claude (Opus 4.8) · **Co-auditor:** Codex (entrada en `workflow/security.md` 2026-06-01).
> **Alcance:** host Ubuntu 26.04 `doyouwin-server` (LAIA-ARCH), SSH, UFW/red, snaps (Nextcloud/Rocket.Chat/Wekan), LXD (`laia-agora` + `agent-*` + VM `laia-dev`), secretos.
> **Naturaleza:** auditoría **read-only** (ningún cambio de config aplicado todavía). Este documento es el plan de ejecución + los protocolos de mantenimiento.

---

## 0. Resumen ejecutivo

No hay **indicadores de compromiso** en lo inspeccionado por las dos IAs (sin malware, sin
miners, sin usuarios extra, sin backdoors en claves, sin paquetes npm/PyPI maliciosos de 2026,
Tailscale sin exposición pública, sesiones todas desde el MacBook de Jorge). Los riesgos son
**misconfiguraciones de hardening**, corregibles en sitio en ~1–2 h de trabajo efectivo.

**[VERIFICADO 2026-06-01 con `sudo` — §4]:** **Internet está CERRADO** — UFW default-deny +
allow IN solo desde LAN/Tailscale/bridges; no hay regla inbound para internet (ni IPv4 público
ni IPv6 global). El journal confirma **cero logins ajenos** (los únicos password-logins fueron
`laia-arch` desde la LAN durante el setup 20-21 may). **No hay IoC → veredicto firme: hardening
en sitio, SIN rebuild.** El riesgo residual es de **superficie LAN/Tailscale**, no de internet.

**Top 4 a cerrar hoy (P0):** secreto world-readable + rotación · estado real de SSH
(password/root) · que UFW bloquee de verdad los puertos web desde internet/IPv6 · password
admin de Nextcloud.

---

## 1. Hallazgos reconciliados (Claude + Codex) — fuente única de verdad

Severidad: 🔴 Crítico · 🟠 Alto · 🟡 Medio · 🔵 Info · 🟢 OK.
Verif.: ✅ verificado en vivo · ⚠️ requiere `sudo` (§4) · 📄 según doc/afirmación.

| # | Componente | Estado reconciliado | Sev | Verif. |
|---|---|---|---|---|
| F1 | **`~/.laia/auth.json`** | `0644` world-readable, con `access_token`+`refresh_token` (OpenAI-Codex) y `credential_pool` (Anthropic/OpenAI/Ollama-Cloud/MiniMax/Copilot). **md5 idéntico** a la copia v2 `0600`. Alcanzable porque `~` y `~/.laia` son `0755`. | 🔴 | ✅ |
| F2 | **Copias legacy de secretos** | `~/.laia/{atlas.yaml,config.yaml,*.bak}` en `0644`; copia operativa `/opt/agora/data/auth.json` `0644` dentro del container (host `/srv/laia/agora` es `700` → exposición host baja, pero hay *drift*). | 🟡 | ✅/📄 |
| F3 | **SSH `PasswordAuthentication yes`** | **CONFIRMADO** en `50-cloud-init.conf`. Sin `AllowUsers`. Pero **solo alcanzable desde LAN+Tailscale** (UFW F5), **no internet**. Journal: únicos password-logins = `laia-arch` desde `192.168.100.95/.98` (LAN, 20-21 may, setup). **Sin logins ajenos ni brute-force.** Desactivar igual (defensa en profundidad ante LAN comprometida). | 🟡 | ✅ |
| F4 | **SSH `PermitRootLogin`** | **`prohibit-password`** confirmado (root solo por clave, nunca contraseña). Aceptable; mejor `no` explícito. | 🔵 | ✅ |
| F5 | **UFW** | **Reglas confirmadas:** default `deny incoming`/`deny routed`/`allow outgoing`. Allow IN **solo** desde `192.168.100.0/24` (LAN, v4), y en interfaces `tailscale0`/`lxdbr0`/`laiadev0` (v4+v6). **No hay regla inbound para internet** (eno2 público v4 ni IPv6 global) ⇒ **internet BLOQUEADO** a todos los servicios. Postura correcta. | 🟢 | ✅ |
| F6 | **Servicios en wildcard** | Bind a `0.0.0.0`/`*`: `22`(ssh), `80`(httpd/Nextcloud), `8080`(node = **Wekan**), `3000`+`35005`(node pid 6606 = **Rocket.Chat**), `8088`(lxd = proxy AGORA). **UFW los limita a LAN+Tailscale** (F5) ⇒ no internet. Residual = exposición en LAN sin TLS + password SSH. | 🟡 | ✅ |
| F7 | **Proxy LXD `agora-api`** | `laia-agora`: `listen tcp:0.0.0.0:8088 → connect tcp:127.0.0.1:8000`. `nat` vacío ⇒ **proxy userspace ⇒ UFW lo filtra** (no DNAT bypass). Confirmado bridged al wildcard, pero **internet bloqueado** por UFW; residual LAN. Rebindear a `127.0.0.1`/`tailscale0` por higiene. | 🟡 | ✅ |
| F8 | **IPv6 público** | Global `2a03:3d60:64:c077::/64` presente; servicios escuchan en `[::]`. **UFW no tiene allow inbound v6 en `eno2`** (solo en tailscale0/lxdbr0/laiadev0) ⇒ **IPv6 desde internet BLOQUEADO**. | 🟢 | ✅ |
| F9 | **Sin TLS en el host** | Nextcloud/Rocket.Chat/Wekan/AGORA en HTTP plano; sin reverse-proxy/HTTPS. Credenciales viajan en claro en LAN. Rocket.Chat con `Access-Control-Allow-Origin: *`. | 🟡 | ✅ |
| F10 | **Fail2Ban** | No instalado / inactivo. Sin mitigación de fuerza bruta. | 🟡 | ✅ |
| F11 | **Nextcloud admin** | Doc dice `changeme`. No verificado (snap responde 500 en localhost por trusted_domains). Crítico si sigue vigente y `*:80` es público. | 🟠 | 📄 |
| F12 | **`laia-arch` = sudo total + grupo `lxd`** | Cuenta operadora root-equivalente (lxd permite container privilegiado que monte `/`). Inherente al rol; define modelo de amenaza: caer esta cuenta = caer el host. | 🔵 | ✅ |
| F13 | **Executors PA** | `0.0.0.0:9091` **dentro** del bridge LXD; sin proxy hacia el host ⇒ no expuestos fuera. | 🔵 | ✅ |
| F14 | **Backups** | Sin backups configurados (doc). Riesgo de disponibilidad / ransomware. | 🟡 | 📄 |
| F15 | **Tailscale SSH `--ssh`** | Ingreso passwordless autenticado por identidad Tailscale. Seguro solo con 2FA en la cuenta + ACLs + key-expiry. Nodos `laia-hermes`/`laia-server` llevan días offline (¿legados?). | 🟡 | ✅ |
| ✅ | **Controles correctos** | UFW activo (DROP+IPv6) · `unattended-upgrades` activo · **0 updates de seguridad pendientes** · `canonical-livepatch` activo · Tailscale Funnel/Serve **sin exposición** · tailnet solo dispositivos de Jorge · solo `root`+`laia-arch` con UID0/shell · `/srv/laia/arch/secrets` en `0700`/`0600` · clave **ED25519** en uso · sin cron/procesos maliciosos · sudoers.d solo regla estrecha `vision` (`systemctl isolate`, no escalable a root). | 🟢 | ✅ |
| 🟢 | **Cadena de suministro npm** | Sin `axios` (malicioso 1.14.1/0.30.4), sin `@tanstack/*` (84 versiones malas 11-may-2026), sin `node-ipc` (9.1.6/9.2.3/12.0.1), sin `plain-crypto-js`. `ua-parser-js 2.0.9`, `eslint-scope 8.4.0/9.1.2`, `rc 1.2.8` = versiones seguras. node/npm **no instalados** como sistema (solo pnpm + node embebido en apps). | 🟢 | ✅ |
| 🟢 | **Cadena de suministro PyPI** | Intérpretes 3.14.4 / 3.12.13 / 3.11.15 limpios. No instalados: `mistralai 2.4.6`, `litellm 1.82.7/1.82.8`, `lightning 2.6.2/2.6.3`, `guardrails-ai`, `durabletask`, `xinference`. Tienes `lightning 2.6.4`, `litellm 1.81.15`, `mistralai 2.3.0` (no maliciosas). Sin payloads (`/tmp/transformers.pyz`, `*.pth`, etc.). | 🟢 | ✅ |

---

## 2. Plan de remediación (priorizado)

> **Regla de oro de SSH:** NO cierres password-auth ni reinicies `ssh` sin tener (a) una sesión
> Tailscale SSH viva **y** (b) una clave ED25519 funcionando. Verifica con una segunda terminal
> antes de cerrar la primera.
> **Guardrail LAIA:** los pasos que tocan `~/.laia`, `/srv/laia`, permisos o credenciales
> requieren OK explícito de Jorge (CLAUDE.md §"Pregunta primero").

### P0 — Hoy (minutos; cierra el riesgo agudo)

**P0.1 · Cerrar el secreto expuesto (F1/F2) — ✅ HECHO 2026-06-01 (Claude)**
```bash
# Aplicado: ~/ y ~/.laia ahora 0700; auth.json/atlas.yaml/config.yaml/*.bak/.env.paths ahora 0600.
# Verificado: barrido find bajo ~ y /srv/laia → 0 secretos world/group-readable. Sin host-side exposure.
```
> Copia legacy `/opt/agora/data/auth.json` `0644` vive **dentro** del contenedor `laia-agora`
> (source host `/srv/laia/agora` es `0700` idmapped → sin alcance host). Fix opcional, no urgente:
> `lxc exec laia-agora -- chmod 600 /opt/agora/data/auth.json` (confirmar que el backend corre como owner).

**Rotación (precautoria, NO de emergencia):** dado que **no hay otros usuarios locales** y los snaps
están confinados, la probabilidad de que el `refresh_token` se leyera es **baja** y no hay evidencia
de lectura. Si quieres ser estricto: re-login/regenerar en cada portal — OpenAI/Codex, Anthropic,
Copilot, MiniMax, Ollama-Cloud — y rotar tokens de `.env` (`TELEGRAM_BOT_TOKEN`, `TAVILY`, etc.).
Es **decisión de Jorge**, no bloqueante.

**P0.2 · Verificar y endurecer SSH (F3/F4)** *(Jorge, con `sudo`)*
```bash
sudo cat /etc/ssh/sshd_config.d/50-cloud-init.conf
sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin|kbdinteractive|pubkeyauthentication|^port |x11forwarding'
```
**✅ HECHO + VERIFICADO EN VIVO 2026-06-01** (`sudo sshd -T`): `passwordauthentication no`,
`permitrootlogin no`, `allowusers laia-arch`. El gotcha del cloud-init se resolvió bien
(password-auth apagado en el propio `50-cloud-init.conf`, que gana por orden de lectura
sobre cualquier drop-in `99-*`, que sería ignorado). Receta aplicada (se conserva para auditoría):
```bash
# 0) (opcional) clave para el path LAN directo — pega la pública de tu MacBook.
#    NO hace falta para no quedarte fuera: Tailscale SSH (100.87.62.18) no usa sshd.
install -d -m 700 ~/.ssh && printf '%s\n' 'ssh-ed25519 AAAA...tu_pública... jorge@macbook' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
# 1) apagar password-auth donde HOY se activa (cloud-init, gana por orden):
sudo sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config.d/50-cloud-init.conf
# 2) resto de hardening (estas claves NO están en 50 → un drop-in 99 las fija bien):
sudo tee /etc/ssh/sshd_config.d/99-laia-hardening.conf >/dev/null <<'EOF'
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AllowUsers laia-arch
MaxAuthTries 3
X11Forwarding no
EOF
# 3) validar sintaxis, recargar, CONFIRMAR (mantén una sesión Tailscale viva):
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin|allowusers|x11forwarding'
# → debe mostrar: passwordauthentication no
```

**P0.3 · UFW — ✅ HECHO + VERIFICADO EN VIVO 2026-06-01** *(`sudo ufw status verbose`)*: `active`,
default `deny (incoming)`, solo permite LAN `192.168.100.0/24` + `tailscale0` + puentes internos
`lxdbr0`/`laiadev0`. **Nada de prod expuesto a internet** (ni IPv4 ni IPv6). Receta (auditoría):
```bash
sudo ufw status verbose
sudo ss -tulnp | grep -E ':(22|80|3000|8080|8088|35005)\b'   # atribuir 8080/35005
```
Objetivo: solo LAN + Tailscale; nada de servicios web abiertos a internet.
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
sudo ufw allow from 192.168.100.0/24
sudo ufw limit 22/tcp                 # rate-limit si mantienes 22 en LAN
# NO 'ufw allow 80/3000/8080/8088/35005' a 'any'. Verifica con: nmap -6 desde fuera (opcional)
sudo ufw reload && sudo ufw status verbose
```

**P0.4 · Password admin Nextcloud (F11)** *(Jorge, `sudo`)*
```bash
sudo nextcloud.occ user:lastlogin admin
sudo nextcloud.occ user:resetpassword admin   # si sigue 'changeme' o desconocido
```

### P1 — Esta semana

**P1.1 · Fail2Ban (F10)** *(Jorge, `sudo`)*
```bash
sudo apt update && sudo apt install -y fail2ban
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled  = true
backend  = systemd
maxretry = 4
findtime = 10m
bantime  = 1h
EOF
sudo systemctl enable --now fail2ban && sudo fail2ban-client status sshd
```

**P1.2 · Rebindear el proxy AGORA fuera del wildcard (F7)** *(Jorge/Claude, `lxd`)*
```bash
# Opción A — solo localhost (si AGORA se consume vía reverse-proxy local):
lxc config device set laia-agora agora-api listen tcp:127.0.0.1:8088
# Opción B — solo Tailscale (consumo remoto seguro):
lxc config device set laia-agora agora-api listen tcp:100.87.62.18:8088
lxc config device show laia-agora | sed -n '/agora-api/,/type/p'
ss -lntp | grep 8088
```

**P1.3 · TLS / reverse-proxy (F9)**
```bash
# Vía simple sin certs públicos (HTTPS solo en el tailnet):
sudo tailscale serve --bg --https=443 localhost:8088    # AGORA con HTTPS interno
# o Caddy (auto-HTTPS si hay dominio real):  sudo apt install -y caddy
```

**P1.4 · Consolidar secretos a v2 y borrar legacy (F2)** *(Jorge, tras P0.1)*
- Fuente única: `/srv/laia/arch/secrets/` (`0700` dir, `0600` ficheros).
- Eliminar duplicados en `~/.laia/` y `/opt/agora/data/` una vez migrados/rotados.

### P2 — Este mes

- **P2.1 Backups inmutables (F14):** `restic` a Backblaze B2 / Hetzner Storage Box; respaldar
  `/mnt/data/nextcloud`, `/var/snap/{nextcloud,rocketchat-server,wekan}/common`,
  `/srv/laia/`, `server-docs`. Programar `restic` + `forget --prune`; probar **restore** una vez.
- **P2.2 Tailscale (F15):** activar 2FA en `jorgemiralles166@`, key-expiry ON, ACLs que limiten
  quién puede `ssh` a `doyouwin-server`, y **revocar** `laia-hermes`/`laia-server` si son legados.
- **P2.3 Supply-chain en CI:** añadir `pnpm audit` / `pip-audit` al job de integridad
  (ya existe `T-DOC` en CI; extender). Ver §3.5.
- **P2.4 Monitorización (§3.6).**

---

## 3. Protocolos de mantenimiento (cómo mantenerlo seguro)

### 3.1 Política de acceso / SSH
- **Ingreso por defecto = Tailscale SSH** (autenticado por identidad + 2FA del tailnet).
- Puerto 22 abierto **solo a LAN** (`192.168.100.0/24`) con `ufw limit`; nunca a internet.
- **Password-auth = OFF**, `PermitRootLogin no`, `AllowUsers laia-arch`, `MaxAuthTries 3`.
- Claves **ED25519** exclusivamente. Una clave por dispositivo; revisar `authorized_keys`
  trimestralmente y al perder/cambiar dispositivo.
- `sudo` con contraseña (NUNCA `NOPASSWD` salvo la regla estrecha `vision` ya existente).

### 3.2 Política de red / firewall
- **Default `deny incoming`** (IPv4 **e** IPv6 — `IPV6=yes`).
- Servicios internos (Nextcloud/Rocket.Chat/Wekan/AGORA) **jamás** bind a `0.0.0.0` cuando
  evitarse: usar `127.0.0.1` + reverse-proxy, o la IP `tailscale0`.
- Proxies LXD: `listen` en `127.0.0.1` o IP Tailscale, nunca `0.0.0.0`. Si se necesita `nat=true`,
  recordar que **hace DNAT y salta UFW** → añadir regla explícita.
- Revisar puertos con `sudo ss -tulnp` tras cada despliegue (§3.8).
- Exposición a internet solo vía **Tailscale Serve/Funnel** consciente, nunca port-forward del router.

### 3.3 Gestión de secretos
- **Fuente única:** `/srv/laia/arch/secrets/` (`0700`/`0600`). Cero copias en `$HOME` world-readable.
- `$HOME` y subdirs con secretos en `0700`; ficheros de secreto `0600`.
- **Prohibido** commitear secretos: mantener `.env*` en `.gitignore`; usar `.env.example` como plantilla.
- **Rotación:** programada cada 90 días y **inmediata** ante cualquier exposición (como F1).
- Verificación periódica: `find ~ /srv/laia -name 'auth.json' -o -name '.env*' | xargs stat -c '%A %n'`.

### 3.4 Gestión de actualizaciones
- `unattended-upgrades` activo (✅) + `canonical-livepatch` (✅).
- **Semanal:** `apt list --upgradable`; aplicar y reiniciar servicios si hay CVEs.
- Snaps auto-actualizan; vigilar `snap changes` y revisar revisiones de Nextcloud/Rocket.Chat.
- Reinicio planificado cuando livepatch acumule parches que requieran reboot.

### 3.5 Higiene de cadena de suministro
- **Lockfiles obligatorios** (`package-lock.json` / `uv.lock`); `npm ci`/`uv sync`, nunca install suelto.
- En CI (job de integridad): `pnpm audit --prod` + `pip-audit` (fallar el build en High/Critical).
- Antes de añadir dependencia: comprobar mantenimiento, edad de la versión y advisories.
- Contrastar incidentes activos (Axios, TanStack, node-ipc, litellm, mistralai, lightning…) en
  Snyk/GitHub Advisories/vendor advisories antes de actualizar paquetes sensibles a IA.
- Pin de versiones críticas (p.ej. el stack torch 2.2.2+cu118 de la P4000) documentado en `server-docs`.

### 3.6 Logging, monitorización y alertas
- Centralizar en `journald`; revisar `journalctl -u ssh`, `fail2ban-client status sshd` semanalmente.
- Alerta de bans de Fail2Ban y de fallos de `unattended-upgrades`.
- Chequeo de integridad de puertos: script que compare `ss -tulnp` contra un baseline aprobado.
- (Opcional) `auditd` para cambios en `/etc/ssh`, `/srv/laia/arch/secrets`, sudoers.

### 3.7 Backup y recuperación
- 3-2-1: datos en HDD + repo remoto cifrado (restic) + retención. Repo **append-only/immutable**
  para resistir ransomware.
- **Probar restore** trimestralmente (un backup no probado no es backup).
- Documentar RPO/RTO por servicio (Nextcloud, Rocket.Chat, AGORA `agora.db`).

### 3.8 Checklist de alta de un servicio nuevo
1. ¿Bind a `127.0.0.1`/`tailscale0` (no `0.0.0.0`)?  2. ¿TLS?  3. ¿Credenciales por defecto cambiadas?
4. ¿Regla UFW mínima necesaria?  5. ¿Secreto en `/srv/laia/arch/secrets` `0600`?  6. ¿Incluido en backups?
7. ¿`sudo ss -tulnp` post-deploy coincide con lo esperado?  8. ¿Anotado en `server-docs` + `workflow/security.md`?

### 3.9 Runbook de respuesta a incidentes
1. **Contener:** aislar (UFW `deny`/desconectar tailnet del nodo), NO apagar (preservar RAM/estado).
2. **Preservar:** snapshot LXD/LVM; copiar `journalctl`, `/var/log`, `ss -tulnp`, `ps auxf`, `lxc list`.
3. **Erradicar:** rotar **todas** las credenciales; identificar vector; parchear.
4. **Recuperar:** restaurar desde backup limpio anterior al IoC; re-deploy.
5. **Post-mortem:** entrada en `workflow/security.md` (tipo/severidad/sistema/acción/pendiente).

---

## 4. Verificación con `sudo` — RESUELTA (2026-06-01)

| Comprobación | Resultado |
|---|---|
| `sshd -T` password-auth | **`passwordauthentication yes`** (confirmado) — pero solo LAN+Tailscale por UFW. |
| `sshd -T` root | **`permitrootlogin prohibit-password`** (root nunca por contraseña). |
| `AllowUsers` | No definido. |
| `ufw status verbose` | default deny in/routed; allow solo LAN(`192.168.100.0/24`)+`tailscale0`+`lxdbr0`+`laiadev0` (v4+v6). **Internet bloqueado.** |
| `ss -tulnp` (puertos) | `8080`=node/Wekan · `3000`+`35005`=node/Rocket.Chat (pid 6606) · `8088`=lxd/AGORA · `80`=httpd/Nextcloud. |
| `journalctl -u ssh` | 4 password-logins, todos `laia-arch` desde LAN (`.95`/`.98`), 20-21 may. **Cero logins ajenos / brute-force.** |

**Veredicto cerrado:** **No hay IoC y no hay exposición a internet.** → **Hardening en sitio,
NO rebuild.** La condición de "línea roja" (password-auth público + login desconocido) **no se
cumple**: aunque password-auth está ON, no es alcanzable desde internet y no hubo accesos ajenos.

Único pendiente menor de verificar: **password admin Nextcloud** (`sudo nextcloud.occ user:lastlogin admin`).

---

## 5. Calendario de auditoría recurrente

| Cadencia | Acciones |
|---|---|
| **Diario (auto)** | `unattended-upgrades`, livepatch, Fail2Ban activos (alertas). |
| **Semanal** | `apt list --upgradable`; `fail2ban-client status sshd`; revisar `journalctl -u ssh` por accesos raros; `ss -tulnp` vs baseline. |
| **Mensual** | `pnpm audit` + `pip-audit`; revisar `authorized_keys` y dispositivos Tailscale; verificar perms de secretos; probar un restore parcial. |
| **Trimestral** | Rotación de secretos (90d); auditoría completa estilo este documento; revisar reglas UFW y proxies LXD; test de restore completo; revisar ACLs Tailscale. |

---

## 6. Trazabilidad con docs LAIA
- Log del incidente: `workflow/security.md` (entrada 2026-06-01 de Codex).
- Este plan: promover a `workflow/plans/` cuando Jorge lo apruebe.
- Decisiones de arquitectura derivadas (p.ej. política bind-localhost para AGORA): `workflow/arch-layout.md`.
- Datos del host: `~/Documents/server-docs/` (actualizar `pendientes.md`: UFW ya activo; añadir Fail2Ban/TLS).
