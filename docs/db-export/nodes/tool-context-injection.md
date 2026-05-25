# ToolContextInjector System

## Metadata

- ID: `99`
- Slug: `tool-context-injection`
- Kind: `doc`
- Status: `active`
- Filename: `tool-context-injection.md`
- Parent: `orchestration-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:03.568510+00:00`
- Updated at: `2026-05-08T08:34:03.568510+00:00`
- Aliases: `tool-context-injection`

## Summary

**Implementado:** Mayo 2026

## Body

# ToolContextInjector — Sistema de Inyección de Contexto

# ToolContextInjector — Sistema Genérico de Inyección de Contexto

**Implementado:** Mayo 2026  
**Uso:** Cualquier herramienta que embeba a Hermes necesita inyectar contexto

---

## Por qué existe

Hermes está embebido en múltiples herramientas (Command Center, Workspace principal, futuras aplicaciones). Sin un mecanismo claro de contexto:

- No sabe en qué herramienta está
- Responde con APIs genéricas o inexistentes (`terminal(background=true)`)
- No puede coordinar trabajo específico de esa herramienta

**Solución:** Un sistema de dos capas que inyecta contexto automáticamente al conectar y lo actualiza reactivamente cuando cambia el estado.

---

## Arquitectura de dos capas

### Capa 1: Contexto estático (System Prompt permanente)

Texto que describe **qué herramienta es**, **roles y responsabilidades**, **herramientas disponibles**, etc. Se pasa **una sola vez** al crear la sesión y persiste en TODOS los turnos.

**Cómo funciona:**
1. Frontend: `<AgentProvider appContext={TOOL_APP_CONTEXT}>`
2. agentRuntime: construye URL con query param `?app_context=<encoded>`
3. Backend: recibe el query param en `/api/control/ws`
4. tui_gateway: lo almacena en `_sessions[sid]["app_context"]`
5. `_make_agent`: lo prepende al `ephemeral_system_prompt`

**Ventaja:** Muy eficiente (una sola vez) y garantizado que existe desde el primer turn.
**Desventaja:** No puede cambiar durante la sesión.

### Capa 2: Estado dinámico (Actualizaciones en chat)

Texto que describe **qué está pasando ahora** (ej: qué terminales están activas). Se inyecta en el chat cuando cambia el estado, renderizado como tarjeta compacta.

**Cómo funciona:**
1. `<ToolContextInjector profile={toolContext} state={estadoDinamico} />`
2. Detecta cambios en `state` comparando `stateHash`
3. Si es la primera inyección: envía `getConnectText(state)` al chat
4. Si hay cambios subsecuentes: envía `getDeltaText(state)` al chat
5. El texto se marca con `CTX_SENTINEL = '__CTX__'` para que el chat lo renderice como tarjeta, no burbuja

**Ventaja:** Reactivo y compacto; la UI muestra lo que Hermes ve.
**Desventaja:** No es persistente si se desconecta; requiere componente `ToolContextInjector` en cada herramienta.

---

## Interfaz ToolContextProfile<S>

```typescript
interface ToolContextProfile<S> {
  /**
   * ID único de la herramienta. Usado para etiquetar mensajes de contexto.
   * Ej: 'command-center', 'workspace', 'mi-herramienta'
   */
  toolId: string

  /**
   * Hash del estado actual. Cambia cuando el estado relevante cambia.
   * Usado para detectar si necesitamos inyectar una actualización.
   * Ej: (terminals) => terminals.filter(t => t.alive).map(t => t.id).sort().join(',')
   */
  stateHash: (state: S) => string

  /**
   * Texto completo a inyectar cuando Hermes se conecta.
   * Describe la herramienta completa, roles, protocolos, herramientas disponibles.
   * Ej: "[COMMAND CENTER]\nROLES: Orchestrator, Frontier, Economy\nHERRAMIENTAS: ..."
   */
  getConnectText: (state: S) => string

  /**
   * (Opcional) Texto corto a inyectar cuando cambia el estado después de conectar.
   * Si no existe, se reutiliza getConnectText.
   * Ej: "[Command Center · actualización] 2 terminales activas"
   */
  getDeltaText?: (state: S) => string
}
```

---

## Paso a paso: Añadir contexto a una nueva herramienta

### 1. Definir el contexto estático

**Archivo:** `frontend/src/lib/contexts/miHerramientaContext.ts`

```typescript
export const MI_HERRAMIENTA_APP_CONTEXT = `\
UBICACIÓN: Estás en Mi Herramienta (/mi-herramienta).

ROL: Hermes/LAIA — Coordinador de Mi Herramienta.

DESCRIPCIÓN:
Mi Herramienta es [descripción breve de qué hace].

HERRAMIENTAS DISPONIBLES (úsalas, no improvises otras):
  mi_herramienta_accion1(param1, param2) → descripción
  mi_herramienta_accion2()               → descripción
  mi_herramienta_listar()                → listar estado actual

PROTOCOLO DE TRABAJO:
  1. Cuando el usuario pida X, haz Y con la herramienta.
  2. Siempre monitorea el resultado con mi_herramienta_listar.
  3. Reporta cambios significativos al usuario.

NUNCA uses APIs genéricas de otro lugar.
NUNCA asumas que existen herramientas que no están listadas aquí.`
```

**Notas:**
- Usa backtick continuado `\` si el string es multilinea
- Sé específico sobre qué herramientas existen en esta herramienta
- Describe el protocolo de trabajo esperado
- Menciona explícitamente qué NO hacer

### 2. Definir el perfil de contexto dinámico

```typescript
// Puedes definir un interfaz para el estado si es complejo
interface MiEstado {
  id: string
  nombre: string
  activo: boolean
  // ...
}

export const miHerramientaContext: ToolContextProfile<MiEstado> = {
  toolId: 'mi-herramienta',

  // Hash: cambia si el estado relevante cambia
  stateHash: (state) => 
    `${state.id}-${state.nombre}-${state.activo}`,

  // Texto al conectar: descripción completa
  getConnectText: (state) => `\
[Mi Herramienta] Estado actual:
  • ID: ${state.id}
  • Nombre: ${state.nombre}
  • Activo: ${state.activo ? 'sí' : 'no'}`,

  // Texto en actualizaciones: compacto
  getDeltaText: (state) => `\
[Mi Herramienta · actualización] ${state.nombre} ${state.activo ? 'activo' : 'inactivo'}`,
}
```

**Notas:**
- `stateHash` debe retornar un string que cambie cuando cualquier estado **relevante** cambie
- Si el estado no cambia, NO se inyecta nada (eficiencia)
- `getConnectText` es detallado (primer contacto)
- `getDeltaText` es conciso (actualizaciones frecuentes)
- Si el estado es simple o no cambia, usa `stateHash: () => 'static'`

### 3. Crear la página con AgentProvider

**Archivo:** `frontend/src/pages/MiHerramienta.tsx`

```typescript
import { AgentProvider, useAgent } from '../lib/agentRuntime'
import { ChatStream } from '../components/workspace/ChatStream'
import { ToolContextInjector } from '../components/common/ToolContextInjector'
import { 
  MI_HERRAMIENTA_APP_CONTEXT, 
  miHerramientaContext 
} from '../lib/contexts/miHerramientaContext'

export default function MiHerramienta() {
  const [estado, setEstado] = useState<MiEstado>({ /* ... */ })

  return (
    <AgentProvider appContext={MI_HERRAMIENTA_APP_CONTEXT}>
      {/* Inyector de contexto dinámico */}
      <ToolContextInjector profile={miHerramientaContext} state={estado} />

      {/* Chat de Hermes */}
      <ChatStream
        onOpenDiff={() => {}}
        onOpenCommands={() => {}}
        onOpenTool={() => {}}
      />

      {/* Tu interfaz específica aquí */}
      <div>
        {/* ... */}
      </div>
    </AgentProvider>
  )
}
```

**Notas:**
- `appContext={MI_HERRAMIENTA_APP_CONTEXT}` va al primer turn y es permanente
- `<ToolContextInjector>` va dentro de `<AgentProvider>` y es reactivo
- El contexto es completamente automático — cambios en `estado` disparan re-inyección

### 4. Asegurarse de que las herramientas existan en el backend

Las herramientas listadas en `MI_HERRAMIENTA_APP_CONTEXT` deben existir en la capa de tools del agente (workspace-context plugin, herramientas de gateway, etc.). De lo contrario, Hermes intentará usarlas y fallará.

**Verificación:**
- Busca dónde se registran las tools en el backend
- Añade tus tools allí
- Documenta su interfaz en el archivo de contexto

---

## Ejemplo completo: Workspace principal

### Archivo: `frontend/src/lib/contexts/workspaceContext.ts`

```typescript
import type { ToolContextProfile } from '../../components/common/ToolContextInjector'

export const WORKSPACE_APP_CONTEXT = `\
UBICACIÓN: Estás en el Workspace Principal (/workspace).

ROL: Hermes/LAIA — Asistente de desarrollo y orquestación.

DESCRIPCIÓN:
El Workspace Principal es tu interfaz para:
  • Editar y revisar código
  • Ejecutar comandos shell
  • Gestionar git
  • Colaborar con usuarios

PARA TRABAJOS COMPLEJOS:
Si necesitas orquestación multi-agente, ve a /command-center y usa allí
el sistema de 3 roles (Orchestrator, Frontier, Economy).

HERRAMIENTAS DISPONIBLES AQUÍ:
  • Edición de archivos (lectura y modificación)
  • Ejecución de comandos shell
  • Operaciones git
  • Exploración del código

NO uses herramientas de Command Center desde aquí (ej: command_center_spawn).
Para eso, navega a /command-center.`

export const workspaceContext: ToolContextProfile<void> = {
  toolId: 'workspace',
  stateHash: () => 'static',  // sin estado dinámico
  getConnectText: () => WORKSPACE_APP_CONTEXT,
}
```

### Uso en Home.tsx

```typescript
<AgentProvider appContext={WORKSPACE_APP_CONTEXT}>
  <ToolContextInjector profile={workspaceContext} state={undefined} />
  <ChatStream ... />
</AgentProvider>
```

---

## Implementación de ToolContextInjector (para referencia)

**Archivo:** `frontend/src/components/common/ToolContextInjector.tsx`

```typescript
import { useCallback, useEffect, useRef } from 'react'
import { useAgent } from '../../lib/agentRuntime'

export const CTX_SENTINEL = '__CTX__'

export interface ToolContextProfile<S> {
  toolId: string
  stateHash: (state: S) => string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
}

interface Props<S> {
  profile: ToolContextProfile<S>
  state: S
}

export function ToolContextInjector<S>({ profile, state }: Props<S>) {
  const { connection, submitContext } = useAgent()
  const injectedHashRef = useRef('')

  // Resetear hash al desconectar
  useEffect(() => {
    if (connection !== 'online') {
      injectedHashRef.current = ''
    }
  }, [connection])

  // Detectar cambios y inyectar contexto
  useEffect(() => {
    if (connection !== 'online') return

    const hash = profile.stateHash(state)
    if (hash === injectedHashRef.current) return

    const prevHash = injectedHashRef.current
    injectedHashRef.current = hash

    if (prevHash === '') {
      // Primera inyección: contexto completo
      submitContext(profile.toolId, profile.getConnectText(state))
    } else if (profile.getDeltaText) {
      // Actualización: texto delta compacto
      submitContext(profile.toolId, profile.getDeltaText(state))
    }
  }, [connection, state, profile, submitContext])

  return null
}
```

**Comportamiento:**
1. Cuando `connection` cambia a `'online'`, hash se resetea
2. En el siguiente efecto, si hash ha cambiado, inyecta contexto
3. Primera vez: `getConnectText` (completo)
4. Subsecuentes: `getDeltaText` (delta, si existe) o `getConnectText` (fallback)

---

## Patrón CTX_SENTINEL en el chat

**En agentRuntime.tsx, función `submitContext`:**

```typescript
const submitContext = useCallback((toolId: string, text: string) => {
  const trimmed = text.trim()
  if (!trimmed) return
  
  // Añadir a array de mensajes con sentinel para UI
  setMessages(prev => [
    ...prev,
    {
      id: makeId('user'),
      role: 'user',
      content: `[${CTX_SENTINEL}:${toolId}]\n${trimmed}`,
    },
  ])
  
  // Enviar texto limpio (sin sentinel) al LLM
  send('prompt.submit', { text: trimmed })
}, [send])
```

**En ChatStream.tsx, renderizado de mensaje:**

```typescript
function parseCtx(content: string): { toolId: string; body: string } | null {
  const prefix = `[${CTX_SENTINEL}:`
  if (!content.startsWith(prefix)) return null
  const end = content.indexOf(']')
  if (end === -1) return null
  return {
    toolId: content.slice(prefix.length, end),
    body: content.slice(end + 2),
  }
}

// En el componente Bubble:
const ctx = parseCtx(msg.content)
if (ctx) {
  return <ContextCard toolId={ctx.toolId} content={ctx.body} />
}
```

**ContextCard:** Tarjeta compacta colapsable que muestra el toolId expandida con el contenido.

---

## Checklist para nuevas herramientas

- [ ] Archivo `miHerramientaContext.ts` con `APP_CONTEXT` y `ToolContextProfile`
- [ ] Página con `<AgentProvider appContext={...}>` envolviendo todo
- [ ] `<ToolContextInjector profile={...} state={...} />` dentro del `AgentProvider`
- [ ] Verificar que todas las herramientas listadas en `APP_CONTEXT` existen en el backend
- [ ] Probar que Hermes responde correctamente sobre dónde está ("dónde estamos", "qué puedo hacer")
- [ ] Verificar que el hash cambia cuando el estado cambia (pruebas de reactividad)
- [ ] Actualizar `command-center.md` de docs si es una herramienta nueva importante

---

## Troubleshooting

| Problema | Causa | Solución |
|---|---|---|
| Hermes no menciona la herramienta | `appContext` no llegó al backend | Verificar URL en agentRuntime, verificar backend log |
| Contexto no se inyecta en el chat | `ToolContextInjector` no conectado o `stateHash` no cambia | Verificar que está dentro de `AgentProvider`, depurar hash |
| Hermes intenta usar herramientas inexistentes | `APP_CONTEXT` lista herramientas que no existen | Verificar backend, registrar tools faltantes |
| Contexto se pierde al reconectar | Hash no se resetea al desconectar | Verificar que `injectedHashRef.current = ''` está en el useEffect de connection |

---

## Referencias

- `command-center.md` — Ejemplo completo: Command Center
- `laia-arch.md` — Estructura general del proyecto
- Código fuente: `frontend/src/components/common/ToolContextInjector.tsx`


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `orchestration-area` (Orquestación y Command Center) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# ToolContextInjector System

# ToolContextInjector — Sistema de Inyección de Contexto

# ToolContextInjector — Sistema Genérico de Inyección de Contexto

**Implementado:** Mayo 2026  
**Uso:** Cualquier herramienta que embeba a Hermes necesita inyectar contexto

---

## Por qué existe

Hermes está embebido en múltiples herramientas (Command Center, Workspace principal, futuras aplicaciones). Sin un mecanismo claro de contexto:

- No sabe en qué herramienta está
- Responde con APIs genéricas o inexistentes (`terminal(background=true)`)
- No puede coordinar trabajo específico de esa herramienta

**Solución:** Un sistema de dos capas que inyecta contexto automáticamente al conectar y lo actualiza reactivamente cuando cambia el estado.

---

## Arquitectura de dos capas

### Capa 1: Contexto estático (System Prompt permanente)

Texto que describe **qué herramienta es**, **roles y responsabilidades**, **herramientas disponibles**, etc. Se pasa **una sola vez** al crear la sesión y persiste en TODOS los turnos.

**Cómo funciona:**
1. Frontend: `<AgentProvider appContext={TOOL_APP_CONTEXT}>`
2. agentRuntime: construye URL con query param `?app_context=<encoded>`
3. Backend: recibe el query param en `/api/control/ws`
4. tui_gateway: lo almacena en `_sessions[sid]["app_context"]`
5. `_make_agent`: lo prepende al `ephemeral_system_prompt`

**Ventaja:** Muy eficiente (una sola vez) y garantizado que existe desde el primer turn.
**Desventaja:** No puede cambiar durante la sesión.

### Capa 2: Estado dinámico (Actualizaciones en chat)

Texto que describe **qué está pasando ahora** (ej: qué terminales están activas). Se inyecta en el chat cuando cambia el estado, renderizado como tarjeta compacta.

**Cómo funciona:**
1. `<ToolContextInjector profile={toolContext} state={estadoDinamico} />`
2. Detecta cambios en `state` comparando `stateHash`
3. Si es la primera inyección: envía `getConnectText(state)` al chat
4. Si hay cambios subsecuentes: envía `getDeltaText(state)` al chat
5. El texto se marca con `CTX_SENTINEL = '__CTX__'` para que el chat lo renderice como tarjeta, no burbuja

**Ventaja:** Reactivo y compacto; la UI muestra lo que Hermes ve.
**Desventaja:** No es persistente si se desconecta; requiere componente `ToolContextInjector` en cada herramienta.

---

## Interfaz ToolContextProfile<S>

```typescript
interface ToolContextProfile<S> {
  /**
   * ID único de la herramienta. Usado para etiquetar mensajes de contexto.
   * Ej: 'command-center', 'workspace', 'mi-herramienta'
   */
  toolId: string

  /**
   * Hash del estado actual. Cambia cuando el estado relevante cambia.
   * Usado para detectar si necesitamos inyectar una actualización.
   * Ej: (terminals) => terminals.filter(t => t.alive).map(t => t.id).sort().join(',')
   */
  stateHash: (state: S) => string

  /**
   * Texto completo a inyectar cuando Hermes se conecta.
   * Describe la herramienta completa, roles, protocolos, herramientas disponibles.
   * Ej: "[COMMAND CENTER]\nROLES: Orchestrator, Frontier, Economy\nHERRAMIENTAS: ..."
   */
  getConnectText: (state: S) => string

  /**
   * (Opcional) Texto corto a inyectar cuando cambia el estado después de conectar.
   * Si no existe, se reutiliza getConnectText.
   * Ej: "[Command Center · actualización] 2 terminales activas"
   */
  getDeltaText?: (state: S) => string
}
```

---

## Paso a paso: Añadir contexto a una nueva herramienta

### 1. Definir el contexto estático

**Archivo:** `frontend/src/lib/contexts/miHerramientaContext.ts`

```typescript
export const MI_HERRAMIENTA_APP_CONTEXT = `\
UBICACIÓN: Estás en Mi Herramienta (/mi-herramienta).

ROL: Hermes/LAIA — Coordinador de Mi Herramienta.

DESCRIPCIÓN:
Mi Herramienta es [descripción breve de qué hace].

HERRAMIENTAS DISPONIBLES (úsalas, no improvises otras):
  mi_herramienta_accion1(param1, param2) → descripción
  mi_herramienta_accion2()               → descripción
  mi_herramienta_listar()                → listar estado actual

PROTOCOLO DE TRABAJO:
  1. Cuando el usuario pida X, haz Y con la herramienta.
  2. Siempre monitorea el resultado con mi_herramienta_listar.
  3. Reporta cambios significativos al usuario.

NUNCA uses APIs genéricas de otro lugar.
NUNCA asumas que existen herramientas que no están listadas aquí.`
```

**Notas:**
- Usa backtick continuado `\` si el string es multilinea
- Sé específico sobre qué herramientas existen en esta herramienta
- Describe el protocolo de trabajo esperado
- Menciona explícitamente qué NO hacer

### 2. Definir el perfil de contexto dinámico

```typescript
// Puedes definir un interfaz para el estado si es complejo
interface MiEstado {
  id: string
  nombre: string
  activo: boolean
  // ...
}

export const miHerramientaContext: ToolContextProfile<MiEstado> = {
  toolId: 'mi-herramienta',

  // Hash: cambia si el estado relevante cambia
  stateHash: (state) => 
    `${state.id}-${state.nombre}-${state.activo}`,

  // Texto al conectar: descripción completa
  getConnectText: (state) => `\
[Mi Herramienta] Estado actual:
  • ID: ${state.id}
  • Nombre: ${state.nombre}
  • Activo: ${state.activo ? 'sí' : 'no'}`,

  // Texto en actualizaciones: compacto
  getDeltaText: (state) => `\
[Mi Herramienta · actualización] ${state.nombre} ${state.activo ? 'activo' : 'inactivo'}`,
}
```

**Notas:**
- `stateHash` debe retornar un string que cambie cuando cualquier estado **relevante** cambie
- Si el estado no cambia, NO se inyecta nada (eficiencia)
- `getConnectText` es detallado (primer contacto)
- `getDeltaText` es conciso (actualizaciones frecuentes)
- Si el estado es simple o no cambia, usa `stateHash: () => 'static'`

### 3. Crear la página con AgentProvider

**Archivo:** `frontend/src/pages/MiHerramienta.tsx`

```typescript
import { AgentProvider, useAgent } from '../lib/agentRuntime'
import { ChatStream } from '../components/workspace/ChatStream'
import { ToolContextInjector } from '../components/common/ToolContextInjector'
import { 
  MI_HERRAMIENTA_APP_CONTEXT, 
  miHerramientaContext 
} from '../lib/contexts/miHerramientaContext'

export default function MiHerramienta() {
  const [estado, setEstado] = useState<MiEstado>({ /* ... */ })

  return (
    <AgentProvider appContext={MI_HERRAMIENTA_APP_CONTEXT}>
      {/* Inyector de contexto dinámico */}
      <ToolContextInjector profile={miHerramientaContext} state={estado} />

      {/* Chat de Hermes */}
      <ChatStream
        onOpenDiff={() => {}}
        onOpenCommands={() => {}}
        onOpenTool={() => {}}
      />

      {/* Tu interfaz específica aquí */}
      <div>
        {/* ... */}
      </div>
    </AgentProvider>
  )
}
```

**Notas:**
- `appContext={MI_HERRAMIENTA_APP_CONTEXT}` va al primer turn y es permanente
- `<ToolContextInjector>` va dentro de `<AgentProvider>` y es reactivo
- El contexto es completamente automático — cambios en `estado` disparan re-inyección

### 4. Asegurarse de que las herramientas existan en el backend

Las herramientas listadas en `MI_HERRAMIENTA_APP_CONTEXT` deben existir en la capa de tools del agente (workspace-context plugin, herramientas de gateway, etc.). De lo contrario, Hermes intentará usarlas y fallará.

**Verificación:**
- Busca dónde se registran las tools en el backend
- Añade tus tools allí
- Documenta su interfaz en el archivo de contexto

---

## Ejemplo completo: Workspace principal

### Archivo: `frontend/src/lib/contexts/workspaceContext.ts`

```typescript
import type { ToolContextProfile } from '../../components/common/ToolContextInjector'

export const WORKSPACE_APP_CONTEXT = `\
UBICACIÓN: Estás en el Workspace Principal (/workspace).

ROL: Hermes/LAIA — Asistente de desarrollo y orquestación.

DESCRIPCIÓN:
El Workspace Principal es tu interfaz para:
  • Editar y revisar código
  • Ejecutar comandos shell
  • Gestionar git
  • Colaborar con usuarios

PARA TRABAJOS COMPLEJOS:
Si necesitas orquestación multi-agente, ve a /command-center y usa allí
el sistema de 3 roles (Orchestrator, Frontier, Economy).

HERRAMIENTAS DISPONIBLES AQUÍ:
  • Edición de archivos (lectura y modificación)
  • Ejecución de comandos shell
  • Operaciones git
  • Exploración del código

NO uses herramientas de Command Center desde aquí (ej: command_center_spawn).
Para eso, navega a /command-center.`

export const workspaceContext: ToolContextProfile<void> = {
  toolId: 'workspace',
  stateHash: () => 'static',  // sin estado dinámico
  getConnectText: () => WORKSPACE_APP_CONTEXT,
}
```

### Uso en Home.tsx

```typescript
<AgentProvider appContext={WORKSPACE_APP_CONTEXT}>
  <ToolContextInjector profile={workspaceContext} state={undefined} />
  <ChatStream ... />
</AgentProvider>
```

---

## Implementación de ToolContextInjector (para referencia)

**Archivo:** `frontend/src/components/common/ToolContextInjector.tsx`

```typescript
import { useCallback, useEffect, useRef } from 'react'
import { useAgent } from '../../lib/agentRuntime'

export const CTX_SENTINEL = '__CTX__'

export interface ToolContextProfile<S> {
  toolId: string
  stateHash: (state: S) => string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
}

interface Props<S> {
  profile: ToolContextProfile<S>
  state: S
}

export function ToolContextInjector<S>({ profile, state }: Props<S>) {
  const { connection, submitContext } = useAgent()
  const injectedHashRef = useRef('')

  // Resetear hash al desconectar
  useEffect(() => {
    if (connection !== 'online') {
      injectedHashRef.current = ''
    }
  }, [connection])

  // Detectar cambios y inyectar contexto
  useEffect(() => {
    if (connection !== 'online') return

    const hash = profile.stateHash(state)
    if (hash === injectedHashRef.current) return

    const prevHash = injectedHashRef.current
    injectedHashRef.current = hash

    if (prevHash === '') {
      // Primera inyección: contexto completo
      submitContext(profile.toolId, profile.getConnectText(state))
    } else if (profile.getDeltaText) {
      // Actualización: texto delta compacto
      submitContext(profile.toolId, profile.getDeltaText(state))
    }
  }, [connection, state, profile, submitContext])

  return null
}
```

**Comportamiento:**
1. Cuando `connection` cambia a `'online'`, hash se resetea
2. En el siguiente efecto, si hash ha cambiado, inyecta contexto
3. Primera vez: `getConnectText` (completo)
4. Subsecuentes: `getDeltaText` (delta, si existe) o `getConnectText` (fallback)

---

## Patrón CTX_SENTINEL en el chat

**En agentRuntime.tsx, función `submitContext`:**

```typescript
const submitContext = useCallback((toolId: string, text: string) => {
  const trimmed = text.trim()
  if (!trimmed) return
  
  // Añadir a array de mensajes con sentinel para UI
  setMessages(prev => [
    ...prev,
    {
      id: makeId('user'),
      role: 'user',
      content: `[${CTX_SENTINEL}:${toolId}]\n${trimmed}`,
    },
  ])
  
  // Enviar texto limpio (sin sentinel) al LLM
  send('prompt.submit', { text: trimmed })
}, [send])
```

**En ChatStream.tsx, renderizado de mensaje:**

```typescript
function parseCtx(content: string): { toolId: string; body: string } | null {
  const prefix = `[${CTX_SENTINEL}:`
  if (!content.startsWith(prefix)) return null
  const end = content.indexOf(']')
  if (end === -1) return null
  return {
    toolId: content.slice(prefix.length, end),
    body: content.slice(end + 2),
  }
}

// En el componente Bubble:
const ctx = parseCtx(msg.content)
if (ctx) {
  return <ContextCard toolId={ctx.toolId} content={ctx.body} />
}
```

**ContextCard:** Tarjeta compacta colapsable que muestra el toolId expandida con el contenido.

---

## Checklist para nuevas herramientas

- [ ] Archivo `miHerramientaContext.ts` con `APP_CONTEXT` y `ToolContextProfile`
- [ ] Página con `<AgentProvider appContext={...}>` envolviendo todo
- [ ] `<ToolContextInjector profile={...} state={...} />` dentro del `AgentProvider`
- [ ] Verificar que todas las herramientas listadas en `APP_CONTEXT` existen en el backend
- [ ] Probar que Hermes responde correctamente sobre dónde está ("dónde estamos", "qué puedo hacer")
- [ ] Verificar que el hash cambia cuando el estado cambia (pruebas de reactividad)
- [ ] Actualizar `command-center.md` de docs si es una herramienta nueva importante

---

## Troubleshooting

| Problema | Causa | Solución |
|---|---|---|
| Hermes no menciona la herramienta | `appContext` no llegó al backend | Verificar URL en agentRuntime, verificar backend log |
| Contexto no se inyecta en el chat | `ToolContextInjector` no conectado o `stateHash` no cambia | Verificar que está dentro de `AgentProvider`, depurar hash |
| Hermes intenta usar herramientas inexistentes | `APP_CONTEXT` lista herramientas que no existen | Verificar backend, registrar tools faltantes |
| Contexto se pierde al reconectar | Hash no se resetea al desconectar | Verificar que `injectedHashRef.current = ''` está en el useEffect de connection |

---

## Referencias

- `command-center.md` — Ejemplo completo: Command Center
- `laia-arch.md` — Estructura general del proyecto
- Código fuente: `frontend/src/components/common/ToolContextInjector.tsx`


> 📅 Documentado: 2026-05-08
