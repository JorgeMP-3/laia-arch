# Workspace UI Frontend (React)

## Metadata

- ID: `86`
- Slug: `workspace-ui-frontend`
- Kind: `doc`
- Status: `active`
- Filename: `workspace-ui-frontend.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:59.212531+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `workspace-ui-frontend`

## Summary

React + TypeScript SPA corriendo en `~/.hermes/workspace-ui/frontend/`.

## Body

# Workspace UI — Frontend React

# Workspace UI — Frontend

React + TypeScript SPA corriendo en `~/.laia/workspace-ui/frontend/`.

## Estructura de directorios

```
frontend/
├── index.html              # Entry HTML
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── src/
│   ├── main.tsx             # createRoot, StrictMode
│   ├── App.tsx               # BrowserRouter + Layout + rutas
│   ├── index.css             # Todo el tema CSS (variables, componentes)
│   ├── App.css                # Estilos estáticos
│   ├── components/
│   │   ├── ChatPanel.tsx     # Panel de chat flotante
│   │   ├── NeuralBackground.tsx
│   │   ├── LaiaNeuralAvatar.tsx
│   │   ├── WorkspaceActions.tsx
│   │   ├── Toast.tsx
│   │   └── workspace/
│   │       ├── Workspace.tsx         # Control center
│   │       ├── TopBar.tsx
│   │       ├── SidePanels.tsx
│   │       ├── SessionsRail.tsx
│   │       ├── CommandPalette.tsx
│   │       ├── ToolDetailModal.tsx
│   │       ├── SettingsDrawer.tsx
│   │       ├── ChatStream.tsx
│   │       ├── ApprovalDialog.tsx
│   │       ├── DiffModal.tsx
│   │       └── PromptDialog.tsx
│   ├── pages/
│   │   ├── Home.tsx              # Landing + scroll transition + workspace
│   │   ├── WorkspaceList.tsx     # Grid de workspaces (Nexus)
│   │   ├── NodeBrowser.tsx       # Tabla de nodos
│   │   ├── NodeEditor.tsx        # Editor de nodo (markdown + preview)
│   │   ├── GraphView.tsx         # Grafo React Flow
│   │   ├── ContextEnginePage.tsx
│   │   └── Setup.tsx
│   └── lib/
│       ├── api.ts           # Cliente HTTP — todos los fetch a FastAPI
│       ├── agentRuntime.tsx  # Provider + hooks para WebSocket RPC
│       ├── kind.ts          # Colores y estilos por kind de nodo
│       ├── time.ts          # relativeTime()
│       └── tauri.ts         # initServerUrl() para Tauri
└── dist/                    # Build de producción (servido por FastAPI)
```

## Dependencias principales

- `react` + `react-dom` ^18
- `react-router-dom` ^6 (SPA routing)
- `@xyflow/react` ^12 (React Flow para grafos)
- `lucide-react` (iconos)
- `tailwindcss` ^3

## API client (`api.ts`)

Objeto `api` con métodos organizados por dominio:

### Workspaces
```ts
api.getWorkspaces(): Promise<Workspace[]>
```

### Nodos
```ts
api.getNodes(ws: string): Promise<NodeSummary[]>
api.getNode(ws: string, ref: string): Promise<Node>
api.createNode(ws: string, payload: NodePayload): Promise<Node>
api.updateNode(ws: string, ref: string, payload: NodePayload): Promise<Node>
api.deleteNode(ws: string, ref: string): Promise<void>
api.searchNodes(ws: string, q: string): Promise<SearchResult[]>
api.getGraph(ws: string): Promise<GraphData>
api.addLink(ws: string, ref: string, payload: LinkPayload): Promise<void>
```

### Context Engine
```ts
api.getContextEngineConfig(): Promise<ContextEngineConfig>
api.getContextEngineInjected(): Promise<InjectedData>
api.getContextEnginePrefetch(q: string): Promise<PrefetchResult>
api.getContextEngineSkills(): Promise<SkillsData>
```

### Chat
```ts
api.chat(messages: ChatMessage[], workspace?: string): Promise<ReadableStream>
```

### Agente (REST)
```ts
api.getSessions(), api.createSession(), api.resumeSession(key)
api.getCurrentSession(), api.interruptSession(), api.undoSession(), api.compressSession()
api.getCommands(), api.executeCommand(cmd, sessionId?)
api.getModels(), api.getAgentConfig(), api.setAgentConfig(key, value)
api.getModes(), api.setModes(modes)
api.getTools(), api.toggleTool(name, enabled)
api.getApprovals(), api.approveApproval(id), api.denyApproval(id)
api.getFileEdits(sessionId?), api.clearFileEdits()
api.getRollbacks(), api.getCronJobs(), api.createCronJob(payload)
api.getAgentStatus()
```

## Tipos de datos principales

```ts
interface Workspace { name: string; node_count: number; edge_count: number; updated_at: string }
interface Node { id: string; slug: string; title: string; kind: string; summary: string;
  content: string; status: string; tags: string[]; parent_id: string | null;
  updated_at: string; created_at: string; filename: string; links: Link[] }
interface NodePayload { title: string; kind: string; content: string; summary: string;
  tags: string[]; parent_ref: string | null; status: string }
interface GraphData { nodes: { id: string; label: string; kind: string }[];
  edges: { source: string; target: string; rel: string }[] }
```

## Temas CSS

Paleta amber/night (`.workspace-theme`):
```css
--brand: #ffc45a;    --bg: #050505;
--ws-bg: #060400;     --ws-text: #e6edf3;
--ws-success: #86efac; --ws-danger: #fca5a5;
```

## GraphView — Algoritmo de layout

`hierarchicalLayout()` en `GraphView.tsx`:

1. **BFS level assignment** — nodos raíz (in-degree 0) en nivel 0
2. **Ordenación inicial** por `kind` (index → topic → project → detail → person → reference → script → doc → agent-note)
3. **3 pasadas de barycenter crossing minimization**: alternando top-down y bottom-up
4. **Posiciones x/y**: cada nivel centrado, gap uniforme

Parámetros:
```ts
const NODE_W = 175    // ancho del nodo
const NODE_GAP = 52   // gap horizontal
const ROW_H = 130     // altura de cada nivel
```

## NodeEditor — Markdown parser

`renderMarkdown()` en `NodeEditor.tsx`:
- Fenced code blocks → `<pre class="md-pre">`
- Inline code → `<code class="inline-code">`
- Headings (h1-h4) → `<h1 class="md-h1">`
- Blockquotes → `<blockquote class="md-blockquote">`
- Lists (ul/ol) → agrupamiento de `<li>` consecutivos
- Tables → detección por `|` con skip de separadores
- Links → `<a class="md-link">` con soporte anchor
- Paragraphs → `<p class="md-p">`

## Build y desarrollo

```bash
cd frontend
npm install
npm run dev      # dev server en puerto de Vite
npm run build    # build a dist/
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI Frontend (React)

# Workspace UI — Frontend React

# Workspace UI — Frontend

React + TypeScript SPA corriendo en `~/.laia/workspace-ui/frontend/`.

## Estructura de directorios

```
frontend/
├── index.html              # Entry HTML
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── src/
│   ├── main.tsx             # createRoot, StrictMode
│   ├── App.tsx               # BrowserRouter + Layout + rutas
│   ├── index.css             # Todo el tema CSS (variables, componentes)
│   ├── App.css                # Estilos estáticos
│   ├── components/
│   │   ├── ChatPanel.tsx     # Panel de chat flotante
│   │   ├── NeuralBackground.tsx
│   │   ├── LaiaNeuralAvatar.tsx
│   │   ├── WorkspaceActions.tsx
│   │   ├── Toast.tsx
│   │   └── workspace/
│   │       ├── Workspace.tsx         # Control center
│   │       ├── TopBar.tsx
│   │       ├── SidePanels.tsx
│   │       ├── SessionsRail.tsx
│   │       ├── CommandPalette.tsx
│   │       ├── ToolDetailModal.tsx
│   │       ├── SettingsDrawer.tsx
│   │       ├── ChatStream.tsx
│   │       ├── ApprovalDialog.tsx
│   │       ├── DiffModal.tsx
│   │       └── PromptDialog.tsx
│   ├── pages/
│   │   ├── Home.tsx              # Landing + scroll transition + workspace
│   │   ├── WorkspaceList.tsx     # Grid de workspaces (Nexus)
│   │   ├── NodeBrowser.tsx       # Tabla de nodos
│   │   ├── NodeEditor.tsx        # Editor de nodo (markdown + preview)
│   │   ├── GraphView.tsx         # Grafo React Flow
│   │   ├── ContextEnginePage.tsx
│   │   └── Setup.tsx
│   └── lib/
│       ├── api.ts           # Cliente HTTP — todos los fetch a FastAPI
│       ├── agentRuntime.tsx  # Provider + hooks para WebSocket RPC
│       ├── kind.ts          # Colores y estilos por kind de nodo
│       ├── time.ts          # relativeTime()
│       └── tauri.ts         # initServerUrl() para Tauri
└── dist/                    # Build de producción (servido por FastAPI)
```

## Dependencias principales

- `react` + `react-dom` ^18
- `react-router-dom` ^6 (SPA routing)
- `@xyflow/react` ^12 (React Flow para grafos)
- `lucide-react` (iconos)
- `tailwindcss` ^3

## API client (`api.ts`)

Objeto `api` con métodos organizados por dominio:

### Workspaces
```ts
api.getWorkspaces(): Promise<Workspace[]>
```

### Nodos
```ts
api.getNodes(ws: string): Promise<NodeSummary[]>
api.getNode(ws: string, ref: string): Promise<Node>
api.createNode(ws: string, payload: NodePayload): Promise<Node>
api.updateNode(ws: string, ref: string, payload: NodePayload): Promise<Node>
api.deleteNode(ws: string, ref: string): Promise<void>
api.searchNodes(ws: string, q: string): Promise<SearchResult[]>
api.getGraph(ws: string): Promise<GraphData>
api.addLink(ws: string, ref: string, payload: LinkPayload): Promise<void>
```

### Context Engine
```ts
api.getContextEngineConfig(): Promise<ContextEngineConfig>
api.getContextEngineInjected(): Promise<InjectedData>
api.getContextEnginePrefetch(q: string): Promise<PrefetchResult>
api.getContextEngineSkills(): Promise<SkillsData>
```

### Chat
```ts
api.chat(messages: ChatMessage[], workspace?: string): Promise<ReadableStream>
```

### Agente (REST)
```ts
api.getSessions(), api.createSession(), api.resumeSession(key)
api.getCurrentSession(), api.interruptSession(), api.undoSession(), api.compressSession()
api.getCommands(), api.executeCommand(cmd, sessionId?)
api.getModels(), api.getAgentConfig(), api.setAgentConfig(key, value)
api.getModes(), api.setModes(modes)
api.getTools(), api.toggleTool(name, enabled)
api.getApprovals(), api.approveApproval(id), api.denyApproval(id)
api.getFileEdits(sessionId?), api.clearFileEdits()
api.getRollbacks(), api.getCronJobs(), api.createCronJob(payload)
api.getAgentStatus()
```

## Tipos de datos principales

```ts
interface Workspace { name: string; node_count: number; edge_count: number; updated_at: string }
interface Node { id: string; slug: string; title: string; kind: string; summary: string;
  content: string; status: string; tags: string[]; parent_id: string | null;
  updated_at: string; created_at: string; filename: string; links: Link[] }
interface NodePayload { title: string; kind: string; content: string; summary: string;
  tags: string[]; parent_ref: string | null; status: string }
interface GraphData { nodes: { id: string; label: string; kind: string }[];
  edges: { source: string; target: string; rel: string }[] }
```

## Temas CSS

Paleta amber/night (`.workspace-theme`):
```css
--brand: #ffc45a;    --bg: #050505;
--ws-bg: #060400;     --ws-text: #e6edf3;
--ws-success: #86efac; --ws-danger: #fca5a5;
```

## GraphView — Algoritmo de layout

`hierarchicalLayout()` en `GraphView.tsx`:

1. **BFS level assignment** — nodos raíz (in-degree 0) en nivel 0
2. **Ordenación inicial** por `kind` (index → topic → project → detail → person → reference → script → doc → agent-note)
3. **3 pasadas de barycenter crossing minimization**: alternando top-down y bottom-up
4. **Posiciones x/y**: cada nivel centrado, gap uniforme

Parámetros:
```ts
const NODE_W = 175    // ancho del nodo
const NODE_GAP = 52   // gap horizontal
const ROW_H = 130     // altura de cada nivel
```

## NodeEditor — Markdown parser

`renderMarkdown()` en `NodeEditor.tsx`:
- Fenced code blocks → `<pre class="md-pre">`
- Inline code → `<code class="inline-code">`
- Headings (h1-h4) → `<h1 class="md-h1">`
- Blockquotes → `<blockquote class="md-blockquote">`
- Lists (ul/ol) → agrupamiento de `<li>` consecutivos
- Tables → detección por `|` con skip de separadores
- Links → `<a class="md-link">` con soporte anchor
- Paragraphs → `<p class="md-p">`

## Build y desarrollo

```bash
cd frontend
npm install
npm run dev      # dev server en puerto de Vite
npm run build    # build a dist/
```


> 📅 Documentado: 2026-05-08
