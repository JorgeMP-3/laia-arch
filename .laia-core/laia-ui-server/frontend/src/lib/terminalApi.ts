import { getApiBase } from './api'

export interface TerminalInfo {
  id: string
  agent_type: string
  label?: string
  command: string[]
  cwd: string
  cols: number
  rows: number
  pid: number | null
  exit_code: number | null
  alive: boolean
  created_at: string
  permission_mode?: 'default' | 'bypass'
  pending_approval?: boolean
  approval_id?: string
  active_workspace?: string
  sandboxed?: boolean
  sandbox_warning?: string
  synapse?: {
    last_plan?: { workspace: string; slug: string; title: string; created_at: string }
    last_log?: { workspace: string; summary: string; created_at: string }
    active_workspace?: string
    sandboxed?: boolean
    sandbox_warning?: string
    created_at?: string
  }
}

export interface SpawnPayload {
  agent_type?: string
  cwd?: string
  cols?: number
  rows?: number
  prompt?: string
  label?: string
  permission_mode?: 'default' | 'bypass'
  require_prompt_approval?: boolean
}

export interface TerminalApproval {
  id: string
  action: 'spawn_prompt' | 'inject'
  terminal_id: string
  terminal_label: string
  agent_type: string
  text: string
  press_enter: boolean
  requested_by: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

export interface TerminalApprovalSettings {
  prompt_approval_required: boolean
}

export interface WorkspaceSynapse {
  active_workspace: string
  readable_workspaces: string[]
  terminal_synapse: Record<string, TerminalInfo['synapse']>
  recent_events: Array<{
    id: number
    event_type: string
    terminal_id?: string
    agent_id?: string
    summary?: string
    created_at: string
    payload?: Record<string, unknown>
  }>
  agent_nodes: Array<{
    slug: string
    title: string
    kind: string
    summary: string
    updated_at: string
  }>
  sandbox_available: boolean
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const base = getApiBase()
  const res = await fetch(`${base}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const terminalApi = {
  list: () => req<TerminalInfo[]>('GET', '/terminals'),
  spawn: (payload: SpawnPayload) => req<TerminalInfo>('POST', '/terminals', payload),
  inject: (id: string, text: string, pressEnter = true) =>
    req<{ ok: boolean; injected: number }>('POST', `/terminals/${id}/inject`, { text, press_enter: pressEnter }),
  approvals: () => req<TerminalApproval[]>('GET', '/terminals/approvals'),
  approvalSettings: () => req<TerminalApprovalSettings>('GET', '/terminals/approvals/settings'),
  setApprovalSettings: (promptApprovalRequired: boolean) =>
    req<TerminalApprovalSettings>('POST', '/terminals/approvals/settings', { prompt_approval_required: promptApprovalRequired }),
  approvePrompt: (id: string) => req<{ ok: boolean; injected: number }>('POST', `/terminals/approvals/${id}/approve`),
  rejectPrompt: (id: string) => req<{ ok: boolean }>('POST', `/terminals/approvals/${id}/reject`),
  synapse: () => req<WorkspaceSynapse>('GET', '/agent-workspace/synapse'),
  kill: (id: string) => req<{ ok: boolean }>('DELETE', `/terminals/${id}`),
}

export function terminalWsUrl(terminalId: string): string {
  const base = getApiBase()
  const isAbsolute = base.startsWith('http')
  const wsBase = isAbsolute
    ? base.replace(/^http/, 'ws')
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api`
  return `${wsBase}/terminals/${terminalId}/ws`
}
