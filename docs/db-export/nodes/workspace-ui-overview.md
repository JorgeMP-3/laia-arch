# Workspace UI Overview

## Metadata

- ID: `84`
- Slug: `workspace-ui-overview`
- Kind: `doc`
- Status: `active`
- Filename: `workspace-ui-overview.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:58.627113+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `workspace-ui-overview`

## Summary

Sistema de interfaz web para LAIA (Local AI Agent). Combina un landing visual, un navegador de works

## Body

# Workspace UI — Vision General

# Workspace UI — Overview

Sistema de interfaz web para LAIA (Local AI Agent). Combina un landing visual, un navegador de workspaces/nodos, un grafo interactivo y un panel de control del agente en tiempo real.

## Stack tecnológico

- **Backend**: Python 3 + FastAPI (2005 líneas en `main.py`)
- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS + CSS custom properties
- **Grafo**: React Flow (`@xyflow/react`)
- **Icons**: Lucide React
- **HTTP Client**: `fetch` API + WebSocket nativo
- **Backend de datos**: `workspace_store` (WorkspaceStore SQLite)

## Componentes clave

### Home (`Home.tsx`)
Landing page con **3 secciones** en scroll:
1. **Landing LAIA** — hero "LAIA" con fondo grid animado que responde al scroll
2. **Transición ciego** — 12 tiras horizontales que se cierran desde arriba hacia abajo revelando el workspace
3. **Workspace** — control center renderizado dentro de `.workspace-theme`

Contiene también cards de navegación a **Core** (control del agente), **Nexus** (knowledge graph) y **Context Engine** (diagnóstico de contexto).

### Workspace (`Workspace.tsx`)
Panel de control del agente. Muestra:
- **SessionsRail** — rail lateral con sesiones activas
- **TopBar** — modelo actual, botones de control
- **SidePanels** — herramientas, approvals, file edits
- **CommandPalette** — paleta de comandos (`/`)
- **ToolDetailModal** — detalle de herramienta activa
- **SettingsDrawer** — configuración de modos

### NodeBrowser (`NodeBrowser.tsx`)
Tabla de nodos con:
- Búsqueda en tiempo real (FTS5 via API)
- Filtro por `kind` (chip pills)
- Gradientes de color por workspace (hash del nombre)
- Navegación inline a grafo y creación de nodos

### NodeEditor (`NodeEditor.tsx`)
Editor completo de nodos:
- **Izquierda**: metadata (título, kind, summary, tags, parent, enlaces)
- **Derecha**: editor de contenido Markdown con **live preview**
- Markdown parser custom (renderizado en `renderMarkdown()`)
- CMD+S para guardar
- Tags con input + Enter
- Añadir enlaces a otros nodos

### GraphView (`GraphView.tsx`)
Grafo interactivo con:
- **Layout hierarchical** (Sugiyama-style): BFS por niveles → barycenter crossing minimization (3 pasadas)
- **React Flow** con `Position.Top/Bottom` para flujo top-down
- Minimap por tipo de nodo
- Leyenda clickeable para filtrar por kind
- Panel de detalle al clickear nodo

## Flujo de datos

```
Frontend (React)
    │
    ├── fetch REST → FastAPI (:8077)
    │                   │
    │                   ├── WorkspaceStore (SQLite) → ~/.laia/workspaces/{ws}/workspace.db
    │                   │
    │                   └── WebSocket → hermes-agent (tui_gateway entry)
    │                                       │
    │                                       └── LLM + Tools + Sessions
    │
    └── WebSocket /api/control/ws → JSON-RPC bidireccional
```

## Modelos de datos

### Workspace
```ts
{ name: string, node_count: number, edge_count: number, updated_at: string }
```

### NodeSummary
```ts
{ id, slug, title, kind, summary, updated_at }
```

### Node (full)
```ts
{ id, slug, title, kind, summary, content, status, parent_id, tags, updated_at, created_at, filename, links: Link[] }
```

### Link
```ts
{ slug, title, kind, rel: edge_type }
```

## Estado global

- `ChatContext` — comparte `{nodeContext, setNodeContext}` con el chat desde cualquier página
- `AgentProvider` — contexto del agente con WebSocket RPC
- Scroll-driven `scrollProgress` para transiciones landing→workspace

## Acceso

- **Desarrollo frontend**: `cd frontend && npm run dev`
- **Backend**: `cd backend && uvicorn main:app --port 8077`
- **Producción**: `start.sh` sirve el built de React estático desde `frontend/dist/`


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI Overview

# Workspace UI — Vision General

# Workspace UI — Overview

Sistema de interfaz web para LAIA (Local AI Agent). Combina un landing visual, un navegador de workspaces/nodos, un grafo interactivo y un panel de control del agente en tiempo real.

## Stack tecnológico

- **Backend**: Python 3 + FastAPI (2005 líneas en `main.py`)
- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS + CSS custom properties
- **Grafo**: React Flow (`@xyflow/react`)
- **Icons**: Lucide React
- **HTTP Client**: `fetch` API + WebSocket nativo
- **Backend de datos**: `workspace_store` (WorkspaceStore SQLite)

## Componentes clave

### Home (`Home.tsx`)
Landing page con **3 secciones** en scroll:
1. **Landing LAIA** — hero "LAIA" con fondo grid animado que responde al scroll
2. **Transición ciego** — 12 tiras horizontales que se cierran desde arriba hacia abajo revelando el workspace
3. **Workspace** — control center renderizado dentro de `.workspace-theme`

Contiene también cards de navegación a **Core** (control del agente), **Nexus** (knowledge graph) y **Context Engine** (diagnóstico de contexto).

### Workspace (`Workspace.tsx`)
Panel de control del agente. Muestra:
- **SessionsRail** — rail lateral con sesiones activas
- **TopBar** — modelo actual, botones de control
- **SidePanels** — herramientas, approvals, file edits
- **CommandPalette** — paleta de comandos (`/`)
- **ToolDetailModal** — detalle de herramienta activa
- **SettingsDrawer** — configuración de modos

### NodeBrowser (`NodeBrowser.tsx`)
Tabla de nodos con:
- Búsqueda en tiempo real (FTS5 via API)
- Filtro por `kind` (chip pills)
- Gradientes de color por workspace (hash del nombre)
- Navegación inline a grafo y creación de nodos

### NodeEditor (`NodeEditor.tsx`)
Editor completo de nodos:
- **Izquierda**: metadata (título, kind, summary, tags, parent, enlaces)
- **Derecha**: editor de contenido Markdown con **live preview**
- Markdown parser custom (renderizado en `renderMarkdown()`)
- CMD+S para guardar
- Tags con input + Enter
- Añadir enlaces a otros nodos

### GraphView (`GraphView.tsx`)
Grafo interactivo con:
- **Layout hierarchical** (Sugiyama-style): BFS por niveles → barycenter crossing minimization (3 pasadas)
- **React Flow** con `Position.Top/Bottom` para flujo top-down
- Minimap por tipo de nodo
- Leyenda clickeable para filtrar por kind
- Panel de detalle al clickear nodo

## Flujo de datos

```
Frontend (React)
    │
    ├── fetch REST → FastAPI (:8077)
    │                   │
    │                   ├── WorkspaceStore (SQLite) → ~/.laia/workspaces/{ws}/workspace.db
    │                   │
    │                   └── WebSocket → hermes-agent (tui_gateway entry)
    │                                       │
    │                                       └── LLM + Tools + Sessions
    │
    └── WebSocket /api/control/ws → JSON-RPC bidireccional
```

## Modelos de datos

### Workspace
```ts
{ name: string, node_count: number, edge_count: number, updated_at: string }
```

### NodeSummary
```ts
{ id, slug, title, kind, summary, updated_at }
```

### Node (full)
```ts
{ id, slug, title, kind, summary, content, status, parent_id, tags, updated_at, created_at, filename, links: Link[] }
```

### Link
```ts
{ slug, title, kind, rel: edge_type }
```

## Estado global

- `ChatContext` — comparte `{nodeContext, setNodeContext}` con el chat desde cualquier página
- `AgentProvider` — contexto del agente con WebSocket RPC
- Scroll-driven `scrollProgress` para transiciones landing→workspace

## Acceso

- **Desarrollo frontend**: `cd frontend && npm run dev`
- **Backend**: `cd backend && uvicorn main:app --port 8077`
- **Producción**: `start.sh` sirve el built de React estático desde `frontend/dist/`


> 📅 Documentado: 2026-05-08
