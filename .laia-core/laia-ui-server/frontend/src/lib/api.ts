// In Tauri the base URL is set at runtime via setApiBase(); in web dev it stays '/api'
let _apiBase = '/api'

export function setApiBase(serverUrl: string) {
  _apiBase = serverUrl ? `${serverUrl}/api` : '/api'
}

export function getApiBase() {
  return _apiBase
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${_apiBase}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = err.detail
    const message = typeof detail === 'string'
      ? detail
      : typeof detail?.summary === 'string'
        ? detail.summary
        : `HTTP ${res.status}`
    throw new ApiError(message, res.status, detail)
  }
  return res.json()
}

export interface Workspace {
  name: string
  node_count: number
  edge_count: number
  updated_at: string | null
}

export interface NodeSummary {
  id: number
  slug: string
  title: string
  kind: string
  summary: string
  updated_at: string
  is_container?: boolean
}

export interface NodeLink {
  slug: string
  title: string
  kind: string
  rel: string
}

export interface Node extends NodeSummary {
  content: string
  status: string
  parent_id: number | null
  tags: string[]
  created_at: string
  filename: string
  links: NodeLink[]
}

export interface SearchResult {
  slug: string
  title: string
  kind: string
  score: number
  summary: string
  is_container?: boolean
}

export interface GraphData {
  nodes: { id: string; label: string; kind: string }[]
  edges: { source: string; target: string; rel: string }[]
}

export interface NodePayload {
  title: string
  kind: string
  content?: string
  summary?: string
  tags?: string[]
  parent_ref?: string | null
  status?: string
}

export interface Event {
  id: number
  event_type: string
  node_id: number | null
  node_slug: string | null
  node_title: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface MarkdownExportSection {
  root?: string
  written: string[]
  removed: string[]
}

export interface MarkdownExportResult {
  context: MarkdownExportSection
  organized: MarkdownExportSection & { root: string }
}

export interface VerifyDbResult {
  verified: boolean
  node_count: number
  missing: string[]
  summary: string
}

export interface CleanExportsResult {
  verification: VerifyDbResult
  deleted: string[]
}

export type MigrationEntry = Record<string, string>

export interface LegacyMigrationManifest {
  workspace: string
  imported: MigrationEntry[]
  moved: MigrationEntry[]
  skipped: MigrationEntry[]
  removed: string[]
  backup: string | null
  verified: boolean
  node_count: number
  missing: string[]
  generated: string[]
}

export interface LegacyMigrationResult {
  manifest: LegacyMigrationManifest
}

// ── Context Engine ────────────────────────────────────────────────────────────

export interface ContextEngineConfig {
  workspace: string
  inject_mode: string
  max_chars: number
  active_workspaces?: string[]
  workspaces?: string[]
}

export interface InjectedNode {
  workspace: string
  title: string
  kind: string
  slug: string
  content: string
  chars: number
}

export interface InjectedData {
  workspace: string
  inject_mode: string
  max_chars: number
  instruction: string
  instruction_chars: number
  nodes_injected: InjectedNode[]
  nodes_by_workspace: Record<string, InjectedNode[]>
  total_chars: number
  pct_used: number
}

export interface PrefetchNode {
  workspace: string
  slug: string
  title: string
  kind: string
}

export interface PrefetchNodesData {
  workspace: string
  inject_mode: string
  nodes: PrefetchNode[]
}

export interface PrefetchResult {
  workspace: string
  slug: string
  title: string
  kind: string
  score: number
  content: string
  chars: number
}

export interface PrefetchData {
  workspace: string
  query: string
  results: PrefetchResult[]
}

export interface SkillEntry {
  name: string
  category: string
  description: string
  path: string
  tags: string[]
}

export interface SkillsData {
  total: number
  by_category: Record<string, SkillEntry[]>
}

// ── Agent Control ─────────────────────────────────────────────────────────────

export interface AgentSession {
  id?: string
  session_id: string
  session_key?: string
  title?: string
  created_at?: string
  started_at?: string | number
  updated_at?: string | number
  message_count?: number
  model?: string
  source?: string
  preview?: string
}

export interface CommandDef {
  name: string
  description: string
  category: string
  aliases: string[]
  args_hint: string
  subcommands: string[]
  cli_only: boolean
  gateway_only: boolean
}

export interface ModelOption {
  id: string
  name: string
  provider?: string
  is_current?: boolean
}

export interface ModelsData {
  current?: string
  options?: ModelOption[]
}

export interface AgentConfig {
  model: string
  provider: string
  reasoning_effort: string
  max_turns: number
  streaming: boolean
  tool_progress: string
  personality: string
  yolo: boolean
  plan_mode: boolean
  ask_before_edit: boolean
  auto_mode: boolean
}

export interface Modes {
  plan_mode: boolean
  auto_mode: boolean
  ask_before_edit: boolean
  yolo: boolean
  reasoning_effort: string
}

export interface FileEdit {
  id: string
  session_id: string
  tool: string
  path: string
  operation: 'write' | 'patch'
  diff: string
  created_at: string
}

export interface ApprovalRequest {
  request_id: string
  session_id: string
  command: string
  reason: string
  prompt_type: string
  created_at: string
  resolved: boolean
}

export interface AgentEntry {
  id: string
  name?: string
  status?: string
  created_by?: string
  created_at?: string
  turns?: number
  model?: string
}

export interface AgentStatus {
  tui_gateway: {
    running: boolean
    session_id: string | null
    sessions_by_area?: Record<string, string | null>
  }
  gateway: { running: boolean; pid: number | null; state: Record<string, unknown> }
  telegram: { home_channel: string | null; channels: Record<string, unknown> }
  platforms: Record<string, unknown>
}

export const api = {
  // ── Workspaces ─────────────────────────────────────────────────────────────
  getWorkspaces: () => req<Workspace[]>('GET', '/workspaces'),
  getNodes: (ws: string) => req<NodeSummary[]>('GET', `/workspaces/${ws}/nodes`),
  getNode: (ws: string, ref: string) => req<Node>('GET', `/workspaces/${ws}/nodes/${ref}`),
  updateNode: (ws: string, ref: string, data: NodePayload) =>
    req<Node>('PUT', `/workspaces/${ws}/nodes/${ref}`, data),
  createNode: (ws: string, data: NodePayload) =>
    req<Node>('POST', `/workspaces/${ws}/nodes`, data),
  deleteNode: (ws: string, ref: string) =>
    req<{ ok: boolean }>('DELETE', `/workspaces/${ws}/nodes/${ref}`),
  searchNodes: (ws: string, q: string) =>
    req<SearchResult[]>('GET', `/workspaces/${ws}/search?q=${encodeURIComponent(q)}`),
  getGraph: (ws: string) => req<GraphData>('GET', `/workspaces/${ws}/graph`),
  addLink: (ws: string, ref: string, data: { target_ref: string; rel: string }) =>
    req('POST', `/workspaces/${ws}/nodes/${ref}/links`, data),
  getEvents: (ws: string) => req<Event[]>('GET', `/workspaces/${ws}/events`),
  exportMarkdown: (ws: string) =>
    req<MarkdownExportResult>('POST', `/workspaces/${ws}/export-markdown`),
  cleanExports: (ws: string) =>
    req<CleanExportsResult>('POST', `/workspaces/${ws}/clean-exports`),
  migrateLegacy: (ws: string) =>
    req<LegacyMigrationResult>('POST', `/workspaces/${ws}/migrate-legacy`),
  verifyDb: (ws: string) =>
    req<VerifyDbResult>('GET', `/workspaces/${ws}/verify-db`),
  getContextEngineConfig: () =>
    req<ContextEngineConfig>('GET', '/context-engine/config'),
  updateContextConfig: (data: Partial<ContextEngineConfig>) =>
    req<ContextEngineConfig>('PUT', '/context-engine/config', data),
  toggleWorkspaceActive: (name: string) =>
    req<ContextEngineConfig>('POST', `/context-engine/workspace/${encodeURIComponent(name)}/toggle-active`),
  getContextEngineInjected: () =>
    req<InjectedData>('GET', '/context-engine/injected'),
  getContextEnginePrefetchNodes: () =>
    req<PrefetchNodesData>('GET', '/context-engine/prefetch-nodes'),
  simulatePrefetch: (q: string) =>
    req<PrefetchData>('GET', `/context-engine/prefetch?q=${encodeURIComponent(q)}`),
  getContextEngineSkills: () =>
    req<SkillsData>('GET', '/context-engine/skills'),

  // ── Agent Sessions ──────────────────────────────────────────────────────────
  getSessions: (areaId = 'workspace') =>
    req<AgentSession[]>('GET', `/agent/sessions?area_id=${encodeURIComponent(areaId)}`),
  createSession: (areaId = 'workspace', appContext = '') => {
    const params = new URLSearchParams({ area_id: areaId })
    if (appContext) params.set('app_context', appContext)
    return req<AgentSession>('POST', `/agent/sessions?${params.toString()}`)
  },
  resumeSession: (sessionKey: string, areaId = 'workspace', appContext = '') => {
    const params = new URLSearchParams({ area_id: areaId })
    if (appContext) params.set('app_context', appContext)
    return req<AgentSession>('POST', `/agent/sessions/resume?${params.toString()}`, { session_key: sessionKey })
  },
  getCurrentSession: (areaId = 'workspace') =>
    req<AgentSession & { history: unknown[]; usage: unknown }>('GET', `/agent/sessions/current?area_id=${encodeURIComponent(areaId)}`),
  interruptSession: (sessionId: string) =>
    req<{ ok: boolean }>('POST', `/agent/sessions/${sessionId}/interrupt`),
  undoSession: (sessionId: string) =>
    req<{ ok: boolean }>('POST', `/agent/sessions/${sessionId}/undo`),
  compressSession: (sessionId: string) =>
    req<{ ok: boolean }>('POST', `/agent/sessions/${sessionId}/compress`),
  getSessionUsage: (sessionId: string) =>
    req<Record<string, unknown>>('GET', `/agent/sessions/${sessionId}/usage`),
  getSessionHistory: (sessionId: string) =>
    req<{ history: unknown[] }>('GET', `/agent/sessions/${sessionId}/history`),
  updateSessionTitle: (sessionId: string, title: string) =>
    req<{ title: string }>('PUT', `/agent/sessions/${sessionId}/title`, { title }),
  branchSession: (sessionId: string, name?: string) =>
    req<AgentSession>('POST', `/agent/sessions/${sessionId}/branch`, { name }),

  // ── Commands ────────────────────────────────────────────────────────────────
  getCommands: () => req<CommandDef[]>('GET', '/agent/commands'),
  searchCommands: (q: string) =>
    req<CommandDef[]>('GET', `/agent/commands/search?q=${encodeURIComponent(q)}`),
  executeCommand: (command: string, sessionId?: string) =>
    req<Record<string, unknown>>('POST', '/agent/commands/execute', { command, session_id: sessionId }),

  // ── Model ───────────────────────────────────────────────────────────────────
  getModels: () => req<ModelsData>('GET', '/agent/models'),
  switchModel: (model: string, areaId?: string) =>
    req<Record<string, unknown>>('POST', `/agent/model${areaId ? `?area_id=${areaId}` : ''}`, { model }),

  // ── Config ──────────────────────────────────────────────────────────────────
  getAgentConfig: (areaId?: string) =>
    req<AgentConfig>('GET', `/agent/config${areaId ? `?area_id=${areaId}` : ''}`),
  setAgentConfig: (key: string, value: unknown, areaId?: string) =>
    req<Record<string, unknown>>('PATCH', `/agent/config${areaId ? `?area_id=${areaId}` : ''}`, { key, value }),

  // ── Reasoning ───────────────────────────────────────────────────────────────
  getReasoning: (areaId?: string) =>
    req<{ effort: string; options: string[] }>('GET', `/agent/reasoning${areaId ? `?area_id=${areaId}` : ''}`),
  setReasoning: (effort: string, areaId?: string) =>
    req<Record<string, unknown>>('POST', `/agent/reasoning${areaId ? `?area_id=${areaId}` : ''}`, { effort }),

  // ── Modes ───────────────────────────────────────────────────────────────────
  getModes: (areaId?: string) =>
    req<Modes>('GET', `/agent/modes${areaId ? `?area_id=${areaId}` : ''}`),
  setModes: (modes: Partial<Modes>, areaId?: string) =>
    req<{ updated: Partial<Modes> }>('POST', `/agent/modes${areaId ? `?area_id=${areaId}` : ''}`, modes),

  // ── Tools ───────────────────────────────────────────────────────────────────
  getTools: () => req<Record<string, unknown>>('GET', '/agent/tools'),
  toggleTool: (name: string, enabled: boolean) =>
    req<Record<string, unknown>>('POST', `/agent/tools/${name}/toggle`, { enabled }),

  // ── Agents / Processes ──────────────────────────────────────────────────────
  getAgents: () => req<{ agents: AgentEntry[] }>('GET', '/agent/agents'),
  stopAgent: (agentId: string) =>
    req<{ ok: boolean }>('DELETE', `/agent/agents/${agentId}`),

  // ── Approvals ───────────────────────────────────────────────────────────────
  getApprovals: () => req<ApprovalRequest[]>('GET', '/agent/approvals'),
  approveCommand: (requestId: string) =>
    req<Record<string, unknown>>('POST', `/agent/approvals/${requestId}/approve`),
  denyCommand: (requestId: string) =>
    req<Record<string, unknown>>('POST', `/agent/approvals/${requestId}/deny`),

  // ── File Edits ──────────────────────────────────────────────────────────────
  getFileEdits: (sessionId?: string) =>
    req<FileEdit[]>('GET', `/agent/file-edits${sessionId ? `?session_id=${sessionId}` : ''}`),
  clearFileEdits: () => req<{ ok: boolean }>('DELETE', '/agent/file-edits'),
  getFileEditDiff: (editId: string) =>
    req<FileEdit & { diff: string }>('GET', `/agent/file-edits/${editId}/diff`),

  // ── Rollbacks ───────────────────────────────────────────────────────────────
  getRollbacks: () => req<{ enabled: boolean; checkpoints: { hash: string; timestamp: string; message: string }[] }>('GET', '/agent/rollbacks'),
  getRollbackDiff: (rollbackId: string) =>
    req<{ diff: string }>('GET', `/agent/rollbacks/${rollbackId}/diff`),
  restoreRollback: (rollbackId: string) =>
    req<Record<string, unknown>>('POST', '/agent/rollbacks/restore', { rollback_id: rollbackId }),

  // ── Cron ────────────────────────────────────────────────────────────────────
  getCronJobs: () => req<Record<string, unknown>>('GET', '/agent/cron'),
  createCronJob: (schedule: string, command: string, name?: string) =>
    req<Record<string, unknown>>('POST', '/agent/cron', { schedule, command, name }),
  deleteCronJob: (jobId: string) =>
    req<Record<string, unknown>>('DELETE', `/agent/cron/${jobId}`),
  pauseCronJob: (jobId: string) =>
    req<Record<string, unknown>>('POST', `/agent/cron/${jobId}/pause`),
  resumeCronJob: (jobId: string) =>
    req<Record<string, unknown>>('POST', `/agent/cron/${jobId}/resume`),
  runCronJob: (jobId: string) =>
    req<Record<string, unknown>>('POST', `/agent/cron/${jobId}/run`),

  // ── Usage / Insights ────────────────────────────────────────────────────────
  getUsage: () => req<Record<string, unknown>>('GET', '/agent/usage'),
  getInsights: (days?: number) =>
    req<Record<string, unknown>>('GET', `/agent/insights${days ? `?days=${days}` : ''}`),

  // ── Personalities ────────────────────────────────────────────────────────────
  getPersonalities: () => req<{ personalities: { name: string; prompt_preview?: string }[]; current?: string }>('GET', '/agent/personalities'),
  setPersonality: (name: string) =>
    req<Record<string, unknown>>('POST', '/agent/personality', { name }),

  // ── Skills ──────────────────────────────────────────────────────────────────
  getAgentSkills: () => req<Record<string, unknown>>('GET', '/agent/skills'),
  getSkillDetail: (name: string) => req<{
    name: string; category: string; description: string;
    version?: string; author?: string; platforms?: string[];
    metadata?: Record<string, unknown>; prerequisites?: Record<string, unknown>;
    body: string; path: string;
  }>('GET', `/agent/skills/${encodeURIComponent(name)}`),
  installSkill: (name: string, category?: string) =>
    req<Record<string, unknown>>('POST', '/agent/skills/install', { name, category }),

  // ── Status ──────────────────────────────────────────────────────────────────
  getAgentStatus: () => req<AgentStatus>('GET', '/agent/status'),
}
