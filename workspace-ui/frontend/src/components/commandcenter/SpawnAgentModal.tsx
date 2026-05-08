import { useState } from 'react'
import { ShieldCheck, ShieldOff, Terminal, X } from 'lucide-react'
import type { SpawnPayload } from '../../lib/terminalApi'

const ROLE_GROUPS = [
  {
    role: 'frontier',
    label: 'Frontier',
    color: '#60a5fa',
    agents: [
      { value: 'claude-code-planner', label: 'Claude Code',     desc: 'cc1 · claude · cuenta Jorge, tech lead, QA del output' },
      { value: 'claude-code-cc2',     label: 'Claude Code cc2', desc: 'cc2 · claude · cuenta Maribel, mismas capacidades' },
      { value: 'codex-worker',        label: 'Codex',           desc: 'codex · OpenAI, requiere o auto-crea repo Git' },
    ],
  },
  {
    role: 'economy',
    label: 'Economy',
    color: '#a78bfa',
    agents: [
      { value: 'opencode-worker', label: 'OpenCode',  desc: 'opencode  · MiniMax u otro modelo barato, bulk code' },
      { value: 'bash',            label: 'Raw Bash',  desc: 'bash -l  · shell interactivo, control total' },
    ],
  },
] as const

type AgentValue = (typeof ROLE_GROUPS)[number]['agents'][number]['value']

const QUICK_TEMPLATES: { label: string; agent: AgentValue; color: string }[] = [
  { label: 'cc1',     agent: 'claude-code-planner', color: '#60a5fa' },
  { label: 'cc2',     agent: 'claude-code-cc2',     color: '#34d399' },
  { label: 'Codex',   agent: 'codex-worker',        color: '#60a5fa' },
  { label: 'Economy', agent: 'opencode-worker',     color: '#a78bfa' },
  { label: 'Bash',    agent: 'bash',                color: '#9ca3af' },
]

interface Props {
  onSpawn: (payload: SpawnPayload) => void
  onClose: () => void
}

export function SpawnAgentModal({ onSpawn, onClose }: Props) {
  const [agentType, setAgentType] = useState<AgentValue>('claude-code-planner')
  const [cwd, setCwd] = useState('')
  const [label, setLabel] = useState('')
  const [prompt, setPrompt] = useState('')
  const [permissionMode, setPermissionMode] = useState<'default' | 'bypass'>('default')

  function handleSubmit() {
    onSpawn({
      agent_type: agentType,
      cwd: cwd.trim() || undefined,
      label: label.trim() || undefined,
      prompt: prompt.trim() || undefined,
      permission_mode: permissionMode,
    })
    onClose()
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%', fontSize: '0.75rem', padding: '7px 10px', borderRadius: 6,
    background: '#1a1500', border: '1px solid rgba(255,255,255,0.1)',
    color: '#e6edf3', outline: 'none', boxSizing: 'border-box',
    fontFamily: 'inherit',
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 480, padding: 20, borderRadius: 12,
          background: '#0d0b00', border: '1px solid rgba(255,196,90,0.2)',
          boxShadow: '0 24px 48px rgba(0,0,0,0.6)',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
          {QUICK_TEMPLATES.map(t => (
            <button
              key={t.agent}
              type="button"
              onClick={() => setAgentType(t.agent)}
              style={{
                padding: '4px 12px', borderRadius: 99, cursor: 'pointer',
                fontSize: '0.65rem', fontFamily: 'monospace',
                border: `1px solid ${t.color}55`,
                background: agentType === t.agent ? `${t.color}20` : 'transparent',
                color: agentType === t.agent ? t.color : '#6b7280',
                transition: 'all 0.1s',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <Terminal size={16} style={{ color: '#ffc45a', flexShrink: 0 }} />
          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#e6edf3', flex: 1 }}>
            Spawn Agent Terminal
          </span>
          <button type="button" onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', padding: 2 }}>
            <X size={14} />
          </button>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 8 }}>
            Agent type
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {ROLE_GROUPS.map(group => (
              <div key={group.role}>
                <div style={{
                  fontFamily: 'monospace', fontSize: '0.55rem', textTransform: 'uppercase',
                  letterSpacing: '0.1em', color: group.color, marginBottom: 5, opacity: 0.85,
                }}>
                  {group.label}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {group.agents.map(opt => {
                    const selected = agentType === opt.value
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setAgentType(opt.value)}
                        style={{
                          display: 'flex', flexDirection: 'column', gap: 2,
                          padding: '8px 12px', borderRadius: 6, cursor: 'pointer', textAlign: 'left',
                          border: selected
                            ? `1px solid ${group.color}55`
                            : '1px solid rgba(255,255,255,0.06)',
                          background: selected ? `${group.color}12` : 'transparent',
                        }}
                      >
                        <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: selected ? group.color : '#e6edf3' }}>
                          {opt.label}
                        </span>
                        <span style={{ fontSize: '0.64rem', color: '#6b7280' }}>{opt.desc}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 6 }}>
            Working directory (optional)
          </label>
          <input
            type="text" value={cwd} onChange={e => setCwd(e.target.value)}
            placeholder="~" style={{ ...fieldStyle, fontFamily: 'monospace' }}
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 6 }}>
            Agent permission mode
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <button
              type="button"
              onClick={() => setPermissionMode('default')}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                borderRadius: 6, cursor: 'pointer', textAlign: 'left',
                border: permissionMode === 'default' ? '1px solid rgba(74,222,128,0.45)' : '1px solid rgba(255,255,255,0.08)',
                background: permissionMode === 'default' ? 'rgba(74,222,128,0.10)' : 'transparent',
                color: permissionMode === 'default' ? '#4ade80' : '#9ca3af',
                fontSize: '0.7rem',
              }}
            >
              <ShieldCheck size={14} />
              Default
            </button>
            <button
              type="button"
              onClick={() => setPermissionMode('bypass')}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                borderRadius: 6, cursor: 'pointer', textAlign: 'left',
                border: permissionMode === 'bypass' ? '1px solid rgba(252,165,165,0.45)' : '1px solid rgba(255,255,255,0.08)',
                background: permissionMode === 'bypass' ? 'rgba(252,165,165,0.10)' : 'transparent',
                color: permissionMode === 'bypass' ? '#fca5a5' : '#9ca3af',
                fontSize: '0.7rem',
              }}
            >
              <ShieldOff size={14} />
              Bypass CLI
            </button>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 6 }}>
            Label (opcional)
          </label>
          <input
            type="text" value={label} onChange={e => setLabel(e.target.value)}
            placeholder="Nombre identificador, ej: auth-module, frontend-fix…"
            style={{ ...fieldStyle, fontFamily: 'monospace' }}
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'block', fontFamily: 'monospace', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: 6 }}>
            Initial prompt (optional)
          </label>
          <textarea
            value={prompt} onChange={e => setPrompt(e.target.value)}
            rows={3} placeholder="Comando o mensaje inicial a inyectar…"
            style={{ ...fieldStyle, resize: 'vertical' }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" onClick={onClose} style={{
            padding: '8px 16px', borderRadius: 6, fontSize: '0.8rem', cursor: 'pointer',
            background: 'transparent', border: '1px solid rgba(255,255,255,0.12)', color: '#9ca3af',
          }}>
            Cancel
          </button>
          <button type="button" onClick={handleSubmit} style={{
            padding: '8px 20px', borderRadius: 6, fontSize: '0.8rem', cursor: 'pointer',
            background: '#ffc45a', border: 'none', color: '#000', fontWeight: 600,
          }}>
            Spawn
          </button>
        </div>
      </div>
    </div>
  )
}
