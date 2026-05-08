import { useState } from 'react'
import { SendHorizonal } from 'lucide-react'
import type { TerminalInfo } from '../../lib/terminalApi'

interface Props {
  terminals: TerminalInfo[]
  onInject: (terminalId: string, text: string, pressEnter: boolean) => void
}

export function InjectBar({ terminals, onInject }: Props) {
  const [targetId, setTargetId] = useState('')
  const [text, setText] = useState('')
  const [pressEnter, setPressEnter] = useState(true)

  const alive = terminals.filter(t => t.alive)
  if (alive.length === 0) return null

  const effectiveTarget = targetId || (alive[0]?.id ?? '')

  function doInject() {
    if (!text.trim()) return
    if (effectiveTarget === '__broadcast__') {
      alive.forEach(t => onInject(t.id, text, pressEnter))
    } else {
      if (!effectiveTarget) return
      onInject(effectiveTarget, text, pressEnter)
    }
    setText('')
  }

  const inputBase: React.CSSProperties = {
    background: '#1a1500', border: '1px solid rgba(255,255,255,0.1)',
    color: '#e6edf3', outline: 'none', borderRadius: 6,
  }

  return (
    <div style={{
      height: 48, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8,
      padding: '0 12px', borderTop: '1px solid rgba(255,255,255,0.06)',
      background: 'rgba(0,0,0,0.25)',
    }}>
      <select
        value={effectiveTarget}
        onChange={e => setTargetId(e.target.value)}
        style={{ ...inputBase, fontFamily: 'monospace', fontSize: '0.68rem', padding: '4px 8px', height: 30 }}
      >
        {alive.map(t => (
          <option key={t.id} value={t.id}>
            {(t.label && t.label !== t.agent_type ? t.label + ' · ' : '') + t.agent_type + ' · ' + t.id.slice(0, 8)}
          </option>
        ))}
        <option value="__broadcast__">→ ALL terminals</option>
      </select>

      <input
        type="text"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') doInject() }}
        placeholder="Inject text into terminal…"
        style={{ ...inputBase, flex: 1, fontSize: '0.8rem', padding: '4px 10px', height: 30 }}
      />

      <button
        type="button"
        onClick={() => setPressEnter(b => !b)}
        title="Append Enter key"
        style={{
          width: 30, height: 30, borderRadius: 6, cursor: 'pointer',
          fontFamily: 'monospace', fontSize: '0.85rem',
          background: pressEnter ? 'rgba(255,196,90,0.15)' : 'transparent',
          border: pressEnter ? '1px solid rgba(255,196,90,0.4)' : '1px solid rgba(255,255,255,0.1)',
          color: pressEnter ? '#ffc45a' : '#6b7280',
        }}
      >
        ↵
      </button>

      <button
        type="button"
        onClick={doInject}
        disabled={!text.trim()}
        style={{
          width: 30, height: 30, borderRadius: 6, border: 'none', cursor: text.trim() ? 'pointer' : 'not-allowed',
          background: '#ffc45a', color: '#000',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: text.trim() ? 1 : 0.4,
        }}
      >
        <SendHorizonal size={13} />
      </button>
    </div>
  )
}
