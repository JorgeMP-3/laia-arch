# LAIA — Layout en disco y contrato de migración

> Documento técnico. Detalla el **modelo objetivo** de dónde vive cada cosa en disco, con
> qué permisos, y qué cruza la red en una migración (`laia-clone`). Es la contraparte de
> implementación de la visión descrita en [`LAIA_ECOSYSTEM.md`](../LAIA_ECOSYSTEM.md)
> (§"Dónde vive todo").
>
> ⚠️ Este archivo describe el **modelo/spec (lo que debería ser)**. Para el **estado real
> en disco de este host** (con sus divergencias actuales) ver
> [`project-map.md`](project-map.md) §"Mapa del sistema completo".
>
> Si hay contradicción sobre **la idea**, gana `LAIA_ECOSYSTEM.md`; sobre **mecánica de
> disco/clone (objetivo)**, gana este archivo; sobre **qué hay realmente ahora**, gana
> `project-map.md`.
>
> Última revisión: 2026-05-27.

---

## 1. Las tres locations

El sistema tiene **tres locations** con propósitos no solapados, cada una con su
semántica de clone y sus permisos. Confundirlas lleva a `agora.db` duplicados y
`laia-clone` ambiguo (ver §3, contrato).

| Location | Qué es | Owner / modo | ¿Clona? |
|---|---|---|---|
| `/opt/laia/` | Código del producto instalado | root:laia-arch 0755 | NO — se reinstala |
| `/srv/laia/` | Datos factory operacionales (fuente de verdad) | root:laia-arch 0750 | SÍ — rsync íntegro |
| `~/laia-arch/LAIA-ARCH/` | Mesa viva interactiva del operador | laia-arch 0700 | SÍ — rsync live |
| `~/.laia/` | Credenciales sensibles del LAIA-ARCH | laia-arch 0600 | SÍ — solo 3 archivos |

---

## 2. Detalle por location

### 2.1 — `/opt/laia/` — Código del producto

Lo que se "vende" y se actualiza. Vive en `/opt` porque es software instalado a nivel
sistema, gestionado por `laia-install` / `laia-release` / `laia-rollback`.

**Modelo objetivo** (layout versionado):

```
/opt/laia/
├── current → versions/vX.Y.Z/      (symlink versionado)
├── versions/
│   └── vX.Y.Z/
│       ├── services/agora-backend/
│       ├── infra/
│       ├── bin/
│       ├── skills/                  (skills bundled del producto)
│       ├── .laia-core/              (motor, regla ⑦)
│       └── LAIA_ECOSYSTEM.md
└── data/                            (config compartida, NO datos)
```

- **Creado por:** `laia-install` en el destino.
- **NO se transfiere en clone:** el destino lo recrea desde el paquete `laia-install`.
- **Permisos:** root:laia-arch 0755.

> ⚠️ **Estado actual vs modelo (2026-05-27):** en este host `/opt/laia` es un symlink a
> `laia-vX.Y.Z` con un volcado **plano** del repo, no el layout `current → versions/`
> de arriba. El modelo versionado es el objetivo; reconciliar el estado real con la
> spec está pendiente (requiere decisión de Jorge).

#### Qué agente corre cuando Jorge teclea `laia` (¡importante!)

Hay **dos** `.laia-core` en esta máquina y conviene no confundirlos:

| | Ruta | Rol | ¿Corre por defecto? |
|---|---|---|---|
| **Producto** | `/opt/laia/.laia-core` (→ `/opt/laia-vX.Y.Z`) | Versión instalada, estable/verificada | **SÍ** |
| **Desarrollo** | `~/LAIA/.laia-core` | Donde se edita el código | No (solo fallback) |

- `laia` resuelve `/usr/local/bin/laia → /opt/laia/bin/laia`, y `exec_agent_cli`
  prefiere `/opt/laia/.laia-core/venv/bin/laia` (el de **producto**); el de dev es solo
  fallback si `/opt` no existe.
- Editar `~/LAIA/.laia-core` **no** cambia lo que corre hasta `laia release` (promueve
  dev → `/opt/laia-vX.Y.Z`). Para probar dev sin release: invocar directo
  `~/LAIA/.laia-core/venv/bin/laia`.
- **Identidad y credenciales son comunes** a ambos y salen siempre de `~/.laia/`
  (`auth.json`, `.env`, `atlas.yaml`), `~/LAIA-ARCH/` (mesa viva) y `/srv/laia/arch/`
  (runtime). NO dependen de qué código corra.
- **Regla de oro:** ejecutar `laia` **sin sudo**, como `laia-arch`. Con `sudo` corre como
  root y la config se va a `/root/.laia/` (error a evitar).

### 2.2 — `/srv/laia/` — Datos factory operacionales

Toda la verdad operacional del producto. Bind-mounted a los containers
correspondientes. Es lo que `laia-clone` rsynchea íntegro.

```
/srv/laia/
├── agora/                           ← bind mount → laia-agora:/opt/agora/data
│   ├── agora.db                     (SQLite real, fuente de verdad ÚNICA)
│   ├── atlas/
│   ├── plugins/                     (plugins instalados runtime)
│   ├── skills/                      (skills instaladas runtime, marketplace)
│   └── logs/
│
├── users/                           ← bind mounts → agent-<slug>:...
│   └── <slug>/
│       ├── home/                    → agent-<slug>:/home/user
│       ├── workspace/               → agent-<slug>:/var/lib/laia/workspace
│       └── plugins/                 → agent-<slug>:/opt/laia/plugins
│
├── arch/                            ← runtime sensible/operacional de LAIA-ARCH
│   ├── cron/                        (jobs programados)
│   ├── sessions/                    (historial de sesiones)
│   ├── sandboxes/                   (ejecución temporal / peligrosa)
│   ├── atlas/                       (snapshot de paths)
│   ├── logs/                        (logs operacionales)
│   ├── platforms/                   (estado/config de integraciones)
│   ├── orchestrator-runs/           (logs/state de orquestaciones)
│   ├── migration/                   (artefactos de migración)
│   ├── whatsapp/                    (state de WhatsApp si aplica)
│   ├── state.db                     (workspace store de Jorge ARCH)
│   ├── response_store.db            (store interno de respuestas)
│   ├── SOUL.md                      (identidad del LAIA-ARCH)
│   └── config.yaml                  (config operacional)
│
├── backups/
└── state/
```

- **Creado por:** `laia-install` crea estructura vacía. `laia-clone` rsynchea contenido
  desde origen.
- **Permisos:** root:laia-arch 0750 a nivel `/srv/laia/`; subdirs con UID/GID mapeado a
  las idmaps LXD del destino tras `clone_phase_h_fix_uid_mapping`.

### 2.3 — `~/LAIA-ARCH/` — Mesa viva de LAIA-ARCH

Datos interactivos que Jorge/LAIA-ARCH crea, edita, instala o reorganiza con
frecuencia. Owner `laia-arch`, mode 0700. Es el `LAIA_HOME` humano del operador.

```
/home/laia-arch/LAIA-ARCH/
├── workspaces/                      (workspaces personales de Jorge ARCH)
├── memories/                        (memorias persistentes editables)
├── skills/                          (skills personales que Jorge desarrolla)
└── plugins/                         (plugins personales que Jorge desarrolla)
```

**NO contiene:** sesiones, sandboxes, atlas, cron, logs, SOUL.md, config.yaml,
state.db, response_store.db, `.env`, `auth.json`. Eso vive en `/srv/laia/arch/` o en
el directorio de credenciales (§2.4).

### 2.4 — `~/.laia/` — Credenciales sensibles del LAIA-ARCH

SOLO información sensible. Mode 0600. Es el único directorio del HOME relevante para el
ecosistema. Bind-mounted readonly al container `laia-agora` para que el backend pueda
leer `auth.json` sin reescribirlo.

```
/home/laia-arch/.laia/
├── auth.json                        (canonical — providers LLM, tokens)
├── .env                             (secretos: API keys, claves de servicio)
├── atlas.yaml                       (registro Atlas v2 — refs del ecosistema)
├── config.yaml                      (paths para laia-pathd)
└── admin-session.json              (sesión activa LAIA-ARCH en AGORA)
```

**NO contiene:** workspaces, memories, skills, plugins, cron, sessions, SOUL.md,
state.db, response_store.db, mlx-servers, cache, logs, bin, checkpoints. Esos viven en
`~/LAIA-ARCH/`, `/srv/laia/arch/` o no existen (runtime regenerable).

- **Creado por:** `laia-install` inicializa con placeholders. `laia-clone` rsynchea solo
  los archivos sensibles, mode 0600.

> ℹ️ El registro **Atlas v2** (`atlas.yaml`) declara todas las coordenadas del
> ecosistema (paths, servicios, containers, sockets, env files) como referencias
> tipadas. Sustituye al "Atlas Path Registry v1" de 32 aliases planos. Ver
> `bin/atlas` (`atlas doctor`, `atlas get`, …).

### 2.5 — Lo que NO está en ningún sitio del producto

Estos archivos pueden existir en el origen pero NO forman parte de LAIA. NO se
transfieren:

- `~/mlx-servers/` o cualquier dato voice/TTS — herramientas personales del operador.
- `~/.laia/cache/`, `~/.laia/logs/`, `~/.laia/bin/`, `~/.laia/checkpoints/`,
  `~/.laia/agora.db` — runtime regenerable o placeholders dev mode.
- `~/.hermes.*`, `~/.claude-cuenta*`, `~/snap`, `~/.vscode-server` — residuos del operador.
- Containers LXD legacy (naming viejo, stopped sin uso) — el filtro
  `clone_phase_h_enumerate_slugs` solo enumera slugs presentes en `agora.db`.

---

## 3. Contrato de transferencia `laia-clone`

Tabla canónica de qué cruza la red en una migración:

| Recurso | Transferido | Mecanismo | Notas |
|---------|-------------|-----------|-------|
| `/opt/laia/` | NO | `laia-install` recrea en destino | Versionado limpio |
| `/srv/laia/agora/` | **SÍ** | rsync íntegro | Incluye `agora.db` (fuente única) |
| `/srv/laia/users/<slug>/{home,workspace,plugins}` | **SÍ** | rsync por slug enumerado de `agora.db` | UID/GID re-mapeados |
| `/srv/laia/arch/` | **SÍ** | rsync sensible/runtime | SOUL, config, sessions, sandboxes, atlas, cron, logs, DBs internas |
| `~/LAIA-ARCH/{workspaces,memories,skills,plugins}` | **SÍ** | rsync live ARCH | Zona editable/interactiva del operador |
| `/srv/laia/backups/`, `/srv/laia/state/` | **SÍ** | rsync íntegro | |
| `~/.laia/auth.json` | **SÍ** | rsync único archivo, mode 0600 | Canonical |
| `~/.laia/.env` | **SÍ** | rsync único archivo, mode 0600 | Secretos |
| `~/.laia/admin-session.json` | OPCIONAL | rsync con flag `--keep-session` | Por defecto NO; obliga relogin |
| `~/.laia/<cualquier otro>` | NO | — | mlx-servers, cache, logs, agora.db huérfano |
| `~/<resto del HOME>` | NO | — | No es producto LAIA |
| Containers vía `lxc export/import` | NO | — | Rompe arm64↔amd64; se reconstruyen locales |
| Snapshots LXD legacy | NO | — | No enumerados |

> ⚠️ **Trampa conocida (migración hermes→arch):** el código fuente gitignored dentro de
> `.laia-core/` (p.ej. el paquete `cron/`, `SOUL.md`, `skills/`) NO viaja con un clone
> basado en git, porque `.gitignore` lo excluye. Si una máquina nueva pierde el agente
> CLI con `ModuleNotFoundError: cron`, recupéralo de la VM original con
> `rsync --ignore-existing` y considéralo force-added (`git add -f`).

---

## 4. Flujo `laia-install` (producto comercial)

```
Cliente con Ubuntu limpio
  │
  ├─ laia-install (Fase B: bare infra: paquetes, usuario laia-arch, /opt/laia)
  ├─ laia-install (Fase G: LXD init + container laia-agora + base-skills + auth admin)
  └─ Resultado: factory-default vivo, listo para alta de empleados via UI
```

---

## 5. Flujo `laia-clone` (migración entre máquinas — PULL pattern)

**Patrón pull:** `laia-clone` se ejecuta EN el servidor nuevo (destino), apuntando con
`--source` al viejo (origen). El nuevo se autoinstala primero y luego tira los datos del
viejo por SSH. NUNCA se ejecuta desde el origen empujando hacia el destino.

**Por qué pull y no push:**
- El destino tiene que tener LAIA al final → coherente con que `laia-install` corra
  primero ahí (lo invoca el propio clone si `/opt/laia` no existe).
- `boot_detect_arch` detecta la arch del host donde corre. En pull, detecta la del
  destino — correcto para reconstruir containers locales.
- Cross-arch (arm64 origen → amd64 destino) funciona porque la reconstrucción se hace en
  el destino con su arch nativa.
- Terminas logueado en el destino, listo para configurar nginx/dominio sin volver al origen.

**Path remapping en transit:** el origen puede tener layout dev (datos del ARCH en
`~/.laia/`) o layout factory (`/srv/laia/arch/` + `~/LAIA-ARCH/`). El clone normaliza
siempre al layout factory en destino:

- `workspaces`, `memories`, `skills`, `plugins` → `~/LAIA-ARCH/`.
- `SOUL.md`, `config.yaml`, `sessions`, `sandboxes`, `atlas`, `cron`, `logs`, DBs internas
  y runtime sensible → `/srv/laia/arch/`.
- Credenciales (`auth.json`, `.env`) → `~/.laia/` mientras AGORA siga montándolas desde ahí.

```
Viejo (origen, contactado por SSH)        Nuevo (destino, ejecuta el comando)
                                                │
                                          1. laia-install --minimal (auto-invocado
                                             si /opt/laia no existe)
                                                │
  /srv/laia/agora/         ◄── rsync ─── /srv/laia/agora/
  /srv/laia/users/<slug>/  ◄── rsync ─── /srv/laia/users/<slug>/
                                                │
  Datos LAIA-ARCH (con remap):
    /srv/laia/arch/  (si existe)  ◄─ rsync ─► /home/laia-arch/LAIA-ARCH/<live-dir>
    o ~/.laia/{...}                            /srv/laia/arch/<runtime-dir>
                                               (+ rewrite paths: en config.yaml)
                                                │
  Credenciales sensibles:
    ~/.laia/auth.json       ◄── rsync ─── /home/laia-arch/.laia/auth.json (0600)
    ~/.laia/.env            ◄── rsync ─── /home/laia-arch/.laia/.env (0600)
                                                │
                                          2. rebuild-3-provision-agora.sh (arch nativa)
                                          3. rebuild-4-first-user.sh --existing-user-only
                                             (por cada slug en agora.db)
                                          4. clone_phase_h_fix_uid_mapping
                                          5. smoke: health, login, users, skills
```

**Comando concreto que se ejecuta en el nuevo:**
```bash
nuevo$ sudo laia-clone --source laia-hermes@viejo.local --yes --bwlimit=50M
```

**Por qué path-remapping en lugar de mover datos en origen:** modificar los paths en
origen requiere refactor de `infra/pathd/`, `services/agora-backend/`, `config.yaml` y
otros componentes, rompiendo el LAIA operativo de la máquina de desarrollo. El clone-time
remap es no invasivo y consistente con la decisión D4 ("no movemos el origen, optimizamos
el destino").

Reglas relacionadas (de `LAIA_ECOSYSTEM.md`): ⑤ (LAIA-ARCH y LAIA-AGORA independientes),
⑦ (`.laia-core/` solo en host y `laia-agora`), ⑨ (a usuarios decir "LAIA"), ⑩ (LAIA-ARCH
invisible para usuarios).
