# LAIA — Estado actual, siguientes pasos y posibles integraciones

> **Fecha:** 2026-05-30 · **Autor:** Claude (Opus 4.8, rol Lead).
> Snapshot consolidado al **cierre de la estabilización** (slices B1–D2) y corte del release
> **v0.2.0**. Complementa, no sustituye:
> - **Idea/visión** → [`../../LAIA_ECOSYSTEM.md`](../../LAIA_ECOSYSTEM.md) (canónico).
> - **Spec de disco/permisos** → [`../arch-layout.md`](../arch-layout.md) (lo que *debe* ser).
> - **Mapa real en el host** → [`../project-map.md`](../project-map.md).
> - **Bitácora de cambios** → [`../changelog.md`](../changelog.md) (entradas 2026-05-29/30).
> - **Plan/checklist de estabilización** → [`estabilizacion/slices.md`](estabilizacion/slices.md).
>
> Marcas: ✅ hecho/verificado · 🟡 listo pero pendiente de ventana · 🔴 bloqueado · 🧪 propuesta.

---

## 1. Estado actual

### 1.1 Estabilización — **completa** (AFK)

Las 8 piezas del plan están mergeadas a `main` y verificadas:

| Slice | Qué | Estado |
|---|---|---|
| **B1** | VM de desarrollo `laia-dev` (LXD anidado, Tailscale) | ✅ #18 |
| **C1** | Anclas del ARCH → `/srv/laia/arch` (`LAIA_CONFIG_HOME`) | ✅ #19 |
| **C2** | Secretos vía `raw.idmap`, `auth.json` **0600** (cierra el 644) | ✅ #21 |
| **state-root** | `agents.json` se queda en `/srv/laia/state` (orquestación AGORA, no ARCH) | ✅ `66faa4d6` |
| **C3** | Script de migración in-place v1→v2 (idempotente, add-before-remove, rollback) | ✅ #22 |
| **C4** | Instalador "nace en layout v2" (install-native) | ✅ #24 · gate 19/19 |
| **D1** | Backups permanentes (`agora.db`+`users`+`arch`→`/mnt/data/laia-backups`) + timer nocturno | ✅ #25 · gate 11/11 |
| **D2** | Suite de integridad end-to-end del ecosistema (6 capas) | ✅ #26/#27 · verde en VM |

**Release `v0.2.0`** cortado: `main → stable` (fast-forward de 84 commits) + tag, empujado.
Tags previos: v0.1.0–v0.1.2.

### 1.2 Dónde está qué — mapa de despliegue

| Lugar | Rama / versión | Layout | Estado |
|---|---|---|---|
| `origin/stable` | **v0.2.0** | — | ✅ release publicado |
| `origin/main` | adelante de stable (refinamiento D2) | — | ✅ desarrollo |
| **Host prod** (este ThinkStation) | `/opt/laia-`**`v0.11.0`** (era-Hermes) | **v1** (`~/.laia`) | 🔴 **sin migrar** — AGORA real corre en el container `laia-agora` (RUNNING) + agentes `agent-*`; servicios systemd del host inactivos |
| **VM `laia-dev`** | install limpio **v0.2.0** | **v2** | ✅ validado — **D2 verde** (9 PASS / 0 FAIL) |

> ⚠️ **Punto clave:** el host de prod **sigue en layout v1** y corre una versión era-Hermes
> (`v0.11.0`). El código v0.2.0 **asume v2** (`/srv/laia/arch`). **No se puede desplegar v0.2.0 a
> prod sin migrar antes a v2** (rompería `laia-pathd`). Ver §2.1.

### 1.3 Qué introduce el layout v2

- **Secretos** en `/srv/laia/arch/secrets/` (`0700`, ficheros `0600`), leídos por `laia-agora`
  vía `raw.idmap` (mapeo uid host↔container) — **sin** `chmod 644` world-readable. `~/.laia/` se elimina.
- **Runtime del ARCH** (`config.yaml`, `atlas.yaml`, `.env.paths`, `state/` del resolver) en `/srv/laia/arch/`.
- **`agents.json`** (state del orquestador AGORA) en `/srv/laia/state` (top-level, no bajo `arch/`).
- **Backups** a `/mnt/data/laia-backups` (otro disco) con timer nocturno + retención 14 días.
- **D2** valida las 6 capas (host → LXD → AGORA → executors → datos 2 zonas → Atlas + backups).

### 1.4 Verificación

- **D2 verde** en la VM tras install factory limpio v0.2.0: `atlas doctor` sin refs rotas, secrets
  0700/0600, `/api/health ok`, `agora.db integrity ok`. Confirmado que el deploy v0.2.0 sobre v2
  produce un ecosistema sano.
- Gates de C4 (19/19) y D1 (11/11) verdes; suite installer 33/33; backend pytest 363.

---

## 2. Siguientes pasos

### 2.1 Ventana de prod (HITL — decisión/ventana de Jorge) 🟡

Secuencia validada en la VM; aplicar a prod en una ventana planificada (usuarios reales):

1. **Migrar prod a v2** — `infra/lxd/scripts/migrate-v1-to-v2.sh` (runbook:
   [`estabilizacion/c3-migration-runbook.md`](estabilizacion/c3-migration-runbook.md)).
   `--dry-run` primero → backup one-shot + `lxc snapshot` → `raw.idmap` + secretos a
   `/srv/laia/arch/secrets` → verify `/api/health` → en verde retira `~/.laia`. Rollback en cada paso.
2. **Desplegar v0.2.0** — `sudo laia-release` (con los follow-ups de §2.2: `safe.directory`,
   `--skip-frontend` o `pnpm build`).
3. **Completar layout operacional** — `setup-prod-dirs.sh` (crea `/srv/laia/state`, etc.).
4. **D2 verde total** en prod + smoke (login + chat).
5. **B2** — reconvertir `~/LAIA` del host a checkout pristino de `stable` (premisa: dev movido a la VM).

### 2.2 Follow-ups del runbook de deploy v2 (AFK, mejoran robustez antes de prod)

1. `laia-release` corre como root → necesita `git config --global --add safe.directory <repo>`
   (o que el propio script lo añada).
2. Smoke `test_flags.sh` falla en `laia-rollback --dry-run` con **<2 versiones** en `/opt`
   (benigno en el primer deploy; prod tiene ≥2). Relajar el assert.
3. `laia-release` exige artefactos de **frontend** (`laia-ui` dist) o `--skip-frontend`.
4. `laia-install` **no crea** `/srv/laia/{state,users}` — los crea `setup-prod-dirs.sh` (paso
   separado). Considerar que el install los cree (factory completo en un paso).
5. `setup-prod-dirs.sh` crea `/srv/laia/agents` (nombre viejo) en vez del canónico
   `/srv/laia/users` (`arch-layout.md` §2.2). Reconciliar.

### 2.3 Más adelante

- **D5b — backup off-site**: destino removible USB `VM-USB` (`/dev/sdb1`), reservado para esto.
- **Limpieza git**: borrar ramas `wip/*` ya mergeadas en `origin`.
- **Versionado**: alinear el esquema de `/opt/laia-vX.Y.Z` (era-Hermes dejó `v0.11.0`) con los
  tags LAIA (`v0.2.0`); tras la migración `laia-rollback` apuntará al install viejo.

---

## 3. Posibles integraciones

> Fundamentado en lo que **ya existe** en `.laia-core/gateway/platforms/`, el marketplace de
> `skills/` y los providers de `laia_cli/auth.py`. **Cada integración nueva pasa por el protocolo
> FASE** (grill → PRD → vertical slices → TDD) antes de construirse; esto es un menú, no un compromiso.

### 3.1 Canales de mensajería (vía el **gateway**, `.laia-core/gateway/platforms/`)

El gateway expone una **API OpenAI-compatible** (`gateway_api`) y adaptadores por plataforma.
Estado de lo que ya está referenciado/implementado:

| Canal | Estado actual | Para producirlo |
|---|---|---|
| **Telegram** | ✅ real (`services/agora-backend/app/telegram_gateway.py`, con tests; `AGORA_TELEGRAM_TOKEN`) | activar/configurar token por despliegue |
| **WhatsApp** | 🟡 puente Node.js (`whatsapp_bridge`) referenciado | levantar el bridge + verificar e2e |
| **Signal** | 🟡 `signal_cli` daemon HTTP referenciado | desplegar signal-cli + adaptador |
| **Feishu (Lark)** | 🟡 `feishu_webhook` receptor referenciado | endpoint público + verificación |
| **BlueBubbles / iMessage** | 🟡 `bluebubbles_webhook` referenciado | server BlueBubbles + webhook |
| 🧪 **Discord / Slack / Matrix / Email** | propuesta (no existe aún) | nuevo adaptador en `gateway/platforms/` |

> Verificar el estado real de implementación de cada 🟡 antes de prometerlo (varios pueden ser
> stub/parcial). El patrón está: cada canal es un adaptador que habla con el gateway.

### 3.2 Providers LLM

Ya soportados en `auth.py`: **OpenAI/Codex, Anthropic, OpenRouter, Gemini, DeepSeek, Nous,
Ollama (local), Z.AI**. 🧪 Ampliables (Groq, Mistral, etc.) y enrutado/fallback por coste/latencia.

### 3.3 Conectores **MCP** (Model Context Protocol)

Existe `mcp_serve.py` + categoría `skills/mcp/`. 🧪 Oportunidad: exponer/consumir servidores MCP
para conectar herramientas externas a los PA-AGORA de forma estándar.

### 3.4 Skills / marketplace

Ya sembradas: **Notion, Linear, Google Workspace, Airtable, GitHub Issues, Maps, arXiv, OCR/PDF,
workspace-read**. Categorías presentes: apple, devops, mlops, media, email, feeds, data-science,
diagramming, creative, gaming… 🧪 Expansión natural por demanda de usuarios (CRM, pagos,
calendarios, almacenamiento, etc.), publicadas vía el marketplace.

### 3.5 Capacidades del agente personal (PA-AGORA)

Skills de plataforma ya presentes: **agent-self-edit, agent-learning, agent-scheduler,
agent-delegation**. 🧪 Profundizar: memoria a largo plazo, delegación entre agentes, jobs
programados (cron del agente), self-improvement con barreras.

---

## 4. Resumen de una línea

Estabilización **terminada** y **v0.2.0 en `stable`**; falta **una ventana de prod** (migrar v1→v2
→ desplegar → B2) y, opcionalmente, **ampliar integraciones** (canales, MCP, skills) sobre la base
del gateway que ya existe.
