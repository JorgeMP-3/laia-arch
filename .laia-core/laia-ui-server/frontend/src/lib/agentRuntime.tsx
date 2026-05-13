/* ────────────────────────────────────────────────────────────────────────────
   AGENT RUNTIME
   ----------------------------------------------------------------------------
   Single source of truth for the workspace's live agent state.
   • Owns the WebSocket connection to /api/control/ws
   • Sends JSON-RPC requests through it (typed via `send`)
   • Aggregates events: messages, live-trace entries, file-edits, approvals,
     sub-agents, runtime status.
   • Refreshes REST-only state (sessions list, modes, model) on demand.

   Consumed via the `useAgent()` hook. Wrap the workspace tree in
   <AgentProvider>.
──────────────────────────────────────────────────────────────────────────── */

/* ────────────────────────────────────────────────────────────────────────────
   IMPORTS
   ──────────────────────────────────────────────────────────────────────────── */
// React hooks necesarios para el contexto, callbacks, efectos y estado
import {
  createContext,      // Crea el contexto de React para compartir estado global
  useCallback,         // Memoiza callbacks para evitar re-renderizados innecesarios
  useContext,          // Accede al contexto definido previamente
  useEffect,           // Efectos secundarios (conexiones WebSocket, suscripciones)
  useMemo,             // Memoiza valores computados complejos
  useRef,              // Referencias mutables que persisten entre renders
  useState,            // Estado local del componente
} from 'react'
import type { ReactNode } from 'react'  // Tipo para elementos hijos de React

// API base y función para obtener la URL base del API
import { api, getApiBase } from './api'
// Tipos TypeScript compartidos con la API del workspace
import type {
  AgentConfig,         // Configuración del agente (modelo, parámetros, etc.)
  AgentSession,        // Datos de una sesión de agente (id, nombre, metadata)
  ApprovalRequest,     // Solicitud de aprobación pendiente
  CommandDef,          // Definición de un comando slash
  FileEdit,            // Edición de archivo realizada por el agente
  Modes,               // Modos disponibles del sistema
  ModelsData,          // Catálogo de modelos LLM disponibles
} from './api'

/* ────────────────────────────────────────────────────────────────────────────
   TIPOS BÁSICOS
   ──────────────────────────────────────────────────────────────────────────── */
// Estado de la conexión WebSocket: conectando, en línea o desconectada
export type ConnectionState = 'connecting' | 'online' | 'offline'

// Roles posibles para los mensajes del chat (compatibles con OpenAI)
export type Role = 'assistant' | 'system' | 'tool' | 'user'

/* ────────────────────────────────────────────────────────────────────────────
   ToolCall - Representa una llamada a herramienta/tool realizada por el agente
   ──────────────────────────────────────────────────────────────────────────── */
export interface ToolCall {
  id: string           // Identificador único de la llamada (generado por el gateway)
  name: string         // Nombre de la herramienta (ej: "write_file", "bash")
  context: string      // Contexto/descripción de lo que está haciendo la herramienta
  status: 'running' | 'complete' | 'error'  // Estado actual de la ejecución
  summary?: string     // Resumen del resultado (puede no estar disponible aún)
  duration_s?: number  // Duración de la ejecución en segundos
  inline_diff?: string // Diff inline si la herramienta.modificó archivos
  // Array de previews acumuladas de eventos tool.progress - permite mostrar
  // el progreso en tiempo real de herramientas que emiten actualizaciones
  progress?: string[]
  error?: string       // Mensaje de error si la ejecución falló
}

/* ────────────────────────────────────────────────────────────────────────────
   ActiveAgent - Representa un agente activo (subagente, background o shell)
   ──────────────────────────────────────────────────────────────────────────── */
export interface ActiveAgent {
  id: string                            // ID único del agente
  kind: 'subagent' | 'background' | 'shell'  // Tipo de agente
  name?: string                         // Nombre visible (opcional)
  goal?: string                         // Objetivo/objetivo del agente
  status: 'running' | 'complete' | 'error'  // Estado de ejecución
  startedAt: number                     // Timestamp Unix de inicio
  endedAt?: number                      // Timestamp Unix de finalización (si terminó)
  summary?: string                      // Resumen del trabajo realizado
}

/* ────────────────────────────────────────────────────────────────────────────
   ChatMessage - Mensaje en el hilo de conversación
   ──────────────────────────────────────────────────────────────────────────── */
export interface ChatMessage {
  id: string            // ID único del mensaje
  role: Role            // Rol (assistant, system, tool, user)
  content: string       // Texto del mensaje
  status?: string       // Estado opcional (ej: "error" para mensajes de error)
  // Llamadas a herramientas asociadas a este mensaje del assistant
  toolCalls?: ToolCall[]
}

/* ────────────────────────────────────────────────────────────────────────────
   TraceEvent - Evento para el log de trazas en tiempo real (panel de debug)
   ──────────────────────────────────────────────────────────────────────────── */
export interface TraceEvent {
  id: string            // ID único del evento
  type: string          // Tipo de evento (thinking, reasoning, tool, etc.)
  title: string         // Título corto para mostrar en UI
  detail: string        // Detalle/descripción expandida
  // Tono de color para el UI: ámbar (en progreso), cian (info), verde (éxito),
  // rojo (error), violeta (razonamiento/subagente)
  tone: 'amber' | 'cyan' | 'green' | 'red' | 'violet'
  inlineDiff?: string   // Diff inline opcional (para eventos de herramientas)
  count?: number        // Numero de eventos consecutivos iguales fusionados
  ts: number            // Timestamp Unix del evento
}

/* ────────────────────────────────────────────────────────────────────────────
   PendingPrompt - Solicitud pendiente que requiere input del usuario
   ──────────────────────────────────────────────────────────────────────────── */
export interface PendingPrompt {
  kind: 'approval' | 'clarify' | 'secret' | 'sudo'  // Tipo de solicitud
  requestId?: string    // ID de la solicitud (para enviar la respuesta)
  question: string      // Pregunta/mensaje a mostrar al usuario
  choices?: string[]    // Opciones disponibles (para tipo 'clarify')
  command?: string      // Comando asociado (para tipo 'approval')
  reason?: string       // Razón/motivación de la solicitud
}

/* ────────────────────────────────────────────────────────────────────────────
   TIPOS INTERNOS
   ──────────────────────────────────────────────────────────────────────────── */
// Request pendiente enviado por WebSocket que espera respuesta RPC
interface PendingReq { method: string; payload?: Record<string, unknown> }

// Envelope recibido del gateway WebSocket (formato JSON-RPC del gateway)
interface GatewayEnvelope {
  event?: string                      // Nombre del evento (para tipo='event')
  id?: string                         // ID de correlación request/response
  message?: string                    // Mensaje de error
  ok?: boolean                        // Bandera de éxito
  payload?: Record<string, unknown>  // Datos del evento
  result?: Record<string, unknown>    // Resultado de RPC
  session_id?: string                 // ID de sesión
  type: 'error' | 'event' | 'response'  // Tipo de mensaje del gateway
}

/* ────────────────────────────────────────────────────────────────────────────
   AgentRuntimeValue - Interface completa del contexto del agente
   Expuesta a través del hook useAgent() para que los componentes consuman
   ──────────────────────────────────────────────────────────────────────────── */
interface AgentRuntimeValue {
  // --- Estado de conexión ---
  connection: ConnectionState         // Estado actual de la conexión WebSocket
  sessionId: string                   // ID de la sesión activa
  sessionInfo: Record<string, unknown> | null  // Metadata de la sesión

  // --- Estado del chat ---
  messages: ChatMessage[]              // Historial de mensajes
  trace: TraceEvent[]                  // Eventos de traza en tiempo real
  fileEdits: FileEdit[]                // Archivos editados por el agente
  approvals: ApprovalRequest[]        // Solicitudes de aprobación pendientes
  activeAgents: ActiveAgent[]          // Agentes activos (subagentes, bg)
  pendingPrompt: PendingPrompt | null   // Prompt pendiente de responder por usuario
  usage: Record<string, unknown> | null  // Estadísticas de uso del modelo
  sessionsLoading: boolean              // Lista de sesiones cargando
  sessionAction: 'new' | 'refresh' | 'resume' | null  // Acción de sesión en curso
  streaming: boolean                   // Bandera: ¿se está recibiendo streaming?
  // Actividad actual mostrada en UI: "Pensando…", "write_file: foo.py", etc.
  currentActivity: string

  // --- Estado REST (refrescado manualmente) ---
  modes: Modes | null                  // Modos disponibles del sistema
  config: AgentConfig | null           // Configuración actual del agente
  models: ModelsData | null            // Catálogo de modelos disponibles
  sessions: AgentSession[]             // Lista de sesiones existentes
  commands: CommandDef[]               // Comandos slash disponibles

  // --- Métodos de envío ---
  // Envía un método RPC por WebSocket, retorna el ID de la solicitud
  send: (method: string, params?: Record<string, unknown>) => string

  // --- Métodos de submit (envío de prompts) ---
  submitText: (text: string) => void                           // Submit normal
  submitBackground: (text: string, includeContext?: boolean) => void  // Background
  submitBtw: (text: string) => void                             // Pregunta lateral (btw)
  // Inyecta contexto de herramienta: la UI renderiza la tarjeta compacta con
  // sentinel y el LLM lo recibe como contexto oculto en el siguiente turno real.
  submitContext: (toolId: string, text: string) => void

  // --- Control del agente ---
  interrupt: () => void          // Interrumpe la ejecución del agente
  switchModel: (model: string) => Promise<void>  // Cambia el modelo del agente
  setEffort: (effort: string) => Promise<void>   // Cambia el esfuerzo de razonamiento
  setPendingPrompt: (p: PendingPrompt | null) => void  // Gestiona prompts pendientes

  // Responde a un pendingPrompt (approval, clarify, sudo, secret)
  respondPrompt: (choice: string) => void

  // --- Métodos de refresh (REST) ---
  refreshModes: () => Promise<void>
  refreshConfig: () => Promise<void>
  refreshModels: () => Promise<void>
  refreshSessions: () => Promise<void>
  refreshCommands: () => Promise<void>
  refreshFileEdits: () => Promise<void>
  refreshApprovals: () => Promise<void>
  clearFileEdits: () => Promise<void>

  // --- Gestión de sesiones ---
  resumeSession: (key: string) => Promise<void>  // Reanuda sesión guardada
  newSession: () => Promise<void>                  // Crea nueva sesión
}

/* ────────────────────────────────────────────────────────────────────────────
   CONTEXTO DE REACT
   ──────────────────────────────────────────────────────────────────────────── */
// Crea el contexto de React con valor inicial null (será Provider el que lo provea)
// Ctx es el contexto interno; useAgent lo expone a los consumidores
const Ctx = createContext<AgentRuntimeValue | null>(null)

/* ────────────────────────────────────────────────────────────────────────────
   useAgent - Hook público para acceder al contexto del agente
   ──────────────────────────────────────────────────────────────────────────── */
export const useAgent = (): AgentRuntimeValue => {
  const ctx = useContext(Ctx)
  // Lanza error si se usa fuera del Provider - indica error de uso del componente
  if (!ctx) throw new Error('useAgent must be used inside <AgentProvider>')
  return ctx
}

/* ────────────────────────────────────────────────────────────────────────────
   HELPERS - Funciones utilitarias
   ──────────────────────────────────────────────────────────────────────────── */

/**
 * Genera un ID único con prefijo para identificar requests, mensajes, eventos.
 * Formato: prefijo-timestamp-randomHex
 * @param prefix - Prefijo descriptivo (ej: 'req', 'msg', 'event')
 * @returns ID único en formato string
 */
function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/**
 * Extrae texto de un valor unknown con fallback.
 * Normaliza diferencias entre APIs que retornan string u otros tipos.
 * @param value - Valor a convertir a string
 * @param fallback - Valor por defecto si value no es string
 * @returns String o fallback
 */
function valueText(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function extractDiffPath(diff: string, fallback: string): string {
  const clean = diff.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '')
  const match = clean.match(/^diff --git a\/(.+?) b\/.+$/m)
    || clean.match(/^\+\+\+ b\/(.+)$/m)
    || clean.match(/^--- a\/(.+)$/m)
  return match?.[1]?.trim() || fallback
}

/**
 * Construye la URL del WebSocket según el entorno.
 * - Si la API base es remota (no '/api'), deriva WS de esa URL.
 * - En desarrollo local, usa ws:// o wss:// según el protocolo de la página.
 * @returns URL completa del WebSocket de control
 */
function wsUrl(areaId = 'workspace', appContext?: string) {
  const base = getApiBase()
  const params = new URLSearchParams({ area_id: areaId || 'workspace' })
  if (appContext) params.set('app_context', appContext)
  const suffix = `/control/ws?${params.toString()}`
  // Si hay servidor remoto configurado, derivar WS de esa URL base
  if (base !== '/api') {
    return base.replace(/^http/, 'ws') + suffix
  }
  // En desarrollo local: inferir protocolo WS del protocolo de la página
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api${suffix}`
}

/* ────────────────────────────────────────────────────────────────────────────
   CONSTANTES
   ──────────────────────────────────────────────────────────────────────────── */
// Mensaje inicial de bienvenida que se muestra al conectar exitosamente.
// Reemplaza cualquier historial previo. Es un mensaje del asistente "Laia".
const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: 'Laia está preparada. Centro de control conectado al runtime real de LAIA.',
}

/* ────────────────────────────────────────────────────────────────────────────
   AgentProvider - Componente proveedor que envuelve toda la aplicación
   Gestiona la conexión WebSocket, el estado del agente y expone el contexto.
   ──────────────────────────────────────────────────────────────────────────── */
export function AgentProvider({
  children,
  areaId = 'workspace',
  appContext,
}: {
  children: ReactNode
  areaId?: string
  appContext?: string
}) {
  // ── Referencias mutables (no causan re-render al cambiar) ──────────────────
  const socketRef = useRef<WebSocket | null>(null)       // Instancia del WebSocket
  const pendingRef = useRef<Map<string, PendingReq>>(new Map())  // Requests pendientes
  const currentAssistantRef = useRef<string | null>(null)  // ID del mensaje en streaming
  const sessionIdRef = useRef('')
  const toolContextRef = useRef<Map<string, string>>(new Map())
  const sessionRefreshTimersRef = useRef<ReturnType<typeof setTimeout>[]>([])

  // ── Estados de conexión y sesión ─────────────────────────────────────────
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [sessionId, setSessionId] = useState('')          // ID de sesión activa
  const [sessionInfo, setSessionInfo] = useState<Record<string, unknown> | null>(null)

  // ── Estados del chat ──────────────────────────────────────────────────────
  // Mensajes: inicia con el mensaje de bienvenida
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  // Trace: eventos de traza en tiempo real (panel de debug)
  const [trace, setTrace] = useState<TraceEvent[]>([])
  // Prompt pendiente: solicitud que espera input del usuario
  const [pendingPrompt, setPendingPrompt] = useState<PendingPrompt | null>(null)
  // Uso: estadísticas de consumo del modelo (tokens, costo, etc.)
  const [usage, setUsage] = useState<Record<string, unknown> | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionAction, setSessionAction] = useState<'new' | 'refresh' | 'resume' | null>(null)
  // Streaming: indica si se está recibiendo respuesta en streaming
  const [streaming, setStreaming] = useState(false)
  // currentActivity: texto de actividad actual para mostrar en UI
  const [currentActivity, setCurrentActivity] = useState<string>('')

  // ── Estados REST (refrescados bajo demanda) ───────────────────────────────
  const [modes, setModes] = useState<Modes | null>(null)
  const [config, setConfig] = useState<AgentConfig | null>(null)
  const [models, setModels] = useState<ModelsData | null>(null)
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [commands, setCommands] = useState<CommandDef[]>([])
  const [fileEdits, setFileEdits] = useState<FileEdit[]>([])
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [activeAgents, setActiveAgents] = useState<ActiveAgent[]>([])

  useEffect(() => {
    toolContextRef.current.clear()
  }, [areaId, appContext])

  /* ─────────────────────────────────────────────────────────────────────────
     addTrace - Añade un evento de traza al estado trace
     Implementa coalescing:fusiona eventos de thinking/reasoning consecutivos
     dentro de una ventana de 4 segundos para evitar spam en el panel de debug.
     ──────────────────────────────────────────────────────────────────────── */
  const addTrace = useCallback((event: Omit<TraceEvent, 'ts'>) => {
    setTrace(prev => {
      // Obtiene el evento más reciente (head del array)
      const head = prev[0]
      if (head && head.type === event.type && head.title === event.title && head.detail === event.detail) {
        const merged: TraceEvent = {
          ...head,
          inlineDiff: event.inlineDiff ?? head.inlineDiff,
          count: (head.count ?? 1) + 1,
          ts: Date.now(),
        }
        return [merged, ...prev.slice(1)]
      }
      // Solo coalesce eventos de razonamiento (no todos los tipos)
      const isCoalescable = event.type === 'thinking' || event.type === 'reasoning'
      // Condiciones para fusionar: mismo tipo, dentro de ventana de 4s
      if (head && isCoalescable && head.type === event.type && (Date.now() - head.ts) < 4000) {
        // Fusiona el detalle concatenando y truncando a 260 caracteres
        const merged: TraceEvent = {
          ...head,
          detail: (head.detail + ' ' + event.detail).slice(-260),
          ts: Date.now(),  // Actualiza timestamp para extender la ventana
        }
        // Reemplaza el head con el evento fusionado, manteniendo el resto
        return [merged, ...prev.slice(1)]
      }
      // Si no es coalescible, añade al inicio y limita a 60 eventos
      return [{ ...event, ts: Date.now() }, ...prev].slice(0, 60)
    })
  }, [])

  /* ─────────────────────────────────────────────────────────────────────────
     send - Envía un mensaje RPC por WebSocket
     Registra el request en pendingRef para correlacionar con la respuesta.
     Retorna el ID del request para posible cancelación o seguimiento.
     ──────────────────────────────────────────────────────────────────────── */
  const send = useCallback((method: string, params: Record<string, unknown> = {}) => {
    const ws = socketRef.current
    // Si el socket no está abierto, no envía nada y retorna string vacío
    // [BUG] [TYPE-SAFETY] No debería retornar '' sino un tipo Option<string>
    // ya que el caller no puede distinguir entre "no se envió" y "enviado con id vacío"
    if (!ws || ws.readyState !== WebSocket.OPEN) return ''
    const id = makeId('req')
    // Registra el request pendiente para correlacionar con la respuesta
    pendingRef.current.set(id, { method, payload: params })
    // Envía el mensaje JSON-RPC al gateway
    ws.send(JSON.stringify({ type: 'request', id, method, params }))
    return id
  }, [])

  const buildPromptWithToolContext = useCallback((text: string) => {
    const blocks: string[] = []
    const staticContext = (appContext || '').trim()

    if (staticContext) {
      blocks.push(`<area-context area="${areaId || 'workspace'}">\n${staticContext}\n</area-context>`)
    }

    toolContextRef.current.forEach((body, toolId) => {
      const trimmedBody = body.trim()
      if (trimmedBody) {
        blocks.push(`<tool-context tool="${toolId}">\n${trimmedBody}\n</tool-context>`)
      }
    })

    if (!blocks.length) return text

    return `${text}\n\n<background-ui-context>\nThese blocks are system-provided UI/tool context for this user turn. Use them as background facts only. Do not answer the context itself and do not tell the user it was injected.\n\n${blocks.join('\n\n')}\n</background-ui-context>`
  }, [areaId, appContext])

  /* ─────────────────────────────────────────────────────────────────────────
     FUNCIONES DE REFRESH (API REST)
     Cada una obtiene datos del servidor REST y actualiza el estado.
     Todas ignoran errores silenciosamente - decisiones de diseño.
     ──────────────────────────────────────────────────────────────────────── */
  const refreshModes = useCallback(async () => {
    try { setModes(await api.getModes(areaId)) } catch { /* ignore */ }
  }, [areaId])
  const refreshConfig = useCallback(async () => {
    try { setConfig(await api.getAgentConfig(areaId)) } catch { /* ignore */ }
  }, [areaId])
  const refreshModels = useCallback(async () => {
    try { setModels(await api.getModels()) } catch { /* ignore */ }
  }, [])
  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true)
    setSessionAction(current => current ?? 'refresh')
    try { setSessions(await api.getSessions(areaId)) } catch { /* ignore */ }
    finally {
      setSessionsLoading(false)
      setSessionAction(current => current === 'refresh' ? null : current)
    }
  }, [areaId])
  const refreshCommands = useCallback(async () => {
    try { setCommands(await api.getCommands()) } catch { /* ignore */ }
  }, [])
  const refreshFileEdits = useCallback(async () => {
    try {
      const edits = await api.getFileEdits()
      if (edits.length > 0) setFileEdits(edits)
    } catch { /* ignore */ }
  }, [])
  const refreshApprovals = useCallback(async () => {
    try {
      const next = await api.getApprovals()
      if (next.length > 0) setApprovals(next)
    } catch { /* ignore */ }
  }, [])
  const clearFileEdits = useCallback(async () => {
    try { await api.clearFileEdits() } catch { /* ignore */ }
    setFileEdits([])
  }, [])

  /* ─────────────────────────────────────────────────────────────────────────
     EFECTO: CARGA INICIAL DE DATOS REST
     Se ejecuta al montar el componente para cargar modos, config, modelos,
     sesiones y comandos. Estas APIs REST no cambian frecuentemente.
     ──────────────────────────────────────────────────────────────────────── */
  useEffect(() => {
    refreshModes()
    refreshConfig()
    refreshModels()
    refreshSessions()
    refreshCommands()
  }, [refreshModes, refreshConfig, refreshModels, refreshSessions, refreshCommands])

  const scheduleSessionTitleRefresh = useCallback(() => {
    for (const delay of [2000, 6000, 15000, 35000]) {
      const timer = setTimeout(() => {
        refreshSessions()
      }, delay)
      sessionRefreshTimersRef.current.push(timer)
    }
  }, [refreshSessions])

  useEffect(() => {
    return () => {
      sessionRefreshTimersRef.current.forEach(clearTimeout)
      sessionRefreshTimersRef.current = []
    }
  }, [])

  /* ─────────────────────────────────────────────────────────────────────────
     EFECTO: PERSISTENCIA DE SESIÓN EN localStorage
     Guarda el ID de sesión activa para que al recargar la página se pueda
     restaurar la sesión previa. El sessionId cambia cuando el gateway
     envía control.ready con un nuevo session_id.
     ──────────────────────────────────────────────────────────────────────── */
  useEffect(() => {
    sessionIdRef.current = sessionId
    if (sessionId) {
      try {
        localStorage.setItem(`laia.${areaId}.lastSessionId`, sessionId)
      } catch { /* ignore */ }  // localStorage puede fallar en algunos navegadores
    }
  }, [areaId, sessionId])

  /* ═════════════════════════════════════════════════════════════════════════
     EFECTO PRINCIPAL: CONEXIÓN WEBSOCKET Y MANEJO DE MENSAJES
     Este es el núcleo del runtime. Establece la conexión WebSocket, maneja
     reconexiones automáticas, y procesa todos los mensajes entrantes del
     gateway (RPC responses y events).
     ═════════════════════════════════════════════════════════════════════════ */
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | null = null  // Timer de reconexión
    let destroyed = false  // Bandera para evitar callbacks después del unmount

    // Función interna que crea y configura la conexión WebSocket
    function connect() {
      // Si el componente se desmuntó, no intenta reconectar
      if (destroyed) return

      const ws = new WebSocket(wsUrl(areaId, appContext))
      socketRef.current = ws
      setConnection('connecting')

      // Callback: conexión establecida exitosamente
      ws.onopen = () => setConnection('online')

      // Callback: conexión cerrada - intenta reconectar en 3s si no fue intencional
      ws.onclose = () => {
        setConnection('offline')
        setStreaming(false)  // Asegura que streaming se desactiva
        if (!destroyed) retryTimer = setTimeout(connect, 3000)
      }

      // Callback: error de conexión - marca como offline
      ws.onerror = () => setConnection('offline')

      // ═══════════════════════════════════════════════════════════════════════
      // onmessage - Procesa TODOS los mensajes entrantes del gateway
      // Tipos de mensaje: 'response' (RPC response), 'error' (RPC error),
      //                    'event' (evento push del gateway)
      // ═══════════════════════════════════════════════════════════════════════
      ws.onmessage = event => {
        let data: GatewayEnvelope
        try {
          data = JSON.parse(event.data) as GatewayEnvelope
        } catch {
          console.warn('[agentRuntime] Malformed gateway message ignored:', event.data?.slice?.(0, 200))
          return
        }

        // ── RPC responses (respuestas a nuestros requests) ──────────────────
        if (data.type === 'response') {
          // Recupera el request pendiente correlacionado por ID
          const pending = data.id ? pendingRef.current.get(data.id) : undefined
          // [BUG] Elimina el pending ANTES de verificar si existe - posible pérdida
          // de información de debugging si el pending no existía
          if (data.id) pendingRef.current.delete(data.id)

          // Procesamiento especial según el método del request original
          if (pending?.method === 'session.usage' && data.result) {
            // Actualiza estadísticas de uso del modelo
            setUsage(data.result)
          }
          if (pending?.method === 'slash.exec' && data.result?.output) {
            // Un slash command devolvió output - lo añade como mensaje system
            setMessages(prev => [...prev, {
              id: makeId('system'),
              role: 'system',
              content: String(data.result?.output ?? ''),
            }])
          }
          if (pending?.method === 'command.dispatch' && data.result?.message) {
            // Un comando envió un mensaje - lo somete como prompt
            // [RACE] Podría enviar antes de que el agente esté listo para recibir
            send('prompt.submit', { text: String(data.result.message) })
          }
          // Track de tareas background: prompt.background devuelve {task_id}
          if (pending?.method === 'prompt.background' && data.result?.task_id) {
            const taskId = String(data.result.task_id)
            // Usa hasta 100 chars del texto como goal/descripción
            const goal = String(pending.payload?.text ?? '').slice(0, 100)
            // Registra el agente background activo
            setActiveAgents(prev => [...prev, {
              id: taskId, kind: 'background', name: taskId,
              goal, status: 'running', startedAt: Date.now(),
            }])
          }
          return
        }

        // ── RPC errors (errores de nuestros requests) ─────────────────────────
        if (data.type === 'error') {
          const pending = data.id ? pendingRef.current.get(data.id) : undefined
          if (data.id) pendingRef.current.delete(data.id)

          // Manejo especial para errores de slash.exec
          // Reintenta como command.dispatch - asumiendo que era un comando, no slash
          if (pending?.method === 'slash.exec') {
            // Extrae nombre y argumentos del comando fallido
            const raw = String(pending.payload?.command ?? '')
            const [name, ...rest] = raw.replace(/^\//, '').split(/\s+/)
            // [RACE] Si el primer slash.exec falló por timeout, el retry también fallará
            send('command.dispatch', { name, arg: rest.join(' ') })
            return
          }

          // Error genérico: lo muestra como mensaje de sistema en el chat
          setMessages(prev => [...prev, {
            id: makeId('error'),
            role: 'system',
            status: 'error',
            content: data.message ?? 'Runtime error',
          }])
          setStreaming(false)
          return
        }

        // Si no es 'response' ni 'error', solo procesamos 'event'
        if (data.type !== 'event') return

        // Extrae el nombre del evento y el payload
        const payload = data.payload ?? {}
        const ev = data.event ?? 'event'
        const eventSessionId = valueText(data.session_id)
        if (ev !== 'control.ready' && eventSessionId) {
          const currentSessionId = sessionIdRef.current
          if (!currentSessionId || eventSessionId !== currentSessionId) {
            return
          }
        }

        // ═══════════════════════════════════════════════════════════════════
        // PROCESAMIENTO DE EVENTOS PUSH (del gateway al cliente)
        // ═══════════════════════════════════════════════════════════════════

        // ── Lifecycle: control.ready ────────────────────────────────────────
        // Primer evento al conectar: el gateway confirma que la sesión está lista.
        // Inicializa sessionId, solicita usage y lista de herramientas.
        if (ev === 'control.ready') {
          const readyArea = valueText(payload.area_id, 'workspace')
          if (readyArea !== areaId) return
          setSessionId(valueText(payload.session_id))
          send('session.usage')   // Solicita estadísticas de uso
          send('tools.list')      // Solicita lista de herramientas disponibles
          addTrace({
            id: makeId('event'),
            type: 'ready',
            title: 'Centro de control en línea',
            detail: valueText(payload.session_id, 'sesión preparada'),
            tone: 'green'
          })

        // ── Lifecycle: session.info ─────────────────────────────────────────
        // Metadata de la sesión (modelo usado, contexto, etc.)
        } else if (ev === 'session.info') {
          setSessionInfo(payload)
          addTrace({
            id: makeId('event'),
            type: 'session',
            title: 'Perfil de sesión cargado',
            detail: valueText(payload.model, 'metadata actualizada'),
            tone: 'cyan'
          })

        // ── Chat: message.start ──────────────────────────────────────────────
        // Indica que el asistente comienza a generar una respuesta.
        // Crea un mensaje vacío del assistant y guarda su ID en currentAssistantRef.
        // [RACE] Si llegan múltiples message.start sin message.complete, se sobreescribe
        } else if (ev === 'message.start') {
          const id = makeId('assistant')
          currentAssistantRef.current = id
          setStreaming(true)
          setCurrentActivity('Pensando…')
          setMessages(prev => [...prev, { id, role: 'assistant', content: '', toolCalls: [] }])

        // ── Chat: message.delta ──────────────────────────────────────────────
        // Fragmento de texto streaming (token-by-token).
        // Concatena al contenido del mensaje del assistant activo.
        // [RACE] currentAssistantRef.current podría estar stale si hay race conditions
        } else if (ev === 'message.delta') {
          const text = valueText(payload.text)
          const targetId = currentAssistantRef.current
          setMessages(prev => prev.map(msg =>
            msg.id === targetId ? { ...msg, content: msg.content + text } : msg))

        // ── Chat: message.complete ────────────────────────────────────────────
        // Finalización del mensaje del assistant. Actualiza contenido final,
        // marca streaming como false, y solicita refresh de archivos/aprobaciones.
        } else if (ev === 'message.complete') {
          const text = valueText(payload.text)
          const targetId = currentAssistantRef.current
          const status = valueText(payload.status)
          // Mensaje fallback si no hay contenido y el status indica error
          const fallback = status === 'error'
            ? 'El runtime terminó con error antes de devolver texto.'
            : ''
          setMessages(prev => prev.map(msg =>
            msg.id === targetId
              ? { ...msg, content: msg.content || text || fallback, status }
              : msg))
          currentAssistantRef.current = null  // Limpia la referencia activa
          setStreaming(false)
          setCurrentActivity('')
          send('session.usage')        // Actualiza estadísticas
          refreshFileEdits()           // Refresca lista de archivos editados
          refreshApprovals()           // Refresca aprobaciones pendientes
          scheduleSessionTitleRefresh() // Captura el titulo auto-generado por la IA

        // ── Runtime: error ───────────────────────────────────────────────────
        // Error general del runtime (no de RPC). Se muestra en chat y trazas.
        } else if (ev === 'error') {
          const message = valueText(payload.message, 'Error del runtime')
          setMessages(prev => [...prev, {
            id: makeId('runtime-error'),
            role: 'system',
            status: 'error',
            content: message
          }])
          setStreaming(false)
          setCurrentActivity('')
          addTrace({
            id: makeId('event'),
            type: 'error',
            title: 'Runtime error',
            detail: message,
            tone: 'red'
          })

        // ── Thinking/Reasoning: streaming de razonamiento ────────────────────
        // Eventos que emiten el proceso de "pensamiento" del modelo.
        // Se coalescen en addTrace para no saturar el panel de debug.
        // [MEMORY] Si el modelo emite muchos tokens de reasoning, el trace puede
        // crecer mucho antes de ser coalesced - potencial memory leak en sesiones largas
        } else if (ev === 'thinking.delta' || ev === 'reasoning.delta' || ev === 'reasoning.available') {
          addTrace({
            id: makeId('event'),
            type: ev.replace('.delta', ''),
            title: ev.startsWith('reasoning') ? 'Reasoning' : 'Thinking',
            detail: valueText(payload.text).slice(0, 260),
            tone: 'violet'
          })
          // Actualiza currentActivity si hay streaming activo o mensaje en progreso
          if (streaming || currentAssistantRef.current) {
            setCurrentActivity(ev.startsWith('reasoning') ? 'Razonando…' : 'Pensando…')
          }

        // ── Status: actualización de estado del runtime ─────────────────────
        } else if (ev === 'status.update') {
          addTrace({
            id: makeId('event'),
            type: valueText(payload.kind, 'status'),
            title: 'Runtime status',
            detail: valueText(payload.text),
            tone: 'amber'
          })
          const txt = valueText(payload.text)
          if (txt) setCurrentActivity(txt.slice(0, 80))

        // ── Tool: inicio de ejecución ─────────────────────────────────────────
        // Una herramienta/tool comienza a ejecutarse.
        // Se añade a toolCalls del mensaje activo del assistant.
        } else if (ev === 'tool.start') {
          const toolId = valueText(payload.tool_id)
          const name = valueText(payload.name, 'tool')
          const context = valueText(payload.context, '')
          const targetId = currentAssistantRef.current

          if (targetId) {
            // Añade la nueva herramienta en ejecución al mensaje activo
            setMessages(prev => prev.map(msg =>
              msg.id === targetId
                ? { ...msg, toolCalls: [...(msg.toolCalls || []), { id: toolId, name, context, status: 'running' }] }
                : msg))
          }
          // Actualiza actividad actual con nombre de herramienta
          setCurrentActivity(`${name}${context ? ': ' + context.slice(0, 60) : ''}`)
          addTrace({
            id: makeId('event'),
            type: 'tool',
            title: name,
            detail: context || 'running',
            tone: 'cyan'
          })

        // ── Tool: progreso intermedio ─────────────────────────────────────────
        // Emitido periódicamente por herramientas que reportan progreso.
        // Acumula previews en el array progress del ToolCall.
        } else if (ev === 'tool.progress') {
          const toolId = valueText(payload.tool_id)
          const name = valueText(payload.name, 'tool')
          const preview = valueText(payload.preview, '')

          // Muestra preview en actividad actual (truncado a 60 chars)
          if (preview) setCurrentActivity(`${name}: ${preview.slice(0, 60)}`)

          addTrace({
            id: makeId('event'),
            type: 'progress',
            title: name,
            detail: preview || 'working',
            tone: 'amber'
          })

          // Append preview a la herramienta activa en el mensaje del assistant
          // [RACE] currentAssistantRef.current puede no ser el mensaje correcto
          // si hubo interleaving de message.start de múltiples agentes
          const targetMsgId = currentAssistantRef.current
          if (targetMsgId && toolId && preview) {
            setMessages(prev => prev.map(msg =>
              msg.id === targetMsgId
                ? {
                    ...msg,
                    toolCalls: (msg.toolCalls || []).map(tc =>
                      tc.id === toolId
                        // Acumula hasta 20 previews máximo (slice(-20))
                        ? { ...tc, progress: [...(tc.progress || []), preview].slice(-20) }
                        : tc),
                  }
                : msg))
          }

        // ── Tool: completación ───────────────────────────────────────────────
        // Una herramienta terminó (éxito o error). Actualiza el ToolCall.
        } else if (ev === 'tool.complete') {
          const toolId = valueText(payload.tool_id)
          const name = valueText(payload.name, 'tool')
          const summary = valueText(payload.summary, valueText(payload.error, 'completed'))
          const errored = !!payload.error              // Bandera de error
          const inlineDiff = valueText(payload.inline_diff)  // Diff si editó archivos
          // Duration: solo actualiza si es número válido
          const duration = typeof payload.duration_s === 'number' ? payload.duration_s as number : undefined
          const targetId = currentAssistantRef.current

          if (targetId && toolId) {
            setMessages(prev => prev.map(msg =>
              msg.id === targetId
                ? {
                    ...msg,
                    toolCalls: (msg.toolCalls || []).map(tc =>
                      tc.id === toolId
                        ? {
                            ...tc,
                            status: errored ? 'error' : 'complete',
                            summary,
                            duration_s: duration,
                            inline_diff: inlineDiff,
                            error: errored ? valueText(payload.error) : undefined,
                          }
                        : tc),
                  }
                : msg))
          }

          setCurrentActivity('')  // Limpia actividad al completar
          addTrace({
            id: makeId('event'),
            type: 'complete',
            title: name,
            detail: summary,
            tone: errored ? 'red' : 'green',
            inlineDiff,
          })

          // Si la herramienta editó archivos, refresca la lista de fileEdits
          // [PERF] podria optimizarse con debounce si hay muchas ediciones rapidas
          if (inlineDiff) {
            const edit: FileEdit = {
              id: toolId || makeId('edit'),
              session_id: sessionIdRef.current,
              tool: name,
              path: extractDiffPath(inlineDiff, summary || name),
              operation: name.includes('patch') ? 'patch' : 'write',
              diff: inlineDiff,
              created_at: new Date().toISOString(),
            }
            setFileEdits(prev => {
              const existing = prev.find(e => e.id === edit.id)
              if (existing) return prev.map(e => e.id === edit.id ? edit : e)
              return [...prev, edit].slice(-80)
            })
          }
          if (name.includes('write_file') || name.includes('patch') ||
              name.includes('str_replace') || name.includes('edit')) {
            refreshFileEdits()
          }

        // ── Approval: solicitud de aprobación ───────────────────────────────
        // El runtime necesita aprobación del usuario para continuar.
        // Configura pendingPrompt y envia notificación si la ventana no tiene focus.
        } else if (ev === 'approval.request') {
          // Gateway usa 'description' como razón/descripción de la aprobación
          const approvalDesc = valueText(payload.description, 'Aprobación requerida')
          setPendingPrompt({
            kind: 'approval',
            requestId: valueText(payload.request_id),
            question: approvalDesc,
            command: valueText(payload.command),
            reason: valueText(payload.description),  // [BUG] reason = description, duplicado
          })
          setApprovals(prev => {
            const requestId = valueText(payload.request_id) || makeId('approval')
            const next = {
              request_id: requestId,
              session_id: sessionIdRef.current,
              command: valueText(payload.command),
              reason: valueText(payload.description),
              prompt_type: valueText(payload.prompt_type, 'approval'),
              created_at: new Date().toISOString(),
              resolved: false,
            }
            const existing = prev.find(a => a.request_id === requestId)
            if (existing) return prev.map(a => a.request_id === requestId ? next : a)
            return [...prev, next]
          })
          refreshApprovals()

          // Notificación nativa del SO si la ventana no tiene foco (solo Tauri)
          // [SEC] No verifica si las notificaciones están habilitadas globalmente
          // antes de intentar enviar - podría violar preferencias del usuario
          if (!document.hasFocus()) {
            import('@tauri-apps/plugin-notification').then(({ isPermissionGranted, requestPermission, sendNotification }) => {
              isPermissionGranted().then(async granted => {
                if (!granted) {
                  // Solicita permiso si no estaba concedido
                  granted = (await requestPermission()) === 'granted'
                }
                if (granted) {
                  sendNotification({
                    title: 'LAIA — Aprobación requerida',
                    body: approvalDesc
                  })
                }
              }).catch(() => {})  // [BUG] Silencia todos los errores - no hay logging
            }).catch(() => {})    // Si el plugin no está instalado, falla silenciosamente

          // ── Clarify: solicitud de clarificación ────────────────────────────
          }
        } else if (ev === 'clarify.request') {
          setPendingPrompt({
            kind: 'clarify',
            requestId: valueText(payload.request_id),
            question: valueText(payload.question),
            // Convierte choices a array de strings (por si vienen como números u objetos)
            choices: Array.isArray(payload.choices) ? payload.choices.map(String) : undefined,
          })

        // ── Sudo/Secret: solicitud de contraseña ─────────────────────────────
        } else if (ev === 'sudo.request' || ev === 'secret.request') {
          setPendingPrompt({
            kind: ev.startsWith('sudo') ? 'sudo' : 'secret',
            requestId: valueText(payload.request_id),
            question: valueText(payload.prompt, ev),
          })

        // ── Subagentes: eventos de subprocesos spawniados ─────────────────────
        // El gateway emite subagent.start, subagent.update, subagent.complete, subagent.error
        } else if (ev.startsWith('subagent.')) {
          addTrace({
            id: makeId('event'),
            type: ev,
            title: valueText(payload.goal, 'Subagent'),
            detail: valueText(payload.summary,
              valueText(payload.text, valueText(payload.tool_preview))),
            tone: 'violet',
          })

          // Genera ID estable para el subagente.
          // El gateway puede enviar task_id (si existe) o construirlo de goal+task_index.
          // [BUG] Si dos subagentes tienen el mismo goal e index, collisionarán
          const subId = valueText(payload.task_id) ||
            `sub:${valueText(payload.goal)}:${valueText(payload.task_index, '0')}`
          const isTerminal = ev === 'subagent.complete' || ev === 'subagent.error'

          setActiveAgents(prev => {
            const existing = prev.find(a => a.id === subId)
            // Calcula el summary nuevo - preserva el anterior si no hay nuevo
            const newSummary = valueText(payload.summary,
              valueText(payload.text, valueText(payload.tool_preview, existing?.summary)))

            if (existing) {
              // Subagente ya existe - actualiza su estado/resumen
              return prev.map(a => a.id === subId
                ? {
                    ...a,
                    summary: newSummary,
                    status: isTerminal
                      ? (ev === 'subagent.error' ? 'error' : 'complete')
                      : a.status,
                    endedAt: isTerminal ? Date.now() : a.endedAt,
                  }
                : a)
            }

            // Primera vez que vemos este subagente - lo registra
            return [...prev, {
              id: subId,
              kind: 'subagent',
              name: valueText(payload.goal, 'subagent').slice(0, 60),
              goal: valueText(payload.goal),
              status: isTerminal ? (ev === 'subagent.error' ? 'error' : 'complete') : 'running',
              startedAt: Date.now(),
              endedAt: isTerminal ? Date.now() : undefined,
              summary: newSummary,
            }]
          })

        // ── btw.complete: respuesta a pregunta lateral ──────────────────────
        } else if (ev === 'btw.complete') {
          const text = valueText(payload.text) ||
            '(el agente no devolvió texto — puede que la pregunta excediera el límite o el modelo retornara un dict)'
          setMessages(prev => [...prev, {
            id: makeId('btw'),
            role: 'assistant',
            content: text,
          }])
          addTrace({
            id: makeId('event'),
            type: 'btw',
            title: 'Side question',
            detail: text.slice(0, 160),
            tone: 'cyan'
          })

        // ── background.complete: tarea background finalizada ─────────────────
        } else if (ev === 'background.complete') {
          const taskId = valueText(payload.task_id)
          const text = valueText(payload.text)

          // Actualiza el agente background con estado final y timestamp
          setActiveAgents(prev => prev.map(a => a.id === taskId
            ? {
                ...a,
                status: text.startsWith('error:') ? 'error' : 'complete',
                endedAt: Date.now(),
                summary: text.slice(0, 200)
              }
            : a))

          addTrace({
            id: makeId('event'),
            type: 'background',
            title: 'Background done',
            detail: text.slice(0, 160),
            tone: 'violet'
          })

          // Añade mensaje system en el chat principal con el resultado
          setMessages(prev => [...prev, {
            id: makeId('system'),
            role: 'system',
            content: `↳ Background ${taskId} → ${text.slice(0, 240)}`,
          }])

        // ── Gateway: eventos internos del gateway/runtime ────────────────────
        } else if (ev === 'gateway.stderr' || ev === 'gateway.protocol_error' || ev === 'gateway.exit') {
          addTrace({
            id: makeId('event'),
            type: ev,
            title: 'Gateway',
            detail: valueText(payload.line,
              valueText(payload.preview, JSON.stringify(payload))),
            tone: ev === 'gateway.exit' ? 'red' : 'amber',
          })
        }
      }  // fin ws.onmessage
    }  // fin connect()

    // Inicia la conexión WebSocket al montar el efecto
    connect()

    // Cleanup: se ejecuta al desmontar o cambiar dependencias del efecto.
    // Marca como destruido, limpia timer de reconexión, y cierra socket.
    return () => {
      destroyed = true
      if (retryTimer) clearTimeout(retryTimer)
      socketRef.current?.close()
    }
    // [DEPENDENCY] Depende de send, addTrace, refreshFileEdits, refreshApprovals.
    // Si estas funciones cambian (referencia nueva), el efecto se reconecta.
    // useCallback memoiza las funciones, así que solo cambia si sus deps cambian.
  }, [areaId, appContext, send, addTrace, refreshFileEdits, refreshApprovals, scheduleSessionTitleRefresh])

  /* ═════════════════════════════════════════════════════════════════════════
     submitText - Envía un mensaje de texto del usuario al runtime
     Detecta si es un slash command (inicia con '/') o un prompt normal.
     No envía si ya hay streaming activo (evita enviar mientras llega respuesta).
     ═════════════════════════════════════════════════════════════════════════ */
  const submitText = useCallback((text: string) => {
    const trimmed = text.trim()
    // No envía si está vacío o si ya hay streaming activo
    // [BUG] Podría haber un caso de uso legítimo para interrumpir y enviar nuevo
    if (!trimmed || streaming) return

    // Añade el mensaje al historial local del chat
    setMessages(prev => [...prev, { id: makeId('user'), role: 'user', content: trimmed }])

    if (trimmed.startsWith('/')) {
      // Es un slash command: lo envía como slash.exec
      send('slash.exec', { command: trimmed })
    } else {
      // Prompt normal: el modelo recibe contexto oculto; el historial guarda el texto limpio.
      send('prompt.submit', {
        text: buildPromptWithToolContext(trimmed),
        persist_user_message: trimmed,
      })
    }
  }, [streaming, send, buildPromptWithToolContext])

  /* ═════════════════════════════════════════════════════════════════════════
     submitBtw - Envía una pregunta lateral "by the way" (fuera de línea principal)
     Estas preguntas se procesan en un contexto separado del chat principal.
     ═════════════════════════════════════════════════════════════════════════ */
  const submitBtw = useCallback((text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    setMessages(prev => [...prev, {
      id: makeId('user'),
      role: 'user',
      content: `(btw) ${trimmed}`,
    }])
    const persisted = `(btw) ${trimmed}`
    send('prompt.btw', {
      text: buildPromptWithToolContext(trimmed),
      persist_user_message: persisted,
    })
  }, [send, buildPromptWithToolContext])

  /* ═════════════════════════════════════════════════════════════════════════
     submitContext - Registra contexto de herramienta para próximos turnos.
     La UI almacena el mensaje con sentinel para renderizarlo como tarjeta,
     pero no dispara prompt.submit: el modelo solo lo ve junto al siguiente
     mensaje real del usuario.
     ═════════════════════════════════════════════════════════════════════════ */
  const submitContext = useCallback((toolId: string, text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    toolContextRef.current.set(toolId, trimmed)
    const sentinel = `[__CTX__:${toolId}]`
    setMessages(prev => {
      // Replace the last context card for this toolId instead of accumulating
      for (let i = prev.length - 1; i >= 0; i--) {
        if (prev[i].content.startsWith(sentinel)) {
          const updated = [...prev]
          updated[i] = { ...updated[i], content: `${sentinel}\n${trimmed}` }
          return updated
        }
      }
      return [...prev, { id: makeId('user'), role: 'user', content: `${sentinel}\n${trimmed}` }]
    })
  }, [])

  /* ═════════════════════════════════════════════════════════════════════════
     submitBackground - Lanza una tarea en segundo plano
     Opcionalmente inyecta las últimas 12 palabras del chat como contexto.
     El gateway recibe un nuevo thread AIAgent sin contexto previo - se
     trabaja haciendo embed del contexto en el prompt.
     ═════════════════════════════════════════════════════════════════════════ */
  const submitBackground = useCallback((text: string, includeContext = false) => {
    const trimmed = text.trim()
    if (!trimmed) return

    let payloadText = trimmed
    if (includeContext) {
      // Construye un prefijo de contexto con los últimos 12 mensajes
      // [RACE] El array `messages` es captado por closure en el momento del submit.
      // Si messages cambia entre el click y el send (muy improbable pero posible),
      // se usará el valor viejo. Esto es aceptable por la naturaleza de "snapshot".
      const recent = messages
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .slice(-12)
        .map(m => `[${m.role.toUpperCase()}]: ${m.content}`)
        .join('\n\n')

      if (recent) {
        payloadText = `## Contexto del chat principal (referencia, no respondas a esto)\n\n${recent}\n\n---\n\n## Tu tarea\n\n${trimmed}`
      }
    }

    // Mensaje de sistema indicando que se lanzó el background task
    setMessages(prev => [...prev, {
      id: makeId('system'),
      role: 'system',
      content: `↳ Lanzado en background${includeContext ? ' (con contexto)' : ''}: ${trimmed.slice(0, 120)}`,
    }])

    send('prompt.background', { text: payloadText })
    // [DEPENDENCY] Depende de messages - cuando messages cambia, se recrea el callback.
    // El valor de messages usado será siempre el más reciente gracias a la dependencia.
  }, [send, messages])

  /* ═════════════════════════════════════════════════════════════════════════
     interrupt - Envía señal de interrupción al runtime
     Intenta detener la ejecución actual del agente de forma limpia.
     ═════════════════════════════════════════════════════════════════════════ */
  const interrupt = useCallback(() => {
    send('session.interrupt')
  }, [send])

  const switchModel = useCallback(async (model: string) => {
    try {
      await api.switchModel(model, areaId)
      await refreshConfig()
      await refreshModels()
    } catch { /* ignore */ }
  }, [areaId, refreshConfig, refreshModels])

  const setEffort = useCallback(async (effort: string) => {
    try {
      await api.setReasoning(effort, areaId)
      await refreshModes()
      await refreshConfig()
    } catch { /* ignore */ }
  }, [areaId, refreshModes, refreshConfig])

  /* ═════════════════════════════════════════════════════════════════════════
     respondPrompt - Responde a un pendingPrompt activo
    不同 tipo de prompt tiene diferente método RPC y formato de respuesta.
     Finalmente limpia el pendingPrompt del estado.
     ═════════════════════════════════════════════════════════════════════════ */
  const respondPrompt = useCallback((choice: string) => {
    if (!pendingPrompt) return  // [BUG] Race condition - pendingPrompt podría ser null
                                // mientras llega la respuesta del server

    if (pendingPrompt.kind === 'approval') {
      // Approval: choice es una de {once, session, always, deny}
      send('approval.respond', { choice })
      if (pendingPrompt.requestId) {
        setApprovals(prev => prev.filter(a => a.request_id !== pendingPrompt.requestId))
      }
      refreshApprovals()
    } else if (pendingPrompt.kind === 'clarify') {
      send('clarify.respond', { request_id: pendingPrompt.requestId, answer: choice })
    } else if (pendingPrompt.kind === 'sudo') {
      send('sudo.respond', { request_id: pendingPrompt.requestId, password: choice })
    } else if (pendingPrompt.kind === 'secret') {
      send('secret.respond', { request_id: pendingPrompt.requestId, value: choice })
    }

    // [BUG] Limpia el pendingPrompt ANTES de confirmar que el server recibió
    // Si el send falla o el usuario hace spam, puede quedar inconsistente
    setPendingPrompt(null)
  }, [pendingPrompt, send, refreshApprovals])

  /* ═════════════════════════════════════════════════════════════════════════
     resumeSession - Restaura una sesión guardada por su key
     Obtiene el historial de mensajes del servidor REST y lo carga en el estado.
     El sessionId se actualiza y se limpian las trazas locales.
     ═════════════════════════════════════════════════════════════════════════ */
  const resumeSession = useCallback(async (key: string) => {
    setSessionAction('resume')
    try {
      // Llama a la API REST para obtener la sesión
      const result = await api.resumeSession(key, areaId, appContext) as unknown as {
        session_id?: string
        messages?: {
          role: string
          text?: string
          content?: unknown
          name?: string
          context?: string
        }[]
      }

      if (result.session_id) setSessionId(result.session_id)

      // Transforma los mensajes del formato gateway al formato interno ChatMessage
      const hist: ChatMessage[] = (result.messages || []).map((m, i) => {
        // Normaliza el rol a uno de los valores válidos
        const role: Role = (m.role === 'user' || m.role === 'assistant' ||
                            m.role === 'tool' || m.role === 'system')
          ? m.role
          : 'system'

        // Extrae el contenido (el gateway puede enviar text, content, o ambos)
        let content = ''
        if (typeof m.text === 'string') {
          content = m.text
        } else if (typeof m.content === 'string') {
          content = m.content
        } else if (Array.isArray(m.content)) {
          // Content array: típicamente partes de mensaje multimodal
          // Convierte cada parte a string y concatena
          content = (m.content as unknown[]).map(p =>
            (typeof p === 'string' ? p : String((p as Record<string, unknown>)?.text ?? ''))
          ).join('')
        }

        // Para mensajes de tool sin texto, muestra nombre y contexto
        if (!content && role === 'tool' && m.name) {
          content = `[${m.name}] ${m.context || ''}`.trim()
        }

        return {
          // ID con algo de aleatoriedad para evitar colisiones en re-renders
          id: `hist-${i}-${Math.random().toString(16).slice(2, 6)}`,
          role,
          content,
        }
      }).filter(m => m.content)  // Filtra mensajes vacíos

      // Si hay historial, lo usa; si no, muestra mensaje de bienvenida
      setMessages(hist.length ? hist : [WELCOME])
      setTrace([])  // Limpia trazas de la sesión anterior
      send('session.usage')  // Actualiza estadísticas
      refreshSessions()
    } catch { /* ignore */ }
    finally { setSessionAction(null) }
  }, [areaId, appContext, send, refreshSessions])

  /* ═════════════════════════════════════════════════════════════════════════
     newSession - Crea una nueva sesión vacía
     Resetea mensajes a solo el welcome, limpia trazas, y refresca la lista
     de sesiones para que aparezca la nueva.
     ═════════════════════════════════════════════════════════════════════════ */
  const newSession = useCallback(async () => {
    setSessionAction('new')
    try {
      const r = await api.createSession(areaId, appContext) as unknown as { session_id?: string }
      if (r.session_id) setSessionId(r.session_id)
      setMessages([WELCOME])
      setTrace([])
      refreshSessions()  // Actualiza la lista de sesiones disponibles
    } catch { /* ignore */ }
    finally { setSessionAction(null) }
  }, [areaId, appContext, refreshSessions])

  /* ═════════════════════════════════════════════════════════════════════════
     value - Objeto de contexto memoizado
     Se recrea solo cuando alguna de las dependencias cambia.
     Agrupa todo el estado y los métodos paraProvider al árbol de componentes.
     ═════════════════════════════════════════════════════════════════════════ */
  const value: AgentRuntimeValue = useMemo(() => ({
    connection, sessionId, sessionInfo, messages, trace, fileEdits, approvals,
    activeAgents, pendingPrompt, usage, sessionsLoading, sessionAction, streaming, currentActivity,
    modes, config, models, sessions, commands,
    send, submitText, submitBackground, submitBtw, submitContext, interrupt, switchModel, setEffort,
    setPendingPrompt, respondPrompt, refreshModes, refreshConfig, refreshModels, refreshSessions,
    refreshCommands, refreshFileEdits, refreshApprovals, clearFileEdits, resumeSession, newSession,
  }), [
    // Estado
    connection, sessionId, sessionInfo, messages, trace, fileEdits, approvals,
    activeAgents, pendingPrompt, usage, sessionsLoading, sessionAction, streaming, currentActivity,
    modes, config, models, sessions, commands,
    // Métodos
    send, submitText, submitBackground, submitBtw, submitContext, interrupt, switchModel, setEffort,
    respondPrompt, refreshModes, refreshConfig, refreshModels, refreshSessions, refreshCommands,
    refreshFileEdits, refreshApprovals, clearFileEdits, resumeSession, newSession,
  ])

  // ── Render ──────────────────────────────────────────────────────────────
  // Envuelve los hijos con el Provider del contexto
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
