import type { ToolContextProfile } from '../../components/common/ToolContextInjector'
import type { ToolAreaProfile } from '../../components/common/ToolAreaProvider'
import type { TerminalInfo } from '../terminalApi'

// Static context injected into the agent's system prompt at session.create time.
// Persists for ALL turns — not affected by the workspace-context plugin's
// per-turn injection. Keep it concise: it's prepended to ephemeral_system_prompt.
export const COMMAND_CENTER_APP_CONTEXT = `\
UBICACIÓN: Command Center (/command-center) — orquestación multi-agente.
ROL: LAIA/LAIA — Orchestrator. Planifica, delega, revisa, documenta en workspace DB.

ROLES:
  Orchestrator (tú): idea→plan concreto, asigna agentes, valida resultados, documenta.
  Frontier (claude-code-planner, codex-worker): plan técnico, debugging, QA, integración.
  Economy (opencode-worker, bash): implementación masiva según plan, scripts, boilerplate.

ASIGNACIÓN: ¿puedo hacerlo yo? → hazlo. ¿arquitectura/QA? → Frontier. ¿implementación? → Economy. ¿N tareas independientes? → N Economy en paralelo.

FLUJO: planifica+documenta → Frontier(plan técnico) → Economy×N(impl.) → Frontier(QA) → documenta cierre.

OBLIGATORIO AL ORQUESTAR:
  1. Antes de delegar, mira el estado real con command_center_read_all si ya hay terminales vivas.
  2. Cada prompt enviado a una terminal debe pasar por command_center_inject; por defecto quedará pendiente de aprobación humana.
  3. Después de spawn/inject, no asumas que el agente continúa bien: usa command_center_read_all o command_center_read con cursor.
  4. Si una terminal muestra permisos, confirmaciones, sudo, errores o espera input, notifícalo y decide explícitamente; no te olvides de ella.
  5. Mientras haya terminales vivas, haz revisiones periódicas de estado antes de responder cierre.

SYNAPSE DB-FIRST:
  - Los agentes PTY reciben 'ccw' y variables COMMAND_CENTER_* para leer workspaces sin tocar SQLite directo.
  - Pueden leer todos los workspaces configurados si lo necesitan.
  - Solo pueden escribir append-only en el workspace activo mediante 'ccw plan' y 'ccw log'.
  - LAIA conserva la autoridad para editar/documentar nodos generales y fusionar conocimiento final.

HERRAMIENTAS:
  command_center_list               → listar terminales
  command_center_read_all           → snapshot todas las terminales (prefiere esto a list+N×read)
  command_center_spawn(agent_type, cwd?, label?, prompt?) → lanzar agente PTY
  command_center_inject(id, text)   → enviar texto a terminal
  command_center_approvals          → ver prompts pendientes de aprobación humana
  command_center_prompt_approval_mode(enabled?) → consultar/activar/desactivar aprobación de prompts
  command_center_read(id, from_line?) → leer output con cursor
  command_center_wait(id, timeout?) → esperar exit de una terminal
  command_center_wait_all(ids[], timeout?) → esperar N terminales en paralelo
  command_center_kill(id)           → matar terminal
  command_center_document(title, content, kind?) → guardar en workspace DB
  command_center_workspace_read(kind?, query?, limit?) → leer workspace DB

NUNCA uses terminal(background=true).`

// Dynamic profile: updates LAIA when the terminal list changes.
function terminalsList(terminals: TerminalInfo[]): string {
  const alive = terminals.filter(t => t.alive)
  if (alive.length === 0) return 'Ninguna terminal activa.'
  return alive.map(t => {
    const synapse = t.synapse
    const plan = synapse?.last_plan ? ` plan:${synapse.last_plan.slug}` : ''
    const log = synapse?.last_log ? ` log:${synapse.last_log.summary}` : ''
    const sandbox = t.sandboxed ? ' sandbox:bwrap' : ' sandbox:degradado'
    return `  • ${t.label || t.agent_type}  [${t.agent_type}]  id:${t.id}  cwd:${t.cwd}${sandbox}${plan}${log}`
  }).join('\n')
}

export const commandCenterContext: ToolContextProfile<TerminalInfo[]> = {
  toolId: 'command-center',

  stateHash: (terminals) =>
    terminals.filter(t => t.alive).map(t => `${t.id}:${t.label||''}`).sort().join(','),

  getConnectText: (terminals) =>
    `[Command Center] Terminales activas (${terminals.filter(t => t.alive).length}):\n${terminalsList(terminals)}`,

  getDeltaText: (terminals) => {
    const alive = terminals.filter(t => t.alive)
    return `[Command Center · actualización] Terminales activas (${alive.length}):\n${terminalsList(terminals)}`
  },
}

export const commandCenterToolArea: ToolAreaProfile<TerminalInfo[]> = {
  areaId: 'command-center',
  appContext: COMMAND_CENTER_APP_CONTEXT,
  dynamicContext: commandCenterContext,
}
