/* ────────────────────────────────────────────────────────────────────────────
   SIDE PANELS (right column)
   Tabbed view: Live Trace · File Edits · Sub-agents · Approvals · Rollbacks · Skills
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Bot,
  Code2,
  FileDiff,
  History,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'
import type { ActiveAgent, TraceEvent } from '../../lib/agentRuntime'
import type { AgentEntry, FileEdit } from '../../lib/api'
import { api } from '../../lib/api'

export type SidePanelTab = 'trace' | 'edits' | 'agents' | 'approvals' | 'rollbacks' | 'skills'

export interface SidePanelsProfile {
  tabs?: SidePanelTab[]
  defaultTab?: SidePanelTab
  labels?: Partial<Record<SidePanelTab, string>>
  emptyLabels?: Partial<Record<SidePanelTab, string>>
}

export interface PanelAgentEntry {
  id: string
  name: string
  status?: string
  kind?: string
  detail?: string
  tone?: 'green' | 'red' | 'violet' | 'amber' | 'cyan'
  onStop?: () => void
}

interface Props {
  onOpenDiff: (edit: FileEdit) => void
  onOpenApproval: () => void
  profile?: SidePanelsProfile
  externalAgents?: PanelAgentEntry[]
}

const DEFAULT_TABS: SidePanelTab[] = ['trace', 'edits', 'agents', 'approvals', 'rollbacks', 'skills']
const DEFAULT_LABELS: Record<SidePanelTab, string> = {
  trace: 'Trace',
  edits: 'Edits',
  agents: 'Agents',
  approvals: 'Approv',
  rollbacks: 'Roll',
  skills: 'Skills',
}
const DEFAULT_EMPTY_LABELS: Record<SidePanelTab, string> = {
  trace: 'esperando eventos del runtime',
  edits: 'sin archivos modificados',
  agents: 'sin sub-agentes activos',
  approvals: 'sin aprobaciones pendientes',
  rollbacks: 'sin checkpoints',
  skills: 'sin skills disponibles',
}

export function SidePanels({ onOpenDiff, onOpenApproval, profile = {}, externalAgents = [] }: Props) {
  const { trace, fileEdits, approvals, activeAgents, refreshFileEdits, refreshApprovals, clearFileEdits } = useAgent()
  const availableTabs = profile.tabs ?? DEFAULT_TABS
  const labels = { ...DEFAULT_LABELS, ...profile.labels }
  const emptyLabels = { ...DEFAULT_EMPTY_LABELS, ...profile.emptyLabels }
  const [tab, setTab] = useState<SidePanelTab>(profile.defaultTab ?? availableTabs[0] ?? 'trace')
  const [shellAgents, setShellAgents] = useState<AgentEntry[]>([])

  function refreshShellAgents() {
    api.getAgents().then(d => setShellAgents(d.agents || [])).catch(() => setShellAgents([]))
  }

  useEffect(() => {
    if (tab === 'agents') refreshShellAgents()
  }, [tab])

  useEffect(() => {
    if (!availableTabs.includes(tab)) {
      setTab(availableTabs[0] ?? 'trace')
    }
  }, [availableTabs, tab])

  // Combined count: live in-process subagents + background tasks + shell processes
  const totalAgents = activeAgents.length + shellAgents.length + externalAgents.length

  useEffect(() => {
    if (approvals.length > 0 && tab === 'trace') setTab('approvals')
  }, [approvals.length])  // eslint-disable-line react-hooks/exhaustive-deps

  const allTabs: { id: SidePanelTab; icon: React.ReactNode; label: string; badge?: number }[] = [
    { id: 'trace',     icon: <Activity size={11} />,        label: labels.trace,     badge: trace.length || undefined },
    { id: 'edits',     icon: <FileDiff size={11} />,        label: labels.edits,     badge: fileEdits.length || undefined },
    { id: 'agents',    icon: <Bot size={11} />,             label: labels.agents,    badge: totalAgents || undefined },
    { id: 'approvals', icon: <AlertTriangle size={11} />,   label: labels.approvals, badge: approvals.length || undefined },
    { id: 'rollbacks', icon: <History size={11} />,         label: labels.rollbacks },
    { id: 'skills',    icon: <Sparkles size={11} />,        label: labels.skills },
  ]
  const tabs = allTabs.filter(t => availableTabs.includes(t.id))

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'rgba(255,196,90,0.003)', overflow: 'hidden' }}>
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', flexShrink: 0, background: 'rgba(0,0,0,0.1)' }}>
        <div className="flex w-full">
          {tabs.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTab(t.id)
                if (t.id === 'edits') refreshFileEdits()
                if (t.id === 'approvals') refreshApprovals()
              }}
              className="flex-1 flex items-center justify-center gap-1 py-2.5 transition-colors"
              style={{
                background: tab === t.id ? 'rgba(255,196,90,0.06)' : 'transparent',
                borderBottom: `2px solid ${tab === t.id ? 'var(--ws-accent)' : 'transparent'}`,
                color: tab === t.id ? 'var(--ws-accent)' : 'var(--ws-text-muted)',
              }}
            >
              {t.icon}
              <span className="mono text-[0.55rem] uppercase tracking-widest">{t.label}</span>
              {t.badge !== undefined && t.badge > 0 && (
                <span className="mono text-[0.55rem]" style={{ opacity: 0.7 }}>{t.badge}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 10 }}>
        {tab === 'trace' && <TraceList trace={trace} emptyLabel={emptyLabels.trace} />}
        {tab === 'edits' && <EditsList edits={fileEdits} onOpen={onOpenDiff} onClear={clearFileEdits} emptyLabel={emptyLabels.edits} />}
        {tab === 'agents' && <AgentsList shellAgents={shellAgents} activeAgents={activeAgents} externalAgents={externalAgents} onRefresh={refreshShellAgents} emptyLabel={emptyLabels.agents} />}
        {tab === 'approvals' && <ApprovalsList onOpen={onOpenApproval} emptyLabel={emptyLabels.approvals} />}
        {tab === 'rollbacks' && <RollbacksList emptyLabel={emptyLabels.rollbacks} />}
        {tab === 'skills' && <SkillsList emptyLabel={emptyLabels.skills} />}
      </div>
    </div>
  )
}

// ── Trace ────────────────────────────────────────────────────────────────────

function TraceList({ trace, emptyLabel }: { trace: TraceEvent[]; emptyLabel: string }) {
  if (trace.length === 0) {
    return <Empty label={emptyLabel} />
  }
  return (
    <div>
      {trace.map((event, i) => {
        const color =
          event.tone === 'red' ? 'var(--ws-danger)' :
          event.tone === 'green' ? 'var(--ws-success)' :
          event.tone === 'cyan' ? 'var(--ws-accent)' :
          event.tone === 'violet' ? 'var(--ws-violet)' : 'var(--ws-warning)'
        const time = new Date(event.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
        return (
          <div key={event.id} className="relative border-l py-2 pl-3 mb-1" style={{ borderColor: i === 0 ? color : 'var(--ws-border)' }}>
            <span
              className={i === 0 ? 'ws-pulse' : ''}
              style={{
                position: 'absolute', left: -3.5, top: 12,
                width: 7, height: 7, borderRadius: '50%',
                background: i === 0 ? color : 'rgba(255,255,255,0.18)',
                boxShadow: i === 0 ? `0 0 8px ${color}` : undefined,
              }}
            />
            <div className="flex items-start justify-between gap-2 mb-0.5">
              <div className="text-[0.72rem] font-medium leading-snug" style={{ color: 'var(--ws-text)' }}>
                {event.title}
              </div>
              <span className="mono text-[0.55rem] shrink-0" style={{ color: 'var(--ws-text-muted)', opacity: 0.5 }}>
                {time}
              </span>
            </div>
            <span
              className="mono inline-block px-1.5 py-0.5 rounded text-[0.5rem] uppercase tracking-widest"
              style={{ color, background: `${color}14`, border: `1px solid ${color}28` }}
            >
              {event.type}
            </span>
            {(event.count ?? 1) > 1 && (
              <span
                className="mono inline-block ml-1 px-1.5 py-0.5 rounded text-[0.5rem] uppercase tracking-widest"
                style={{ color: 'var(--ws-text-muted)', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--ws-border)' }}
              >
                x{event.count}
              </span>
            )}
            <div className="text-[0.66rem] mt-1 leading-relaxed" style={{ color: 'var(--ws-text-muted)' }}>
              {event.detail}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Edits ────────────────────────────────────────────────────────────────────

function EditsList({ edits, onOpen, onClear, emptyLabel }: { edits: FileEdit[]; onOpen: (e: FileEdit) => void; onClear: () => void; emptyLabel: string }) {
  if (edits.length === 0) return <Empty label={emptyLabel} />
  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
          {edits.length} cambios
        </span>
        <button type="button" onClick={onClear} className="ws-pill" style={{ padding: '2px 6px' }}>
          <Trash2 size={9} /> limpiar
        </button>
      </div>
      {edits.slice().reverse().map(edit => (
        <button
          key={edit.id}
          type="button"
          onClick={() => onOpen(edit)}
          className="block w-full text-left rounded-md p-2 mb-1.5 transition-colors"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ws-border)' }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--ws-border-strong)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--ws-border)'}
        >
          <div className="flex items-center gap-2 mb-1">
            <Code2 size={11} style={{ color: 'var(--ws-accent)' }} />
            <span className="ws-pill" style={{ padding: '0 5px', fontSize: '0.5rem' }} data-active="true">
              {edit.operation}
            </span>
            <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
              {new Date(edit.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="mono text-[0.66rem] truncate" style={{ color: 'var(--ws-text)' }}>
            {edit.path}
          </div>
        </button>
      ))}
    </div>
  )
}

// ── Agents ───────────────────────────────────────────────────────────────────

function AgentsList({ shellAgents, activeAgents, externalAgents, onRefresh, emptyLabel }: {
  shellAgents: AgentEntry[]
  activeAgents: ActiveAgent[]
  externalAgents: PanelAgentEntry[]
  onRefresh: () => void
  emptyLabel: string
}) {
  if (shellAgents.length === 0 && activeAgents.length === 0 && externalAgents.length === 0) {
    return <Empty label={emptyLabel} />
  }

  const running = activeAgents.filter(a => a.status === 'running')
  const finished = activeAgents.filter(a => a.status !== 'running').slice(-5)

  return (
    <div>
      {externalAgents.length > 0 && (
        <>
          <SectionLabel text={`command center (${externalAgents.length})`} />
          {externalAgents.map(agent => (
            <PanelAgentCard key={agent.id} agent={agent} />
          ))}
        </>
      )}

      {running.length > 0 && (
        <>
          <SectionLabel text={`activos (${running.length})`} />
          {running.map(a => <ActiveAgentCard key={a.id} a={a} />)}
        </>
      )}

      {shellAgents.length > 0 && (
        <>
          <div className="flex items-center justify-between mt-2">
            <SectionLabel text={`shell processes (${shellAgents.length})`} />
            <button type="button" onClick={onRefresh} className="ws-pill" style={{ padding: '1px 6px', fontSize: '0.55rem' }}>
              recargar
            </button>
          </div>
          {shellAgents.map(agent => (
            <div
              key={agent.id}
              className="rounded-md p-2.5 mb-1.5"
              style={{ background: 'rgba(196, 181, 253, 0.06)', border: '1px solid rgba(196, 181, 253, 0.18)' }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Bot size={11} style={{ color: 'var(--ws-violet)' }} />
                  <span className="text-[0.7rem] font-medium truncate" style={{ color: 'var(--ws-text)' }}>
                    {agent.name || agent.id?.slice(0, 12) || 'process'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => api.stopAgent(agent.id).then(() => onRefresh())}
                  className="ws-pill"
                  style={{ padding: '2px 6px', color: 'var(--ws-danger)' }}
                  title="Detener"
                >
                  stop
                </button>
              </div>
              {agent.status && (
                <div className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
                  status: <span style={{ color: 'var(--ws-text)' }}>{agent.status}</span>
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {finished.length > 0 && (
        <>
          <SectionLabel text="recientes" />
          {finished.map(a => <ActiveAgentCard key={a.id} a={a} />)}
        </>
      )}
    </div>
  )
}

function SectionLabel({ text }: { text: string }) {
  return (
    <div className="mono text-[0.55rem] uppercase tracking-widest mb-1.5 mt-1" style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
      {text}
    </div>
  )
}

function ActiveAgentCard({ a }: { a: ActiveAgent }) {
  const color = a.status === 'error' ? 'var(--ws-danger)' :
                a.status === 'complete' ? 'var(--ws-success)' :
                'var(--ws-violet)'
  const icon = a.status === 'running' ? '◐' : a.status === 'error' ? '✕' : '✓'
  const elapsed = ((a.endedAt || Date.now()) - a.startedAt) / 1000
  return (
    <div className="rounded-md p-2.5 mb-1.5" style={{ background: `${color}0E`, border: `1px solid ${color}33` }}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={a.status === 'running' ? 'ws-pulse' : ''} style={{ color }}>{icon}</span>
          <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color }}>{a.kind}</span>
          <span className="text-[0.7rem] truncate" style={{ color: 'var(--ws-text)' }}>
            {a.name || a.id.slice(0, 14)}
          </span>
        </div>
        <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
          {elapsed < 60 ? `${elapsed.toFixed(0)}s` : `${(elapsed / 60).toFixed(1)}m`}
        </span>
      </div>
      {a.goal && a.goal !== a.name && (
        <div className="text-[0.62rem] mb-1 line-clamp-2" style={{ color: 'var(--ws-text-muted)' }}>{a.goal}</div>
      )}
      {a.summary && (
        <div className="text-[0.62rem]" style={{ color: 'var(--ws-text)' }}>{a.summary}</div>
      )}
    </div>
  )
}

function PanelAgentCard({ agent }: { agent: PanelAgentEntry }) {
  const color =
    agent.tone === 'red' ? 'var(--ws-danger)' :
    agent.tone === 'green' ? 'var(--ws-success)' :
    agent.tone === 'cyan' ? 'var(--ws-accent)' :
    agent.tone === 'amber' ? 'var(--ws-warning)' :
    'var(--ws-violet)'
  const running = agent.status === 'running'

  return (
    <div className="rounded-md p-2.5 mb-1.5" style={{ background: `${color}0E`, border: `1px solid ${color}33` }}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={running ? 'ws-pulse' : ''} style={{ color }}>{running ? '◐' : '✓'}</span>
          {agent.kind && (
            <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color }}>
              {agent.kind}
            </span>
          )}
          <span className="text-[0.7rem] truncate" style={{ color: 'var(--ws-text)' }}>
            {agent.name}
          </span>
        </div>
        {agent.onStop && running && (
          <button
            type="button"
            onClick={agent.onStop}
            className="ws-pill"
            style={{ padding: '2px 6px', color: 'var(--ws-danger)' }}
            title="Detener"
          >
            stop
          </button>
        )}
      </div>
      <div className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
        {agent.status || 'unknown'} · {agent.id.slice(0, 8)}
      </div>
      {agent.detail && (
        <div className="text-[0.62rem] mt-1 line-clamp-2" style={{ color: 'var(--ws-text-muted)' }}>
          {agent.detail}
        </div>
      )}
    </div>
  )
}

// ── Approvals ────────────────────────────────────────────────────────────────

function ApprovalsList({ onOpen, emptyLabel }: { onOpen: () => void; emptyLabel: string }) {
  const { approvals } = useAgent()
  if (approvals.length === 0) return <Empty label={emptyLabel} />
  return (
    <div>
      {approvals.map(approval => (
        <button
          key={approval.request_id}
          type="button"
          onClick={onOpen}
          className="block w-full text-left rounded-md p-2.5 mb-1.5 transition-colors"
          style={{ background: 'rgba(252, 165, 165, 0.06)', border: '1px solid rgba(252, 165, 165, 0.22)' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={11} style={{ color: 'var(--ws-danger)' }} />
            <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-danger)' }}>
              {approval.prompt_type}
            </span>
          </div>
          <div className="mono text-[0.66rem] truncate" style={{ color: 'var(--ws-text)' }}>
            {approval.command}
          </div>
          {approval.reason && (
            <div className="text-[0.6rem] mt-1" style={{ color: 'var(--ws-text-muted)' }}>
              {approval.reason}
            </div>
          )}
        </button>
      ))}
    </div>
  )
}

// ── Rollbacks ────────────────────────────────────────────────────────────────

function RollbacksList({ emptyLabel }: { emptyLabel: string }) {
  const [data, setData] = useState<{ enabled: boolean; checkpoints: { hash: string; timestamp: string; message: string }[] } | null>(null)
  const [loading, setLoading] = useState(false)

  function refresh() {
    setLoading(true)
    api.getRollbacks().then(setData).catch(() => setData({ enabled: false, checkpoints: [] })).finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  if (loading && !data) return <Empty label="cargando…" />
  if (!data?.enabled) return <Empty label="rollback deshabilitado" />
  if (data.checkpoints.length === 0) return <Empty label={emptyLabel} />

  async function restore(hash: string) {
    if (!confirm(`Restaurar checkpoint ${hash.slice(0, 8)}? Sobrescribirá cambios.`)) return
    try { await api.restoreRollback(hash); refresh() } catch { /* ignore */ }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
          {data.checkpoints.length} checkpoints
        </span>
        <button type="button" onClick={refresh} className="ws-pill" style={{ padding: '2px 6px' }}>
          recargar
        </button>
      </div>
      {data.checkpoints.map(cp => (
        <div key={cp.hash} className="rounded-md p-2 mb-1.5" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ws-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <History size={11} style={{ color: 'var(--ws-accent)' }} />
            <span className="mono text-[0.6rem]" style={{ color: 'var(--ws-accent)' }}>{cp.hash.slice(0, 8)}</span>
            <span className="mono text-[0.55rem] truncate" style={{ color: 'var(--ws-text-muted)' }}>
              {cp.timestamp || ''}
            </span>
            <button type="button" onClick={() => restore(cp.hash)} className="ws-pill ml-auto" style={{ padding: '1px 6px', fontSize: '0.55rem' }}>
              restaurar
            </button>
          </div>
          <div className="text-[0.66rem]" style={{ color: 'var(--ws-text)' }}>
            {cp.message || '(sin mensaje)'}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Skills ───────────────────────────────────────────────────────────────────

interface SkillEntry {
  name: string
  description?: string
  category?: string
  version?: string
  author?: string
  platforms?: string[]
  tags?: string[]
}

function SkillsList({ emptyLabel }: { emptyLabel: string }) {
  const [skills, setSkills] = useState<SkillEntry[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  function refresh() {
    setLoading(true)
    api.getAgentSkills().then((d: Record<string, unknown>) => {
      const raw = d.skills as unknown
      const arr: SkillEntry[] = []
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        for (const [, list] of Object.entries(raw as Record<string, unknown>)) {
          if (Array.isArray(list)) {
            for (const s of list as Record<string, unknown>[]) {
              if (typeof s === 'string') {
                arr.push({ name: s })
              } else if (s && typeof s === 'object') {
                arr.push({
                  name: String(s.name || ''),
                  description: String(s.description || ''),
                  category: String(s.category || ''),
                  version: String(s.version || ''),
                  author: String(s.author || ''),
                  platforms: Array.isArray(s.platforms) ? s.platforms.map(String) : [],
                  tags: Array.isArray(s.tags) ? s.tags.map(String) : [],
                })
              }
            }
          }
        }
      } else if (Array.isArray(raw)) {
        for (const s of raw as Record<string, unknown>[]) {
          arr.push({
            name: String(s.name || ''),
            description: String(s.description || ''),
            category: String(s.category || ''),
          })
        }
      }
      setSkills(arr.filter(s => s.name))
    }).catch(() => setSkills([])).finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  if (loading && skills.length === 0) return <Empty label="cargando skills…" />
  if (skills.length === 0) return <Empty label={emptyLabel} />

  const filtered = query
    ? skills.filter(s =>
        s.name.toLowerCase().includes(query.toLowerCase()) ||
        (s.description || '').toLowerCase().includes(query.toLowerCase()) ||
        (s.category || '').toLowerCase().includes(query.toLowerCase()))
    : skills

  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Buscar skill, descripción o categoría…"
        className="field w-full text-[0.7rem] mb-2"
        style={{ padding: '5px 8px', borderRadius: 8 }}
      />
      <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
        {filtered.length} skills
      </span>
      <div className="mt-2">
        {filtered.map(s => (
          <button
            key={`${s.category}/${s.name}`}
            type="button"
            onClick={() => setSelected(s.name)}
            className="block w-full text-left rounded-md p-2 mb-1 transition-colors"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ws-border)', cursor: 'pointer' }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--ws-border-strong)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--ws-border)'}
          >
            <div className="flex items-center gap-2 mb-0.5">
              <Sparkles size={10} style={{ color: 'var(--ws-violet)' }} />
              <span className="mono text-[0.66rem]" style={{ color: 'var(--ws-accent)' }}>{s.name}</span>
              {s.category && (
                <span className="mono text-[0.5rem] px-1 py-0.5 rounded" style={{ color: 'var(--ws-text-muted)', background: 'rgba(255,255,255,0.04)' }}>
                  {s.category}
                </span>
              )}
            </div>
            {s.description && (
              <div className="text-[0.6rem] line-clamp-2" style={{ color: 'var(--ws-text-muted)' }}>{s.description}</div>
            )}
          </button>
        ))}
      </div>
      {selected && <SkillDetailModal name={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function SkillDetailModal({ name, onClose }: { name: string; onClose: () => void }) {
  const [data, setData] = useState<{
    name: string; category: string; description: string; version?: string;
    author?: string; platforms?: string[]; body: string; path: string;
  } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getSkillDetail(name)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [name])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="ws-card flex flex-col"
        style={{ width: '90vw', maxWidth: 800, maxHeight: '85vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="ws-card-header">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Sparkles size={13} style={{ color: 'var(--ws-violet)' }} />
            <span className="mono text-[0.7rem]" style={{ color: 'var(--ws-accent)' }}>{name}</span>
            {data?.category && (
              <span className="mono text-[0.55rem] px-1 py-0.5 rounded"
                style={{ color: 'var(--ws-text-muted)', background: 'rgba(255,255,255,0.04)' }}>
                {data.category}
              </span>
            )}
          </div>
          <button type="button" onClick={onClose} className="ws-pill" style={{ padding: '3px 6px' }}>
            cerrar
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {loading && <div className="mono text-[0.65rem]" style={{ color: 'var(--ws-text-muted)' }}>cargando…</div>}
          {!loading && !data && <div className="text-[0.7rem]" style={{ color: 'var(--ws-danger)' }}>No se pudo cargar el detalle de la skill</div>}
          {data && (
            <>
              {data.description && (
                <p className="text-sm mb-3" style={{ color: 'var(--ws-text)' }}>{data.description}</p>
              )}
              <div className="grid grid-cols-2 gap-2 mb-3 mono text-[0.6rem]" style={{ color: 'var(--ws-text-muted)' }}>
                {data.version && <div>version: <span style={{ color: 'var(--ws-text)' }}>{data.version}</span></div>}
                {data.author && <div>author: <span style={{ color: 'var(--ws-text)' }}>{data.author}</span></div>}
                {data.platforms && data.platforms.length > 0 && (
                  <div className="col-span-2">platforms: <span style={{ color: 'var(--ws-text)' }}>{data.platforms.join(', ')}</span></div>
                )}
                <div className="col-span-2 truncate">path: <span style={{ color: 'var(--ws-text)' }}>{data.path}</span></div>
              </div>
              <div className="mono text-[0.55rem] uppercase tracking-widest mb-1.5" style={{ color: 'var(--ws-text-muted)', opacity: 0.7 }}>
                SKILL.md
              </div>
              <pre className="mono text-xs leading-relaxed" style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                background: 'rgba(0,0,0,0.3)', padding: 12, borderRadius: 6,
                border: '1px solid var(--ws-border)', color: 'var(--ws-text)',
                maxHeight: 400, overflow: 'auto',
              }}>
                {data.body}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Empty state ──────────────────────────────────────────────────────────────

function Empty({ label }: { label: string }) {
  return (
    <div className="text-center py-8 mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)', opacity: 0.5 }}>
      {label}
    </div>
  )
}
