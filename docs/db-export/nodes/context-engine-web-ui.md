# Workspace UI (FastAPI + React)

## Metadata

- ID: `82`
- Slug: `context-engine-web-ui`
- Kind: `doc`
- Status: `active`
- Filename: `context-engine-web-ui.md`
- Parent: `context-engine-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:58.021346+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `context-engine-web-ui`

## Summary

**Backend:** `~/.hermes/workspace-ui/backend/main.py` (FastAPI)

## Body

# Workspace UI — FastAPI + React

# Workspace UI — Hermes Context Engine

**Backend:** `~/.laia/workspace-ui/backend/main.py` (FastAPI)
**Frontend:** `~/.laia/workspace-ui/frontend/` (React + Vite + TypeScript)
**Puerto por defecto:** 8077

Interfaz web para controlar sesiones Hermes y visualizar el estado del Context Engine.

---

## 1. Arquitectura General

```
Browser (React)
    ↓
    ↓ WebSocket / HTTP
FastAPI Backend (port 8077)
    ↓
    ↓ stdio JSON-RPC
hermes-agent (tui_gateway.entry)
    ↓
    ↓ control bridge
LAIA (TUI gateway)
```

El backend es un bridge: recibe conexiones web y las convierte en llamadas JSON-RPC al gateway de Hermes.

---

## 2. Backend FastAPI

### Endpoints

#### GET /
Sirve el frontend compilado (`frontend/dist/index.html`).

---

#### WebSocket /ws
Bridge bidireccional entre web UI y hermes-agent gateway.

**Flujo:**
1. Browser conecta WebSocket → FastAPI
2. FastAPI lanza proceso `hermes-agent` (o usa existente)
3. stdin/stdout del proceso ←→ WebSocket del browser
4. Mensajes JSON-RPC en ambos direcciones

**Control de sesion:** ciertos methods requieren una `session_id` activa:
- `prompt.submit`, `prompt.background`, `prompt.btw`
- `session.interrupt`, `session.undo`, `session.compress`
- `session.title`, `session.branch`, `session.steer`
- Tools deapproval/respond, slash.exec, command.dispatch

---

#### GET /api/health
Health check del backend.

---

### LAIA Control Center Bridge

**Clase:** `HermesWebSession`

Gestiona el proceso `hermes-agent` como subprocess async:

```python
class HermesWebSession:
    proc: asyncio.subprocess.Process | None
    pending: dict[str, asyncio.Future]
    clients: set[asyncio.Queue]
    control_session_id: str | None

    async start()                        # Lanza gateway si no esta corriendo
    async stop()                       # Termina el proceso
    async rpc(method, params, session_id)  # Envía JSON-RPC y espera respuesta
    async _read_stdout()               # Lee stdout del gateway y despacha a clients
    async _read_stderr()               # Loguea stderr
```

### Resolucion de Rutas

```python
HERMES_AGENT_ROOT = HERMES_HOME / "hermes-agent"
HERMES_AGENT_PYTHON = HERMES_AGENT_ROOT / "venv" / "bin" / "python"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
```

---

## 3. Frontend React

### Stack

- **React 19** + **TypeScript**
- **Vite** — build tool
- **TanStack Query** — gestion de estado async
- **shiki** — syntax highlighting

### Tema Visual

- **Primary:** amber (#F59E0B)
- **Background:** zinc-900 (#18181B)
- **Text:** zinc-100
- **Accent:** cyan-400
- **Error:** red-500

### Archivo de Configuracion

```json
{
  "hermes_web_url": "ws://localhost:8077/ws",
  "theme": "amber"
}
```

---

## 4. API REST — Context Engine

### GET /api/context-engine/config

Devuelve la configuracion actual del plugin workspace-context.

**Respuesta:**

```json
{
  "workspace": "arete",
  "inject_mode": "all-indexes",
  "max_chars": 20000,
  "workspaces": ["arete", "doyouwin", "pixelcore", "laia_arch", "servidor_jmp"],
  "active_workspaces": ["arete"]
}
```

---

### PUT /api/context-engine/config

Actualiza campos de la configuracion del plugin. Solo acepta campos en la whitelist: `workspace`, `inject_mode`, `max_chars`, `active_workspaces`, `workspaces`.

**Request body:**

```json
{
  "active_workspaces": ["arete", "doyouwin"],
  "inject_mode": "all-indexes"
}
```

**Respuesta:** devuelve el config completo tras la actualizacion (misma forma que GET).

---

### POST /api/context-engine/workspace/{name}/toggle-active

Activa o desactiva un workspace para escritura. Si ya esta activo, lo desactiva. Si esta inactivo, lo activa.

**Respuesta:**

```json
{
  "active_workspaces": ["arete", "doyouwin"]
}
```

---

### GET /api/context-engine/injected

Devuelve el contenido que se inyecta al system prompt del agente (bloque contextual completo).

---

### GET /api/context-engine/prefetch?q=

Simula el prefetch que haria el plugin para una query dada. Devuelve los nodos que se inyectarian antes del turno.

---

### GET /api/context-engine/skills

Lista las skills escaneadas en el entorno Hermes.

---

## 5. API REST — Workspaces

### GET /api/workspaces

Lista todos los workspaces disponibles con estado.

**Respuesta:**

```json
{
  "workspaces": [
    {
      "name": "arete",
      "path": "/home/laia-arch/.laia/workspaces/arete",
      "has_db": true,
      "has_index": true
    }
  ],
  "active": "arete"
}
```

---

## 6. Pestana Context Engine (Frontend)

En la ruta `/context-engine` se encuentra el diagnostico del Context Engine. Incluye:

- **Configuracion:** muestra `workspace`, `inject_mode`, `max_chars`, `active_workspaces`, `workspaces`
- **Workspace toggle:** cada workspace muestra un badge EDITABLE (verde) o SOLO LECTURA (gris). Al hacer click se llama a `POST /api/context-engine/workspace/{name}/toggle-active`
- **Prefetch preview:** permite probar queries y ver que nodos devolveria
- **Injected block:** muestra exactamente el contenido que recibe el agente

---

## 7. Iniciar la UI

```bash
cd ~/.laia/workspace-ui/backend
python3 main.py
# http://localhost:8077
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `context-engine-area` (Context Engine) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI (FastAPI + React)

# Workspace UI — FastAPI + React

# Workspace UI — Hermes Context Engine

**Backend:** `~/.laia/workspace-ui/backend/main.py` (FastAPI)
**Frontend:** `~/.laia/workspace-ui/frontend/` (React + Vite + TypeScript)
**Puerto por defecto:** 8077

Interfaz web para controlar sesiones Hermes y visualizar el estado del Context Engine.

---

## 1. Arquitectura General

```
Browser (React)
    ↓
    ↓ WebSocket / HTTP
FastAPI Backend (port 8077)
    ↓
    ↓ stdio JSON-RPC
hermes-agent (tui_gateway.entry)
    ↓
    ↓ control bridge
LAIA (TUI gateway)
```

El backend es un bridge: recibe conexiones web y las convierte en llamadas JSON-RPC al gateway de Hermes.

---

## 2. Backend FastAPI

### Endpoints

#### GET /
Sirve el frontend compilado (`frontend/dist/index.html`).

---

#### WebSocket /ws
Bridge bidireccional entre web UI y hermes-agent gateway.

**Flujo:**
1. Browser conecta WebSocket → FastAPI
2. FastAPI lanza proceso `hermes-agent` (o usa existente)
3. stdin/stdout del proceso ←→ WebSocket del browser
4. Mensajes JSON-RPC en ambos direcciones

**Control de sesion:** ciertos methods requieren una `session_id` activa:
- `prompt.submit`, `prompt.background`, `prompt.btw`
- `session.interrupt`, `session.undo`, `session.compress`
- `session.title`, `session.branch`, `session.steer`
- Tools deapproval/respond, slash.exec, command.dispatch

---

#### GET /api/health
Health check del backend.

---

### LAIA Control Center Bridge

**Clase:** `HermesWebSession`

Gestiona el proceso `hermes-agent` como subprocess async:

```python
class HermesWebSession:
    proc: asyncio.subprocess.Process | None
    pending: dict[str, asyncio.Future]
    clients: set[asyncio.Queue]
    control_session_id: str | None

    async start()                        # Lanza gateway si no esta corriendo
    async stop()                       # Termina el proceso
    async rpc(method, params, session_id)  # Envía JSON-RPC y espera respuesta
    async _read_stdout()               # Lee stdout del gateway y despacha a clients
    async _read_stderr()               # Loguea stderr
```

### Resolucion de Rutas

```python
HERMES_AGENT_ROOT = HERMES_HOME / "hermes-agent"
HERMES_AGENT_PYTHON = HERMES_AGENT_ROOT / "venv" / "bin" / "python"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
```

---

## 3. Frontend React

### Stack

- **React 19** + **TypeScript**
- **Vite** — build tool
- **TanStack Query** — gestion de estado async
- **shiki** — syntax highlighting

### Tema Visual

- **Primary:** amber (#F59E0B)
- **Background:** zinc-900 (#18181B)
- **Text:** zinc-100
- **Accent:** cyan-400
- **Error:** red-500

### Archivo de Configuracion

```json
{
  "hermes_web_url": "ws://localhost:8077/ws",
  "theme": "amber"
}
```

---

## 4. API REST — Context Engine

### GET /api/context-engine/config

Devuelve la configuracion actual del plugin workspace-context.

**Respuesta:**

```json
{
  "workspace": "arete",
  "inject_mode": "all-indexes",
  "max_chars": 20000,
  "workspaces": ["arete", "doyouwin", "pixelcore", "laia_arch", "servidor_jmp"],
  "active_workspaces": ["arete"]
}
```

---

### PUT /api/context-engine/config

Actualiza campos de la configuracion del plugin. Solo acepta campos en la whitelist: `workspace`, `inject_mode`, `max_chars`, `active_workspaces`, `workspaces`.

**Request body:**

```json
{
  "active_workspaces": ["arete", "doyouwin"],
  "inject_mode": "all-indexes"
}
```

**Respuesta:** devuelve el config completo tras la actualizacion (misma forma que GET).

---

### POST /api/context-engine/workspace/{name}/toggle-active

Activa o desactiva un workspace para escritura. Si ya esta activo, lo desactiva. Si esta inactivo, lo activa.

**Respuesta:**

```json
{
  "active_workspaces": ["arete", "doyouwin"]
}
```

---

### GET /api/context-engine/injected

Devuelve el contenido que se inyecta al system prompt del agente (bloque contextual completo).

---

### GET /api/context-engine/prefetch?q=

Simula el prefetch que haria el plugin para una query dada. Devuelve los nodos que se inyectarian antes del turno.

---

### GET /api/context-engine/skills

Lista las skills escaneadas en el entorno Hermes.

---

## 5. API REST — Workspaces

### GET /api/workspaces

Lista todos los workspaces disponibles con estado.

**Respuesta:**

```json
{
  "workspaces": [
    {
      "name": "arete",
      "path": "/home/laia-arch/.laia/workspaces/arete",
      "has_db": true,
      "has_index": true
    }
  ],
  "active": "arete"
}
```

---

## 6. Pestana Context Engine (Frontend)

En la ruta `/context-engine` se encuentra el diagnostico del Context Engine. Incluye:

- **Configuracion:** muestra `workspace`, `inject_mode`, `max_chars`, `active_workspaces`, `workspaces`
- **Workspace toggle:** cada workspace muestra un badge EDITABLE (verde) o SOLO LECTURA (gris). Al hacer click se llama a `POST /api/context-engine/workspace/{name}/toggle-active`
- **Prefetch preview:** permite probar queries y ver que nodos devolveria
- **Injected block:** muestra exactamente el contenido que recibe el agente

---

## 7. Iniciar la UI

```bash
cd ~/.laia/workspace-ui/backend
python3 main.py
# http://localhost:8077
```


> 📅 Documentado: 2026-05-08
