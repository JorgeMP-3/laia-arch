# Contexto de Herramientas en LAIA

**Implementado:** Mayo 2026  
**Actualizado:** Mayo 2026  
**Uso:** cualquier herramienta que embeba a Hermes/LAIA con un chat propio

---

## Objetivo

Hermes puede estar embebido en varias areas de trabajo: Workspace, Command Center y futuras herramientas. Cada area necesita que el modelo sepa:

- donde esta;
- que rol debe cumplir;
- que herramientas reales puede usar;
- que estado dinamico ve la UI.

La regla principal es: **cada area tiene su propia sesion activa**. Asi se evita que el system prompt de Command Center contamine Workspace, o al reves.

La segunda regla es igual de importante: **el contexto dinamico de una herramienta no debe enviarse como un prompt independiente**. Debe mostrarse en la UI como contexto y debe llegar al modelo solo como informacion de fondo del siguiente turno real del usuario.

---

## Arquitectura de tres capas

### 1. `appContext`: identidad estatica del area

Texto estable que se inyecta en el `ephemeral_system_prompt` cuando se crea la sesion del area.

Flujo:

1. Frontend registra la herramienta en `toolRegistry.ts`.
2. La pagina monta `<ToolShell profile={...} state={...}>`.
3. `ToolShell` monta `ToolAreaProvider`.
4. `AgentProvider` abre `/api/control/ws?area_id=<areaId>&app_context=<encoded>`.
5. Backend llama `ensure_session(area_id, app_context)`.
6. Backend crea o reutiliza una sesion solo para ese `areaId`.
7. `tui_gateway.session.create` guarda `app_context`.
8. `_make_agent()` prepende ese contexto al `ephemeral_system_prompt`.

Si cambia el `appContext` de un mismo `areaId`, backend crea una sesion nueva para evitar prompts obsoletos.

Ademas, el frontend vuelve a adjuntar ese `appContext` dentro de `<background-ui-context>` en cada prompt normal. Esto refuerza la identidad del area incluso si el usuario conserva una sesion antigua o si el runtime se reconecta.

### 2. `ToolContextInjector`: estado dinamico visible

Texto que cambia con el estado de la herramienta: terminales activas, seleccion actual, procesos, etc.

El inyector:

- calcula `stateHash(state)`;
- manda `getConnectText(state)` al conectar;
- manda `getDeltaText(state)` cuando cambia el hash;
- si no hay `getDeltaText`, reutiliza `getConnectText`;
- marca el mensaje con `CTX_SENTINEL` para renderizarlo como `ContextCard`.

El inyector **no llama a `prompt.submit` directamente**. `submitContext(toolId, text)` hace dos cosas:

1. guarda el ultimo contexto dinamico en un buffer interno por `toolId`;
2. anade al chat un mensaje con sentinel para que la UI lo renderice como `ContextCard`.

Cuando el usuario envia un mensaje real, `submitText(text)` construye un prompt enriquecido:

```text
<mensaje real del usuario>

<background-ui-context>
These blocks are system-provided UI/tool context for this user turn. Use them as background facts only. Do not answer the context itself and do not tell the user it was injected.

<area-context area="command-center">
...
</area-context>

<tool-context tool="command-center">
...
</tool-context>
</background-ui-context>
```

La UI y el historial persistido conservan solo el mensaje limpio del usuario. El modelo ve el bloque de fondo para ese turno, pero no debe responder al bloque como si fuera una solicitud independiente.

### 3. Context Engine: indices/workspaces por turno

El contexto de indices de workspace no pertenece al `appContext`. Sigue entrando por el mecanismo de memoria/prefetch en cada turno, porque depende de la consulta, de `active_workspaces`, de `inject_mode` y del presupuesto de caracteres.

No mover este contexto al system prompt de herramienta ni duplicarlo en `appContext`. La capa de herramienta identifica donde esta el chat; el Context Engine decide que memoria/indexes conviene inyectar para una consulta concreta.

---

## Flujo runtime completo

### Conexion y sesion por area

```text
Pagina de herramienta
  -> ToolShell
    -> ToolAreaProvider(profile, state)
      -> AgentProvider(areaId, appContext)
        -> WebSocket /api/control/ws?area_id=<areaId>&app_context=<encoded>
          -> workspace-ui backend ensure_session(area_id, app_context)
            -> tui_gateway session.create(app_context)
              -> AIAgent(ephemeral_system_prompt + app_context)
```

`ensure_session(area_id, app_context)` reutiliza solo la sesion activa de esa misma area cuando el hash de `appContext` coincide. Si el hash cambia, se crea una sesion nueva para no mantener un system prompt antiguo.

`area_id` por defecto es `workspace` para compatibilidad con clientes antiguos.

### Turno de usuario con contexto dinamico

```text
ToolContextInjector detecta cambio de estado
  -> submitContext(toolId, contextText)
    -> guarda contextText en toolContextRef[toolId]
    -> muestra ContextCard en el chat
    -> NO envia prompt.submit

Usuario escribe "donde estamos?"
  -> submitText("donde estamos?")
    -> UI muestra solo "donde estamos?"
    -> prompt.submit({
         text: "donde estamos?\n\n<background-ui-context>...</background-ui-context>",
         persist_user_message: "donde estamos?"
       })
      -> tui_gateway run_conversation(
           run_message=<prompt enriquecido>,
           persist_user_message=<mensaje limpio>
         )
```

Este flujo evita el fallo anterior: el modelo ya no responde a `[Workspace] Contexto activo...` ni a `[Command Center] Terminales activas...` como si fueran prompts del usuario.

### Historial limpio con `persist_user_message`

El gateway acepta `persist_user_message` en `prompt.submit`. Si llega:

- el modelo recibe `text`;
- el historial de conversacion guarda `persist_user_message`;
- el contexto oculto no queda acumulado como mensaje visible ni contamina sesiones futuras.

Esto es obligatorio para cualquier inyeccion frontend que agregue contexto oculto al turno.

---

## Interfaces

### `ToolAreaProfile<S>`

```typescript
interface ToolAreaProfile<S = void> {
  areaId: string
  appContext: string
  dynamicContext?: ToolContextProfile<S>
}
```

### `ToolContextProfile<S>`

```typescript
interface ToolContextProfile<S> {
  toolId: string
  stateHash: (state: S) => string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
}
```

### `ToolAreaProvider`

```tsx
<ToolAreaProvider profile={toolAreaProfile} state={state}>
  <ChatStream ... />
  <MiHerramienta />
</ToolAreaProvider>
```

Internamente monta `AgentProvider` con `areaId/appContext` y, si existe, `ToolContextInjector`.

### `ToolShell`

```tsx
<ToolShell profile={toolAreaProfile} state={state}>
  <ChatStream ... />
  <MiHerramienta />
</ToolShell>
```

Es el wrapper recomendado para paginas nuevas. Expone `data-tool-area` y deja un punto unico para layout comun futuro.

---

## Receta para una herramienta nueva

### 1. Crear el perfil

Archivo recomendado: `frontend/src/lib/contexts/miHerramientaContext.ts`

```typescript
import type { ToolAreaProfile } from '../../components/common/ToolAreaProvider'
import type { ToolContextProfile } from '../../components/common/ToolContextInjector'

interface MiEstado {
  activo: boolean
  nombre: string
}

export const MI_HERRAMIENTA_APP_CONTEXT = `\
UBICACION: Estas en Mi Herramienta (/mi-herramienta).
ROL: Hermes/LAIA - coordinador de Mi Herramienta.

HERRAMIENTAS DISPONIBLES:
  mi_herramienta_listar()          -> listar estado
  mi_herramienta_accion(nombre)    -> ejecutar accion

NUNCA inventes herramientas que no esten listadas aqui.`

export const miHerramientaContext: ToolContextProfile<MiEstado> = {
  toolId: 'mi-herramienta',
  stateHash: state => `${state.nombre}:${state.activo}`,
  getConnectText: state =>
    `[Mi Herramienta] ${state.nombre} esta ${state.activo ? 'activa' : 'inactiva'}`,
  getDeltaText: state =>
    `[Mi Herramienta - actualizacion] ${state.nombre}: ${state.activo ? 'activa' : 'inactiva'}`,
}

export const miHerramientaArea: ToolAreaProfile<MiEstado> = {
  areaId: 'mi-herramienta',
  appContext: MI_HERRAMIENTA_APP_CONTEXT,
  dynamicContext: miHerramientaContext,
}
```

### 2. Montar la pagina

```tsx
export default function MiHerramientaPage() {
  const [state, setState] = useState<MiEstado>({ activo: true, nombre: 'demo' })

  return (
    <ToolShell profile={miHerramientaArea} state={state}>
      <ChatStream
        onOpenDiff={() => {}}
        onOpenCommands={() => {}}
        onOpenTool={() => {}}
      />
      <MiHerramientaUI state={state} onChange={setState} />
    </ToolShell>
  )
}
```

### 3. Registrar la herramienta en `toolRegistry.ts`

Anadir una entrada con `areaId`, `route`, `label`, `description`, `capabilities` y, si usa Hermes, `toolArea`.

### 4. Registrar tools reales

Toda tool mencionada en `appContext` debe existir en backend/toolsets. Si el prompt lista `mi_herramienta_accion`, Hermes la intentara usar.

### 5. Probar aislamiento

- Entrar en la herramienta y preguntar "donde estamos".
- Entrar en otra area y repetir.
- Volver a la primera area: debe conservar su sesion y su identidad.
- Cambiar estado dinamico y verificar que aparece una `ContextCard`.
- Verificar que la `ContextCard` no genera respuesta automatica de Hermes.
- Verificar que el historial guardado contiene solo el mensaje real del usuario, no `<background-ui-context>`.

---

## Cambios implementados

### Frontend

| Archivo | Cambio |
|---|---|
| `.laia-arch/workspace-ui/frontend/src/lib/agentRuntime.tsx` | `AgentProvider` acepta `areaId` y `appContext`; abre el WebSocket con ambos valores; filtra eventos por `session_id`; mantiene `toolContextRef`; construye `<background-ui-context>` al enviar prompts reales; usa `persist_user_message`; limpia contexto al cambiar de area/appContext |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolAreaProvider.tsx` | Wrapper que monta `AgentProvider` y `ToolContextInjector` usando un perfil unico de herramienta |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolShell.tsx` | Wrapper recomendado para paginas de herramienta; centraliza el punto de integracion futuro |
| `.laia-arch/workspace-ui/frontend/src/components/common/ToolContextInjector.tsx` | Inyector generico; reinicia su hash al cambiar `sessionId`; usa fallback `getDeltaText ?? getConnectText`; llama a `submitContext` sin disparar prompts |
| `.laia-arch/workspace-ui/frontend/src/lib/toolRegistry.ts` | Registro unico de areas/herramientas con ruta, etiqueta, capacidades y perfil asociado |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/workspaceContext.ts` | Perfil `workspace` con `appContext` estatico y contexto dinamico del Workspace principal |
| `.laia-arch/workspace-ui/frontend/src/lib/contexts/commandCenterContext.ts` | Perfil `command-center` con identidad propia y estado dinamico de terminales |
| `.laia-arch/workspace-ui/frontend/src/pages/Home.tsx` | Workspace principal montado con `ToolShell`/perfil `workspace` |
| `.laia-arch/workspace-ui/frontend/src/pages/CommandCenter.tsx` | Command Center montado con `ToolShell`/perfil `command-center` |
| `.laia-arch/workspace-ui/frontend/src/App.tsx` | Se elimina el chat global legacy para evitar dobles runtimes no aislados |
| `.laia-arch/workspace-ui/frontend/src/lib/api.ts` | Endpoints de sesiones aceptan `area_id` opcional manteniendo `workspace` como default |

### Backend workspace-ui

| Archivo | Cambio |
|---|---|
| `.laia-arch/workspace-ui/backend/main.py` | Sustituye una sesion global por sesiones activas por area; normaliza `area_id`; calcula hash de `app_context`; `ensure_session(area_id, app_context)` crea/reutiliza por area; `control.ready` emite `{area_id, session_id}`; endpoints de sesiones aceptan `area_id`; CORS deja de usar `allow_credentials=True` con wildcard |
| `.laia-arch/workspace-ui/backend/tests/test_control_ws.py` | Cobertura esperada para WebSocket de control por area |

### Gateway Hermes

| Archivo | Cambio |
|---|---|
| `.laia-arch/tui_gateway/server.py` | `prompt.submit` acepta `persist_user_message`; `_run_prompt_submit` lo pasa a `AIAgent.run_conversation`; `prompt.btw` queda disponible como alias compatible |
| `.laia-arch/toolsets.py` | Toolsets alineados para exponer herramientas de Command Center donde el prompt las anuncia |
| `.laia-arch/tools/command_center_tool.py` | Herramientas nativas de Command Center: list/spawn/inject/read/kill |

### Documentacion

| Archivo | Cambio |
|---|---|
| `docs/docs/command-center.md` | Documenta Command Center, herramientas nativas, arquitectura PTY y contexto por area |
| `docs/docs/tool-context-injection.md` | Documenta la arquitectura extensible de contexto, sesiones por area, `ToolAreaProvider`, `ToolShell`, `persist_user_message` y troubleshooting |
| `docs/docs/README.md` | Indice actualizado con los documentos nuevos |

---

## Checklist

- [ ] `areaId` unico, estable y corto.
- [ ] Entrada en `toolRegistry.ts`.
- [ ] `appContext` conciso, estatico y con tools reales.
- [ ] `ToolShell` usado como wrapper de pagina.
- [ ] `stateHash` cambia solo cuando cambia estado relevante.
- [ ] `getDeltaText` compacto para actualizaciones frecuentes.
- [ ] `submitContext` nunca se usa para iniciar una respuesta del modelo.
- [ ] El contexto dinamico llega al modelo solo dentro de `<background-ui-context>` en un turno real.
- [ ] `prompt.submit` usa `persist_user_message` cuando `text` contiene contexto oculto.
- [ ] Tests de WebSocket para nueva area si la herramienta crea una ruta nueva.
- [ ] Documentacion actualizada si la herramienta es parte principal de LAIA.

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| Hermes responde como otra herramienta | `areaId` omitido o reutilizado | Usar `areaId` unico y verificar URL WebSocket |
| Hermes no ve el contexto estatico | `appContext` no llega a `session.create` | Revisar query `app_context` y `ensure_session` |
| Se crea sesion nueva inesperada | Cambio el texto de `appContext` | Es esperado: el hash cambio para evitar prompt obsoleto |
| ContextCard no aparece | `ToolContextInjector` no esta dentro del provider | Usar `ToolAreaProvider` |
| Hermes responde "Contexto recibido" | El contexto dinamico se envio por `prompt.submit` directo | `submitContext` debe solo guardar buffer y renderizar tarjeta |
| Hermes usa tools inexistentes | `appContext` anuncia tools no registradas | Registrar tools o corregir el prompt |
| Prefetch de workspace parece ausente | Confundir `appContext` con Context Engine | Revisar configuracion `workspace-context`, no el area provider |
| El historial queda lleno de `<background-ui-context>` | Falta `persist_user_message` | Enviar `{ text: promptEnriquecido, persist_user_message: textoLimpio }` |
| Command Center dice que esta en Workspace | Sesion vieja o `area_id/appContext` no llegaron | Reiniciar gateway/backend, recargar UI y verificar URL WebSocket |

---

## Verificacion manual

1. Reiniciar los procesos que sirven workspace-ui/backend y `tui_gateway`.
2. Abrir Workspace principal.
3. Confirmar que aparece `CONTEXT · WORKSPACE`.
4. No debe aparecer una respuesta automatica del modelo a esa tarjeta.
5. Preguntar: `donde estamos?`
6. La respuesta debe indicar Workspace principal.
7. Abrir Command Center.
8. Confirmar que aparece contexto de Command Center/terminales como tarjeta.
9. Preguntar: `hola, donde estamos?`
10. La respuesta debe indicar Command Center, no Workspace.
11. Abrir DevTools y verificar que el WebSocket usa `area_id=command-center` en `/api/control/ws`.
12. Revisar historial de sesion: debe guardar el mensaje limpio, no el bloque `<background-ui-context>`.

## Verificacion tecnica

Comandos usados durante la implementacion:

```bash
cd /home/laia-arch/LAIA/.laia-arch/workspace-ui/frontend
npm run build
```

```bash
cd /home/laia-arch/LAIA
python3 -m py_compile .laia-arch/tui_gateway/server.py
```

`pytest` no estaba disponible en el entorno usado para esta implementacion (`No module named pytest`). Cuando este instalado, ejecutar las pruebas del backend/gateway correspondientes.

---

## Referencias

- `frontend/src/components/common/ToolAreaProvider.tsx`
- `frontend/src/components/common/ToolShell.tsx`
- `frontend/src/components/common/ToolContextInjector.tsx`
- `frontend/src/lib/toolRegistry.ts`
- `frontend/src/lib/agentRuntime.tsx`
- `backend/main.py`
- `tui_gateway/server.py`
