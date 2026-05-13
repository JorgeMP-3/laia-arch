import { useCallback, useEffect, useRef, useState } from 'react'
import { BrainCircuit, Check, ChevronDown, Cpu, Database, FileText, PanelLeft, PanelRight, Plus, ShieldCheck, ShieldOff, Square, Terminal, X } from 'lucide-react'
import { useAgent } from '../lib/agentRuntime'
import type { ToolCall } from '../lib/agentRuntime'
import { ChatStream } from '../components/workspace/ChatStream'
import { ToolShell } from '../components/common/ToolShell'
import { SessionsRail } from '../components/workspace/SessionsRail'
import { SidePanels } from '../components/workspace/SidePanels'
import type { PanelAgentEntry } from '../components/workspace/SidePanels'
import { DiffModal } from '../components/workspace/DiffModal'
import { ApprovalDialog } from '../components/workspace/ApprovalDialog'
import { PromptDialog } from '../components/workspace/PromptDialog'
import { ToolDetailModal } from '../components/workspace/ToolDetailModal'
import { TerminalPanel } from '../components/commandcenter/TerminalPanel'
import type { TerminalPanelHandle } from '../components/commandcenter/TerminalPanel'
import { SpawnAgentModal } from '../components/commandcenter/SpawnAgentModal'
import { InjectBar } from '../components/commandcenter/InjectBar'
import { terminalApi } from '../lib/terminalApi'
import type { TerminalApproval, TerminalInfo, SpawnPayload, WorkspaceSynapse } from '../lib/terminalApi'
import { commandCenterToolArea } from '../lib/contexts/commandCenterContext'
import type { FileEdit } from '../lib/api'

const REASONING_LEVELS = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const

function CCAgentControls() {
  const { models, config, modes, streaming, interrupt, switchModel, setEffort } = useAgent()
  const [modelOpen, setModelOpen] = useState(false)
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const currentModel = config?.model || models?.current || '—'
  const currentEffort = modes?.reasoning_effort ?? 'medium'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {/* Model picker */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => { setModelOpen(o => !o); setReasoningOpen(false) }}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
            border: '1px solid rgba(255,196,90,0.25)', background: 'rgba(255,196,90,0.07)',
            color: '#ffc45a', fontFamily: 'monospace', fontSize: '0.65rem',
          }}
        >
          <Cpu size={11} />
          <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{currentModel}</span>
          <ChevronDown size={10} />
        </button>
        {modelOpen && (
          <div style={{
            position: 'absolute', left: 0, top: '100%', marginTop: 4, zIndex: 50,
            minWidth: 280, maxHeight: 360, overflowY: 'auto',
            background: '#0d0b00', border: '1px solid rgba(255,196,90,0.2)',
            borderRadius: 8, padding: 6, boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
          }}>
            {(() => {
              const opts = models?.options ?? []
              const grouped: Record<string, typeof opts> = {}
              for (const opt of opts) {
                const p = opt.provider || 'other'
                if (!grouped[p]) grouped[p] = []
                grouped[p].push(opt)
              }
              return Object.keys(grouped).sort().map(prov => (
                <div key={prov} style={{ marginBottom: 4 }}>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.52rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#ffc45a', opacity: 0.7, padding: '3px 8px' }}>{prov}</div>
                  {grouped[prov].map((opt, i) => (
                    <button
                      key={`${prov}-${i}`}
                      type="button"
                      onClick={() => { setModelOpen(false); void switchModel(opt.id) }}
                      style={{
                        display: 'block', width: '100%', textAlign: 'left',
                        padding: '5px 10px', borderRadius: 5, cursor: 'pointer', border: 'none',
                        background: opt.id === currentModel ? 'rgba(255,196,90,0.12)' : 'transparent',
                        color: opt.id === currentModel ? '#ffc45a' : '#e6edf3',
                        fontFamily: 'monospace', fontSize: '0.68rem',
                      }}
                    >{opt.name || opt.id}</button>
                  ))}
                </div>
              ))
            })()}
            {!models?.options?.length && (
              <div style={{ padding: '8px 10px', fontSize: '0.7rem', color: '#6b7280' }}>Sin modelos</div>
            )}
          </div>
        )}
      </div>

      {/* Reasoning effort */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => { setReasoningOpen(o => !o); setModelOpen(false) }}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
            border: `1px solid ${currentEffort !== 'none' ? 'rgba(196,181,253,0.35)' : 'rgba(255,255,255,0.1)'}`,
            background: currentEffort !== 'none' ? 'rgba(196,181,253,0.08)' : 'transparent',
            color: currentEffort !== 'none' ? '#c4b5fd' : '#6b7280',
            fontFamily: 'monospace', fontSize: '0.65rem',
          }}
        >
          <BrainCircuit size={11} />
          {currentEffort}
          <ChevronDown size={10} />
        </button>
        {reasoningOpen && (
          <div style={{
            position: 'absolute', left: 0, top: '100%', marginTop: 4, zIndex: 50,
            minWidth: 130, background: '#0d0b00', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, padding: 4, boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
          }}>
            {REASONING_LEVELS.map(level => (
              <button
                key={level}
                type="button"
                onClick={() => { setReasoningOpen(false); void setEffort(level) }}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '5px 10px', borderRadius: 5, cursor: 'pointer', border: 'none',
                  background: currentEffort === level ? 'rgba(196,181,253,0.12)' : 'transparent',
                  color: currentEffort === level ? '#c4b5fd' : '#e6edf3',
                  fontFamily: 'monospace', fontSize: '0.7rem',
                }}
              >{level}</button>
            ))}
          </div>
        )}
      </div>

      {/* Stop button */}
      {streaming && (
        <button
          type="button"
          onClick={interrupt}
          title="Interrumpir agente"
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
            border: '1px solid rgba(252,165,165,0.35)', background: 'rgba(252,165,165,0.08)',
            color: '#fca5a5', fontFamily: 'monospace', fontSize: '0.65rem',
          }}
        >
          <Square size={11} fill="currentColor" />
          Stop
        </button>
      )}
    </div>
  )
}

function defaultPanelOpen(minWidth: number) {
  return typeof window === 'undefined' ? true : window.innerWidth >= minWidth
}

export default function CommandCenter() {
  const [diffEdit, setDiffEdit] = useState<FileEdit | null>(null)
  const [toolDetail, setToolDetail] = useState<ToolCall | null>(null)
  const [terminals, setTerminals] = useState<TerminalInfo[]>([])
  const [showSpawn, setShowSpawn] = useState(false)
  const [showSessions, setShowSessions] = useState(() => defaultPanelOpen(1280))
  const [showInspector, setShowInspector] = useState(() => defaultPanelOpen(1360))
  const terminalRefs = useRef<Map<string, TerminalPanelHandle>>(new Map())
  const [terminalApprovals, setTerminalApprovals] = useState<TerminalApproval[]>([])
  const [synapse, setSynapse] = useState<WorkspaceSynapse | null>(null)
  const [promptApprovalRequired, setPromptApprovalRequired] = useState(true)
  const [hermesWidth, setHermesWidth] = useState(340)
  const dragging = useRef(false)
  const dragStartX = useRef(0)
  const dragStartW = useRef(0)
  const [dragHover, setDragHover] = useState(false)
  const [layoutCols, setLayoutCols] = useState<1|2|3>(2)

  const refreshTerminalApprovals = useCallback(async () => {
    try {
      const [approvals, settings] = await Promise.all([
        terminalApi.approvals(),
        terminalApi.approvalSettings(),
      ])
      setTerminalApprovals(approvals)
      setPromptApprovalRequired(settings.prompt_approval_required)
    } catch {
      // Command Center should still be usable if the approval side-channel is offline.
    }
  }, [])

  const refreshSynapse = useCallback(async () => {
    try {
      setSynapse(await terminalApi.synapse())
    } catch {
      // Synapse is an enhancement; terminals remain usable if it is unavailable.
    }
  }, [])

  function onDragHandleMouseDown(e: React.MouseEvent) {
    dragging.current = true
    dragStartX.current = e.clientX
    dragStartW.current = hermesWidth
    function onMove(ev: MouseEvent) {
      if (!dragging.current) return
      const delta = ev.clientX - dragStartX.current
      setHermesWidth(Math.max(220, Math.min(600, dragStartW.current + delta)))
    }
    function onUp() {
      dragging.current = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  // Poll terminal list every 2s so terminals spawned by Hermes via its tool appear automatically
  useEffect(() => {
    let cancelled = false
    const sync = () => {
      if (cancelled) return
      terminalApi.list().then(fresh => {
        if (cancelled) return
        setTerminals(prev => {
          // Keep existing entries (preserves local alive=false from WS exit events),
          // merge in any new terminals from the backend, drop ones gone from backend.
          const merged = fresh.map(f => {
            const existing = prev.find(p => p.id === f.id)
            // Prefer local alive=false (WebSocket already told us it exited)
            if (existing && !existing.alive) return { ...f, alive: false }
            return f
          })
          // Only update state if something actually changed
          const changed =
            merged.length !== prev.length ||
            merged.some((t, i) => t.id !== prev[i]?.id || t.alive !== prev[i]?.alive)
          return changed ? merged : prev
        })
      }).catch(() => {})
      void refreshSynapse()
    }
    sync()
    const id = setInterval(sync, 2000)
    return () => { cancelled = true; clearInterval(id) }
  }, [refreshSynapse])

  useEffect(() => {
    let cancelled = false
    const sync = async () => {
      if (cancelled) return
      await refreshTerminalApprovals()
      await refreshSynapse()
    }
    void sync()
    const id = setInterval(sync, 2000)
    return () => { cancelled = true; clearInterval(id) }
  }, [refreshTerminalApprovals, refreshSynapse])

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth < 900) {
        setShowSessions(false)
        setShowInspector(false)
        setLayoutCols(1)
      }
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const handleSpawn = useCallback(async (payload: SpawnPayload) => {
    try {
      const info = await terminalApi.spawn(payload)
      setTerminals(prev => [...prev, info])
    } catch (e) {
      console.error('Failed to spawn terminal', e)
    }
  }, [])

  const handleKill = useCallback(async (id: string) => {
    try { await terminalApi.kill(id) } catch { /* ignore */ }
    terminalRefs.current.delete(id)
    setTerminals(prev => prev.filter(t => t.id !== id))
  }, [])

  const handleExit = useCallback((id: string, code: number) => {
    setTerminals(prev => prev.map(t => t.id === id ? { ...t, alive: false, exit_code: code } : t))
    console.info(`[CC] Terminal ${id.slice(0, 8)} exited with code ${code}`)
  }, [])

  const handleInject = useCallback((terminalId: string, text: string, pressEnter: boolean) => {
    terminalRefs.current.get(terminalId)?.inject(text, pressEnter)
  }, [])

  const handleApproveTerminalPrompt = useCallback(async (id: string) => {
    await terminalApi.approvePrompt(id)
    await refreshTerminalApprovals()
  }, [refreshTerminalApprovals])

  const handleRejectTerminalPrompt = useCallback(async (id: string) => {
    await terminalApi.rejectPrompt(id)
    await refreshTerminalApprovals()
  }, [refreshTerminalApprovals])

  const handleTogglePromptApprovals = useCallback(async () => {
    const next = !promptApprovalRequired
    const settings = await terminalApi.setApprovalSettings(next)
    setPromptApprovalRequired(settings.prompt_approval_required)
    await refreshTerminalApprovals()
  }, [promptApprovalRequired, refreshTerminalApprovals])


  const aliveCount = terminals.filter(t => t.alive).length
  const cols = terminals.length === 0 ? 1 : Math.min(layoutCols, terminals.length)
  const pendingApprovalCount = terminalApprovals.filter(a => a.status === 'pending').length
  const panelAgents: PanelAgentEntry[] = terminals.map(t => ({
    id: t.id,
    name: t.label || t.agent_type || t.id.slice(0, 8),
    kind: t.agent_type || 'pty',
    status: t.alive ? 'running' : `exit ${t.exit_code ?? ''}`.trim(),
    detail: t.cwd,
    tone: t.alive ? 'green' : 'amber',
    onStop: t.alive ? () => handleKill(t.id) : undefined,
  }))

  return (
    <ToolShell
      profile={commandCenterToolArea}
      state={terminals}
      className="workspace-theme"
      style={{
        display: 'flex', flexDirection: 'column', height: '100vh',
        background: '#060400', color: '#e6edf3', overflow: 'hidden',
      }}
    >
      <style>{`
        @keyframes cc-dot-pulse{0%,100%{opacity:1}50%{opacity:.45}}
        .cc-tool-toggle{
          display:flex;align-items:center;gap:6px;height:28px;padding:0 9px;border-radius:6px;
          border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.025);
          color:#8b949e;font:600 0.64rem ui-monospace,SFMono-Regular,Menlo,monospace;
          text-transform:uppercase;letter-spacing:.06em;cursor:pointer;
        }
        .cc-tool-toggle[data-active='true']{color:#ffc45a;background:rgba(255,196,90,0.1);border-color:rgba(255,196,90,0.22)}
        @media (max-width: 1180px){
          .cc-toggle-label{display:none}
          .cc-hermes-pane{width:min(330px,38vw)!important}
        }
        @media (max-width: 900px){
          .cc-body{position:relative}
          .cc-hermes-pane{width:min(360px,46vw)!important}
          .cc-sessions-pane,.cc-inspector-pane{
            position:absolute;top:0;bottom:0;z-index:35;background:#050505;
            box-shadow:0 18px 45px rgba(0,0,0,.55);
          }
          .cc-sessions-pane{left:0;width:min(82vw,260px)!important}
          .cc-inspector-pane{right:0;width:min(86vw,340px)!important}
        }
        @media (max-width: 680px){
          .cc-hermes-pane{display:none!important}
          .cc-topbar{padding:0 8px!important;gap:6px!important}
        }
      `}</style>
      {/* Top bar */}
      <div className="cc-topbar" style={{
        height: 48, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 16px', background: 'rgba(8,6,0,0.98)',
        borderBottom: '1px solid rgba(255,196,90,0.15)',
      }}>
        <Terminal size={14} style={{ color: '#ffc45a' }} />
        <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#ffc45a' }}>
          Command Center
        </span>
        {aliveCount > 0 && (
          <span style={{
            padding: '2px 8px', borderRadius: 99, fontSize: '0.65rem', fontFamily: 'monospace',
            background: 'rgba(74,222,128,0.12)', border: '1px solid rgba(74,222,128,0.3)', color: '#4ade80',
          }}>
            {aliveCount} running
          </span>
        )}
        <div style={{ display: 'flex', gap: 6, marginLeft: 6 }}>
          <button
            type="button"
            onClick={() => setShowSessions(v => !v)}
            className="cc-tool-toggle"
            data-active={showSessions ? 'true' : 'false'}
            title={showSessions ? 'Ocultar sesiones' : 'Mostrar sesiones'}
          >
            <PanelLeft size={13} />
            <span className="cc-toggle-label">Sesiones</span>
          </button>
          <button
            type="button"
            onClick={() => setShowInspector(v => !v)}
            className="cc-tool-toggle"
            data-active={showInspector ? 'true' : 'false'}
            title={showInspector ? 'Ocultar trace, skills y agentes' : 'Mostrar trace, skills y agentes'}
          >
            <PanelRight size={13} />
            <span className="cc-toggle-label">Panel</span>
          </button>
        </div>
        <div style={{ display: 'flex', gap: 3, marginLeft: 8 }}>
          {([1,2,3] as const).map(n => (
            <button
              key={n}
              type="button"
              onClick={() => setLayoutCols(n)}
              title={`${n} column${n>1?'s':''}`}
              style={{
                width: 28, height: 28, borderRadius: 4, border: 'none', cursor: 'pointer',
                background: layoutCols === n ? 'rgba(255,196,90,0.15)' : 'transparent',
                color: layoutCols === n ? '#ffc45a' : '#6b7280',
                fontFamily: 'monospace', fontSize: '0.65rem', letterSpacing: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {'▮'.repeat(n)}
            </button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={handleTogglePromptApprovals}
          className="cc-tool-toggle"
          data-active={promptApprovalRequired ? 'true' : 'false'}
          title={promptApprovalRequired ? 'Prompts de Hermes requieren aprobación' : 'Prompts de Hermes se inyectan sin aprobación'}
          style={{
            borderColor: pendingApprovalCount > 0 ? 'rgba(252,165,165,0.45)' : undefined,
            color: pendingApprovalCount > 0 ? '#fca5a5' : undefined,
          }}
        >
          {promptApprovalRequired ? <ShieldCheck size={13} /> : <ShieldOff size={13} />}
          <span className="cc-toggle-label">Aprobación</span>
          {pendingApprovalCount > 0 && (
            <span style={{
              minWidth: 16, height: 16, borderRadius: 99, padding: '0 5px',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(252,165,165,0.16)', color: '#fca5a5',
              fontSize: '0.58rem',
            }}>
              {pendingApprovalCount}
            </span>
          )}
        </button>
        <CCAgentControls />
        <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.08)', margin: '0 4px' }} />
        <button
          type="button"
          onClick={() => setShowSpawn(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 600,
            background: '#ffc45a', border: 'none', color: '#000', cursor: 'pointer',
          }}
        >
          <Plus size={13} />
          Spawn Agent
        </button>
      </div>

      {/* Body */}
      <div className="cc-body" style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {showSessions && (
          <div className="cc-sessions-pane" style={{ width: 218, flexShrink: 0, minHeight: 0 }}>
            <SessionsRail
              profile={{
                title: 'sesiones cc',
                searchPlaceholder: 'Buscar sesion CC...',
                emptyLabel: 'sin sesiones de command center',
                newSessionTitle: 'Nueva sesion Command Center',
                refreshTitle: 'Recargar sesiones CC',
              }}
            />
          </div>
        )}

        {/* Hermes panel — resizable left */}
        <div className="cc-hermes-pane" style={{
          width: hermesWidth, flexShrink: 0, display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '8px 12px 0',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
          }}>
            <span style={{ fontFamily: 'monospace', fontSize: '0.58rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#ffc45a', opacity: 0.7 }}>
              Hermes
            </span>
          </div>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <ChatStream
              onOpenDiff={setDiffEdit}
              onOpenCommands={() => {}}
              onOpenTool={setToolDetail}
            />
          </div>
        </div>

        {/* Drag handle */}
        <div
          onMouseDown={onDragHandleMouseDown}
          onMouseEnter={() => setDragHover(true)}
          onMouseLeave={() => setDragHover(false)}
          style={{
            width: 5, flexShrink: 0, cursor: 'col-resize', zIndex: 10,
            background: dragHover ? 'rgba(255,196,90,0.25)' : 'transparent',
            borderRight: '1px solid rgba(255,255,255,0.07)',
            transition: 'background 0.15s',
          }}
        />

        {/* Terminal grid + inject bar */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          <WorkspaceSynapsePanel synapse={synapse} terminals={terminals} />
          <TerminalApprovalQueue
            approvals={terminalApprovals}
            onApprove={handleApproveTerminalPrompt}
            onReject={handleRejectTerminalPrompt}
          />
          {terminals.length === 0 ? (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 12,
            }}>
              <Terminal size={40} style={{ color: '#6b7280', opacity: 0.3 }} />
              <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', opacity: 0.5 }}>
                No terminals — click "Spawn Agent"
              </span>
            </div>
          ) : (
            <div style={{
              flex: 1,
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, 1fr)`,
              gridAutoRows: terminals.length <= 2 ? '1fr' : 'calc(50vh - 48px)',
              gap: 8, padding: 8,
              overflow: 'auto',
            }}>
              {terminals.map(t => (
                <TerminalPanel
                  key={t.id}
                  info={t}
                  onKill={handleKill}
                  onExit={handleExit}
                  ref={el => {
                    if (el) terminalRefs.current.set(t.id, el)
                    else terminalRefs.current.delete(t.id)
                  }}
                />
              ))}
            </div>
          )}
          <InjectBar terminals={terminals} onInject={handleInject} />
        </div>

        {showInspector && (
          <div className="cc-inspector-pane" style={{ width: 310, flexShrink: 0, minHeight: 0, borderLeft: '1px solid rgba(255,255,255,0.07)' }}>
            <SidePanels
              onOpenDiff={setDiffEdit}
              onOpenApproval={() => { /* approval is auto-shown below */ }}
              externalAgents={panelAgents}
              profile={{
                tabs: ['trace', 'agents', 'skills'],
                defaultTab: 'agents',
                labels: {
                  trace: 'Trace',
                  agents: 'PTY',
                  skills: 'Skills',
                },
                emptyLabels: {
                  trace: 'sin eventos del Command Center',
                  agents: 'sin agentes PTY activos',
                  skills: 'sin skills disponibles',
                },
              }}
            />
          </div>
        )}
      </div>

      {showSpawn && (
        <SpawnAgentModal onSpawn={handleSpawn} onClose={() => setShowSpawn(false)} />
      )}
      <CommandCenterOverlays
        diffEdit={diffEdit}
        setDiffEdit={setDiffEdit}
        toolDetail={toolDetail}
        setToolDetail={setToolDetail}
      />
    </ToolShell>
  )
}

function WorkspaceSynapsePanel({
  synapse,
  terminals,
}: {
  synapse: WorkspaceSynapse | null
  terminals: TerminalInfo[]
}) {
  if (!synapse) return null
  const recentAgentEvents = synapse.recent_events
    .filter(e => e.event_type.startsWith('agent_'))
    .slice(0, 4)
  const activeWithSynapse = terminals.filter(t => t.alive && (t.synapse || synapse.terminal_synapse[t.id]))
  const absorbPrompt = () => {
    const eventLines = recentAgentEvents.length
      ? recentAgentEvents.map(e => `- ${e.event_type}: ${e.summary || e.agent_id || e.terminal_id || 'evento'} (${e.created_at})`).join('\n')
      : '- Sin eventos agenticos recientes.'
    const terminalLines = activeWithSynapse.length
      ? activeWithSynapse.slice(0, 8).map(t => {
          const state = t.synapse || synapse.terminal_synapse[t.id] || {}
          return `- ${t.id} ${t.label || t.agent_type}: ${state.last_plan?.title || state.last_log?.summary || 'ccw listo'}`
        }).join('\n')
      : '- Sin terminales publicando en la sinapsis.'
    window.dispatchEvent(new CustomEvent('cc:hermes-draft', {
      detail: {
        text: [
          'Absorbe la Workspace Synapse de Command Center y documenta el cierre operativo.',
          '',
          `Workspace activo: ${synapse.active_workspace || '—'}`,
          `Workspaces legibles: ${synapse.readable_workspaces.join(', ') || '—'}`,
          '',
          'Eventos recientes:',
          eventLines,
          '',
          'Terminales:',
          terminalLines,
          '',
          'Actualiza la documentación/memoria del workspace con lo integrado, riesgos pendientes y próximos pasos. No borres eventos append-only.',
        ].join('\n'),
      },
    }))
  }

  return (
    <div style={{
      flexShrink: 0,
      display: 'grid',
      gridTemplateColumns: 'minmax(220px, 0.9fr) minmax(260px, 1.2fr) minmax(220px, 1fr)',
      gap: 8,
      padding: '8px 10px',
      borderBottom: '1px solid rgba(255,196,90,0.12)',
      background: 'rgba(12,9,0,0.48)',
    }}>
      <div style={{
        border: '1px solid rgba(255,196,90,0.16)', borderRadius: 8, padding: 9,
        minWidth: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
          <Database size={13} style={{ color: '#ffc45a' }} />
          <span style={{ fontFamily: 'monospace', fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#ffc45a' }}>
            Workspace Synapse
          </span>
          <button
            type="button"
            onClick={absorbPrompt}
            title="Preparar cierre para Hermes"
            style={{
              marginLeft: 'auto',
              width: 24,
              height: 22,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              border: '1px solid rgba(255,196,90,0.24)',
              background: 'rgba(255,196,90,0.08)',
              color: '#ffc45a',
              cursor: 'pointer',
            }}
          >
            <FileText size={12} />
          </button>
        </div>
        <div style={{ fontFamily: 'monospace', fontSize: '0.68rem', color: '#e6edf3', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          activo: {synapse.active_workspace || '—'}
        </div>
        <div style={{ fontSize: '0.62rem', color: '#8b949e', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          lee: {synapse.readable_workspaces.join(', ') || '—'}
        </div>
        {!synapse.sandbox_available && (
          <div style={{ fontSize: '0.62rem', color: '#fca5a5', marginTop: 4 }}>
            bwrap no disponible: protección degradada
          </div>
        )}
      </div>

      <div style={{
        border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: 9,
        minWidth: 0,
      }}>
        <div style={{ fontFamily: 'monospace', fontSize: '0.58rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e', marginBottom: 6 }}>
          actividad agentica
        </div>
        {recentAgentEvents.length === 0 ? (
          <div style={{ fontSize: '0.68rem', color: '#6b7280' }}>sin planes/logs recientes</div>
        ) : recentAgentEvents.map(event => (
          <div key={event.id} style={{
            display: 'flex', gap: 6, alignItems: 'baseline',
            fontSize: '0.66rem', color: '#c9d1d9', overflow: 'hidden',
          }}>
            <span style={{ color: '#ffc45a', fontFamily: 'monospace', flexShrink: 0 }}>{event.event_type}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {event.summary || event.agent_id || event.terminal_id || 'evento'}
            </span>
          </div>
        ))}
      </div>

      <div style={{
        border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: 9,
        minWidth: 0,
      }}>
        <div style={{ fontFamily: 'monospace', fontSize: '0.58rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e', marginBottom: 6 }}>
          terminales enlazadas
        </div>
        {activeWithSynapse.length === 0 ? (
          <div style={{ fontSize: '0.68rem', color: '#6b7280' }}>sin agentes publicando</div>
        ) : activeWithSynapse.slice(0, 4).map(t => {
          const state = t.synapse || synapse.terminal_synapse[t.id] || {}
          return (
            <div key={t.id} style={{ fontSize: '0.66rem', color: '#c9d1d9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: state.sandboxed ? '#4ade80' : '#fbbf24', fontFamily: 'monospace' }}>
                {t.id}
              </span>
              {' · '}
              {state.last_plan?.title || state.last_log?.summary || 'ccw listo'}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TerminalApprovalQueue({
  approvals,
  onApprove,
  onReject,
}: {
  approvals: TerminalApproval[]
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const pending = approvals.filter(a => a.status === 'pending')
  if (pending.length === 0) return null

  return (
    <div style={{
      flexShrink: 0, display: 'flex', gap: 8, overflowX: 'auto',
      padding: '8px 10px',
      borderBottom: '1px solid rgba(252,165,165,0.14)',
      background: 'rgba(40,10,10,0.28)',
    }}>
      {pending.map(item => (
        <div
          key={item.id}
          style={{
            minWidth: 320, maxWidth: 520, flex: '0 0 auto',
            border: '1px solid rgba(252,165,165,0.28)',
            borderRadius: 8,
            background: 'rgba(10,6,4,0.92)',
            padding: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
            <ShieldCheck size={13} style={{ color: '#fca5a5', flexShrink: 0 }} />
            <span style={{
              fontFamily: 'monospace', fontSize: '0.62rem', textTransform: 'uppercase',
              letterSpacing: '0.08em', color: '#fca5a5', flex: 1,
            }}>
              Prompt pendiente · {item.terminal_label || item.agent_type}
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: '0.55rem', color: '#6b7280' }}>
              {item.terminal_id}
            </span>
          </div>
          <pre style={{
            margin: 0, maxHeight: 86, overflow: 'auto',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            fontFamily: 'ui-monospace,SFMono-Regular,Menlo,monospace',
            fontSize: '0.68rem', lineHeight: 1.45, color: '#e6edf3',
          }}>
            {item.text}
          </pre>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginTop: 9 }}>
            <button
              type="button"
              onClick={() => onReject(item.id)}
              title="Rechazar prompt"
              style={{
                width: 28, height: 28, borderRadius: 6, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1px solid rgba(252,165,165,0.25)', background: 'transparent', color: '#fca5a5',
              }}
            >
              <X size={13} />
            </button>
            <button
              type="button"
              onClick={() => onApprove(item.id)}
              title="Aprobar e inyectar"
              style={{
                width: 28, height: 28, borderRadius: 6, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: 'none', background: '#4ade80', color: '#031307',
              }}
            >
              <Check size={14} />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function CommandCenterOverlays({
  diffEdit,
  setDiffEdit,
  toolDetail,
  setToolDetail,
}: {
  diffEdit: FileEdit | null
  setDiffEdit: (edit: FileEdit | null) => void
  toolDetail: ToolCall | null
  setToolDetail: (tool: ToolCall | null) => void
}) {
  const { pendingPrompt } = useAgent()

  return (
    <>
      {pendingPrompt?.kind === 'approval' && <ApprovalDialog />}
      {pendingPrompt && pendingPrompt.kind !== 'approval' && <PromptDialog />}
      <DiffModal edit={diffEdit} onClose={() => setDiffEdit(null)} />
      <ToolDetailModal tc={toolDetail} onClose={() => setToolDetail(null)} />
    </>
  )
}
