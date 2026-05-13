/* ────────────────────────────────────────────────────────────────────────────
   CHAT STREAM (center)
   Conversation, prompt input, slash commands, interrupt, "view diff" buttons
   shown inline whenever the agent edits a file.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ChevronDown, ChevronRight, CircleStop, FileDiff, Send, Slash } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'
import type { ChatMessage } from '../../lib/agentRuntime'
import type { FileEdit } from '../../lib/api'
import type { ToolCall } from '../../lib/agentRuntime'
import { CTX_SENTINEL } from '../common/ToolContextInjector'

interface Props {
  onOpenDiff: (edit: FileEdit) => void
  onOpenCommands: () => void
  onOpenTool: (tc: ToolCall) => void
}

export function ChatStream({ onOpenDiff, onOpenCommands, onOpenTool }: Props) {
  const { messages, fileEdits, streaming, connection, submitText, submitBackground, interrupt, commands, currentActivity } = useAgent()
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [input, setInput] = useState('')
  const [showSlash, setShowSlash] = useState(false)
  const [bgMode, setBgMode] = useState(false)
  const [bgWithContext, setBgWithContext] = useState(true)

  useEffect(() => {
    const onDraft = (event: Event) => {
      const text = (event as CustomEvent<{ text?: string }>).detail?.text
      if (!text) return
      setInput(text)
      setBgMode(false)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
    window.addEventListener('cc:hermes-draft', onDraft as EventListener)
    return () => window.removeEventListener('cc:hermes-draft', onDraft as EventListener)
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  // Slash autocomplete: typed when input starts with "/"
  const slashMatches = useMemo(() => {
    if (!input.startsWith('/')) return []
    const q = input.slice(1).toLowerCase()
    return commands
      .filter(c => c.name.toLowerCase().startsWith(q) || c.aliases.some(a => a.toLowerCase().startsWith(q)))
      .slice(0, 8)
  }, [input, commands])

  // Group file edits by message — show edit chips after assistant turns
  const editsByTime = useMemo(() => fileEdits.slice().sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  ), [fileEdits])
  const recentEdits = editsByTime.slice(0, 5)

  function doSubmit() {
    if (!input.trim()) return
    if (bgMode) {
      submitBackground(input, bgWithContext)
      setInput('')
      setShowSlash(false)
      return
    }
    if (streaming) return
    submitText(input)
    setInput('')
    setShowSlash(false)
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    doSubmit()
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      doSubmit()
    } else if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      onOpenCommands()
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
      <div style={{ height: 40, padding: '0 16px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, background: 'rgba(0,0,0,0.1)' }}>
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={streaming ? 'ws-pulse' : ''}
            style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: streaming ? 'var(--ws-success)' : 'var(--ws-accent)',
              boxShadow: `0 0 8px ${streaming ? 'var(--ws-success)' : 'var(--ws-accent)'}` }}
          />
          <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
            {streaming && currentActivity
              ? <span style={{ color: 'var(--ws-accent)' }}>{currentActivity}</span>
              : streaming ? 'procesando…' : 'chat · laia'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onOpenCommands}
            className="ws-pill"
            style={{ padding: '3px 8px' }}
            title="Paleta de comandos (⌘K)"
          >
            <Slash size={11} />
            <span>⌘K</span>
          </button>
          <button
            type="button"
            onClick={interrupt}
            disabled={!streaming}
            className="ws-pill"
            style={{ padding: '3px 8px', opacity: streaming ? 1 : 0.4, color: streaming ? 'var(--ws-danger)' : undefined }}
            title="Interrumpir"
          >
            <CircleStop size={11} />
            <span>stop</span>
          </button>
        </div>
      </div>

      <div ref={containerRef} className="flex-1 overflow-y-auto" style={{ padding: '20px 24px' }}>
        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          {messages.map(msg => (
            <Bubble key={msg.id} msg={msg} onOpenTool={onOpenTool} />
          ))}

          {recentEdits.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
                Archivos modificados
              </span>
              {recentEdits.map(edit => (
                <button
                  key={edit.id}
                  type="button"
                  onClick={() => onOpenDiff(edit)}
                  className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[0.7rem] transition-colors"
                  style={{
                    background: 'rgba(255,196,90,0.08)',
                    border: '1px solid rgba(255,196,90,0.22)',
                    color: 'var(--ws-accent)',
                  }}
                >
                  <FileDiff size={11} />
                  <span className="mono truncate" style={{ maxWidth: 280 }}>
                    {edit.path.split('/').slice(-2).join('/')}
                  </span>
                  <span className="ws-pill" style={{ padding: '0 5px', fontSize: '0.5rem' }}>
                    {edit.operation}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ padding: 14, borderTop: '1px solid var(--ws-border)', background: 'rgba(0,0,0,0.18)', position: 'relative' }}>
        {showSlash && slashMatches.length > 0 && (
          <div
            className="ws-card absolute left-3 right-3 z-30"
            style={{ bottom: 'calc(100% + 6px)', maxHeight: 220, overflowY: 'auto', padding: 6 }}
          >
            {slashMatches.map(cmd => (
              <button
                key={cmd.name}
                type="button"
                onClick={() => { setInput(`/${cmd.name} `); inputRef.current?.focus(); setShowSlash(false) }}
                className="block w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors"
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div className="flex items-center gap-2">
                  <span className="mono" style={{ color: 'var(--ws-accent)' }}>/{cmd.name}</span>
                  <span className="text-[0.65rem]" style={{ color: 'var(--ws-text-muted)' }}>{cmd.description}</span>
                </div>
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <span className="mono text-base pb-2" style={{ color: connection === 'online' ? 'var(--ws-accent)' : 'var(--ws-text-muted)' }}>›</span>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => { setInput(e.target.value); setShowSlash(e.target.value.startsWith('/')) }}
            onKeyDown={handleKey}
            rows={1}
            disabled={connection !== 'online'}
            placeholder={
              connection !== 'online' ? 'Conectando al runtime…' :
              bgMode ? 'Lanza una tarea en background (subagente paralelo)…' :
              'Pregúntale a Laia…  (/ para comandos · ⌘K paleta)'
            }
            className="field flex-1 resize-none rounded-lg text-sm"
            style={{ padding: '8px 12px', minHeight: 38, maxHeight: 200 }}
          />
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setBgMode(b => !b)}
              className="ws-pill"
              style={{
                padding: '6px 10px', height: 38, fontSize: '0.65rem',
                color: bgMode ? 'var(--ws-violet)' : 'var(--ws-text-muted)',
                borderColor: bgMode ? 'rgba(196,181,253,0.4)' : 'var(--ws-border)',
              }}
              title="Background: lanza un subagente paralelo (no bloquea el chat principal)"
            >
              bg
            </button>
            {bgMode && (
              <button
                type="button"
                onClick={() => setBgWithContext(c => !c)}
                className="ws-pill"
                style={{
                  padding: '6px 8px', height: 38, fontSize: '0.55rem',
                  color: bgWithContext ? 'var(--ws-violet)' : 'var(--ws-text-muted)',
                  borderColor: bgWithContext ? 'rgba(196,181,253,0.4)' : 'var(--ws-border)',
                }}
                title={bgWithContext
                  ? 'Incluye los últimos 12 mensajes del chat principal como contexto'
                  : 'Subagente sin contexto del chat'}
              >
                {bgWithContext ? '+ctx' : '−ctx'}
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={!input.trim() || (streaming && !bgMode) || connection !== 'online'}
            className="btn-primary flex items-center justify-center rounded-lg"
            style={{ width: 38, height: 38 }}
            aria-label="Enviar"
          >
            <Send size={15} />
          </button>
        </div>
      </form>
    </div>
  )
}

function parseCtx(content: string): { toolId: string; body: string } | null {
  const prefix = `[${CTX_SENTINEL}:`
  if (!content.startsWith(prefix)) return null
  const end = content.indexOf(']')
  if (end === -1) return null
  const toolId = content.slice(prefix.length, end)
  const body = content.slice(end + 2) // skip "]\n"
  return { toolId, body }
}

function ContextCard({ toolId, body }: { toolId: string; body: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex justify-end">
      <div style={{
        maxWidth: '78%',
        border: '1px solid rgba(255,196,90,0.15)',
        borderRadius: '8px 8px 3px 8px',
        overflow: 'hidden',
        fontSize: '0.7rem',
        fontFamily: 'monospace',
      }}>
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 w-full text-left"
          style={{
            padding: '5px 10px',
            background: 'rgba(255,196,90,0.06)',
            color: 'rgba(255,196,90,0.6)',
            cursor: 'pointer',
            border: 'none',
          }}
        >
          {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          <span style={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.58rem' }}>
            context · {toolId}
          </span>
        </button>
        {open && (
          <pre style={{
            margin: 0, padding: '8px 10px',
            background: 'rgba(0,0,0,0.25)',
            color: 'rgba(230,237,243,0.55)',
            fontSize: '0.65rem',
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxHeight: 300,
            overflowY: 'auto',
          }}>
            {body}
          </pre>
        )}
      </div>
    </div>
  )
}

function Bubble({ msg, onOpenTool }: { msg: ChatMessage; onOpenTool: (tc: ToolCall) => void }) {
  if (msg.role === 'user') {
    const ctx = parseCtx(msg.content)
    if (ctx) return <ContextCard toolId={ctx.toolId} body={ctx.body} />
    return (
      <div className="flex justify-end">
        <div
          style={{
            maxWidth: '78%',
            background: 'linear-gradient(135deg, rgba(255,196,90,0.12), rgba(224,168,48,0.08))',
            border: '1px solid rgba(255,196,90,0.25)',
            color: 'var(--ws-text)',
            borderRadius: '12px 12px 3px 12px',
            padding: '8px 12px',
          }}
        >
          <Markdown text={msg.content} />
        </div>
      </div>
    )
  }
  if (msg.role === 'system' || msg.role === 'tool') {
    return (
      <div className="flex">
        <div
          style={{
            width: '100%',
            paddingLeft: 12,
            paddingTop: 4, paddingBottom: 4,
            borderLeft: `2px solid ${msg.status === 'error' ? 'rgba(252,165,165,0.6)' : 'var(--ws-border)'}`,
            color: msg.status === 'error' ? 'var(--ws-danger)' : 'var(--ws-text-muted)',
            fontSize: '0.72rem',
            lineHeight: 1.55,
            whiteSpace: 'pre-wrap',
          }}
        >
          {msg.content}
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="mono text-[0.65rem]" style={{ color: 'var(--ws-accent)' }}>›</span>
        <span className="mono text-[0.55rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
          laia
        </span>
      </div>
      <div style={{ paddingLeft: 16, color: 'var(--ws-text)' }}>
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="flex flex-col gap-1 mb-2">
            {msg.toolCalls.map(tc => <ToolCallChip key={tc.id} tc={tc} onOpen={() => onOpenTool(tc)} />)}
          </div>
        )}
        {msg.content
          ? <Markdown text={msg.content} />
          : <span className="mono ws-pulse text-base" style={{ color: 'var(--ws-accent)' }}>▊</span>}
      </div>
    </div>
  )
}

function ToolCallChip({ tc, onOpen }: {
  tc: NonNullable<ChatMessage['toolCalls']>[number]
  onOpen: () => void
}) {
  const color = tc.status === 'error'
    ? 'var(--ws-danger)'
    : tc.status === 'complete'
      ? 'var(--ws-success)'
      : 'var(--ws-accent)'
  const icon = tc.status === 'running' ? '◐' : tc.status === 'error' ? '✕' : '✓'
  return (
    <button
      type="button"
      onClick={onOpen}
      title="Click para ver detalle"
      className="flex items-center gap-2 mono text-[0.66rem] text-left transition-colors"
      style={{
        background: 'rgba(255,196,90,0.04)',
        border: `1px solid ${color}33`,
        borderRadius: 4,
        padding: '3px 8px',
        color: 'var(--ws-text-muted)',
        cursor: 'pointer',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = `${color}1a` }}
      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,196,90,0.04)' }}
    >
      <span className={tc.status === 'running' ? 'ws-pulse' : ''} style={{ color }}>{icon}</span>
      <span style={{ color }}>{tc.name}</span>
      {tc.context && (
        <span className="truncate" style={{ color: 'var(--ws-text-muted)', maxWidth: 380 }}>
          {tc.context}
        </span>
      )}
      {typeof tc.duration_s === 'number' && (
        <span style={{ color: 'var(--ws-text-muted)', opacity: 0.55, marginLeft: 'auto' }}>
          {tc.duration_s < 1 ? `${Math.round(tc.duration_s * 1000)}ms` : `${tc.duration_s.toFixed(1)}s`}
        </span>
      )}
    </button>
  )
}

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const re = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g
  let last = 0, idx = 0, m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    if (m[2]) parts.push(<strong key={idx++} style={{ color: 'var(--ws-accent)', fontWeight: 600 }}>{m[2]}</strong>)
    else if (m[3]) parts.push(<code key={idx++} className="mono" style={{ color: 'var(--ws-accent)', background: 'rgba(255,196,90,0.08)', padding: '1px 5px', borderRadius: 3, fontSize: '0.86em' }}>{m[3]}</code>)
    else if (m[4]) parts.push(<a key={idx++} href={m[5]} target="_blank" rel="noreferrer" style={{ color: 'var(--ws-accent)' }}>{m[4]}</a>)
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

function Markdown({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {lines.map((line, i) => {
        if (!line.trim()) return null
        if (line.startsWith('```')) return null
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return (
            <div key={i} className="flex gap-2 text-sm leading-relaxed">
              <span style={{ color: 'var(--ws-accent)' }}>·</span>
              <span>{inline(line.slice(2))}</span>
            </div>
          )
        }
        if (line.startsWith('# ')) {
          return <h3 key={i} className="text-base font-semibold" style={{ color: 'var(--ws-text)' }}>{inline(line.slice(2))}</h3>
        }
        return <p key={i} className="text-sm leading-relaxed">{inline(line)}</p>
      })}
    </div>
  )
}
