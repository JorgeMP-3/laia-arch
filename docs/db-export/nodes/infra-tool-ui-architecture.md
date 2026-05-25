# Tool UI Architecture

## Metadata

- ID: `116`
- Slug: `infra-tool-ui-architecture`
- Kind: `doc`
- Status: `active`
- Filename: `infra-tool-ui-architecture.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:35:14.253327+00:00`
- Updated at: `2026-05-08T08:35:14.253327+00:00`
- Aliases: `infra-tool-ui-architecture`

## Summary

**Implementado:** Mayo 2026

## Body

# Arquitectura UI de Herramientas LAIA

**Implementado:** Mayo 2026  
**Alcance:** workspace-ui frontend, runtime Hermes embebido y nuevas herramientas integrables

---

## Objetivo

LAIA empezo con una UI centrada en el Workspace principal, pero el sistema crecio hasta incluir Command Center y futuras herramientas con chat propio. El objetivo de esta arquitectura es que cada herramienta se integre como parte de un ecosistema comun, no como una pantalla aislada con mantenimiento especial.

La UI queda organizada alrededor de tres conceptos:

1. **area**: identidad estable de una herramienta o superficie de trabajo.
2. **profile**: contrato unico que describe el area para frontend y runtime.
3. **shell/provider**: wrapper comun que conecta la herramienta con Hermes, contexto dinamico y layout.

---

## Principios

- Cada herramienta con Hermes embebido tiene un `areaId` unico.
- Cada area tiene una sesion activa separada en backend.
- El `appContext` describe identidad, rol y tools reales de forma estatica.
- El estado cambiante se inyecta con `ToolContextInjector`, no en el system prompt.
- El contexto dinamico se muestra como `ContextCard`, pero no genera respuestas automaticas.
- El historial guarda mensajes limpios del usuario.
- Las nuevas herramientas se registran en un punto unico (`toolRegistry.ts`).
- Las paginas no deben montar `AgentProvider` manualmente salvo que haya una razon tecnica clara.

---

## Piezas frontend

### `ToolAreaProfile<S>`

Contrato principal para una herramienta:

```typescript
interface ToolAreaProfile<S = void> {
  areaId: string
  appContext: string
  dynamicContext?: ToolContextProfile<S>
}
```

Campos:

| Campo | Uso |
|---|---|
| `areaId` | Identificador estable usado por frontend/backend para aislar sesion |
| `appContext` | Contexto estatico de area que define ubicacion, rol y herramientas reales |
| `dynamicContext` | Perfil opcional para estado cambiante visible en UI |

### `ToolContextProfile<S>`

Contrato del contexto dinamico:

```typescript
interface ToolContextProfile<S> {
  toolId: string
  stateHash: (state: S) => string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
}
```

Semantica:

- `stateHash` decide si hay que reinjectar.
- `getConnectText` genera el contexto completo al conectar o reconectar.
- `getDeltaText` genera actualizaciones compactas.
- Si `getDeltaText` no existe, se usa `getConnectText`.
- El hash se resetea cuando cambia `sessionId` para evitar saltarse la inyeccion inicial de una sesion nueva.

### `ToolAreaProvider`

Wrapper funcional. Monta:

- `AgentProvider(areaId, appContext)`;
- `ToolContextInjector` si el perfil tiene `dynamicContext`;
- los hijos de la pagina.

Uso:

```tsx
<ToolAreaProvider profile={profile} state={state}>
  <ChatStream />
  <ToolUI />
</ToolAreaProvider>
```

### `ToolShell`

Wrapper recomendado para paginas nuevas. Encapsula `ToolAreaProvider` y deja un punto unico para layout comun, atributos `data-tool-area` y futuras capacidades transversales.

Uso:

```tsx
<ToolShell profile={miHerramientaArea} state={miEstado}>
  <MiHerramienta />
</ToolShell>
```

### `toolRegistry.ts`

Registro central de herramientas/areas. Debe contener:

- `areaId`;
- `route`;
- `label`;
- `description`;
- `capabilities`;
- `toolArea` cuando la herramienta usa Hermes embebido.

Este registro evita que cada pantalla tenga que inventar su propio contrato de integracion.

---

## Piezas runtime

### `AgentProvider`

Responsabilidades principales:

- abrir `/api/control/ws?area_id=<areaId>&app_context=<encoded>`;
- mantener `sessionId`;
- filtrar eventos que pertenecen a otra sesion;
- exponer `submitText`, `submitContext`, `submitBtw`, `submitBackground`;
- mantener `toolContextRef` con el ultimo contexto dinamico por `toolId`;
- construir prompts enriquecidos con `<background-ui-context>`;
- usar `persist_user_message` para guardar historial limpio.

### `submitContext`

Antes del cambio, `submitContext` llamaba a `prompt.submit` y eso hacia que Hermes respondiera al contexto. Ahora:

```text
submitContext(toolId, text)
  -> toolContextRef[toolId] = text
  -> messages += "[__CTX__:<toolId>]\n<text>"
  -> NO prompt.submit
```

La UI sigue mostrando la tarjeta de contexto, pero el modelo no recibe un turno nuevo.

### `submitText`

Cuando hay un mensaje real del usuario:

```text
submitText(userText)
  -> UI muestra userText limpio
  -> prompt.submit({
       text: userText + "\n\n<background-ui-context>...</background-ui-context>",
       persist_user_message: userText
     })
```

El bloque oculto incluye:

- `area-context`: `appContext` del area actual;
- `tool-context`: ultimo contexto dinamico de cada herramienta registrada en `toolContextRef`.

### `submitBtw`

`submitBtw` sigue usando `prompt.btw`, pero tambien puede adjuntar el contexto oculto. El historial persiste la forma limpia `(btw) <texto>`.

---

## Piezas backend

### workspace-ui backend

El backend mantiene sesiones activas por area:

```text
area_sessions[areaId] = {
  session_id,
  app_context_hash,
  metadata
}
```

`ensure_session(area_id, app_context)`:

1. normaliza `area_id`;
2. calcula hash de `app_context`;
3. reutiliza la sesion solo si el area coincide y el hash coincide;
4. crea una sesion nueva si cambia el `appContext`;
5. emite `control.ready` con `{ area_id, session_id }`.

`workspace` es el area por defecto para compatibilidad.

### tui_gateway

Cambios relevantes:

- `session.create(app_context)` sigue siendo la unica entrada de contexto estatico al `ephemeral_system_prompt`;
- `prompt.submit` acepta `persist_user_message`;
- `_run_prompt_submit` pasa `persist_user_message` a `AIAgent.run_conversation`;
- `prompt.btw` existe como alias compatible.

Esto permite que el modelo reciba contexto oculto sin guardar ese contexto como mensaje visible en la conversacion.

---

## Herramientas integradas actualmente

### Workspace principal

| Campo | Valor |
|---|---|
| `areaId` | `workspace` |
| Ruta | `/` |
| Perfil | `workspaceToolArea` |
| Contexto dinamico | Workspace principal activo |
| Objetivo | Chat directo de desarrollo, codigo, shell, git y Context Engine |

### Command Center

| Campo | Valor |
|---|---|
| `areaId` | `command-center` |
| Ruta | `/command-center` |
| Perfil | `commandCenterToolArea` |
| Contexto dinamico | Terminales PTY activas |
| Objetivo | Orquestacion multi-agente con terminales visibles |

---

## Como crear una herramienta nueva

### 1. Crear contexto

Archivo:

```text
.laia-arch/workspace-ui/frontend/src/lib/contexts/<toolName>Context.ts
```

Debe exportar:

- `TOOL_APP_CONTEXT`;
- `toolContext` si hay estado dinamico;
- `toolArea`.

### 2. Registrar en `toolRegistry.ts`

La herramienta debe tener entrada unica en el registro. Si usa Hermes, enlazar `toolArea`.

### 3. Montar con `ToolShell`

La pagina debe envolver su UI con:

```tsx
<ToolShell profile={toolArea} state={state}>
  ...
</ToolShell>
```

### 4. Registrar tools backend

Si `appContext` menciona herramientas como `mi_tool_read`, esas tools deben existir realmente en backend/toolsets. No anunciar tools que no esten registradas.

### 5. Probar identidad

Preguntas minimas:

- En la herramienta nueva: `donde estamos?`
- En Workspace: `donde estamos?`
- En Command Center: `donde estamos?`

Cada area debe responder con su identidad propia.

---

## Reglas de mantenimiento

- No montar chats globales legacy junto a areas aisladas.
- No reutilizar `areaId` entre herramientas.
- No poner estado cambiante en `appContext`.
- No llamar a `prompt.submit` desde inyectores de contexto.
- No persistir prompts enriquecidos sin `persist_user_message`.
- No anunciar tools inexistentes en `appContext`.
- No mezclar Context Engine con `appContext`: son capas diferentes.

---

## Checklist profesional para PRs

- [ ] Nueva herramienta registrada en `toolRegistry.ts`.
- [ ] Perfil `ToolAreaProfile` creado.
- [ ] `areaId` unico y estable.
- [ ] `appContext` breve, estatico y con tools reales.
- [ ] Pagina montada con `ToolShell`.
- [ ] Contexto dinamico probado si existe.
- [ ] `ContextCard` aparece sin respuesta automatica del modelo.
- [ ] `donde estamos?` responde correctamente en la nueva area.
- [ ] Workspace y Command Center siguen respondiendo con su identidad propia.
- [ ] Build frontend pasa.
- [ ] Sintaxis backend/gateway pasa si se tocaron Python.
- [ ] Documentacion actualizada.

---

## Archivos relevantes

| Archivo | Responsabilidad |
|---|---|
| `.laia-arch/workspace-ui/frontend/src/lib/agentRuntime.tsx` | Runtime central de Hermes embebido |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolAreaProvider.tsx` | Provider comun para areas |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolShell.tsx` | Shell recomendado para paginas |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolContextInjector.tsx` | Inyeccion dinamica de contexto |
| `.laia-arch/workspace-ui/frontend/src/lib/toolRegistry.ts` | Registro central de herramientas |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/workspaceContext.ts` | Perfil Workspace |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/commandCenterContext.ts` | Perfil Command Center |
| `.laia-arch/workspace-ui/backend/main.py` | Sesiones activas por area y WebSocket control |
| `.laia-arch/tui_gateway/server.py` | Gateway JSON-RPC, `prompt.submit`, `persist_user_message` |


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Tool UI Architecture

# Arquitectura UI de Herramientas LAIA

**Implementado:** Mayo 2026  
**Alcance:** workspace-ui frontend, runtime Hermes embebido y nuevas herramientas integrables

---

## Objetivo

LAIA empezo con una UI centrada en el Workspace principal, pero el sistema crecio hasta incluir Command Center y futuras herramientas con chat propio. El objetivo de esta arquitectura es que cada herramienta se integre como parte de un ecosistema comun, no como una pantalla aislada con mantenimiento especial.

La UI queda organizada alrededor de tres conceptos:

1. **area**: identidad estable de una herramienta o superficie de trabajo.
2. **profile**: contrato unico que describe el area para frontend y runtime.
3. **shell/provider**: wrapper comun que conecta la herramienta con Hermes, contexto dinamico y layout.

---

## Principios

- Cada herramienta con Hermes embebido tiene un `areaId` unico.
- Cada area tiene una sesion activa separada en backend.
- El `appContext` describe identidad, rol y tools reales de forma estatica.
- El estado cambiante se inyecta con `ToolContextInjector`, no en el system prompt.
- El contexto dinamico se muestra como `ContextCard`, pero no genera respuestas automaticas.
- El historial guarda mensajes limpios del usuario.
- Las nuevas herramientas se registran en un punto unico (`toolRegistry.ts`).
- Las paginas no deben montar `AgentProvider` manualmente salvo que haya una razon tecnica clara.

---

## Piezas frontend

### `ToolAreaProfile<S>`

Contrato principal para una herramienta:

```typescript
interface ToolAreaProfile<S = void> {
  areaId: string
  appContext: string
  dynamicContext?: ToolContextProfile<S>
}
```

Campos:

| Campo | Uso |
|---|---|
| `areaId` | Identificador estable usado por frontend/backend para aislar sesion |
| `appContext` | Contexto estatico de area que define ubicacion, rol y herramientas reales |
| `dynamicContext` | Perfil opcional para estado cambiante visible en UI |

### `ToolContextProfile<S>`

Contrato del contexto dinamico:

```typescript
interface ToolContextProfile<S> {
  toolId: string
  stateHash: (state: S) => string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
}
```

Semantica:

- `stateHash` decide si hay que reinjectar.
- `getConnectText` genera el contexto completo al conectar o reconectar.
- `getDeltaText` genera actualizaciones compactas.
- Si `getDeltaText` no existe, se usa `getConnectText`.
- El hash se resetea cuando cambia `sessionId` para evitar saltarse la inyeccion inicial de una sesion nueva.

### `ToolAreaProvider`

Wrapper funcional. Monta:

- `AgentProvider(areaId, appContext)`;
- `ToolContextInjector` si el perfil tiene `dynamicContext`;
- los hijos de la pagina.

Uso:

```tsx
<ToolAreaProvider profile={profile} state={state}>
  <ChatStream />
  <ToolUI />
</ToolAreaProvider>
```

### `ToolShell`

Wrapper recomendado para paginas nuevas. Encapsula `ToolAreaProvider` y deja un punto unico para layout comun, atributos `data-tool-area` y futuras capacidades transversales.

Uso:

```tsx
<ToolShell profile={miHerramientaArea} state={miEstado}>
  <MiHerramienta />
</ToolShell>
```

### `toolRegistry.ts`

Registro central de herramientas/areas. Debe contener:

- `areaId`;
- `route`;
- `label`;
- `description`;
- `capabilities`;
- `toolArea` cuando la herramienta usa Hermes embebido.

Este registro evita que cada pantalla tenga que inventar su propio contrato de integracion.

---

## Piezas runtime

### `AgentProvider`

Responsabilidades principales:

- abrir `/api/control/ws?area_id=<areaId>&app_context=<encoded>`;
- mantener `sessionId`;
- filtrar eventos que pertenecen a otra sesion;
- exponer `submitText`, `submitContext`, `submitBtw`, `submitBackground`;
- mantener `toolContextRef` con el ultimo contexto dinamico por `toolId`;
- construir prompts enriquecidos con `<background-ui-context>`;
- usar `persist_user_message` para guardar historial limpio.

### `submitContext`

Antes del cambio, `submitContext` llamaba a `prompt.submit` y eso hacia que Hermes respondiera al contexto. Ahora:

```text
submitContext(toolId, text)
  -> toolContextRef[toolId] = text
  -> messages += "[__CTX__:<toolId>]\n<text>"
  -> NO prompt.submit
```

La UI sigue mostrando la tarjeta de contexto, pero el modelo no recibe un turno nuevo.

### `submitText`

Cuando hay un mensaje real del usuario:

```text
submitText(userText)
  -> UI muestra userText limpio
  -> prompt.submit({
       text: userText + "\n\n<background-ui-context>...</background-ui-context>",
       persist_user_message: userText
     })
```

El bloque oculto incluye:

- `area-context`: `appContext` del area actual;
- `tool-context`: ultimo contexto dinamico de cada herramienta registrada en `toolContextRef`.

### `submitBtw`

`submitBtw` sigue usando `prompt.btw`, pero tambien puede adjuntar el contexto oculto. El historial persiste la forma limpia `(btw) <texto>`.

---

## Piezas backend

### workspace-ui backend

El backend mantiene sesiones activas por area:

```text
area_sessions[areaId] = {
  session_id,
  app_context_hash,
  metadata
}
```

`ensure_session(area_id, app_context)`:

1. normaliza `area_id`;
2. calcula hash de `app_context`;
3. reutiliza la sesion solo si el area coincide y el hash coincide;
4. crea una sesion nueva si cambia el `appContext`;
5. emite `control.ready` con `{ area_id, session_id }`.

`workspace` es el area por defecto para compatibilidad.

### tui_gateway

Cambios relevantes:

- `session.create(app_context)` sigue siendo la unica entrada de contexto estatico al `ephemeral_system_prompt`;
- `prompt.submit` acepta `persist_user_message`;
- `_run_prompt_submit` pasa `persist_user_message` a `AIAgent.run_conversation`;
- `prompt.btw` existe como alias compatible.

Esto permite que el modelo reciba contexto oculto sin guardar ese contexto como mensaje visible en la conversacion.

---

## Herramientas integradas actualmente

### Workspace principal

| Campo | Valor |
|---|---|
| `areaId` | `workspace` |
| Ruta | `/` |
| Perfil | `workspaceToolArea` |
| Contexto dinamico | Workspace principal activo |
| Objetivo | Chat directo de desarrollo, codigo, shell, git y Context Engine |

### Command Center

| Campo | Valor |
|---|---|
| `areaId` | `command-center` |
| Ruta | `/command-center` |
| Perfil | `commandCenterToolArea` |
| Contexto dinamico | Terminales PTY activas |
| Objetivo | Orquestacion multi-agente con terminales visibles |

---

## Como crear una herramienta nueva

### 1. Crear contexto

Archivo:

```text
.laia-arch/workspace-ui/frontend/src/lib/contexts/<toolName>Context.ts
```

Debe exportar:

- `TOOL_APP_CONTEXT`;
- `toolContext` si hay estado dinamico;
- `toolArea`.

### 2. Registrar en `toolRegistry.ts`

La herramienta debe tener entrada unica en el registro. Si usa Hermes, enlazar `toolArea`.

### 3. Montar con `ToolShell`

La pagina debe envolver su UI con:

```tsx
<ToolShell profile={toolArea} state={state}>
  ...
</ToolShell>
```

### 4. Registrar tools backend

Si `appContext` menciona herramientas como `mi_tool_read`, esas tools deben existir realmente en backend/toolsets. No anunciar tools que no esten registradas.

### 5. Probar identidad

Preguntas minimas:

- En la herramienta nueva: `donde estamos?`
- En Workspace: `donde estamos?`
- En Command Center: `donde estamos?`

Cada area debe responder con su identidad propia.

---

## Reglas de mantenimiento

- No montar chats globales legacy junto a areas aisladas.
- No reutilizar `areaId` entre herramientas.
- No poner estado cambiante en `appContext`.
- No llamar a `prompt.submit` desde inyectores de contexto.
- No persistir prompts enriquecidos sin `persist_user_message`.
- No anunciar tools inexistentes en `appContext`.
- No mezclar Context Engine con `appContext`: son capas diferentes.

---

## Checklist profesional para PRs

- [ ] Nueva herramienta registrada en `toolRegistry.ts`.
- [ ] Perfil `ToolAreaProfile` creado.
- [ ] `areaId` unico y estable.
- [ ] `appContext` breve, estatico y con tools reales.
- [ ] Pagina montada con `ToolShell`.
- [ ] Contexto dinamico probado si existe.
- [ ] `ContextCard` aparece sin respuesta automatica del modelo.
- [ ] `donde estamos?` responde correctamente en la nueva area.
- [ ] Workspace y Command Center siguen respondiendo con su identidad propia.
- [ ] Build frontend pasa.
- [ ] Sintaxis backend/gateway pasa si se tocaron Python.
- [ ] Documentacion actualizada.

---

## Archivos relevantes

| Archivo | Responsabilidad |
|---|---|
| `.laia-arch/workspace-ui/frontend/src/lib/agentRuntime.tsx` | Runtime central de Hermes embebido |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolAreaProvider.tsx` | Provider comun para areas |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolShell.tsx` | Shell recomendado para paginas |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolContextInjector.tsx` | Inyeccion dinamica de contexto |
| `.laia-arch/workspace-ui/frontend/src/lib/toolRegistry.ts` | Registro central de herramientas |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/workspaceContext.ts` | Perfil Workspace |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/commandCenterContext.ts` | Perfil Command Center |
| `.laia-arch/workspace-ui/backend/main.py` | Sesiones activas por area y WebSocket control |
| `.laia-arch/tui_gateway/server.py` | Gateway JSON-RPC, `prompt.submit`, `persist_user_message` |


> 📅 Documentado: 2026-05-08
