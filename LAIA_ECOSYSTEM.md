# LAIA Ecosystem — El Documento Definitivo

> **Documento de visión.** Qué es LAIA, sus entidades, sus reglas y hacia dónde va.
> Documentación complementaria:
> - 🗺️ **Mapa del repo** (carpetas, objetivo, archivos) → [`workflow/project-map.md`](workflow/project-map.md)
> - 📐 **Layout en disco / migración** (`/opt`, `/srv`, `~/.laia`, contrato `laia-clone`) → [`workflow/arch-layout.md`](workflow/arch-layout.md)
>
> Si hay contradicción sobre **la idea**, gana este documento. No se edita sin consenso
> explícito de Jorge.
>
> v2 — 2026-05-27.

---

## 1. Visión

**LAIA es un ecosistema de agentes de IA personales.**

LAIA es el ser supremo. Un ente con distintos **medios de expresión** para interactuar
con el mundo. Dos de esos medios son:

- **LAIA-ARCH** — su expresión como administrador. Vive en el host. Solo Jorge lo ve.
  Controla la infraestructura. El ser superior en las sombras.
  **Los usuarios nunca ven ni interactúan con LAIA-ARCH.**

- **LAIA-AGORA** — su expresión como plataforma multi-usuario. Vive en un container.
  Da servicio a todos los agentes personales. El cerebro centralizado que piensa por
  todos. **Para los usuarios, esto es simplemente "LAIA".**

Dentro de LAIA-AGORA habitan los **PA-AGORA** (Personal Agent AGORA): asistentes
individuales que cada usuario configura a su gusto. Tienen nombre propio, personalidad
propia, y viven en containers privados donde el usuario es root.

### Cómo llamamos a las cosas

| Interno (devs) | Usuario ve | Descripción |
|----------------|------------|-------------|
| **LAIA-ARCH** | *(invisible)* | El administrador del host. Solo Jorge. |
| **LAIA-AGORA** | **LAIA** | La plataforma. El coordinador. "Chatear con LAIA". |
| **PA-AGORA** | "Mi agente", "Nombrix" | El agente personal de cada usuario. |

Cada persona tiene su propio agente. Vive en su propio contenedor privado. Tiene el
nombre que esa persona elige, la personalidad que esa persona le da, y ejecuta las
tareas que esa persona le pide. Nadie más puede usarlo.

Imagina un edificio de oficinas. En cada despacho hay un asistente personal trabajando
para su jefe. Los asistentes no se meten en el despacho de otro. Pero todos comparten
una recepción común donde consultan información compartida y se coordinan entre ellos.

Eso es LAIA.

---

## 2. Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│ HOST (el edificio)                                                 │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 🧠 LAIA-AGORA — El cerebro centralizado (container laia-agora) │ │
│  │                                                                │ │
│  │  La inteligencia que comparten todos los agentes:              │ │
│  │   • El motor del agente (.laia-core)                           │ │
│  │   • El Backend / API que lo conecta todo                       │ │
│  │   • Una instancia de IA por cada sesión de chat                │ │
│  │   • Marketplace (plugins y skills) y Control Center (admin)     │ │
│  │   • La base de datos central (usuarios, agentes, config)       │ │
│  │                                                                │ │
│  │  Cuando un usuario chatea, el LLM razona AQUÍ. Cuando necesita  │ │
│  │  ejecutar algo en el despacho del usuario, lo envía al executor.│ │
│  └───────────────────────────────┬────────────────────────────────┘ │
│                                  │ HTTP (puente interno LXD)        │
│  ┌───────────────────────────────▼────────────────────────────────┐ │
│  │ PA-AGORA (containers privados, uno por usuario)                 │ │
│  │                                                                 │ │
│  │   agent-jorge: "Nombrix"          agent-maria: "MariaBot"       │ │
│  │   • Root total, sin restricciones • Root total, sin restricciones│ │
│  │   • Workspace y archivos propios  • Workspace y archivos propios │ │
│  │   • El executor recibe órdenes    • El executor recibe órdenes  │ │
│  │     de LAIA y las ejecuta aquí      de LAIA y las ejecuta aquí   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 👑 LAIA-ARCH — El ser superior que habita en las sombras       │ │
│  │                                                                │ │
│  │  En el host, fuera de los containers. Solo Jorge lo usa.       │ │
│  │  Tiene todo el toolset del ecosistema + herramientas del host. │ │
│  │  Ve a todos los usuarios; ninguno lo ve a él.                  │ │
│  │  Gestiona la infraestructura: LXD, nginx, systemd, deploy.     │ │
│  │  NO es parte de LAIA-AGORA — es el administrador del host.      │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Las tres entidades del ecosistema

### LAIA-AGORA — El coordinador autónomo

LAIA-AGORA no es una persona. Es un **agente autónomo** que coordina el ecosistema.
Vive en el container `laia-agora`. Es el cerebro centralizado que piensa por todos.

- Los empleados pueden chatear con él para preguntar sobre información compartida.
- Tiene un toolset restringido: consultas a workspaces compartidos, estado de agentes, mensajes.
- Gestiona empleados, aprueba plugins, asigna tareas, ve workspaces de todos.
- **NO** ejecuta herramientas en su propio container (ahí vive el código base).
- **NO** tiene auto-modificación, scheduler ni delegación propias.
- **NO** gestiona la infraestructura del host (eso es LAIA-ARCH).
- Para los usuarios, LAIA-AGORA es simplemente **"LAIA"**.

### Empleado (usuario normal)

- Tiene su propio PA-AGORA con nombre y personalidad propia.
- Chatea con su agente para tareas personales, trabajo y automatización.
- Su agente ejecuta herramientas dentro de SU container (archivos, comandos, código).
- Instala plugins y skills desde el Marketplace.
- Configura su propia API key de LLM (DeepSeek, OpenAI, Anthropic, etc).
- Puede chatear con LAIA (el coordinador) para preguntar sobre información compartida.
- Ve los workspaces compartidos a los que tiene acceso.
- **NO** ve los agentes de otros usuarios.
- **NO** ve el código base (está en `laia-agora`, no en su container).
- **NO** sabe que LAIA-ARCH existe. Para él, "LAIA" es LAIA-AGORA.

### LAIA-ARCH (Jorge — el ser superior en las sombras)

- **Solo Jorge** tiene acceso. Ningún usuario sabe que existe.
- Tiene todo el toolset del ecosistema + herramientas administrativas del host.
- **Ve a todos los usuarios**, containers, workspaces, tareas. Ellos no lo ven a él.
- Vive en el host, fuera de los containers. Tiene su propio `.laia-core/`.
- Gestiona infraestructura: LXD, systemd, nginx, Cloudflare, red, deploy.
- Ejecuta `laia-install` y `laia-clone` para desplegar y migrar.

---

## 4. Cómo funciona un chat

### Con el PA-AGORA (tu agente personal)

```
1. Usuario escribe: "Crea un script que me diga buenos días"

2. El mensaje viaja al Backend de LAIA-AGORA.

3. AGORA identifica al usuario: "Es Jorge, su agente es Nombrix,
   su container es agent-jorge".

4. AGORA prepara una instancia de IA para la sesión:
   carga el alma de Nombrix, la API key de LLM que Jorge configuró,
   y el toolset disponible.

5. El LLM razona: "Necesito crear un archivo → herramienta write_file".

6. AGORA intercepta la tool call y la reenvía al executor del usuario:
   "esto se ejecuta en el despacho de Jorge, no aquí".

7. El executor en agent-jorge ejecuta write_file como root, sin
   restricciones. El archivo se crea en el home del usuario.

8. AGORA recibe la confirmación; el LLM continúa y responde por streaming.

9. El usuario ve: "He creado el archivo buenos_dias.sh en tu carpeta."
```

La clave: **el LLM razona en el cerebro (laia-agora); las acciones se ejecutan en el
despacho del usuario (su container)**. Esa separación es la columna vertebral.

### Con LAIA (el coordinador)

```
1. El usuario cambia al modo LAIA y pregunta:
   "¿Qué tareas tiene Maria pendientes?"

2. AGORA reconoce que es un chat con LAIA → toolset restringido de
   coordinación, ejecutado en el container del propio usuario y con su API key.

3. El LLM razona como LAIA, consulta el estado del ecosistema
   (usuarios, tareas, workspaces compartidos) y responde por streaming.
```

LAIA no es un agente aparte: es un **modo de chat** con un toolset acotado a coordinación.

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
- **⑭** LAIA no se auto-modifica. No tiene acceso a auto-edición, scheduler ni delegación.

---

## 6. Componentes del ecosistema

Vista conceptual de las piezas. La mecánica concreta (puertos, endpoints, tablas) vive
en el código y en [`workflow/arch-layout.md`](workflow/arch-layout.md).

### Dentro de LAIA-AGORA (el cerebro)

- **Motor del agente (`.laia-core`)** — el núcleo que razona y usa herramientas, con su
  gateway multi-plataforma y su scheduler (`cron`).
- **Backend / API** — la capa REST que conecta todo: auth, usuarios, chat, marketplace.
- **Pool de agentes** — una instancia de IA viva por sesión de chat.
- **Tool Forwarder** — intercepta las tool calls del LLM y las reenvía al container del usuario.
- **Marketplace** — publicar, aprobar e instalar plugins y skills.
- **Control Center** — administración: estado del sistema, logs, auditoría, jobs.
- **Coordinador LAIA** — modo de chat con toolset de coordinación.
- **Base de datos central** — usuarios, agentes, plugins, aprendizajes, uso/coste.

### En el despacho del usuario (el executor)

- **laia-executor** — microservicio que recibe tool calls del cerebro y las ejecuta como root.
- **Herramientas de ejecución** — archivos, comandos, código, procesos, cron, workspace privado.
- **Workspace y archivos personales** — persistentes vía bind mount desde `/srv/laia/users/`.
- **Plugins propios** — instalados por el usuario desde el Marketplace.

### En el host (infraestructura)

- **LXD** — hipervisor de contenedores; gestiona `laia-agora` y los `agent-<slug>`.
- **nginx** — proxy inverso (internet → LAIA-AGORA, servicios web).
- **systemd** — servicios del host (gateway, pathd).
- **Atlas v2** — el registro universal del ecosistema: declara cada coordenada (paths,
  servicios, containers, sockets, env files) como referencia tipada, una sola vez. El
  código consulta Atlas en vez de hardcodear. Es el "DNS" del ecosistema (`bin/atlas`).
- **WorkspaceStore** — librería compartida (SQLite + FTS5) para todos los workspaces.

---

## 7. Workspaces y conocimiento compartido

LAIA no es solo un chat. Es un sistema de conocimiento.

### Workspace colectivo (AGORA)

Un workspace compartido donde vive la información de la plataforma: documentación del
ecosistema, decisiones de arquitectura, guías para desarrolladores, estado de proyectos.
Todos los usuarios pueden leerlo. El admin de LAIA-AGORA puede editarlo.

### Workspace privado (cada usuario)

Cada usuario tiene su propio workspace personal. Solo él lo ve y lo edita. Aquí guarda
sus notas, aprendizajes y conocimiento privado.

### Workspaces compartidos

Los usuarios pueden compartir workspaces entre sí. María comparte su workspace
"proyecto-alpha" con Jorge. LAIA puede buscar en workspaces compartidos cuando alguien
le pregunta.

### LAIA como coordinador de conocimiento

Cuando un empleado pregunta a LAIA ("¿Quién trabaja en el proyecto Alpha?", "¿Qué
decisiones se tomaron sobre la API de usuarios?"), LAIA consulta los workspaces
compartidos y el estado del ecosistema, y responde con información agregada. No accede a
datos privados de usuarios sin permiso.

---

## 8. Dónde vive todo (resumen)

El sistema separa **código**, **datos+secretos operacionales** y **mesa viva** en
locations con propósitos no solapados:

- **`/opt/laia/`** — el código del producto instalado. Lo que se "vende" y se actualiza
  (`laia-install`, `laia-release`, `laia-rollback`). No se transfiere en una migración:
  el destino lo reinstala.
- **`/srv/laia/`** — **toda** la verdad operacional y sensible, root-owned (la fuente de
  verdad). Incluye `agora/` (`agora.db`), `users/` (datos de cada PA-AGORA), `arch/`
  (runtime de LAIA-ARCH: `state.db`, `sessions`, `atlas`, `config.yaml`…) y
  **`arch/secrets/`** (los **secretos** del operador: `auth.json`, `.env`, mode 0600). Es
  lo que `laia-clone` rsynchea íntegro.
- **`~/LAIA-ARCH/`** — la **mesa viva** interactiva del operador: `workspaces`, `memories`,
  `skills`, `plugins` y `SOUL.md` (lo que Jorge crea y edita a diario).

Los **secretos viven en `/srv/laia/arch/secrets/`** (root-owned), no en el home: reduce la
superficie de exposición accidental y deja todo el estado sensible bajo un único árbol
respaldable y migrable. **`~/.laia/` queda eliminado.**

> 🛠️ **Estado de migración (2026-05-29):** este layout es el **objetivo** decidido en
> [`workflow/plans/estabilizacion/`](workflow/plans/estabilizacion/). Reemplazar el layout
> anterior (secretos en `~/.laia/`, runtime mezclado en `~/LAIA-ARCH/`) es el **Bloque C**
> del plan: se ensaya en la VM de desarrollo y se aplica en producción con backup. **Hasta
> ejecutarlo, en disco aún rige el layout anterior** — foto real en
> [`workflow/plans/estabilizacion/estado-ecosistema-servidor.md`](workflow/plans/estabilizacion/estado-ecosistema-servidor.md).

> 📐 El **modelo** completo — árbol de directorios, permisos, idmaps LXD, contrato de
> transferencia `laia-clone` y flujos `install`/`clone` — está en
> [`workflow/arch-layout.md`](workflow/arch-layout.md). Para el **mapa real del sistema
> entero** (todas las locations en disco — `/opt`, `/srv`, `~/LAIA-ARCH`, containers — y el
> repo) ver [`workflow/project-map.md`](workflow/project-map.md).

---

## 9. Lo construido y lo que viene

### Estado actual (2026)

El ecosistema está funcional de punta a punta:

- Arquitectura cerebro centralizado + executors por usuario.
- Backend de LAIA-AGORA (API REST completa) con auth, chat, usuarios.
- Pool de agentes + Tool Forwarder.
- Control Center (administración) y Marketplace (plugins + skills).
- Coordinador LAIA (modo chat), Scheduler + aprendizajes, Webhooks.
- Tracking de uso y presupuesto.
- Atlas v2 (registro universal del ecosistema, con auto-sanación y diagnóstico).
- Instalador y migrador (`laia-install`, `laia-clone`, rebuild scripts, smoke/preflight).

La suite de tests acompaña a cada integración (regla: toda integración nueva necesita su
test y la suite completa pasa antes de declarar "hecho").

### Próximo — UI de LAIA-AGORA

Reconstruir la interfaz web desde cero (la v1 se archiva). Incluirá:

- Chat con el PA-AGORA y chat con LAIA (coordinador).
- Configuración del agente (nombre, personalidad, LLM).
- Marketplace (explorar e instalar plugins/skills).
- Workspaces (explorar documentos compartidos).
- Panel de admin (empleados, aprobaciones, estado de la flota).

### Futuro — LAIA OS

Cuando el ecosistema esté maduro:

- ISO de Ubuntu personalizada con LAIA preinstalado.
- Instalador gráfico.
- Lenovo ThinkStation P720 como hardware de producción.
- GPU para Whisper local.

---

> Documento de visión — v2 — 2026-05-27. Detalle técnico en `workflow/arch-layout.md`.
