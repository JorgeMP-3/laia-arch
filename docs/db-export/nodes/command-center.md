# Command Center — Multi-Agent Orchestration

## Metadata

- ID: `98`
- Slug: `command-center`
- Kind: `doc`
- Status: `active`
- Filename: `command-center.md`
- Parent: `orchestration-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:03.195357+00:00`
- Updated at: `2026-05-08T08:34:03.195357+00:00`
- Aliases: `command-center`

## Summary

**Ruta:** `/command-center`

## Body

# Command Center — Orquestación Multi-Agente

# Command Center — Orquestación Multi-Agente

**Ruta:** `/command-center`  
**Implementado:** Mayo 2026

---

## Qué es

El Command Center es la sala de control multi-agente de LAIA. Permite a Hermes lanzar, monitorear e inyectar texto en agentes PTY (terminales reales con Claude Code, Codex, OpenCode o bash), coordinando trabajos complejos con el sistema de 3 roles.

---

## Sistema de 3 Roles

| Rol | Quién | Cuándo usarlo |
|---|---|---|
| **Orchestrator** | Hermes/LAIA | Siempre — planifica, asigna, monitorea, documenta |
| **Frontier** | `claude-code-planner`, `codex-worker` | Arquitectura, debugging difícil, QA, revisión de código |
| **Economy** | `opencode-worker`, `bash` | Implementación rutinaria, scripts, tareas repetitivas |

**Protocolo de orquestación:**
1. Spawn `claude-code-planner` con el plan técnico
2. Leer su output con `command_center_read` hasta que salga
3. Spawn `opencode-worker`(s) con tareas específicas del plan
4. Monitorear con `command_center_read` periódico
5. Si hay errores → `command_center_inject` corrección o nuevo frontier para debug
6. Al terminar → documentar en workspace DB

---

## Herramientas nativas de Hermes en Command Center

```
command_center_list                             → listar terminales activas con IDs
command_center_spawn(agent_type, cwd, prompt)   → lanzar agente PTY
command_center_inject(terminal_id, text)        → enviar texto a terminal en ejecución
command_center_read(terminal_id)                → leer output reciente de una terminal
command_center_kill(terminal_id)                → matar terminal
```

**Nunca** usar `terminal(background=true)` — esa API no existe en esta interfaz.

---

## Arquitectura técnica

### Terminales PTY via WebSocket

Cada terminal es un proceso PTY real en el backend. El frontend usa **xterm.js** conectado por WebSocket. Los frames tienen formato:

```
{ t: 'o', d: '<base64>' }  ← output del proceso
{ t: 'i', d: '<base64>' }  ← input del usuario
{ t: 'r', d: {cols, rows} } ← resize
{ t: 'exit', d: <code> }   ← proceso terminado
```

### Componentes frontend

```
src/pages/CommandCenter.tsx
  ├── terminalApi       ← REST: list/spawn/kill
  ├── TerminalPanel     ← xterm.js + WebSocket, expone inject() via ref
  ├── SpawnAgentModal   ← formulario para lanzar agente
  ├── InjectBar         ← barra para inyectar texto a cualquier terminal
  └── AgentProvider     ← chat de Hermes embebido (panel izquierdo)
      ├── HermesNotifyBridge    ← bridge para notificar a Hermes cuando muere una terminal
      └── ToolContextInjector   ← inyecta contexto del Command Center a Hermes
```

---

## Sistema de inyección de contexto (ToolContextInjector)

### El problema que resuelve

Hermes se embebe en múltiples herramientas (Command Center, Workspace principal, futuras). Sin inyección de contexto, no sabe en qué herramienta está y responde con APIs genéricas o inexistentes.

### Arquitectura de dos capas

**Capa 1 — Contexto estático (system prompt permanente):**  
`COMMAND_CENTER_APP_CONTEXT` se pasa como `appContext` al `AgentProvider`, que lo envía al backend como query param `?app_context=...`. El backend lo propaga hasta `tui_gateway`, que lo prepende al `ephemeral_system_prompt` del agente en `session.create`. Este contexto persiste en TODOS los turnos de la sesión.

**Capa 2 — Estado dinámico (lista de terminales activas):**  
`ToolContextInjector` usa `submitContext` para inyectar actualizaciones cuando cambia la lista de terminales. Estas se renderizan en el chat como tarjetas colapsables (no como burbujas de usuario).

### Cadena de propagación de app_context

```
CommandCenter.tsx
  └── <AgentProvider appContext={COMMAND_CENTER_APP_CONTEXT}>
        └── agentRuntime.tsx → wsUrl(appContext)
              └── WebSocket: /api/control/ws?app_context=<encoded>
                    └── backend/main.py → control_ws(app_context: str = Query(""))
                          └── ensure_session(app_context=...)
                                └── rpc("session.create", {"app_context": ...})
                                      └── tui_gateway/server.py → _sessions[sid]["app_context"]
                                            └── _make_agent() → ephemeral_system_prompt
```

### Interfaz ToolContextProfile

```typescript
interface ToolContextProfile<S> {
  toolId: string
  getConnectText: (state: S) => string   // texto completo al conectar
  getDeltaText?: (state: S) => string    // texto corto en actualizaciones
  stateHash: (state: S) => string        // cambia cuando el estado relevante cambia
}
```

### Añadir contexto a una nueva herramienta

1. Crear `src/lib/contexts/miHerramientaContext.ts`:
```typescript
export const MI_HERRAMIENTA_APP_CONTEXT = `
UBICACIÓN: Estás en Mi Herramienta.
ROL: ...
HERRAMIENTAS: ...`

export const miHerramientaContext: ToolContextProfile<MiEstado> = {
  toolId: 'mi-herramienta',
  stateHash: (state) => state.id,
  getConnectText: (state) => `[Mi Herramienta] Estado: ...`,
  getDeltaText: (state) => `[Mi Herramienta · actualización] ...`,
}
```

2. En la página:
```tsx
<AgentProvider appContext={MI_HERRAMIENTA_APP_CONTEXT}>
  <ToolContextInjector profile={miHerramientaContext} state={miEstado} />
  <ChatStream ... />
</AgentProvider>
```

### Sentinel CTX y ContextCard

Los mensajes de contexto se marcan con `CTX_SENTINEL = '__CTX__'` para que el chat los renderice como tarjetas compactas colapsables en lugar de burbujas de usuario normales. El texto limpio (sin sentinel) es lo que llega al LLM.

Formato interno en el array de mensajes:
```
[__CTX__:command-center]
[Command Center] Terminales activas (2):
  • claude-code-planner  id:abc123  cwd:/home/laia-arch/...
  • opencode-worker      id:def456  cwd:/home/laia-arch/...
```

---

## Archivos relevantes

| Archivo | Descripción |
|---|---|
| `frontend/src/pages/CommandCenter.tsx` | Página principal — grid de terminales + chat Hermes |
| `frontend/src/components/commandcenter/TerminalPanel.tsx` | Terminal xterm.js individual |
| `frontend/src/components/commandcenter/SpawnAgentModal.tsx` | Modal para lanzar agentes |
| `frontend/src/components/commandcenter/InjectBar.tsx` | Barra de inyección de texto |
| `frontend/src/components/common/ToolContextInjector.tsx` | Inyector genérico de contexto |
| `frontend/src/lib/contexts/commandCenterContext.ts` | Perfil de contexto del Command Center |
| `frontend/src/lib/contexts/workspaceContext.ts` | Perfil de contexto del workspace principal |
| `frontend/src/lib/terminalApi.ts` | Cliente REST para terminales (list/spawn/kill) |
| `frontend/src/lib/agentRuntime.tsx` | Runtime de Hermes — WebSocket, submitContext |
| `backend/main.py` | FastAPI — endpoint `/api/control/ws` con `app_context` |
| `tui_gateway/server.py` | Gateway — `session.create` → `_make_agent` → `ephemeral_system_prompt` |

---

## Relacionado

→ `tool-context-injection` — Sistema genérico ToolContextInjector (documentación técnica completa para desarrolladores)

→ ToolContextInjector — Sistema de Inyección de Contexto: `tool-context-injection.md`


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `orchestration-area` (Orquestación y Command Center) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Command Center — Multi-Agent Orchestration

# Command Center — Orquestación Multi-Agente

# Command Center — Orquestación Multi-Agente

**Ruta:** `/command-center`  
**Implementado:** Mayo 2026

---

## Qué es

El Command Center es la sala de control multi-agente de LAIA. Permite a Hermes lanzar, monitorear e inyectar texto en agentes PTY (terminales reales con Claude Code, Codex, OpenCode o bash), coordinando trabajos complejos con el sistema de 3 roles.

---

## Sistema de 3 Roles

| Rol | Quién | Cuándo usarlo |
|---|---|---|
| **Orchestrator** | Hermes/LAIA | Siempre — planifica, asigna, monitorea, documenta |
| **Frontier** | `claude-code-planner`, `codex-worker` | Arquitectura, debugging difícil, QA, revisión de código |
| **Economy** | `opencode-worker`, `bash` | Implementación rutinaria, scripts, tareas repetitivas |

**Protocolo de orquestación:**
1. Spawn `claude-code-planner` con el plan técnico
2. Leer su output con `command_center_read` hasta que salga
3. Spawn `opencode-worker`(s) con tareas específicas del plan
4. Monitorear con `command_center_read` periódico
5. Si hay errores → `command_center_inject` corrección o nuevo frontier para debug
6. Al terminar → documentar en workspace DB

---

## Herramientas nativas de Hermes en Command Center

```
command_center_list                             → listar terminales activas con IDs
command_center_spawn(agent_type, cwd, prompt)   → lanzar agente PTY
command_center_inject(terminal_id, text)        → enviar texto a terminal en ejecución
command_center_read(terminal_id)                → leer output reciente de una terminal
command_center_kill(terminal_id)                → matar terminal
```

**Nunca** usar `terminal(background=true)` — esa API no existe en esta interfaz.

---

## Arquitectura técnica

### Terminales PTY via WebSocket

Cada terminal es un proceso PTY real en el backend. El frontend usa **xterm.js** conectado por WebSocket. Los frames tienen formato:

```
{ t: 'o', d: '<base64>' }  ← output del proceso
{ t: 'i', d: '<base64>' }  ← input del usuario
{ t: 'r', d: {cols, rows} } ← resize
{ t: 'exit', d: <code> }   ← proceso terminado
```

### Componentes frontend

```
src/pages/CommandCenter.tsx
  ├── terminalApi       ← REST: list/spawn/kill
  ├── TerminalPanel     ← xterm.js + WebSocket, expone inject() via ref
  ├── SpawnAgentModal   ← formulario para lanzar agente
  ├── InjectBar         ← barra para inyectar texto a cualquier terminal
  └── AgentProvider     ← chat de Hermes embebido (panel izquierdo)
      ├── HermesNotifyBridge    ← bridge para notificar a Hermes cuando muere una terminal
      └── ToolContextInjector   ← inyecta contexto del Command Center a Hermes
```

---

## Sistema de inyección de contexto (ToolContextInjector)

### El problema que resuelve

Hermes se embebe en múltiples herramientas (Command Center, Workspace principal, futuras). Sin inyección de contexto, no sabe en qué herramienta está y responde con APIs genéricas o inexistentes.

### Arquitectura de dos capas

**Capa 1 — Contexto estático (system prompt permanente):**  
`COMMAND_CENTER_APP_CONTEXT` se pasa como `appContext` al `AgentProvider`, que lo envía al backend como query param `?app_context=...`. El backend lo propaga hasta `tui_gateway`, que lo prepende al `ephemeral_system_prompt` del agente en `session.create`. Este contexto persiste en TODOS los turnos de la sesión.

**Capa 2 — Estado dinámico (lista de terminales activas):**  
`ToolContextInjector` usa `submitContext` para inyectar actualizaciones cuando cambia la lista de terminales. Estas se renderizan en el chat como tarjetas colapsables (no como burbujas de usuario).

### Cadena de propagación de app_context

```
CommandCenter.tsx
  └── <AgentProvider appContext={COMMAND_CENTER_APP_CONTEXT}>
        └── agentRuntime.tsx → wsUrl(appContext)
              └── WebSocket: /api/control/ws?app_context=<encoded>
                    └── backend/main.py → control_ws(app_context: str = Query(""))
                          └── ensure_session(app_context=...)
                                └── rpc("session.create", {"app_context": ...})
                                      └── tui_gateway/server.py → _sessions[sid]["app_context"]
                                            └── _make_agent() → ephemeral_system_prompt
```

### Interfaz ToolContextProfile

```typescript
interface ToolContextProfile<S> {
  toolId: string
  getConnectText: (state: S) => string   // texto completo al conectar
  getDeltaText?: (state: S) => string    // texto corto en actualizaciones
  stateHash: (state: S) => string        // cambia cuando el estado relevante cambia
}
```

### Añadir contexto a una nueva herramienta

1. Crear `src/lib/contexts/miHerramientaContext.ts`:
```typescript
export const MI_HERRAMIENTA_APP_CONTEXT = `
UBICACIÓN: Estás en Mi Herramienta.
ROL: ...
HERRAMIENTAS: ...`

export const miHerramientaContext: ToolContextProfile<MiEstado> = {
  toolId: 'mi-herramienta',
  stateHash: (state) => state.id,
  getConnectText: (state) => `[Mi Herramienta] Estado: ...`,
  getDeltaText: (state) => `[Mi Herramienta · actualización] ...`,
}
```

2. En la página:
```tsx
<AgentProvider appContext={MI_HERRAMIENTA_APP_CONTEXT}>
  <ToolContextInjector profile={miHerramientaContext} state={miEstado} />
  <ChatStream ... />
</AgentProvider>
```

### Sentinel CTX y ContextCard

Los mensajes de contexto se marcan con `CTX_SENTINEL = '__CTX__'` para que el chat los renderice como tarjetas compactas colapsables en lugar de burbujas de usuario normales. El texto limpio (sin sentinel) es lo que llega al LLM.

Formato interno en el array de mensajes:
```
[__CTX__:command-center]
[Command Center] Terminales activas (2):
  • claude-code-planner  id:abc123  cwd:/home/laia-arch/...
  • opencode-worker      id:def456  cwd:/home/laia-arch/...
```

---

## Archivos relevantes

| Archivo | Descripción |
|---|---|
| `frontend/src/pages/CommandCenter.tsx` | Página principal — grid de terminales + chat Hermes |
| `frontend/src/components/commandcenter/TerminalPanel.tsx` | Terminal xterm.js individual |
| `frontend/src/components/commandcenter/SpawnAgentModal.tsx` | Modal para lanzar agentes |
| `frontend/src/components/commandcenter/InjectBar.tsx` | Barra de inyección de texto |
| `frontend/src/components/common/ToolContextInjector.tsx` | Inyector genérico de contexto |
| `frontend/src/lib/contexts/commandCenterContext.ts` | Perfil de contexto del Command Center |
| `frontend/src/lib/contexts/workspaceContext.ts` | Perfil de contexto del workspace principal |
| `frontend/src/lib/terminalApi.ts` | Cliente REST para terminales (list/spawn/kill) |
| `frontend/src/lib/agentRuntime.tsx` | Runtime de Hermes — WebSocket, submitContext |
| `backend/main.py` | FastAPI — endpoint `/api/control/ws` con `app_context` |
| `tui_gateway/server.py` | Gateway — `session.create` → `_make_agent` → `ephemeral_system_prompt` |

---

## Relacionado

→ `tool-context-injection` — Sistema genérico ToolContextInjector (documentación técnica completa para desarrolladores)

→ ToolContextInjector — Sistema de Inyección de Contexto: `tool-context-injection.md`


> 📅 Documentado: 2026-05-08
