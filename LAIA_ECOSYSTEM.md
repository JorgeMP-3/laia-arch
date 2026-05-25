# LAIA Ecosystem — El Documento Definitivo

> 📅 v1.1 — 2026-05-21 — añadida §8 Layout en disco + contrato `laia-clone`; renumerado roadmap a §9

---

## 1. Visión

**LAIA es un ecosistema de agentes de IA personales.**

LAIA es el ser supremo. Un ente que tiene distintos **medios de expresión**
para interactuar con el mundo. Dos de esos medios son:

- **LAIA-ARCH** — su expresión como administrador. Vive en el host.
  Solo Jorge lo ve. Controla la infraestructura. El ser superior en las sombras.
  **Los usuarios nunca ven ni interactúan con LAIA-ARCH.**

- **LAIA-AGORA** — su expresión como plataforma multi-usuario.
  Vive en un container. Da servicio a todos los PA-AGORA.
  El cerebro centralizado que piensa por todos.
  **Para los usuarios, esto es simplemente "LAIA".**

Dentro de LAIA-AGORA habitan los **PA-AGORA** (Personal Agent AGORA): asistentes
individuales que cada usuario configura a su gusto. Tienen nombre propio,
personalidad propia, y viven en containers privados donde el usuario es root.

### Cómo llamamos a las cosas

| Interno (devs) | Usuario ve | Descripción |
|----------------|------------|-------------|
| **LAIA-ARCH** | *(invisible)* | El administrador del host. Solo Jorge. |
| **LAIA-AGORA** | **LAIA** | La plataforma. El coordinador. "Chatear con LAIA". |
| **PA-AGORA** | "Mi agente", "Nombrix" | El agente personal de cada usuario. |

Cada persona tiene su propio agente. Vive en su propio contenedor privado.
Tiene el nombre que esa persona elige. Tiene la personalidad que esa persona
le da. Ejecuta las tareas que esa persona le pide. Y nadie más puede usarlo.

Imagina un edificio de oficinas. En cada despacho hay un asistente personal
trabajando para su jefe. Los asistentes no se meten en el despacho de otro.
Pero todos comparten una recepción común donde pueden consultar información
compartida y coordinarse entre ellos.

Eso es LAIA.

---

## 2. Arquitectura

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ HOST (el edificio)                                                            │
│                                                                               │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ 🧠 LAIA-AGORA — El cerebro centralizado                                   │  │
│ │                                                                           │  │
│ │ Container LXD: `laia-agora`                                               │  │
│ │                                                                           │  │
│ │ Aquí vive la inteligencia que comparten todos los agentes:                │  │
│ │   • El motor .laia-core (el cerebro)                                      │  │
│ │   • LAIA-AGORA Backend (la API que lo conecta todo)                            │  │
│ │   • El Pool de Agentes (una instancia de IA por cada sesión de chat)    │  │
│ │   • El Marketplace (tienda de plugins y skills)                           │  │
│ │   • El Control Center (panel de administración)                           │  │
│ │   • La base de datos central (usuarios, agentes, configuración)          │  │
│ │                                                                           │  │
│ │ Cuando un usuario chatea con su agente, el LLM razona AQUÍ.               │  │
│ │ Cuando necesita ejecutar algo en el despacho del usuario,                  │  │
│ │ se lo envía por HTTP al executor.                                         │  │
│ └───────────────────────────┬───────────────────────────────────────────────┘  │
│                             │ HTTP (puente interno LXD)                        │
│ ┌───────────────────────────▼───────────────────────────────────────────────┐  │
│ │ PA-AGORA(containers LXD)                                                      │  │
│ │                                                                             │  │
│ │ Container: `agent-jorge`          Container: `agent-maria`                  │  │
│ │ ┌─────────────────────────┐      ┌─────────────────────────┐                │  │
│ │ │ Agente: "Nombrix"       │      │ Agente: "MariaBot"      │                │  │
│ │ │                         │      │                         │                │  │
│ │ │ • Root total             │      │ • Root total             │                │  │
│ │ │ • Sin restricciones      │      │ • Sin restricciones      │                │  │
│ │ │ • Workspace privado      │      │ • Workspace privado      │                │  │
│ │ │ • Archivos personales    │      │ • Archivos personales    │                │  │
│ │ │ • Plugins propios        │      │ • Plugins propios        │                │  │
│ │ │                         │      │                         │                │  │
│ │ │ El executor recibe       │      │ El executor recibe       │                │  │
│ │ │ órdenes de LAIA          │      │ órdenes de LAIA          │                │  │
│ │ │ y las ejecuta aquí.     │      │ y las ejecuta aquí.     │                │  │
│ │ └─────────────────────────┘      └─────────────────────────┘                │  │
│ └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────────┐  │
│ │ 👑 LAIA-ARCH — El ser superior que habita en las sombras                   │  │
│ │                                                                                                │  │
│ │ En el host, fuera de los containers. Solo Jorge lo usa.                                        │  │
│ │                                                                                                │  │
│ │ LAIA-ARCH tiene TODAS las herramientas del ecosistema (71 tools).             │  │
│ │ Es el agente más poderoso. Ningún usuario lo ve.                                │  │
│ │ Pero LAIA-ARCH sí ve a todos los usuarios, sus containers, sus workspaces.      │  │
│ │                                                                                                │  │
│ │ Gestiona la infraestructura: LXD, nginx, systemd, backups, deploy.                             │  │
│ │ NO es parte de LAIA-AGORA — es el administrador del host.                                           │  │
│ └────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────
```

---

## 3. Las tres entidades del ecosistema

### LAIA-AGORA — El coordinador autónomo

LAIA-AGORA no es una persona. Es un **agente autónomo** que coordina el ecosistema.
Vive en el container `laia-agora`. Es el cerebro centralizado que piensa por todos.

- Los empleados pueden chatear con él para preguntar sobre información compartida.
- Tiene un toolset restringido: consultas a workspaces compartidos, estado de agentes, mensajes.
- Gestiona empleados, aprueba plugins, asigna tareas, ve workspaces de todos.
- **NO** ejecuta herramientas en su propio container (el código base está ahí).
- **NO** tiene `agent_self`, `agent_scheduler`, ni `agent_delegation`.
- **NO** gestiona la infraestructura del host (eso es LAIA-ARCH).
- Para los usuarios, LAIA-AGORA es simplemente **"LAIA"**.

### Empleado (usuario normal)

- Tiene su propio PA-AGORA con nombre y personalidad propia.
- Chatea con su agente para tareas personales, trabajo, automatización.
- Su agente ejecuta herramientas dentro de SU container (archivos, comandos, código).
- Instala plugins y skills desde el Marketplace.
- Configura su propia API key de LLM (DeepSeek, OpenAI, etc).
- Puede chatear con LAIA (el coordinador) para preguntar sobre información compartida.
- Ve los workspaces compartidos a los que tiene acceso.
- **NO** ve los agentes de otros usuarios.
- **NO** ve el código base (está en `laia-agora`, no en su container).
- **NO** sabe que LAIA-ARCH existe. Para el usuario, "LAIA" es LAIA-AGORA.

### LAIA-ARCH (Jorge — el ser superior en las sombras)

- **Solo Jorge** tiene acceso. Ningún usuario sabe que existe.
- Tiene las **71 herramientas** del ecosistema + herramientas administrativas del host.
- **Ve a todos los usuarios**, containers, workspaces, tareas. Los usuarios no lo ven a él.
- Vive en el host, fuera de los containers. Tiene `.laia-core/` propio.
- Gestiona infraestructura: LXD, systemd, nginx, Cloudflare, red, deploy.
- Ejecuta `laia-install` y `laia-clone` para desplegar y migrar.

---

## 4. Flujo de un chat con el PA-AGORA

```
1. Usuario escribe en el chat: "Crea un script que me diga buenos días"

2. El mensaje viaja a LAIA-AGORA Backend (laia-agora)
   → POST /api/agents/me/chat

3. AGORA busca al usuario en la base de datos
   → "Este es Jorge, su agente se llama Nombrix, su container es agent-jorge"

4. AGORA crea (o reutiliza) una instancia de IA para esta sesión
   → AgentPool.get_or_create(session_id)
   → Carga el soul de Nombrix: "Soy Nombrix, PA-AGORA de Jorge..."
   → Carga la API key de LLM que Jorge configuró (DeepSeek)
   → Crea el AIAgent con 71 herramientas disponibles

5. El LLM razona
   → "Necesito crear un archivo. Voy a usar la herramienta write_file"

6. AGORA intercepta la llamada a write_file
   → "Esta herramienta se ejecuta en el container del usuario"
   → Tool Forwarder: POST http://agent-jorge:9091/exec
   → Body: {tool: "write_file", args: {path: "/home/jorge/buenos_dias.sh", content: "..."}}

7. El executor en agent-jorge recibe la orden
   → Ejecuta write_file como root (sin restricciones)
   → El archivo se crea en /home/jorge/buenos_dias.sh
   → Responde: {ok: true, path: "/home/jorge/buenos_dias.sh"}

8. AGORA recibe la confirmación
   → El LLM continúa: "Perfecto, he creado el script. ¿Quieres que lo ejecute?"
   → Respuesta final via SSE streaming

9. El usuario ve la respuesta en el chat
   → "He creado el archivo buenos_dias.sh en tu carpeta personal."
```

### Flujo de un chat con LAIA (coordinador)

```
1. Usuario cambia al modo LAIA en el chat y pregunta:
   "¿Qué tareas tiene Maria pendientes?"

2. El mensaje viaja a AGORA → POST /api/laia/chat

3. AGORA reconoce que es un chat con LAIA
   → Toolset restringido: solo tools de coordinación
   → Mismo container del usuario (agent-jorge)
   → Misma API key del usuario

4. El LLM razona con el system prompt de LAIA:
   "Eres LAIA, la coordinadora del ecosistema LAIA-AGORA..."

5. LAIA decide usar: laia_list_users + agent_status_fleet
   → Consulta la base de datos de LAIA-AGORA
   → "Maria tiene 3 tareas pendientes: revisar PR #42, actualizar docs, probar endpoint nuevo"

6. Respuesta via streaming al usuario
```

---

## 5. Reglas duras del ecosistema

Estas reglas **no se negocian**. Definen la arquitectura.

### Reglas de propiedad

- **①** Cada usuario tiene UN PA-AGORA. No comparte agente con nadie.
- **②** El nombre del agente lo elige el usuario. "LAIA" está reservado para el coordinador.
- **③** El container del usuario es SU espacio. Él es root. Sin sandbox, sin restricciones.
- **④** Los archivos del usuario sobreviven aunque el container se destruya (bind mounts en `/srv/laia/users/`).

### Reglas de separación

- **⑤** LAIA-ARCH y LAIA-AGORA son independientes. El admin de LAIA-AGORA no es admin de LAIA-ARCH.
- **⑥** El admin de LAIA-AGORA no accede al código base de LAIA-AGORA. No hace `lxc exec`. No gestiona infraestructura.
- **⑦** `.laia-core/` solo existe en el host (para LAIA-ARCH) y en `laia-agora` (para LAIA-AGORA). NUNCA en containers de usuario.
- **⑧** El usuario nunca ve el código de `.laia-core/`. Su container no lo contiene.

### Reglas de naming (cara al usuario)

- **⑨** Para los usuarios, LAIA-AGORA es simplemente **"LAIA"**. Nunca le digas "LAIA-AGORA" a un usuario.
- **⑩** LAIA-ARCH es **invisible** para los usuarios. No saben que existe. No necesitan saberlo.
- **⑪** Los PA-AGORA son simplemente **"tu agente"** o el nombre que el usuario le puso ("Nombrix").

### Reglas del coordinador

- **⑫** LAIA (el coordinador) no es un agente separado. Es un modo de chat con toolset restringido.
- **⑬** LAIA nunca ejecuta herramientas en `laia-agora`. Siempre en el container del usuario que llama.
- **⑭** LAIA no se auto-modifica. No tiene acceso a `agent_self`, `agent_scheduler`, ni `agent_delegation`.

---

## 6. Componentes del ecosistema

### Dentro de LAIA-AGORA (container `laia-agora` — el cerebro)

| Componente | Propósito |
|------------|-----------|
| **.laia-core/** | Motor del agente: run_agent.py, AIAgent, 71 herramientas, gateway multi-plataforma |
| **LAIA-AGORA Backend** | API REST (80+ endpoints). Auth JWT, gestión de usuarios, chat, marketplace |
| **AgentPool** | Pool de instancias AIAgent. Una por sesión de chat. TTL 60 minutos |
| **Tool Forwarder** | Plugin que intercepta tool calls del LLM y las envía al container del usuario |
| **Marketplace** | Tienda de plugins y skills. Publicar, aprobar, instalar |
| **Control Center** | API de administración: estado del sistema, logs, auditoría, jobs |
| **LAIA Coordinator** | Modo de chat con toolset de coordinación para consultas compartidas |
| **Scheduler** | Ejecuta tareas programadas (cron) y decay de aprendizajes |
| **Webhooks** | Recibe triggers externos con autenticación HMAC |
| **Usage Ledger** | Tracking de tokens y coste por llamada al LLM |
| **agora.db** | Base de datos SQLite con 15+ tablas (usuarios, agentes, plugins, aprendizajes...) |

### PA-AGORA dentro de LAIA-AGORA (el executor)

| Componente | Propósito |
|------------|-----------|
| **laia-executor** | Microservicio FastAPI (:9091). Recibe tool calls del cerebro y las ejecuta |
| **Herramientas (22)** | read_file, write_file, bash, python_exec, procesos, cron, workspace privado... |
| **Workspace privado** | Base de datos SQLite personal del usuario |
| **Archivos personales** | Bind mount persistente desde `/srv/laia/users/{slug}/home/` |
| **Plugins propios** | Plugins instalados por el usuario desde el Marketplace |

### En el host (infraestructura)

| Componente | Propósito |
|------------|-----------|
| **LXD** | Hipervisor de contenedores. Gestiona laia-agora y los agent-{slug} |
| **nginx** | Proxy inverso. Internet → LAIA-AGORA, servicios web |
| **systemd** | Gestión de servicios. laia-gateway, laia-pathd |
| **Atlas Path Registry** | DNS de archivos. 32 aliases. Resuelve rutas sin hardcodear |
| **WorkspaceStore** | Librería compartida SQLite + FTS5 para todos los workspaces |

---

## 7. Workspaces y conocimiento compartido

LAIA no es solo un chat. Es un sistema de conocimiento.

### Workspace colectivo (AGORA)

Un workspace compartido donde vive la información de la plataforma:
- Documentación del ecosistema
- Decisiones de arquitectura
- Guías para desarrolladores
- Estado de los proyectos

Todos los usuarios pueden leerlo. El admin LAIA-AGORA puede editarlo.

### Workspace privado (cada usuario)

Cada usuario tiene su propio workspace personal. Solo él puede verlo y editarlo.
Aquí guarda sus notas, aprendizajes, y conocimiento privado.

### Workspaces compartidos

Los usuarios pueden compartir workspaces entre sí. María puede compartir
su workspace "proyecto-alpha" con Jorge. LAIA puede buscar en workspaces
compartidos cuando un usuario le pregunta.

### LAIA como coordinador de conocimiento

Cuando un empleado pregunta a LAIA:
- "¿Quién está trabajando en el proyecto Alpha?"
- "¿Qué decisiones se tomaron sobre la API de usuarios?"
- "¿Cuántas tareas completó Maria esta semana?"

LAIA consulta los workspaces compartidos, la base de datos de LAIA-AGORA,
y responde con la información agregada. No accede a datos privados
de usuarios sin permiso.

---

## 8. Layout del sistema en disco

> 📅 Sección añadida 2026-05-21 — Define las locations definitivas y el contrato de `laia-install` / `laia-clone`. Reemplaza cualquier referencia previa a `~/.laia/` como home operacional de LAIA-ARCH.

El sistema tiene **tres locations** con propósitos no solapados. Cada una con su semántica de clone y sus permisos. Confundirlas lleva a `agora.db` duplicados y `laia-clone` ambiguo (ver §8.6 contrato).

### 8.1 — `/opt/laia/` — Código del producto

Lo que se "vende" y se actualiza. Vive en `/opt` porque es software instalado a nivel sistema, gestionado por `laia-install` / `laia-release` / `laia-rollback`.

```
/opt/laia/
├── current → versions/v2.5.X/      (symlink versionado)
├── versions/
│   └── v2.5.X/
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

### 8.2 — `/srv/laia/` — Datos factory operacionales

Toda la verdad operacional del producto. Bind-mounted a los containers correspondientes. Es lo que `laia-clone` rsynchea íntegro.

```
/srv/laia/
├── agora/                           ← bind mount → laia-agora:/opt/agora/data
│   ├── agora.db                     (SQLite real, 20 tablas, fuente de verdad ÚNICA)
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

- **Creado por:** `laia-install` crea estructura vacía. `laia-clone` rsynchea contenido desde origen.
- **Permisos:** root:laia-arch 0750 a nivel `/srv/laia/`, subdirs con UID/GID mapeado a las idmaps LXD del destino tras `clone_phase_h_fix_uid_mapping`.

### 8.3 — `/home/laia-arch/LAIA-ARCH/` — Mesa viva de LAIA-ARCH

Datos interactivos que Jorge/LAIA-ARCH crea, edita, instala o reorganiza con frecuencia.
Owner `laia-arch`, mode 0700. Es el `LAIA_HOME` humano del operador.

```
/home/laia-arch/
└── LAIA-ARCH/
    ├── workspaces/                  (workspaces personales de Jorge ARCH)
    ├── memories/                    (memorias persistentes editables)
    ├── skills/                      (skills personales que Jorge desarrolla)
    └── plugins/                     (plugins personales que Jorge desarrolla)
```

**NO contiene:** sesiones, sandboxes, atlas, cron, logs, SOUL.md, config.yaml,
state.db, response_store.db, `.env`, `auth.json`. Eso vive en `/srv/laia/arch/`
o en el directorio de credenciales legacy de §8.4.

### 8.4 — `/home/laia-arch/.laia/` — Credenciales sensibles del LAIA-ARCH

SOLO información sensible. Mode 0600. Es el único directorio del HOME relevante para el ecosistema LAIA. Bind-mounted readonly al container `laia-agora` para que el backend pueda leer `auth.json` sin reescribirlo.

```
/home/laia-arch/
└── .laia/
    ├── auth.json                    (canonical — providers LLM, tokens)
    ├── .env                         (secretos: API keys, claves de servicio)
    └── admin-session.json           (sesión activa LAIA-ARCH en AGORA)
```

**NO contiene:** workspaces, memories, skills, plugins, cron, sessions, SOUL.md,
state.db, response_store.db, config.yaml, mlx-servers, cache, logs, bin,
checkpoints. Esos viven en `/home/laia-arch/LAIA-ARCH/`, `/srv/laia/arch/` o
no existen (runtime regenerable).

- **Creado por:** `laia-install` inicializa con placeholders. `laia-clone` rsynchea sólo los 3 archivos sensibles, mode 0600.

### 8.5 — Lo que NO está en ningún sitio del producto

Estos archivos pueden existir en el origen pero NO forman parte de LAIA. NO se transfieren:

- `~/mlx-servers/` o cualquier dato voice/TTS — herramientas personales del operador, fuera del producto.
- `~/.laia/cache/`, `~/.laia/logs/`, `~/.laia/bin/`, `~/.laia/checkpoints/`, `~/.laia/agora.db` — runtime regenerable o placeholders dev mode.
- `~/.hermes.*`, `~/.claude-cuenta*`, `~/snap`, `~/.vscode-server` — residuos del operador, no del producto.
- Containers LXD legacy (`laia-<slug>` con naming viejo, containers stopped sin uso) — el filtro `clone_phase_h_enumerate_slugs` solo enumera slugs presentes en `agora.db`.

### 8.6 — Contrato de transferencia `laia-clone`

Tabla canónica de qué cruza la red en una migración:

| Recurso | Transferido | Mecanismo | Notas |
|---------|-------------|-----------|-------|
| `/opt/laia/` | NO | `laia-install` recrea en destino | Versionado limpio |
| `/srv/laia/agora/` | **SÍ** | rsync íntegro | Incluye `agora.db` (fuente única) |
| `/srv/laia/users/<slug>/{home,workspace,plugins}` | **SÍ** | rsync por slug enumerado de `agora.db` | UID/GID re-mapeados |
| `/srv/laia/arch/` | **SÍ** | rsync sensible/runtime | SOUL, config, sessions, sandboxes, atlas, cron, logs, DBs internas |
| `/home/laia-arch/LAIA-ARCH/{workspaces,memories,skills,plugins}` | **SÍ** | rsync live ARCH | Zona editable/interactiva del operador |
| `/srv/laia/backups/`, `/srv/laia/state/` | **SÍ** | rsync íntegro | |
| `~/.laia/auth.json` | **SÍ** | rsync único archivo, mode 0600 | Canonical |
| `~/.laia/.env` | **SÍ** | rsync único archivo, mode 0600 | Secretos |
| `~/.laia/admin-session.json` | OPCIONAL | rsync con flag `--keep-session` | Por defecto NO; obliga relogin en destino |
| `~/.laia/<cualquier otro>` | NO | — | mlx-servers, cache, logs, agora.db huérfano |
| `~/<resto del HOME>` | NO | — | No es producto LAIA |
| Containers vía `lxc export/import` | NO | — | Rompe arm64↔amd64; se reconstruyen locales |
| Snapshots LXD legacy | NO | — | No enumerados |

### 8.7 — Flujo `laia-install` (producto comercial)

```
Cliente con Ubuntu limpio
  │
  ├─ laia-install (Fase B: bare infra: paquetes, usuario laia-arch, /opt/laia)
  ├─ laia-install (Fase G: LXD init + container laia-agora + base-skills + auth admin)
  └─ Resultado: factory-default vivo, listo para alta de empleados via UI
```

### 8.8 — Flujo `laia-clone` (migración entre máquinas — PULL pattern)

**Patrón pull:** `laia-clone` se ejecuta EN el servidor nuevo (destino), apuntando con `--source` al viejo (origen). El nuevo se autoinstala primero y luego tira los datos del viejo por SSH. NUNCA se ejecuta desde el origen empujando hacia el destino.

**Por qué pull y no push:**
- El destino tiene que tener LAIA al final → coherente con que `laia-install` corra primero ahí (lo invoca el propio clone si `/opt/laia` no existe).
- `boot_detect_arch` detecta la arch del host donde corre. En pull, detecta la del destino — correcto para reconstruir containers locales.
- Cross-arch (arm64 origen → amd64 destino) funciona porque la reconstrucción se hace en el destino con su arch nativa.
- Terminas logueado en el destino, listo para configurar nginx/dominio sin volver al origen.

**Path remapping en transit:** el origen puede tener layout dev (datos del ARCH en `~/.laia/`) o layout factory (`/srv/laia/arch/` + `/home/laia-arch/LAIA-ARCH/`). El clone normaliza siempre al layout factory en destino:

- `workspaces`, `memories`, `skills`, `plugins` → `/home/laia-arch/LAIA-ARCH/`.
- `SOUL.md`, `config.yaml`, `sessions`, `sandboxes`, `atlas`, `cron`, `logs`, DBs internas y runtime sensible → `/srv/laia/arch/`.
- Credenciales (`auth.json`, `.env`) → `/home/laia-arch/.laia/` mientras AGORA siga montándolas desde ahí.

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
    /srv/laia/arch/         (si existe)
    o ~/.laia/{workspaces,memories,skills,plugins,
                cron,sessions,sandboxes,logs,
                state.db,SOUL.md,config.yaml,
                atlas,platforms,...}
                            ◄── rsync ─── /home/laia-arch/LAIA-ARCH/<live-dir>
                                          /srv/laia/arch/<runtime-dir>
                                          (+ rewrite paths: en config.yaml)
                                                │
  Credenciales sensibles:
    ~/.laia/auth.json       ◄── rsync ─── /home/laia-arch/.laia/auth.json (0600)
    ~/.laia/.env            ◄── rsync ─── /home/laia-arch/.laia/.env (0600)
                                                │
                                          2. rebuild-3-provision-agora.sh (arch nativa del nuevo)
                                                │
                                          3. rebuild-4-first-user.sh --existing-user-only
                                             (por cada slug en agora.db)
                                                │
                                          4. clone_phase_h_fix_uid_mapping
                                                │
                                          5. smoke: health, login, users, skills
```

**Comando concreto que se ejecuta en el nuevo:**
```bash
nuevo$ sudo laia-clone --source laia-hermes@viejo.local --yes --bwlimit=50M
```

**Por qué path-remapping en lugar de mover datos en origen:** modificar los paths en origen requiere refactor de `infra/pathd/`, `services/agora-backend/`, `config.yaml` y otros componentes, rompiendo el LAIA operativo de la máquina de desarrollo. El clone-time remap es no invasivo y consistente con la decisión D4 ("no movemos el origen, optimizamos el destino").

Reglas relacionadas: ⑤ (LAIA-ARCH y LAIA-AGORA independientes), ⑦ (`.laia-core/` solo en host y `laia-agora`), ⑨ (a usuarios decir "LAIA"), ⑩ (LAIA-ARCH invisible para usuarios).

---

## 9. Lo construido y lo que viene

### v2.5 — Actual (Mayo 2026)

| Sistema | Estado | Tests |
|---------|--------|-------|
| Arquitectura cerebro centralizado + executors | ✅ Funcional | 431 |
| LAIA-AGORA Backend (80+ endpoints) | ✅ Funcional | 342 |
| AgentPool + Tool Forwarder | ✅ Funcional | 25 |
| Control Center (API admin) | ✅ Funcional | 342 |
| Marketplace (plugins + skills) | ✅ Funcional | 342 |
| Agent Areas (identidad del agente) | ✅ Funcional | 342 |
| LAIA Coordinator (modo chat) | ✅ Funcional | 342 |
| Scheduler + Learnings | ✅ Funcional | 342 |
| Webhooks | ✅ Funcional | 342 |
| Usage Ledger + Budget | ✅ Funcional | 342 |
| Rebuild scripts (1-2-3-4) | ✅ Funcional | Shell |
| DevOps (preflight, smoke, state) | ✅ Funcional | Shell |
| `agent-*` naming | ✅ Funcional | Shell |
| laia-init wizard | ✅ Funcional | Shell |

### Próximo — UI de LAIA-AGORA

Reconstruir la interfaz web desde cero. La UI actual (v1) se archiva.
La nueva UI incluirá:

- Chat con el PA-AGORA
- Chat con LAIA (coordinador)
- Configuración del agente (nombre, personalidad, LLM)
- Marketplace (explorar e instalar plugins/skills)
- Workspaces (explorar documentos compartidos)
- Panel de admin (empleados, aprobaciones, estado de la flota)

### Futuro — LAIA OS

Cuando el ecosistema esté maduro:
- ISO de Ubuntu personalizada con LAIA preinstalado
- Instalador gráfico
- Lenovo ThinkStation P720 como hardware de producción
- GPU para Whisper local

---

> 📅 Documento definitivo — v1.1 — 2026-05-21
