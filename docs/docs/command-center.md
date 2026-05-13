# Command Center — Orquestación Multi-Agente

**Ruta:** `/command-center`  
**Implementado:** Mayo 2026  
**Actualizado:** Mayo 2026

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
4. Monitorear con `command_center_read_all` o `command_center_read` periódico
5. Si hay errores → `command_center_inject` corrección o nuevo frontier para debug
6. Al terminar → documentar en workspace DB

---

## Herramientas nativas de Hermes en Command Center

```
command_center_list                             → listar terminales activas con IDs
command_center_spawn(agent_type, cwd, prompt)   → lanzar agente PTY
command_center_inject(terminal_id, text)        → enviar texto a terminal en ejecución
command_center_approvals                        → listar prompts pendientes de aprobación
command_center_prompt_approval_mode(enabled?)   → activar/desactivar aprobación previa
command_center_read(terminal_id)                → leer output reciente de una terminal
command_center_read_all                         → snapshot de todas las terminales vivas
command_center_kill(terminal_id)                → matar terminal
```

**Nunca** usar `terminal(background=true)` — esa API no existe en esta interfaz.

Por defecto, los prompts que Hermes intenta enviar a agentes PTY pasan por aprobación humana en la UI antes de inyectarse. El usuario puede aprobar/rechazar cada prompt desde la barra de aprobaciones del Command Center, o desactivar temporalmente esa barrera desde el toggle `Aprobación` / `command_center_prompt_approval_mode(false)`.

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
  └── ToolShell         ← area aislada de Hermes para Command Center
      └── AgentProvider         ← chat de Hermes embebido (panel izquierdo)
          ├── HermesNotifyBridge  ← bridge para notificar a Hermes cuando muere una terminal
          └── ToolContextInjector ← inyecta contexto del Command Center a Hermes
```

---

## Sistema de inyección de contexto (ToolContextInjector)

### El problema que resuelve

Hermes se embebe en múltiples herramientas (Command Center, Workspace principal, futuras). Sin inyección de contexto, no sabe en qué herramienta está y responde con APIs genéricas o inexistentes.

### Arquitectura de contexto

**Capa 1 — Sesion aislada por area:**  
Command Center usa `areaId="command-center"`. Backend mantiene una sesion activa por area, asi que Workspace y Command Center no comparten system prompt ni historial activo.

**Capa 2 — Contexto estatico (system prompt permanente):**  
`COMMAND_CENTER_APP_CONTEXT` se pasa como `appContext` al `ToolAreaProvider`, que lo envia al backend como query param `?app_context=...`. El backend lo propaga hasta `tui_gateway`, que lo prepende al `ephemeral_system_prompt` del agente en `session.create`. Este contexto persiste en todos los turnos de la sesion del area.

**Capa 3 — Estado dinamico (lista de terminales activas):**  
`ToolContextInjector` usa `submitContext` para registrar actualizaciones cuando cambia la lista de terminales. Estas se renderizan en el chat como tarjetas colapsables (no como burbujas de usuario) y se adjuntan como contexto oculto en el siguiente turno real del usuario.

Importante: el estado dinamico **no** debe llamar a `prompt.submit` directamente. Si se enviara como prompt independiente, Hermes responderia a la tarjeta de contexto como si fuera un mensaje del usuario y podria confundir Command Center con Workspace.

### Cadena de propagación de app_context

```
CommandCenter.tsx
  └── <ToolAreaProvider profile={commandCenterToolArea} state={terminals}>
        └── AgentProvider areaId="command-center" appContext={COMMAND_CENTER_APP_CONTEXT}
              └── WebSocket: /api/control/ws?area_id=command-center&app_context=<encoded>
                    └── backend/main.py → control_ws(area_id, app_context)
                          └── ensure_session(area_id="command-center", app_context=...)
                                └── rpc("session.create", {"app_context": ...})
                                      └── tui_gateway/server.py → _sessions[sid]["app_context"]
                                            └── _make_agent() → ephemeral_system_prompt
```

### Cadena de propagación del estado dinamico

```
CommandCenter.tsx obtiene terminales activas
  └── commandCenterContext.stateHash(terminals)
        └── ToolContextInjector detecta cambio
              └── submitContext("command-center", text)
                    ├── guarda text en toolContextRef["command-center"]
                    └── muestra ContextCard en el chat

Usuario envia "donde estamos?"
  └── submitText("donde estamos?")
        └── prompt.submit({
              text: "donde estamos?\n\n<background-ui-context>...</background-ui-context>",
              persist_user_message: "donde estamos?"
            })
              └── tui_gateway.run_conversation(
                    run_message=<texto enriquecido>,
                    persist_user_message=<texto limpio>
                  )
```

El modelo ve:

- la pregunta real del usuario;
- el `area-context` de Command Center;
- el `tool-context` con terminales activas.

El historial guarda solo la pregunta real. Esto evita que el chat se llene de bloques internos y evita respuestas automaticas a tarjetas de contexto.

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

export const miHerramientaArea: ToolAreaProfile<MiEstado> = {
  areaId: 'mi-herramienta',
  appContext: MI_HERRAMIENTA_APP_CONTEXT,
  dynamicContext: miHerramientaContext,
}
```

2. En la página:
```tsx
<ToolAreaProvider profile={miHerramientaArea} state={miEstado}>
  <ChatStream ... />
</ToolAreaProvider>
```

### Sentinel CTX y ContextCard

Los mensajes de contexto se marcan con `CTX_SENTINEL = '__CTX__'` para que el chat los renderice como tarjetas compactas colapsables en lugar de burbujas de usuario normales.

El sentinel es solo UI. El LLM no debe recibir el sentinel ni debe recibir esa tarjeta como prompt independiente. El texto limpio se guarda como contexto dinamico y se adjunta al siguiente prompt real dentro de `<background-ui-context>`.

Formato interno en el array de mensajes:
```
[__CTX__:command-center]
[Command Center] Terminales activas (2):
  • claude-code-planner  id:abc123  cwd:/home/laia-arch/...
  • opencode-worker      id:def456  cwd:/home/laia-arch/...
```

---

## Problemas corregidos en la integracion

### Command Center respondia como Workspace

Sintoma:

```text
Usuario: hola, donde estamos??
LAIA: Estamos en el Workspace Principal...
```

Causas posibles:

- sesion global compartida entre areas;
- `area_id` omitido o no propagado;
- `appContext` antiguo reutilizado;
- contexto dinamico enviado como prompt normal.

Correccion implementada:

- `areaId="command-center"` en el perfil de Command Center;
- backend mantiene sesiones activas por area;
- `control.ready` incluye `area_id` y `session_id`;
- frontend filtra eventos por `session_id`;
- `appContext` de Command Center se adjunta tambien como contexto oculto en turnos reales.

### Workspace respondia a `CONTEXT · WORKSPACE`

Sintoma:

```text
CONTEXT · WORKSPACE
[Workspace] Contexto activo: Workspace Principal.

LAIA: Contexto recibido...
```

Causa:

`submitContext` renderizaba la tarjeta y ademas llamaba a `prompt.submit`. El modelo recibia el contexto como si fuera una pregunta.

Correccion implementada:

- `submitContext` solo actualiza `toolContextRef` y renderiza `ContextCard`;
- `submitText` adjunta el contexto oculto solo cuando hay mensaje real del usuario;
- `prompt.submit` usa `persist_user_message` para persistir el mensaje limpio.

---

## Prueba esperada

Despues de reiniciar workspace-ui/backend y `tui_gateway`:

1. Abrir `/command-center`.
2. Verificar que el WebSocket apunta a `/api/control/ws?area_id=command-center&app_context=...`.
3. Preguntar: `hola, donde estamos?`
4. Respuesta esperada: Command Center, centro de control multi-agente, con terminales/PTYs visibles.
5. Abrir `/`.
6. Verificar que aparece la tarjeta `CONTEXT · WORKSPACE` sin que LAIA responda automaticamente.
7. Preguntar: `donde estamos?`
8. Respuesta esperada: Workspace principal.

---

## Archivos relevantes

| Archivo | Descripción |
|---|---|
| `frontend/src/pages/CommandCenter.tsx` | Página principal — grid de terminales + chat Hermes |
| `frontend/src/components/commandcenter/TerminalPanel.tsx` | Terminal xterm.js individual |
| `frontend/src/components/commandcenter/SpawnAgentModal.tsx` | Modal para lanzar agentes |
| `frontend/src/components/commandcenter/InjectBar.tsx` | Barra de inyección de texto |
| `frontend/src/components/common/ToolAreaProvider.tsx` | Provider de area con `areaId`, `appContext` y contexto dinamico |
| `frontend/src/components/common/ToolShell.tsx` | Wrapper recomendado para paginas/herramientas con Hermes embebido |
| `frontend/src/components/common/ToolContextInjector.tsx` | Inyector genérico de contexto |
| `frontend/src/lib/toolRegistry.ts` | Registro central de herramientas/areas |
| `frontend/src/lib/contexts/commandCenterContext.ts` | Perfil de contexto del Command Center |
| `frontend/src/lib/contexts/workspaceContext.ts` | Perfil de contexto del workspace principal |
| `frontend/src/lib/terminalApi.ts` | Cliente REST para terminales (list/spawn/kill) |
| `frontend/src/lib/agentRuntime.tsx` | Runtime de Hermes — WebSocket, sesiones por area, `submitContext`, `background-ui-context` |
| `backend/main.py` | FastAPI — endpoint `/api/control/ws` con `area_id` y `app_context` |
| `tui_gateway/server.py` | Gateway — `session.create` → `_make_agent` → `ephemeral_system_prompt`; `prompt.submit.persist_user_message` |
