import type React from 'react'
import { useEffect, useRef, useState } from 'react'
import { Send, X, MessageSquare, ChevronDown, Download, Maximize2, Minimize2 } from 'lucide-react'
import { LaiaNeuralAvatar, type AvatarState } from './LaiaNeuralAvatar'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  role: 'user' | 'assistant'
  content: string
  isError?: boolean
  ts?: number
}

function buildWelcome(workspace: string | undefined, nodeContext: { title: string; slug: string; kind: string } | null): Message {
  let context = ''
  if (nodeContext) {
    context = ` Estoy viendo el nodo **"${nodeContext.title}"** (${nodeContext.kind}) en el workspace **${workspace}**.`
  } else if (workspace) {
    context = ` Estoy en el workspace **${workspace}**.`
  }
  return {
    role: 'assistant',
    content: `Hola! Soy Laia.${context} ¿Qué necesitas?`,
    ts: Date.now(),
  }
}

// ── Markdown renderer ─────────────────────────────────────────────────────────

function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  // Matches: **bold**, *italic*, `code`, [link](url)
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g
  let last = 0; let m: RegExpExecArray | null; let idx = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    if (m[2])      parts.push(<strong key={idx++} style={{ color: 'var(--brand)', fontWeight: 600 }}>{m[2]}</strong>)
    else if (m[3]) parts.push(<em key={idx++} style={{ color: 'rgba(255,255,255,0.75)', fontStyle: 'italic' }}>{m[3]}</em>)
    else if (m[4]) parts.push(
      <code key={idx++} className="mono px-1.5 py-0.5 rounded text-xs"
        style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--brand)', border: '1px solid rgba(255,196,90,0.2)' }}>
        {m[4]}
      </code>
    )
    else if (m[5]) parts.push(
      <a key={idx++} href={m[6]} target="_blank" rel="noreferrer"
        style={{ color: 'var(--brand)', textDecoration: 'underline', textUnderlineOffset: '3px' }}>
        {m[5]}
      </a>
    )
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

function MarkdownBlock({ text }: { text: string }) {
  if (!text) return null

  const blocks: React.ReactNode[] = []
  const lines = text.split('\n')
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      blocks.push(
        <div key={key++} className="rounded-lg overflow-hidden my-2"
          style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)' }}>
          {lang && (
            <div className="mono px-3 py-1 text-[0.6rem] font-medium"
              style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
              {lang}
            </div>
          )}
          <pre className="mono px-3 py-2.5 text-xs overflow-x-auto leading-relaxed m-0"
            style={{ color: 'rgba(255,230,150,0.9)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {codeLines.join('\n')}
          </pre>
        </div>
      )
      i++ // skip closing ```
      continue
    }

    // Headings
    const hMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (hMatch) {
      const level = hMatch[1].length
      const sizes = ['text-base', 'text-sm', 'text-sm']
      blocks.push(
        <div key={key++} className={`font-bold mt-3 mb-1 ${sizes[level - 1]}`}
          style={{ color: level === 1 ? 'var(--brand)' : 'var(--text-main)' }}>
          {renderInline(hMatch[2])}
        </div>
      )
      i++; continue
    }

    // Table — lines starting with |
    if (line.startsWith('|')) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i].startsWith('|')) {
        tableLines.push(lines[i])
        i++
      }
      // Parse: first row = headers, second row = separator (skip), rest = data
      const parseRow = (row: string) =>
        row.split('|').slice(1, -1).map(cell => cell.trim())
      const isSeparator = (row: string) => /^\|[\s|:-]+\|$/.test(row)

      const nonSep = tableLines.filter(l => !isSeparator(l))
      const headers = nonSep[0] ? parseRow(nonSep[0]) : []
      const rows = nonSep.slice(1).map(parseRow)

      blocks.push(
        <div key={key++} className="my-2 overflow-x-auto rounded-lg"
          style={{ border: '1px solid var(--border)' }}>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr style={{ background: 'rgba(255,196,90,0.07)', borderBottom: '1px solid var(--border)' }}>
                {headers.map((h, j) => (
                  <th key={j} className="px-3 py-2 text-left font-semibold"
                    style={{ color: 'var(--brand)', whiteSpace: 'nowrap', borderRight: j < headers.length - 1 ? '1px solid var(--border)' : undefined }}>
                    {renderInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}
                  style={{ borderBottom: ri < rows.length - 1 ? '1px solid rgba(255,255,255,0.05)' : undefined, background: ri % 2 === 1 ? 'rgba(255,255,255,0.02)' : undefined }}>
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2"
                      style={{ color: 'var(--text-main)', borderRight: ci < row.length - 1 ? '1px solid rgba(255,255,255,0.05)' : undefined }}>
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      continue
    }

    // Horizontal rule
    if (line.match(/^---+$/)) {
      blocks.push(<hr key={key++} className="my-2" style={{ borderColor: 'var(--border)' }} />)
      i++; continue
    }

    // Unordered list
    if (line.match(/^[-*+]\s/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^[-*+]\s/)) {
        items.push(lines[i].slice(2))
        i++
      }
      blocks.push(
        <ul key={key++} className="my-1.5 pl-4 flex flex-col gap-0.5">
          {items.map((item, j) => (
            <li key={j} className="text-sm leading-relaxed list-none flex gap-2">
              <span style={{ color: 'var(--brand)', marginTop: '0.3em', flexShrink: 0 }}>·</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    }

    // Ordered list
    if (line.match(/^\d+\.\s/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        items.push(lines[i].replace(/^\d+\.\s/, ''))
        i++
      }
      blocks.push(
        <ol key={key++} className="my-1.5 pl-2 flex flex-col gap-0.5">
          {items.map((item, j) => (
            <li key={j} className="text-sm leading-relaxed list-none flex gap-2">
              <span className="mono text-xs font-bold shrink-0 mt-0.5" style={{ color: 'var(--brand)', minWidth: '1.2em' }}>
                {j + 1}.
              </span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      )
      continue
    }

    // Blockquote
    if (line.startsWith('> ')) {
      const qLines: string[] = []
      while (i < lines.length && lines[i].startsWith('> ')) {
        qLines.push(lines[i].slice(2))
        i++
      }
      blocks.push(
        <blockquote key={key++} className="my-2 pl-3 py-0.5"
          style={{ borderLeft: '2px solid rgba(255,196,90,0.5)', color: 'var(--text-muted)' }}>
          {qLines.map((l, j) => <div key={j} className="text-sm">{renderInline(l)}</div>)}
        </blockquote>
      )
      continue
    }

    // Empty line → spacer between paragraphs
    if (line.trim() === '') {
      i++; continue
    }

    // Regular paragraph
    blocks.push(
      <p key={key++} className="text-sm leading-relaxed my-0.5">
        {renderInline(line)}
      </p>
    )
    i++
  }

  return <div className="flex flex-col gap-0">{blocks}</div>
}

// ── Save chat ─────────────────────────────────────────────────────────────────

function saveChat(messages: Message[], workspace: string | undefined) {
  const header = `# Chat con Laia${workspace ? ` — ${workspace}` : ''}\n_${new Date().toLocaleString('es-ES')}_\n\n---\n\n`
  const body = messages
    .map(m => {
      const who = m.role === 'user' ? '**Tú**' : '**Laia**'
      return `${who}\n\n${m.content}`
    })
    .join('\n\n---\n\n')
  const blob = new Blob([header + body], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `laia-chat-${workspace ?? 'session'}-${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
}

// ── ChatPanel ─────────────────────────────────────────────────────────────────

interface ChatPanelProps {
  workspace: string | undefined
  nodeContext: { title: string; slug: string; kind: string } | null
  isOpen: boolean
  onClose: () => void
}

export function ChatPanel({ workspace, nodeContext, isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>(() => [buildWelcome(workspace, nodeContext)])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [opening, setOpening] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Animate open: panel lives at bottom:20px always (same as button).
  // Opening expands height. Closing collapses height instantly.
  useEffect(() => {
    if (isOpen) {
      setOpening(true)
    } else {
      setOpening(false)
    }
  }, [isOpen])

  // Derive avatar state
  const avatarState: AvatarState = streaming ? 'streaming' : minimized ? 'idle' : 'idle'

  // Reset welcome when workspace context changes
  useEffect(() => {
    setMessages([buildWelcome(workspace, nodeContext)])
  }, [workspace, nodeContext])

  // Auto-scroll on new content
  useEffect(() => {
    if (!minimized) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, minimized])

  // Focus input when panel opens or un-minimizes
  useEffect(() => {
    if (isOpen && !minimized) {
      const id = setTimeout(() => inputRef.current?.focus(), 180)
      return () => clearTimeout(id)
    }
  }, [isOpen, minimized])

  function appendToLastMessage(text: string) {
    setMessages(prev => {
      const copy = [...prev]
      const last = copy[copy.length - 1]
      if (last?.role === 'assistant') copy[copy.length - 1] = { ...last, content: last.content + text }
      return copy
    })
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg: Message = { role: 'user', content: text, ts: Date.now() }
    const assistantMsg: Message = { role: 'assistant', content: '', ts: Date.now() }
    setMessages(prev => [...prev, userMsg, assistantMsg])
    setInput('')
    setStreaming(true)
    if (minimized) setMinimized(false)

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content })),
          workspace,
        }),
      })

      if (!resp.ok) {
        const errText = await resp.text().catch(() => `HTTP ${resp.status}`)
        setMessages(prev => {
          const copy = [...prev]
          copy[copy.length - 1] = { role: 'assistant', content: errText, isError: true }
          return copy
        })
        setStreaming(false)
        return
      }

      const reader = resp.body?.getReader()
      if (!reader) { setStreaming(false); return }

      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const json = JSON.parse(line.slice(6)) as { type: string; text?: string; message?: string }
            if (json.type === 'delta' && json.text) appendToLastMessage(json.text)
            if (json.type === 'done') setStreaming(false)
            if (json.type === 'error') {
              setMessages(prev => {
                const copy = [...prev]
                copy[copy.length - 1] = { role: 'assistant', content: json.message ?? 'Error desconocido', isError: true }
                return copy
              })
              setStreaming(false)
            }
          } catch { /* skip malformed lines */ }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error de conexión'
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = { role: 'assistant', content: msg, isError: true }
        return copy
      })
      setStreaming(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  // Panel dimensions — bottom is always 20px (same as the button)
  const panelW = expanded ? 560 : 356
  const fullH = expanded ? 640 : 500
  // Height: 0 when fully closed, 52 header-only when minimized, full otherwise
  const panelH =
    !isOpen && !opening ? 0
    : minimized ? 52
    : fullH

  return (
    <div
      className="fixed z-50 flex flex-col chat-panel-shadow"
      style={{
        bottom: '20px',
        right: '16px',
        width: `${panelW}px`,
        height: `${panelH}px`,
        background: 'rgba(8,8,10,0.94)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid var(--border)',
        borderRadius: '16px',
        boxShadow: expanded
          ? '0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04) inset'
          : '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04) inset',
        opacity: isOpen || opening ? 1 : 0,
        pointerEvents: isOpen ? 'all' : 'none',
        transition: 'width 320ms cubic-bezier(0.22,1,0.36,1), height 360ms cubic-bezier(0.22,1,0.36,1), opacity 160ms ease',
        overflow: 'hidden',
      }}
    >
      {/* ── Amber glow fill overlay (opening only) ── */}
      {isOpen && opening && (
        <div
          className="chat-fill-glow open"
          style={{
            background: 'radial-gradient(ellipse 80% 60% at 100% 100%, rgba(255,196,90,0.55) 0%, rgba(255,140,30,0.2) 45%, transparent 70%)',
          }}
        />
      )}

      {/* ── Header ── */}
      <div
        className="flex items-center gap-2.5 px-4 shrink-0 cursor-pointer select-none"
        style={{
          height: '52px',
          borderBottom: minimized ? 'none' : '1px solid var(--border)',
          background: 'rgba(255,255,255,0.02)',
        }}
        onClick={() => setMinimized(m => !m)}
      >
        {/* Animated avatar */}
        <div className="shrink-0" onClick={e => e.stopPropagation()}>
          <LaiaNeuralAvatar size={28} state={avatarState} />
        </div>

        {/* Name + context */}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold" style={{ color: 'var(--text-main)' }}>Laia</div>
          {workspace && !minimized && (
            <div className="text-[0.6rem] truncate" style={{ color: 'var(--text-muted)' }}>{workspace}</div>
          )}
        </div>

        {/* Status dot */}
        <span
          className={`h-1.5 w-1.5 rounded-full shrink-0 ${streaming ? 'animate-pulse' : ''}`}
          style={{
            background: streaming ? 'var(--brand)' : '#4ade80',
            boxShadow: streaming ? '0 0 6px rgba(255,196,90,0.7)' : '0 0 6px rgba(74,222,128,0.6)',
          }}
        />

        {/* Action buttons */}
        <div className="flex items-center gap-0.5 ml-1" onClick={e => e.stopPropagation()}>
          {/* Save chat */}
          {!minimized && (
            <button
              onClick={() => saveChat(messages, workspace)}
              className="h-7 w-7 flex items-center justify-center rounded-lg transition-all"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'var(--text-main)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
              title="Guardar conversación"
              aria-label="Guardar chat"
            >
              <Download size={13} />
            </button>
          )}

          {/* Expand/compress */}
          {!minimized && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="h-7 w-7 flex items-center justify-center rounded-lg transition-all"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'var(--text-main)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
              title={expanded ? 'Compactar' : 'Ampliar'}
              aria-label={expanded ? 'Compactar' : 'Ampliar ventana'}
            >
              {expanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          )}

          {/* Minimize */}
          <button
            onClick={() => setMinimized(m => !m)}
            className="h-7 w-7 flex items-center justify-center rounded-lg transition-all"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'var(--text-main)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
            title={minimized ? 'Expandir' : 'Minimizar'}
            aria-label="Minimizar"
          >
            <ChevronDown
              size={13}
              style={{
                transform: minimized ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 220ms ease',
              }}
            />
          </button>

          {/* Close */}
          <button
            onClick={onClose}
            className="h-7 w-7 flex items-center justify-center rounded-lg transition-all"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; e.currentTarget.style.color = '#fca5a5' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
            title="Cerrar"
            aria-label="Cerrar"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* ── Messages ── */}
      {!minimized && (
        <>
          <div className="flex-1 overflow-y-auto px-3.5 py-3 flex flex-col gap-2.5 min-h-0">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="shrink-0 mt-0.5">
                    <LaiaNeuralAvatar size={20} state={i === messages.length - 1 ? avatarState : 'idle'} />
                  </div>
                )}
                <div
                  className="max-w-[86%] rounded-xl px-3 py-2.5"
                  style={
                    msg.role === 'user'
                      ? { background: 'rgba(255,196,90,0.1)', border: '1px solid rgba(255,196,90,0.2)', borderRadius: '12px 12px 4px 12px', wordBreak: 'break-word' }
                      : msg.isError
                        ? { background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '4px 12px 12px 12px', color: '#fca5a5', wordBreak: 'break-word' }
                        : { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px 12px 12px 12px', wordBreak: 'break-word' }
                  }
                >
                  {msg.content === '' && msg.role === 'assistant' && streaming
                    ? null
                    : <MarkdownBlock text={msg.content} />}
                </div>
              </div>
            ))}

            {/* Typing dots */}
            {streaming && messages[messages.length - 1]?.content === '' && (
              <div className="flex gap-2 justify-start">
                <div className="shrink-0 mt-0.5">
                  <LaiaNeuralAvatar size={20} state="thinking" />
                </div>
                <div className="flex items-center gap-1 px-3.5 py-3 rounded-xl"
                  style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px 12px 12px 12px' }}>
                  {[0, 150, 300].map(delay => (
                    <span key={delay} className="h-1.5 w-1.5 rounded-full animate-bounce"
                      style={{ background: 'var(--text-muted)', animationDelay: `${delay}ms` }} />
                  ))}
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Input ── */}
          <div className="flex items-center gap-2 px-3 py-3 shrink-0"
            style={{ borderTop: '1px solid var(--border)', background: 'rgba(255,255,255,0.01)' }}>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={streaming}
              placeholder="Pregunta a Laia…"
              className="field flex-1 min-w-0 rounded-xl px-3.5 py-2 text-sm"
            />
            <button
              onClick={() => void sendMessage()}
              disabled={streaming || !input.trim()}
              className="btn-primary h-9 w-9 shrink-0 flex items-center justify-center rounded-xl"
              aria-label="Enviar"
            >
              <Send size={14} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ── Tab trigger ────────────────────────────────────────────────────────────────

interface ChatTabProps {
  isOpen: boolean
  onClick: () => void
}

export function ChatTab({ isOpen, onClick }: ChatTabProps) {
  return (
    <button
      onClick={onClick}
      className="fixed z-50 flex items-center gap-2 rounded-full transition-all"
      style={{
        bottom: '20px',
        right: '16px',
        height: '44px',
        paddingLeft: '14px',
        paddingRight: '14px',
        background: isOpen
          ? 'rgba(255,255,255,0.05)'
          : 'linear-gradient(135deg, #ffd580 0%, #ffc45a 50%, #ff9a3c 100%)',
        border: isOpen ? '1px solid var(--border)' : '1px solid transparent',
        color: isOpen ? 'var(--text-muted)' : '#000',
        boxShadow: isOpen ? 'none' : '0 0 20px rgba(255,196,90,0.4), 0 4px 12px rgba(0,0,0,0.3)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: '13px',
        fontWeight: 600,
        letterSpacing: '0.01em',
        transition: 'all 220ms ease',
      }}
      onMouseEnter={e => {
        if (!isOpen) e.currentTarget.style.boxShadow = '0 0 28px rgba(255,196,90,0.6), 0 4px 16px rgba(0,0,0,0.4)'
        else e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
      }}
      onMouseLeave={e => {
        if (!isOpen) e.currentTarget.style.boxShadow = '0 0 20px rgba(255,196,90,0.4), 0 4px 12px rgba(0,0,0,0.3)'
        else e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
      }}
      aria-label={isOpen ? 'Abrir/cerrar chat' : 'Abrir chat con Laia'}
    >
      <MessageSquare size={14} />
      <span>Laia</span>
    </button>
  )
}
