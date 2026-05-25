# Workspace UI Backend (FastAPI)

## Metadata

- ID: `85`
- Slug: `workspace-ui-backend`
- Kind: `doc`
- Status: `active`
- Filename: `workspace-ui-backend.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:58.910590+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `workspace-ui-backend`

## Summary

FastAPI app en `~/.hermes/workspace-ui/backend/main.py` (~2005 líneas).

## Body

# Workspace UI — Backend FastAPI

# Workspace UI — Backend

FastAPI app en `~/.laia/workspace-ui/backend/main.py` (~2005 líneas).

## Arquitectura

```
Backend FastAPI (:8077)
    │
    ├── WorkspaceStore (importado de workspace_store)
    │       └── SQLite en ~/.laia/workspaces/{ws}/workspace.db
    │
    ├── HermesWebSession (clase HermesGatewayError)
    │       └── Spawns hermes-agent tui_gateway como subprocess
    │       └── JSON-RPC sobre stdin/stdout del subprocess
    │       └── Broadcast de eventos a todos los clientes WebSocket
    │
    └── Rutas REST (60+ endpoints)
```

## HermesWebSession — Bridge JSON-RPC

Clase que conecta el servidor FastAPI con el gateway TUI del agente.

### Métodos principales

```python
class HermesWebSession:
    proc: asyncio.subprocess.Process | None
    pending: dict[str, asyncio.Future]  # RPC requests esperando respuesta
    clients: set[asyncio.Queue]         # Clientes WebSocket conectados
    control_session_id: str | None       # Sesión de control activa
    
    async start()                       # Inicia subprocess del gateway
    async stop()                        # Termina subprocess
    async add_client() -> Queue         # Nuevo cliente WS
    async ensure_control_session()      # Crea sesión de control si no existe
    async request(method, params)       # Envía JSON-RPC y espera respuesta
    async broadcast(message)             # Envía evento a todos los clientes
```

### Gateway spawning

```python
def _gateway_argv(self) -> list[str]:
    # Override: HERMES_WEB_GATEWAY_CMD env var
    return [python, "-m", "tui_gateway.entry"]

def _gateway_env(self) -> dict[str, str]:
    PYTHONPATH = HERMES_AGENT_ROOT + : + current_PYTHONPATH
    HERMES_PYTHON_SRC_ROOT = HERMES_AGENT_ROOT
```

### Métodos JSON-RPC permitidos

**Sin sesión** (`CONTROL_ALLOWED_METHODS`):
`session.create`, `session.list`, `session.resume`, `session.branch`, `session.close`, `session.interrupt`, `session.undo`, `session.compress`, `session.usage`, `session.history`, `session.title`, `session.steer`, `commands.catalog`, `slash.exec`, `command.dispatch`, `approval.respond`, `clarify.respond`, `sudo.respond`, `secret.respond`, `model.options`, `config.get`, `config.set`, `tools.list`, `tools.show`, `tools.configure`, `toolsets.list`, `rollback.list`, `rollback.diff`, `rollback.restore`, `agents.list`, `process.stop`, `prompt.submit`, `prompt.background`, `prompt.btw`, `personality`, `skin`, `voice.toggle`, `cron.manage`, `skills.manage`, `insights.get`, `plugins.list`, `reload.mcp`, `browser.manage`, `complete.slash`, `complete.path`

**Con sesión** (`CONTROL_SESSION_METHODS`): mismos pero requieren `session_id` en params (auto-inyectado si hay `control_session_id`).

## WebSocket endpoint

```
WS /api/control/ws
```

1. Cliente se conecta → `add_client()` devuelve queue
2. `send_loop()` envía mensajes de la queue al WS
3. Cliente envía `{"type": "request", "id": "...", "method": "...", "params": {...}}`
4. Validación: method debe estar en `CONTROL_ALLOWED_METHODS`
5. Si method está en `CONTROL_SESSION_METHODS`, se inyecta `session_id`
6. Se llama `request()` → respuesta o error
7. La sesión de control se reutiliza para requests consecutivos

## Rutas REST — Detalle

### GET /api/workspaces
Lista workspaces iterando `~/.laia/workspaces/` y leyendo cada `WorkspaceStore`.

### GET /api/workspaces/{ws}/nodes/{ref}
`store.get_node(ref)` + enriquecimiento con enlaces salientes.

### GET /api/workspaces/{ws}/graph
```python
nodes = [{"id": n["slug"], "label": n["title"], "kind": n["kind"]} for n in store.list_all_nodes()]
edges = [{"source": e["from_slug"], "target": e["to_slug"], "rel": e["edge_type"]} for e in store.list_edges()]
return {"nodes": nodes, "edges": edges}
```

### GET /api/context-engine/injected
Lee `config.yaml` → `plugins.workspace-context`:
- `inject_mode`: `"index"` | `"all-indexes"` | `"full"`
- Renderiza nodos con `store.render_node_markdown(node)`
- Calcula `total_chars` vs `max_chars` y `pct_used`

### POST /api/chat
Streaming SSE (`text/event-stream`):
1. Construye system prompt desde `SOUL.md` + workspace index
2. POST a `http://localhost:8642/v1/chat/completions`
3. Relay de tokens delta como `data: {"type": "delta", "text": ...}`
4. Manejo de errores: si connect refused → "El agente no está disponible"

### GET /api/agent/sessions
Normaliza la respuesta del gateway: `'id'` → `'session_id'`, `'key'` → `'session_key'`.

### POST /api/agent/modes
- **yolo**: gateway `config.set` siempre toggles → solo llama si `_yolo_state` cambió
- **reasoning_effort**: pasa el valor directamente a `config.set`
- **plan_mode, auto_mode, ask_before_edit**: persiste a `config.yaml` (no al gateway — son hints de UI)

## Event tracking

`_track_gateway_event()` hook listener en `CONTROL_BRIDGE._sync_listeners`:

### Approval requests
```python
_pending_approvals[request_id] = {
    "request_id", "session_id", "command", "reason",
    "prompt_type": "approval", "pattern_keys": [],
    "created_at", "resolved": False
}
```

### Tool starts
```python
_pending_tool_starts[tool_id] = {
    "name", "context", "session_id", "started_at"
}
```

### Tool completes → File edits
Si tool name contiene "patch", "write_file", etc.:
```python
_file_edits.append({
    "id": tool_id, "session_id", "tool", "path",
    "operation": "patch"|"write", "diff": inline_diff,
    "summary", "created_at"
})
# Máximo 200 entries (FIFO eviction)
```

## CORS y static files

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
# Si frontend/dist/ existe:
app.mount("/assets", StaticFiles(...))
app.mount("/", SPA catch-all)
# Si no: GET / → JSON 503 Service Unavailable
```

## Puerto por defecto

8077 (`uvicorn main:app --port 8077`).


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI Backend (FastAPI)

# Workspace UI — Backend FastAPI

# Workspace UI — Backend

FastAPI app en `~/.laia/workspace-ui/backend/main.py` (~2005 líneas).

## Arquitectura

```
Backend FastAPI (:8077)
    │
    ├── WorkspaceStore (importado de workspace_store)
    │       └── SQLite en ~/.laia/workspaces/{ws}/workspace.db
    │
    ├── HermesWebSession (clase HermesGatewayError)
    │       └── Spawns hermes-agent tui_gateway como subprocess
    │       └── JSON-RPC sobre stdin/stdout del subprocess
    │       └── Broadcast de eventos a todos los clientes WebSocket
    │
    └── Rutas REST (60+ endpoints)
```

## HermesWebSession — Bridge JSON-RPC

Clase que conecta el servidor FastAPI con el gateway TUI del agente.

### Métodos principales

```python
class HermesWebSession:
    proc: asyncio.subprocess.Process | None
    pending: dict[str, asyncio.Future]  # RPC requests esperando respuesta
    clients: set[asyncio.Queue]         # Clientes WebSocket conectados
    control_session_id: str | None       # Sesión de control activa
    
    async start()                       # Inicia subprocess del gateway
    async stop()                        # Termina subprocess
    async add_client() -> Queue         # Nuevo cliente WS
    async ensure_control_session()      # Crea sesión de control si no existe
    async request(method, params)       # Envía JSON-RPC y espera respuesta
    async broadcast(message)             # Envía evento a todos los clientes
```

### Gateway spawning

```python
def _gateway_argv(self) -> list[str]:
    # Override: HERMES_WEB_GATEWAY_CMD env var
    return [python, "-m", "tui_gateway.entry"]

def _gateway_env(self) -> dict[str, str]:
    PYTHONPATH = HERMES_AGENT_ROOT + : + current_PYTHONPATH
    HERMES_PYTHON_SRC_ROOT = HERMES_AGENT_ROOT
```

### Métodos JSON-RPC permitidos

**Sin sesión** (`CONTROL_ALLOWED_METHODS`):
`session.create`, `session.list`, `session.resume`, `session.branch`, `session.close`, `session.interrupt`, `session.undo`, `session.compress`, `session.usage`, `session.history`, `session.title`, `session.steer`, `commands.catalog`, `slash.exec`, `command.dispatch`, `approval.respond`, `clarify.respond`, `sudo.respond`, `secret.respond`, `model.options`, `config.get`, `config.set`, `tools.list`, `tools.show`, `tools.configure`, `toolsets.list`, `rollback.list`, `rollback.diff`, `rollback.restore`, `agents.list`, `process.stop`, `prompt.submit`, `prompt.background`, `prompt.btw`, `personality`, `skin`, `voice.toggle`, `cron.manage`, `skills.manage`, `insights.get`, `plugins.list`, `reload.mcp`, `browser.manage`, `complete.slash`, `complete.path`

**Con sesión** (`CONTROL_SESSION_METHODS`): mismos pero requieren `session_id` en params (auto-inyectado si hay `control_session_id`).

## WebSocket endpoint

```
WS /api/control/ws
```

1. Cliente se conecta → `add_client()` devuelve queue
2. `send_loop()` envía mensajes de la queue al WS
3. Cliente envía `{"type": "request", "id": "...", "method": "...", "params": {...}}`
4. Validación: method debe estar en `CONTROL_ALLOWED_METHODS`
5. Si method está en `CONTROL_SESSION_METHODS`, se inyecta `session_id`
6. Se llama `request()` → respuesta o error
7. La sesión de control se reutiliza para requests consecutivos

## Rutas REST — Detalle

### GET /api/workspaces
Lista workspaces iterando `~/.laia/workspaces/` y leyendo cada `WorkspaceStore`.

### GET /api/workspaces/{ws}/nodes/{ref}
`store.get_node(ref)` + enriquecimiento con enlaces salientes.

### GET /api/workspaces/{ws}/graph
```python
nodes = [{"id": n["slug"], "label": n["title"], "kind": n["kind"]} for n in store.list_all_nodes()]
edges = [{"source": e["from_slug"], "target": e["to_slug"], "rel": e["edge_type"]} for e in store.list_edges()]
return {"nodes": nodes, "edges": edges}
```

### GET /api/context-engine/injected
Lee `config.yaml` → `plugins.workspace-context`:
- `inject_mode`: `"index"` | `"all-indexes"` | `"full"`
- Renderiza nodos con `store.render_node_markdown(node)`
- Calcula `total_chars` vs `max_chars` y `pct_used`

### POST /api/chat
Streaming SSE (`text/event-stream`):
1. Construye system prompt desde `SOUL.md` + workspace index
2. POST a `http://localhost:8642/v1/chat/completions`
3. Relay de tokens delta como `data: {"type": "delta", "text": ...}`
4. Manejo de errores: si connect refused → "El agente no está disponible"

### GET /api/agent/sessions
Normaliza la respuesta del gateway: `'id'` → `'session_id'`, `'key'` → `'session_key'`.

### POST /api/agent/modes
- **yolo**: gateway `config.set` siempre toggles → solo llama si `_yolo_state` cambió
- **reasoning_effort**: pasa el valor directamente a `config.set`
- **plan_mode, auto_mode, ask_before_edit**: persiste a `config.yaml` (no al gateway — son hints de UI)

## Event tracking

`_track_gateway_event()` hook listener en `CONTROL_BRIDGE._sync_listeners`:

### Approval requests
```python
_pending_approvals[request_id] = {
    "request_id", "session_id", "command", "reason",
    "prompt_type": "approval", "pattern_keys": [],
    "created_at", "resolved": False
}
```

### Tool starts
```python
_pending_tool_starts[tool_id] = {
    "name", "context", "session_id", "started_at"
}
```

### Tool completes → File edits
Si tool name contiene "patch", "write_file", etc.:
```python
_file_edits.append({
    "id": tool_id, "session_id", "tool", "path",
    "operation": "patch"|"write", "diff": inline_diff,
    "summary", "created_at"
})
# Máximo 200 entries (FIFO eviction)
```

## CORS y static files

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
# Si frontend/dist/ existe:
app.mount("/assets", StaticFiles(...))
app.mount("/", SPA catch-all)
# Si no: GET / → JSON 503 Service Unavailable
```

## Puerto por defecto

8077 (`uvicorn main:app --port 8077`).


> 📅 Documentado: 2026-05-08
