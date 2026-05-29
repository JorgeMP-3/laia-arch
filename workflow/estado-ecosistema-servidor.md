# Estado real del ecosistema LAIA en el servidor — snapshot verificado

> **Fecha:** 2026-05-28 · **Host:** `doyouwin-server` · **Autor:** Claude (Opus).
> Inventario **verificado en disco** de cómo está configurado TODO el ecosistema LAIA en
> este servidor. Complementa `project-map.md` (vista de pájaro) y `plans/estabilizacion/auditoria-profunda-ecosistema.md`
> (problemas) con el detalle de **runtime, servicios, containers, red y configuración**.
>
> Marcas: ✅ verificado · ⚠️ divergencia respecto a la spec (`arch-layout.md`) · 🔴 problema ·
> 🔒 no inspeccionado (zona root/producción).

---

## 1. Resumen ejecutivo

- **Una sola máquina** (ThinkStation P720 = `doyouwin-server`) hace **producción y desarrollo a la vez**.
- **Producción instalada:** `/opt/laia` → **v0.11.0**. La plataforma multi-usuario corre en
  el container `laia-agora` y responde (`:8088` ✅).
- **Ecosistema vivo de punta a punta:** cerebro (`laia-agora`) + 3 executors por-usuario
  (`agent-jorge-dev`, `agent-verify-bob`, `agent-verify-carol`) + daemon `laia-pathd` + Atlas.
- **Estado general:** funcional, pero con **divergencias de layout** (config-home), **refs de
  Atlas rotas**, **integraciones de mensajería apagadas** (salvo Signal), **sin sistema de backups** y
  un **agujero de seguridad** (`auth.json` en 644).

---

## 2. Hardware y SO

| | |
|---|---|
| Hardware | Lenovo **ThinkStation P720** (SKU 30BBS36T05) |
| Hostname (Ubuntu) | **`doyouwin-server`** |
| SO / kernel | Ubuntu **26.04 LTS** / Linux 7.0.0-15 |
| CPU / RAM | **40 cores** (Xeon Silver 4114) / **30 GiB** (~21 disponibles → la RAM es el límite) |
| Virtualización | `/dev/kvm` presente (KVM disponible) |
| Discos | NVMe 477 G → `/` · HDD 3,6 T → `/mnt/data` (audio/TTS/models/nextcloud; 3,4 T libres) · pendrives USB |
| ⚠️ Nota | `/srv` y `/opt` **NO** son volúmenes separados: cuelgan del LV root |

---

## 3. Mapa de disco (las zonas del ecosistema)

| Zona | Owner | Qué es | Estado |
|---|---|---|---|
| `/opt/laia` → `/opt/laia-v0.11.0` | root | **Código de producto instalado** (lo que corre `laia`). Layout **plano** (no `current→versions/`). | ✅ / ⚠️ plano |
| `/opt/laia-v0.0.0-clone` | root | **Leftover** de un clone antiguo (basura, borrable). | 🔴 basura |
| `/usr/local/bin/laia*` | root | Symlinks → `/opt/laia/bin/{laia,clone,install,release,rollback}`. | ✅ |
| `/srv/laia/agora` | root (`drwx------`) | **Datos centrales** (agora.db, .env, plugins, skills, logs). Bind-mount → `laia-agora`. | ✅ 🔒 |
| `/srv/laia/users/{jorge-dev,verify-bob,verify-carol}` | root | Home/workspace/plugins de cada usuario (bind-mount a su container). | ✅ |
| `/srv/laia/{arch,backups,state}` | — | **NO existen** (la spec los pide). | ⚠️ |
| `~/.laia/` | laia-arch | **Secretos + config**: `.env`, `.env.paths`, `atlas.yaml`, `auth.json`, `config.yaml`, `state/`. | ✅ (con problemas, §9) |
| `~/LAIA-ARCH/` | laia-arch `0700` | **Hogar del agente** — hoy guarda TODO (mesa viva + runtime + credenciales). ~700 MB. | ⚠️ (§9) |
| `~/LAIA/` | laia-arch | **Repo de desarrollo** (rama `wip/claude/estabilizacion-plan-v2`). | ✅ |
| `~/workspaces/` | laia-arch | Duplicado **vacío** (esqueletos 72 KB) — basura del path no fijado. | 🔴 basura |
| `/root/.laia/` | — | **No existe** (el huérfano que mencionaba `project-map` ya no está). | ✅ |

Contenido de `~/LAIA-ARCH/` (el hogar del agente, todo junto):
- **Mesa viva (correcto aquí):** `workspaces/` (263 M, 7 ws con datos), `memories/`, `skills` → symlink a `~/LAIA/skills`, `plugins/`.
- **Runtime (la spec lo quiere en `/srv/laia/arch/`):** `state.db` (187 M), `sessions/` (203 M), `cron/`, `logs/` (13 M), `atlas/`, `sandboxes/`, `orchestrator-runs/`, `migration/`, `response_store.db`, `SOUL.md`, `config.yaml` (14 K), `platforms/`, `whatsapp/`, `checkpoints/`, `bin/` (12 M), `pathd.sock`.
- **Credenciales (la spec las quiere en `~/.laia/`):** `auth.json` (5,5 K), `.env`, `.admin-credentials`.
- **Cruft:** `config.yaml.pre-migrate.bak`, `models_dev_cache.json` (2 M), `*.cache.yaml`, `.skills_prompt_snapshot.json`, `auth.lock`.

---

## 4. Versión y git

- **Producción:** `/opt/laia/VERSION` = **v0.11.0** (symlink a `/opt/laia-v0.11.0`).
- **Dev:** `~/LAIA` en rama `wip/claude/estabilizacion-plan-v2`; `VERSION` del repo vacío.
- Últimos merges: PR#11 (atlas visualize), PR#10 (estrategia de PRs en AGENTS).

---

## 5. Servicios y puertos

| Puerto | Servicio | ¿LAIA? | Estado |
|---|---|---|---|
| `*:8088` | **agora_api** (NAT del host → `laia-agora:8000`, FastAPI, 80+ endpoints, JWT) | ✅ LAIA-AGORA | ✅ online (24 ms) |
| `0.0.0.0:8080` | **signal-cli** HTTP (gateway de Signal) | ✅ LAIA | ✅ online |
| `10.99.0.x:9091` | **laia-executor** (uno por container de agente) | ✅ LAIA | ✅ (jorge-dev responde) |
| `:8642` | gateway_api (OpenAI-compat del `.laia-core/gateway`) | ✅ LAIA (config) | 🔴 offline |
| `:9000` | whatsapp_bridge (Node) | ✅ LAIA (config) | 🔴 offline |
| `:8765` / `:8645` | feishu_webhook / bluebubbles_webhook | ✅ LAIA (config) | 🔴 offline |
| `*:80` | Nextcloud (Apache snap) | ❌ | ✅ |
| `:3000` | Wekan | ❌ | ✅ |
| `:27017` / `:27019` | MongoDB (Rocketchat / Wekan) | ❌ | ✅ |
| `:5002` | TTS daemon (voz de Jorge) | ❌ | ✅ |
| `:9277` | oz/warp daemon | ❌ | ✅ |
| `:22` SSH · `:631` CUPS · `:53` DNS · `:35005` LXD-monitor · `:35041/:43313` VS Code · tailscale | infra/SO | ❌ | — |

**Procesos LAIA verificados:** `laia-pathd` (host, venv de `/opt/laia`) · `uvicorn app.main:app :8000` (dentro de `laia-agora`) · **3× `laia-executor`** (uno en cada container de agente).

---

## 6. LXD (ejecución)

**Containers** (todos `RUNNING`, **0 snapshots**, red `lxdbr0`):

| Container | IP | Imagen | Rol |
|---|---|---|---|
| `laia-agora` | 10.99.0.199 | orchestrator (build 2026-05-26) | Cerebro LAIA-AGORA (agora-backend + pool + `.laia-core`) |
| `agent-jorge-dev` | 10.99.0.163 | per-user executor (2026-05-26) | PA-AGORA de Jorge (executor :9091) |
| `agent-verify-bob` | 10.99.0.120 | per-user executor | **Agente de prueba** (verificación 26-may) |
| `agent-verify-carol` | 10.99.0.134 | per-user executor | **Agente de prueba** (verificación 26-may) |

**Bind mounts:**
- `laia-agora`: `~/.laia/auth.json` → `/opt/agora/data/auth.json` (credenciales, readonly) · `/srv/laia/agora` → `/opt/agora/data`.
- cada agente: `/srv/laia/users/<slug>/{home,plugins,workspace}` → `/home/user`, `/opt/laia/plugins`, `/var/lib/laia/workspace`.

**Perfiles:** `default` (4) · `laia-agora` (1; ⚠️ comentario de sizing dice "ARM dev host 7,2 GB / 2 vCPU·3 GB" — **stale**, era del viejo host Hermes) · `laia-employee` (3; executor-only, root, sin sandbox).
**Red:** `lxdbr0` 10.99.0.1/24 (NAT gestionado). Físicas `eno1/eno2/wlp2s0` sin usar por LXD.
**Storage:** un único pool `default` (driver `dir`, `/var/snap/lxd/...`).

---

## 7. Atlas v2 — registro del ecosistema

`~/.laia/atlas.yaml` es **el registro de DESARROLLO** (`laia_root = ~/LAIA`). Resumen de
`atlas doctor` (✅ online / ⚠️ offline):

- **PATHS (✅):** agora_backend, laia_core, laia_executor, infra/bin/skills/workspace_store, arch_{workspaces,skills,memories}, laia_arch_home, laia_home (`~/.laia`), laia_root (`~/LAIA`), opt_laia, srv_{laia,agora,users}.
- **PATHS (⚠️ no existen en host):** `executor_{profile_file,token_file,workspace_root}` y `laia_process_log_dir` (viven **dentro del container**), `srv_state`, `workspace_store_lib` (`/opt/laia/lib`).
- **SERVICES:** `agora_api` ✅ · `signal_cli` ✅ · `gateway_api`, `whatsapp_bridge`, `feishu_webhook`, `bluebubbles_webhook` ⚠️ offline · 🔴 **`executor_api` → `http://agent-jorge:9091`** (name resolution failed — el container es `agent-jorge-dev`).
- **CONTAINERS:** `agora_container` ✅ · 🔴 **`jorge_container` → `agent-jorge`** (no existe; es `agent-jorge-dev`).
- **SOCKETS:** 🔴 **`pathd_socket` → `~/.laia/pathd.sock`** reportado offline porque **el socket real está en `~/LAIA-ARCH/pathd.sock`** (ver §9).
- **ENV_FILES:** ⚠️ `agora_env` → `/srv/laia/agora/.env` no existe en host (el container tiene su propia copia interna).

→ **14 refs marcadas offline** (la mayoría son opcionales / internas de container; las 🔴 sí son bugs reales).

---

## 8. Red y acceso

- **LXD:** `lxdbr0` 10.99.0.1/24 NAT → los containers se hablan por la bridge interna.
- **Tailscale:** ✅ **instalado y activo en el host** (`doyouwin-server` = `100.87.62.18`). Tailnet de Jorge:
  - `jorges-macbook-pro` (active), `iphone-13`.
  - ⚠️ `laia-hermes` (offline, visto hace 1 día) y `laia-server` (offline, 23 h) — **máquinas viejas** en el tailnet.
  - ⚠️ aviso de salud: "Tailscale can't reach the configured DNS servers".
  - → el **acceso al taller (VM) será por Tailscale**, directo desde el Mac.
- **nginx:** `inactive`, sin `sites-enabled` → **no está sirviendo LAIA** (el `:80` lo ocupa Nextcloud).

---

## 9. Configuración del agente y el problema de "config-home"

`~/.laia/config.yaml` (config legacy de `laia-pathd`) define los paths; `~/.laia/.env.paths`
es su export auto-generado. Apuntan a:
`laia_root=~/LAIA`, `laia_home=~/.laia`, `laia_arch_home=~/LAIA-ARCH`, `pathd_socket=~/.laia/pathd.sock`.

**Pero la realidad diverge en tres puntos (esto es el Bloque C del plan):**

1. ⚠️ **Socket en sitio distinto al declarado.** El daemon corre como servicio systemd con
   `LAIA_HOME=/home/laia-arch/LAIA-ARCH`, así que el socket real está en
   **`~/LAIA-ARCH/pathd.sock`**, no en `~/.laia/pathd.sock` (lo que dicen `config.yaml`,
   `.env.paths` y `atlas.yaml`). Por eso `atlas doctor` lo ve "offline" aunque funciona.
2. 🔴 **Dos `auth.json` descoordinados:** `~/.laia/auth.json` (10.403 B, **modo 644** — el que
   monta `laia-agora`) y `~/LAIA-ARCH/auth.json` (5.567 B, 600). Tamaños distintos = desincronizados.
3. ⚠️ **Workspaces sembrados por todas partes:** el agente calcula `<home>/workspaces`; con el
   home bien resuelto escribe en `~/LAIA-ARCH/workspaces/` (datos reales, 263 M), pero al
   ejecutarse con el home mal resuelto crea esqueletos **vacíos** en `~/workspaces` y `~/LAIA/workspaces`.

🔴 **Seguridad:** `~/.laia/auth.json` (tokens reales de OpenAI) está en **644** (legible por otros); la spec exige 0600.

---

## 10. Integraciones de mensajería

- **Signal:** ✅ `signal-cli` HTTP en `:8080` (host). `~/LAIA-ARCH/platforms/` solo contiene `pairing/`.
- **Gateway multiplataforma** (`.laia-core/gateway`, OpenAI-compat `:8642`) y puentes
  **WhatsApp / Feishu / BlueBubbles**: declarados en Atlas pero **apagados** (connection refused).

---

## 11. Datos

| Dato | Dónde | Estado |
|---|---|---|
| `/srv/laia/agora/` (mesa del cerebro AGORA; bind → `laia-agora:/opt/agora/data`) | `SOUL.md`, `sessions/`, `memories/`, `skills/`+`skill-store/`, `installed-{plugins,skills}/`, `plugin-store/`, `workspaces/`, `frontend/`, `cron/`, `logs/`, `agora.db` | ✅ |
| `agora.db` (BD central: usuarios, agentes, plugins, uso) | `/srv/laia/agora/agora.db` — **18 MB**, modo WAL (vivo) | ✅ inventariada (22 tablas, ver abajo) |
| Workspaces de Jorge (con datos) | `~/LAIA-ARCH/workspaces/` (263 M, 7 ws) | ✅ (donde la spec los quiere) |
| `state.db` (workspace store / memoria del ARCH) | `~/LAIA-ARCH/state.db` (187 M) | ⚠️ spec → `/srv/laia/arch/` |
| Historial de sesiones | `~/LAIA-ARCH/sessions/` (203 M) | ⚠️ spec → `/srv/laia/arch/` |
| Datos de usuarios | `/srv/laia/users/<slug>/` | ✅ |
| **Backups** | solo `.bak` **manuales y viejos** de `agora.db` (`pre-cleanup`, 17-18 may, mismo disco); nada para `users/` ni runtime ARCH | 🔴 **sin sistema de backups** |

> El `auth.json` en `/srv/laia/agora/` es de 0 bytes (punto de montaje; las credenciales
> reales llegan por el bind de `~/.laia/auth.json`).

**Esquema de `agora.db`** (22 tablas, conteos 2026-05-28):

- **Identidad / flota:** `users` (5) · `agents` (4) · `agent_areas` (5). ⚠️ 5 usuarios y 4
  agentes pero solo **3 containers** (jorge-dev, verify-bob, verify-carol) → hay **registros de
  más** (los de prueba bob/carol + posible residuo); cuadrar al retirar los verify.
- **Actividad:** `events` (**37 678** — el grueso de la BD) · `usage_ledger` (15) · `admin_jobs` (6) ·
  `conversations` (0) · `coordinator_messages` (0) · `tasks` (0).
- **Scheduler / delegación / aprendizaje:** `agent_scheduled_jobs` (0) · `agent_child_runs` (0) ·
  `agent_learnings` (0) · `auto_imports` (0).
- **Marketplace:** `skill_registry` (16) / `skill_installs` (16) · `plugin_registry` (6) / `plugin_installs` (2).
- **Mensajería:** `telegram_links` (**1** — Telegram enlazado) · `webhook_subscriptions` (1).

→ El esquema **confirma la arquitectura documentada** (coordinador, scheduler, marketplace,
usage tracking, webhooks). Notas: además de Signal, hay **Telegram enlazado**; conversaciones
y tasks vacías (sin historial persistido); la BD es casi toda log de `events`.

---

## 12. Qué NO es LAIA (para no confundir)

Nextcloud (`:80`), Wekan (`:3000`), Rocketchat/MongoDB (`:27017/:27019`), stack de
audio/TTS (`/mnt/data`, `:5002`, `audio-models`), oz/warp (`:9277`), VS Code Server,
CUPS (`:631`). Y en el home: `.local`, `.config`, `.cache`, `.codex/.claude/.opencode/.copilot`
(herramientas de dev), `Desktop/Documents/...` (escritorio).

---

## 13. Divergencias y problemas (consolidado)

| # | Tema | Severidad | Bloque del plan |
|---|---|---|---|
| 1 | `~/.laia/auth.json` en **644** (tokens reales) | 🔴 seguridad | A |
| 2 | Refs Atlas rotas: `agent-jorge`(→`-dev`), `executor_api` | 🔴 | A |
| 3 | `bin/atlas.py` duplicado · `.curator_state` · `atlas.yaml.bak` · `~/workspaces` y `~/LAIA/workspaces` vacíos | 🟡 limpieza | A |
| 4 | 2 tests de agora-backend fallan | 🟠 | A |
| 5 | **Sin sistema de backups** (solo `.bak` viejos de `agora.db`, mismo disco) | 🔴 | A (prerequisito C) |
| 6 | Socket pathd en `~/LAIA-ARCH` ≠ declarado en config/atlas | ⚠️ | C |
| 7 | 2 `auth.json` descoordinados | 🟠 | C |
| 8 | Runtime (state.db, sessions…) en `~/LAIA-ARCH` (spec: `/srv/laia/arch`) → se **bendice** vía docs | ⚠️ | C |
| 9 | `/opt/laia` plano + leftover `laia-v0.0.0-clone` | 🟡 | (futuro) |
| 10 | Integraciones de mensajería apagadas; perfil LXD con sizing stale; máquinas viejas en tailnet | 🟢 info | — |
| 11 | No hay entorno de desarrollo aislado (dev y prod conviven) | 🟠 | B (el taller) |

---

> Snapshot verificado 2026-05-28. Pendiente de inspección con sudo: estructura interna de
> `agora.db` y listado de `/srv/laia/agora/`. El resto está verificado en disco.
