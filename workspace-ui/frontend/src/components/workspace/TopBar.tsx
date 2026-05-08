/* ────────────────────────────────────────────────────────────────────────────
   TOP BAR
   Connection status · model selector · modes toggles (Plan/Auto/Ask) ·
   reasoning effort · context meter · settings entry-point.
   Width: full. Height: 52px.
──────────────────────────────────────────────────────────────────────────── */
import { useState } from 'react'
import { Activity, BrainCircuit, ChevronDown, Cpu, Settings2, Square } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'
import { api } from '../../lib/api'

const REASONING_LEVELS = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const

interface Props {
  onOpenSettings: () => void
}

export function TopBar({ onOpenSettings }: Props) {
  const { connection, sessionId, modes, models, config, usage, streaming,
          interrupt, switchModel, setEffort, refreshModes } = useAgent()
  const [modelOpen, setModelOpen] = useState(false)
  const [reasoningOpen, setReasoningOpen] = useState(false)

  const connColor =
    connection === 'online' ? 'var(--ws-success)' :
    connection === 'connecting' ? 'var(--ws-warning)' : 'var(--ws-danger)'

  const currentModel = config?.model || models?.current || '—'
  const ctxUsed = typeof usage?.context_used === 'number' ? usage.context_used as number : 0
  const ctxMax = typeof usage?.context_max === 'number' ? usage.context_max as number : 0
  const ctxPct = typeof usage?.context_percent === 'number'
    ? usage.context_percent as number
    : (ctxMax > 0 ? Math.round((ctxUsed / ctxMax) * 100) : 0)
  const fmtK = (n: number) => n >= 1000 ? `${(n/1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n)

  async function pickModel(model: string) {
    setModelOpen(false)
    await switchModel(model)
  }

  async function pickReasoning(effort: string) {
    setReasoningOpen(false)
    await setEffort(effort)
  }

  return (
    <div
      className="flex items-center gap-3 px-4 flex-shrink-0"
      style={{
        height: 48,
        background: 'rgba(8,6,0,0.98)',
        borderBottom: '1px solid rgba(255,196,90,0.15)',
      }}
    >
      {/* Status */}
      <div className="flex items-center gap-2">
        <span
          className={connection === 'connecting' ? 'ws-pulse' : ''}
          style={{ width: 6, height: 6, borderRadius: '50%', background: connColor, boxShadow: `0 0 6px ${connColor}` }}
        />
        <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
          {connection}
        </span>
        {sessionId && (
          <span className="mono text-[0.58rem]" style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
            · {sessionId.slice(0, 12)}…
          </span>
        )}
      </div>

      <div style={{ width: 1, height: 18, background: 'var(--ws-border)' }} />

      {/* Model selector — grouped by provider, with search */}
      <div className="relative">
        <button
          type="button"
          onClick={() => { setModelOpen(o => !o); setReasoningOpen(false) }}
          className="ws-pill flex items-center"
          data-active="true"
        >
          <Cpu size={11} />
          <span className="truncate" style={{ maxWidth: 180 }}>{currentModel}</span>
          <ChevronDown size={11} />
        </button>
        {modelOpen && (
          <div
            className="ws-card absolute left-0 top-full mt-1 z-30"
            style={{ minWidth: 320, maxHeight: 420, overflowY: 'auto', padding: 6 }}
          >
            {(() => {
              const opts = models?.options ?? []
              const grouped: Record<string, typeof opts> = {}
              for (const opt of opts) {
                const p = opt.provider || 'other'
                if (!grouped[p]) grouped[p] = []
                grouped[p].push(opt)
              }
              const providers = Object.keys(grouped).sort()
              return providers.map(prov => (
                <div key={prov} style={{ marginBottom: 6 }}>
                  <div className="mono text-[0.55rem] uppercase tracking-widest px-2 py-1" style={{ color: 'var(--ws-accent)', opacity: 0.75 }}>
                    {prov}
                  </div>
                  {grouped[prov].map((opt, i) => (
                    <button
                      key={`${prov}-${opt.id}-${i}`}
                      type="button"
                      onClick={() => pickModel(opt.id)}
                      className="block w-full px-3 py-1 text-left text-xs rounded transition-colors"
                      style={{
                        background: opt.id === currentModel ? 'rgba(255,196,90,0.1)' : 'transparent',
                        color: opt.id === currentModel ? 'var(--ws-accent)' : 'var(--ws-text)',
                      }}
                    >
                      <span className="mono">{opt.name || opt.id}</span>
                    </button>
                  ))}
                </div>
              ))
            })()}
            {!models?.options?.length && (
              <div className="px-3 py-2 text-[0.7rem]" style={{ color: 'var(--ws-text-muted)' }}>
                Sin modelos cargados
              </div>
            )}
          </div>
        )}
      </div>

      {/* Reasoning */}
      <div className="relative">
        <button
          type="button"
          onClick={() => { setReasoningOpen(o => !o); setModelOpen(false) }}
          className="ws-pill"
          data-active={modes?.reasoning_effort && modes.reasoning_effort !== 'none' ? 'true' : 'false'}
        >
          <BrainCircuit size={11} />
          {modes?.reasoning_effort ?? 'medium'}
          <ChevronDown size={11} />
        </button>
        {reasoningOpen && (
          <div className="ws-card absolute left-0 top-full mt-1 z-30" style={{ minWidth: 140, padding: 4 }}>
            {REASONING_LEVELS.map(level => (
              <button
                key={level}
                type="button"
                onClick={() => pickReasoning(level)}
                className="block w-full px-3 py-1 text-left text-xs rounded"
                style={{
                  background: modes?.reasoning_effort === level ? 'rgba(196,181,253,0.12)' : 'transparent',
                  color: modes?.reasoning_effort === level ? 'var(--ws-violet)' : 'var(--ws-text)',
                }}
              >
                {level}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ width: 1, height: 18, background: 'var(--ws-border)' }} />

      {/* Yolo mode */}
      <ModeChip label="Yolo" on={!!modes?.yolo} onClick={() => { void api.setModes({ yolo: !modes?.yolo }).then(() => refreshModes()) }} danger />

      <div className="flex-1" />

      {/* Context meter — used / max with % */}
      <div className="flex items-center gap-2" title={ctxMax > 0 ? `${ctxUsed.toLocaleString()} / ${ctxMax.toLocaleString()} tokens` : 'sin datos de uso'}>
        <Activity size={11} style={{ color: 'var(--ws-accent)' }} />
        <span className="mono text-[0.6rem]" style={{ color: 'var(--ws-text-muted)' }}>
          ctx
        </span>
        <div style={{ width: 90, height: 5, borderRadius: 3, background: 'var(--ws-border)', overflow: 'hidden', position: 'relative' }}>
          <div style={{
            width: `${Math.min(100, ctxPct)}%`,
            height: '100%',
            background: ctxPct > 85 ? 'var(--ws-danger)' : ctxPct > 65 ? 'var(--ws-warning)' : 'var(--ws-accent)',
            boxShadow: `0 0 6px ${ctxPct > 85 ? 'var(--ws-danger)' : ctxPct > 65 ? 'var(--ws-warning)' : 'var(--ws-accent-glow)'}`,
            transition: 'width 0.3s ease, background 0.3s ease',
          }} />
        </div>
        <span className="mono text-[0.62rem]" style={{
          color: ctxPct > 85 ? 'var(--ws-danger)' : ctxPct > 65 ? 'var(--ws-warning)' : 'var(--ws-accent)',
          minWidth: 32, textAlign: 'right',
        }}>
          {ctxPct}%
        </span>
        {ctxMax > 0 && (
          <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)', opacity: 0.7 }}>
            {fmtK(ctxUsed)}/{fmtK(ctxMax)}
          </span>
        )}
      </div>

      {/* Stop */}
      {streaming && (
        <button
          type="button"
          onClick={interrupt}
          className="ws-pill"
          title="Interrumpir agente"
          style={{ color: 'var(--ws-danger)', borderColor: 'rgba(252,165,165,0.35)' }}
        >
          <Square size={11} fill="currentColor" />
        </button>
      )}

      {/* Settings */}
      <button
        type="button"
        onClick={onOpenSettings}
        className="ws-pill"
        title="Personalizar workspace"
      >
        <Settings2 size={11} />
      </button>
    </div>
  )
}

function ModeChip({ label, on, onClick, danger }: { label: string; on: boolean; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick} className="flex items-center gap-1.5">
      <span
        className="ws-toggle"
        data-on={on ? 'true' : 'false'}
        style={danger && on ? { background: 'rgba(252,165,165,0.4)', borderColor: 'rgba(252,165,165,0.6)', boxShadow: '0 0 8px rgba(252,165,165,0.4)' } : undefined}
      />
      <span
        className="text-[0.66rem]"
        style={{ color: on ? (danger ? 'var(--ws-danger)' : 'var(--ws-accent)') : 'var(--ws-text-muted)' }}
      >
        {label}
      </span>
    </button>
  )
}
