# Workspace UI — General

## Metadata

- ID: `87`
- Slug: `workspace-ui-general`
- Kind: `doc`
- Status: `active`
- Filename: `workspace-ui-general.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:59.552690+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `workspace-ui-general`

## Summary

Interfaz web completa del sistema LAIA, corriendo en **FastAPI** (backend) + **React + Vite + TypeSc

## Body

# Workspace UI — Interfaz Web

# Workspace UI

Interfaz web completa del sistema LAIA, corriendo en **FastAPI** (backend) + **React + Vite + TypeScript** (frontend).

## Arquitectura general

```
~/.laia/workspace-ui/
├── backend/           # FastAPI app (Python)
│   └── main.py        # 2005 líneas — toda la lógica server
├── frontend/          # React SPA
│   ├── src/
│   │   ├── App.tsx              # Router + layout principal
│   │   ├── main.tsx             # Entry point
│   │   ├── index.css            # Tema CSS (paleta amber/neón)
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx    # Panel de chat global
│   │   │   ├── NeuralBackground.tsx
│   │   │   ├── WorkspaceActions.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── workspace/
│   │   │       ├── Workspace.tsx         # Control center principal
│   │   │       ├── TopBar.tsx
│   │   │       ├── SidePanels.tsx
│   │   │       ├── SessionsRail.tsx
│   │   │       ├── CommandPalette.tsx
│   │   │       ├── ToolDetailModal.tsx
│   │   │       ├── SettingsDrawer.tsx
│   │   │       ├── ChatStream.tsx
│   │   │       ├── ApprovalDialog.tsx
│   │   │       ├── DiffModal.tsx
│   │   │       └── PromptDialog.tsx
│   │   ├── pages/
│   │   │   ├── Home.tsx         # Landing + transición + workspace
│   │   │   ├── WorkspaceList.tsx  # Grid de workspaces (Nexus)
│   │   │   ├── NodeBrowser.tsx  # Tabla de nodos
│   │   │   ├── NodeEditor.tsx   # Editor markdown con preview
│   │   │   ├── GraphView.tsx    # Grafo interactivo (React Flow)
│   │   │   ├── ContextEnginePage.tsx
│   │   │   └── Setup.tsx
│   │   └── lib/
│   │       ├── api.ts           # Cliente API (fetch/ws)
│   │       ├── agentRuntime.tsx  # Runtime del agente via WS
│   │       └── kind.ts, time.ts, tauri.ts
├── previews/
└── start.sh          # Script de inicio
```

## Rutas principales (SPA)

| Ruta | Componente | Descripción |
|---|---|---|
| `/` | `Home` | Landing LAIA + transición scroll + workspace |
| `/workspaces` | `WorkspaceList` | Grid de todos los workspaces |
| `/ws/:ws` | `NodeBrowser` | Lista/tabla de nodos del workspace |
| `/ws/:ws/new` | `NodeEditor` | Crear nuevo nodo |
| `/ws/:ws/nodes/:slug` | `NodeEditor` | Editar nodo existente |
| `/ws/:ws/graph` | `GraphView` | Visualización de grafo |
| `/context-engine` | `ContextEnginePage` | Diagnóstico de contexto inyectado |

## API REST backend

Todo en `main.py` (FastAPI). Base URL: `http://localhost:8077`

### Workspaces
- `GET /api/workspaces` — lista todos los workspaces
- `POST /api/workspaces/{ws}/export-markdown` — exportar a MD
- `POST /api/workspaces/{ws}/clean-exports` — limpiar exports
- `POST /api/workspaces/{ws}/migrate-legacy` — migrar desde markdown
- `GET /api/workspaces/{ws}/verify-db` — verificar completitud DB

### Nodos
- `GET /api/workspaces/{ws}/nodes` — listar nodos (resumen)
- `GET /api/workspaces/{ws}/nodes/{ref}` — obtener nodo completo con enlaces
- `POST /api/workspaces/{ws}/nodes` — crear nodo
- `PUT /api/workspaces/{ws}/nodes/{ref}` — actualizar nodo
- `DELETE /api/workspaces/{ws}/nodes/{ref}` — eliminar nodo

### Búsqueda y Grafo
- `GET /api/workspaces/{ws}/search?q=` — buscar nodos (FTS5)
- `GET /api/workspaces/{ws}/graph` — obtener grafo completo (nodos + aristas)
- `POST /api/workspaces/{ws}/nodes/{ref}/links` — añadir enlace

### Context Engine
- `GET /api/context-engine/config` — configuración actual
- `GET /api/context-engine/injected` — contenido inyectado al agente
- `GET /api/context-engine/prefetch-nodes` — nodos disponibles para prefetch
- `GET /api/context-engine/prefetch?q=` — simular prefetch
- `GET /api/context-engine/skills` — skills escaneadas

### Chat
- `POST /api/chat` — streaming SSE con Laia (usa `SOUL.md` + workspace index como system)

### Control del Agente (WebSocket + REST)
- `WebSocket /api/control/ws` — JSON-RPC bridge al TUI gateway
- `GET /api/agent/sessions` — listar sesiones
- `POST /api/agent/sessions` — crear sesión
- `POST /api/agent/sessions/resume` — recuperar sesión
- `GET /api/agent/sessions/current` — sesión actual
- `POST /api/agent/sessions/{id}/interrupt|undo|compress`
- `GET /api/agent/commands` — catálogo de comandos
- `POST /api/agent/commands/execute` — ejecutar comando
- `GET /api/agent/models` — modelos disponibles
- `GET /api/agent/config` — configuración actual
- `PATCH /api/agent/config` — modificar config
- `GET/POST /api/agent/modes` — plan_mode, auto_mode, yolo, reasoning
- `GET /api/agent/tools` — lista de herramientas
- `POST /api/agent/tools/{name}/toggle` — activar/desactivar tool
- `GET /api/agent/approvals` — aprobaciones pendientes
- `POST /api/agent/approvals/{id}/approve|deny`
- `GET /api/agent/file-edits` — edits detectados
- `GET /api/agent/rollbacks` — snapshots disponibles
- `GET/POST /api/agent/cron` — gestión de jobs cron
- `GET /api/agent/insights` — métricas de uso
- `GET /api/agent/personalities` — personalidades disponibles
- `GET /api/agent/status` — estado del gateway + Telegram

## Tema visual

Paleta **amber/neón** definida en `index.css`:

```css
--brand: #ffc45a;           /* Ámbar principal */
--bg: #050505;              /* Near-black */
--text-main: #ffffff;
--text-muted: #a0a0a0;
--ws-bg: #060400;           /* Fondo workspace */
--ws-surface: rgba(255,255,255,0.025);
--ws-border: rgba(255,255,255,0.07);
--ws-success: #86efac;
--ws-warning: #fbbf24;
--ws-danger: #fca5a5;
```

## Inicio

```bash
cd ~/.laia/workspace-ui
./start.sh
# o manualmente:
cd ~/.laia/workspace-ui/backend
pip install -r requirements.txt
uvicorn main:app --port 8077 --reload
```

Acceso: **http://localhost:8077**

→ Command Center — Orquestación Multi-Agente: `command-center.md`
→ ToolContextInjector — Sistema de Inyección de Contexto: `tool-context-injection.md`
→ Workspace UI — Backend FastAPI: `workspace-ui-backend.md`
→ Workspace UI — FastAPI + React: `context-engine-docs-03-web-ui.md`
→ Workspace UI — Frontend React: `workspace-ui-frontend.md`
→ Workspace UI — Hermes Context Engine: `03-web-ui.md`
→ Workspace UI — Vision General: `workspace-ui-overview.md`


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI — General

# Workspace UI — Interfaz Web

# Workspace UI

Interfaz web completa del sistema LAIA, corriendo en **FastAPI** (backend) + **React + Vite + TypeScript** (frontend).

## Arquitectura general

```
~/.laia/workspace-ui/
├── backend/           # FastAPI app (Python)
│   └── main.py        # 2005 líneas — toda la lógica server
├── frontend/          # React SPA
│   ├── src/
│   │   ├── App.tsx              # Router + layout principal
│   │   ├── main.tsx             # Entry point
│   │   ├── index.css            # Tema CSS (paleta amber/neón)
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx    # Panel de chat global
│   │   │   ├── NeuralBackground.tsx
│   │   │   ├── WorkspaceActions.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── workspace/
│   │   │       ├── Workspace.tsx         # Control center principal
│   │   │       ├── TopBar.tsx
│   │   │       ├── SidePanels.tsx
│   │   │       ├── SessionsRail.tsx
│   │   │       ├── CommandPalette.tsx
│   │   │       ├── ToolDetailModal.tsx
│   │   │       ├── SettingsDrawer.tsx
│   │   │       ├── ChatStream.tsx
│   │   │       ├── ApprovalDialog.tsx
│   │   │       ├── DiffModal.tsx
│   │   │       └── PromptDialog.tsx
│   │   ├── pages/
│   │   │   ├── Home.tsx         # Landing + transición + workspace
│   │   │   ├── WorkspaceList.tsx  # Grid de workspaces (Nexus)
│   │   │   ├── NodeBrowser.tsx  # Tabla de nodos
│   │   │   ├── NodeEditor.tsx   # Editor markdown con preview
│   │   │   ├── GraphView.tsx    # Grafo interactivo (React Flow)
│   │   │   ├── ContextEnginePage.tsx
│   │   │   └── Setup.tsx
│   │   └── lib/
│   │       ├── api.ts           # Cliente API (fetch/ws)
│   │       ├── agentRuntime.tsx  # Runtime del agente via WS
│   │       └── kind.ts, time.ts, tauri.ts
├── previews/
└── start.sh          # Script de inicio
```

## Rutas principales (SPA)

| Ruta | Componente | Descripción |
|---|---|---|
| `/` | `Home` | Landing LAIA + transición scroll + workspace |
| `/workspaces` | `WorkspaceList` | Grid de todos los workspaces |
| `/ws/:ws` | `NodeBrowser` | Lista/tabla de nodos del workspace |
| `/ws/:ws/new` | `NodeEditor` | Crear nuevo nodo |
| `/ws/:ws/nodes/:slug` | `NodeEditor` | Editar nodo existente |
| `/ws/:ws/graph` | `GraphView` | Visualización de grafo |
| `/context-engine` | `ContextEnginePage` | Diagnóstico de contexto inyectado |

## API REST backend

Todo en `main.py` (FastAPI). Base URL: `http://localhost:8077`

### Workspaces
- `GET /api/workspaces` — lista todos los workspaces
- `POST /api/workspaces/{ws}/export-markdown` — exportar a MD
- `POST /api/workspaces/{ws}/clean-exports` — limpiar exports
- `POST /api/workspaces/{ws}/migrate-legacy` — migrar desde markdown
- `GET /api/workspaces/{ws}/verify-db` — verificar completitud DB

### Nodos
- `GET /api/workspaces/{ws}/nodes` — listar nodos (resumen)
- `GET /api/workspaces/{ws}/nodes/{ref}` — obtener nodo completo con enlaces
- `POST /api/workspaces/{ws}/nodes` — crear nodo
- `PUT /api/workspaces/{ws}/nodes/{ref}` — actualizar nodo
- `DELETE /api/workspaces/{ws}/nodes/{ref}` — eliminar nodo

### Búsqueda y Grafo
- `GET /api/workspaces/{ws}/search?q=` — buscar nodos (FTS5)
- `GET /api/workspaces/{ws}/graph` — obtener grafo completo (nodos + aristas)
- `POST /api/workspaces/{ws}/nodes/{ref}/links` — añadir enlace

### Context Engine
- `GET /api/context-engine/config` — configuración actual
- `GET /api/context-engine/injected` — contenido inyectado al agente
- `GET /api/context-engine/prefetch-nodes` — nodos disponibles para prefetch
- `GET /api/context-engine/prefetch?q=` — simular prefetch
- `GET /api/context-engine/skills` — skills escaneadas

### Chat
- `POST /api/chat` — streaming SSE con Laia (usa `SOUL.md` + workspace index como system)

### Control del Agente (WebSocket + REST)
- `WebSocket /api/control/ws` — JSON-RPC bridge al TUI gateway
- `GET /api/agent/sessions` — listar sesiones
- `POST /api/agent/sessions` — crear sesión
- `POST /api/agent/sessions/resume` — recuperar sesión
- `GET /api/agent/sessions/current` — sesión actual
- `POST /api/agent/sessions/{id}/interrupt|undo|compress`
- `GET /api/agent/commands` — catálogo de comandos
- `POST /api/agent/commands/execute` — ejecutar comando
- `GET /api/agent/models` — modelos disponibles
- `GET /api/agent/config` — configuración actual
- `PATCH /api/agent/config` — modificar config
- `GET/POST /api/agent/modes` — plan_mode, auto_mode, yolo, reasoning
- `GET /api/agent/tools` — lista de herramientas
- `POST /api/agent/tools/{name}/toggle` — activar/desactivar tool
- `GET /api/agent/approvals` — aprobaciones pendientes
- `POST /api/agent/approvals/{id}/approve|deny`
- `GET /api/agent/file-edits` — edits detectados
- `GET /api/agent/rollbacks` — snapshots disponibles
- `GET/POST /api/agent/cron` — gestión de jobs cron
- `GET /api/agent/insights` — métricas de uso
- `GET /api/agent/personalities` — personalidades disponibles
- `GET /api/agent/status` — estado del gateway + Telegram

## Tema visual

Paleta **amber/neón** definida en `index.css`:

```css
--brand: #ffc45a;           /* Ámbar principal */
--bg: #050505;              /* Near-black */
--text-main: #ffffff;
--text-muted: #a0a0a0;
--ws-bg: #060400;           /* Fondo workspace */
--ws-surface: rgba(255,255,255,0.025);
--ws-border: rgba(255,255,255,0.07);
--ws-success: #86efac;
--ws-warning: #fbbf24;
--ws-danger: #fca5a5;
```

## Inicio

```bash
cd ~/.laia/workspace-ui
./start.sh
# o manualmente:
cd ~/.laia/workspace-ui/backend
pip install -r requirements.txt
uvicorn main:app --port 8077 --reload
```

Acceso: **http://localhost:8077**

→ Command Center — Orquestación Multi-Agente: `command-center.md`
→ ToolContextInjector — Sistema de Inyección de Contexto: `tool-context-injection.md`
→ Workspace UI — Backend FastAPI: `workspace-ui-backend.md`
→ Workspace UI — FastAPI + React: `context-engine-docs-03-web-ui.md`
→ Workspace UI — Frontend React: `workspace-ui-frontend.md`
→ Workspace UI — Hermes Context Engine: `03-web-ui.md`
→ Workspace UI — Vision General: `workspace-ui-overview.md`


> 📅 Documentado: 2026-05-08
