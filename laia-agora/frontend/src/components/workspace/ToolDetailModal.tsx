/* ────────────────────────────────────────────────────────────────────────────
   TOOL DETAIL MODAL
   Opened when a tool chip in the chat is clicked. Shows full context, accumulated
   progress, summary, inline diff (if any), and error.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react'
import { Check, Copy, Terminal, X } from 'lucide-react'
import type { ToolCall } from '../../lib/agentRuntime'

const ANSI_RE = /\x1B\[[0-9;]*[A-Za-z]/g
function stripAnsi(s: string): string { return s.replace(ANSI_RE, '') }

interface Props {
  tc: ToolCall | null
  onClose: () => void
}

export function ToolDetailModal({ tc, onClose }: Props) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!tc) return null

  const color = tc.status === 'error' ? 'var(--ws-danger)' :
                tc.status === 'complete' ? 'var(--ws-success)' :
                'var(--ws-accent)'

  const fullText = [
    `tool: ${tc.name}`,
    `context: ${tc.context}`,
    tc.summary ? `summary: ${tc.summary}` : '',
    typeof tc.duration_s === 'number' ? `duration: ${tc.duration_s.toFixed(2)}s` : '',
    tc.error ? `error: ${tc.error}` : '',
    tc.progress?.length ? `progress:\n${tc.progress.join('\n')}` : '',
    tc.inline_diff ? `diff:\n${stripAnsi(tc.inline_diff)}` : '',
  ].filter(Boolean).join('\n\n')

  async function copy() {
    try {
      await navigator.clipboard.writeText(fullText)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* ignore */ }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="ws-card flex flex-col"
        style={{ width: '90vw', maxWidth: 900, maxHeight: '85vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="ws-card-header" style={{ borderColor: `${color}33` }}>
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Terminal size={13} style={{ color }} />
            <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color }}>
              {tc.status}
            </span>
            <span className="mono text-[0.7rem]" style={{ color: 'var(--ws-text)' }}>
              {tc.name}
            </span>
            {typeof tc.duration_s === 'number' && (
              <span className="mono text-[0.6rem]" style={{ color: 'var(--ws-text-muted)' }}>
                · {tc.duration_s < 1 ? `${Math.round(tc.duration_s * 1000)}ms` : `${tc.duration_s.toFixed(2)}s`}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={copy} className="ws-pill" style={{ padding: '3px 8px', fontSize: '0.6rem' }}>
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? 'copiado' : 'copy'}
            </button>
            <button type="button" onClick={onClose} className="ws-pill" style={{ padding: '3px 6px' }}>
              <X size={11} />
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 14 }}>
          {tc.context && (
            <Field label="Argumento / contexto">
              <pre className="mono text-xs leading-relaxed" style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                background: 'rgba(0,0,0,0.3)', padding: 10, borderRadius: 6,
                border: '1px solid var(--ws-border)', color: 'var(--ws-text)',
              }}>
                {tc.context}
              </pre>
            </Field>
          )}

          {tc.summary && (
            <Field label="Resumen">
              <div className="text-[0.75rem]" style={{ color: 'var(--ws-text)' }}>
                {tc.summary}
              </div>
            </Field>
          )}

          {tc.error && (
            <Field label="Error">
              <pre className="mono text-xs" style={{
                whiteSpace: 'pre-wrap',
                background: 'rgba(248,113,113,0.08)', padding: 10, borderRadius: 6,
                border: '1px solid rgba(248,113,113,0.3)', color: 'var(--ws-danger)',
              }}>
                {tc.error}
              </pre>
            </Field>
          )}

          {tc.progress && tc.progress.length > 0 && (
            <Field label={`Progreso (${tc.progress.length} eventos)`}>
              <pre className="mono text-xs leading-relaxed" style={{
                whiteSpace: 'pre-wrap',
                background: 'rgba(0,0,0,0.3)', padding: 10, borderRadius: 6,
                border: '1px solid var(--ws-border)', color: 'var(--ws-text-muted)',
                maxHeight: 200, overflow: 'auto',
              }}>
                {tc.progress.map((p, i) => (
                  <div key={i} style={{ borderLeft: '2px solid var(--ws-border)', paddingLeft: 8, marginBottom: 4 }}>
                    {stripAnsi(p)}
                  </div>
                ))}
              </pre>
            </Field>
          )}

          {tc.inline_diff && (
            <Field label="Diff">
              <pre className="mono text-xs" style={{
                whiteSpace: 'pre',
                background: 'rgba(0,0,0,0.3)', padding: 10, borderRadius: 6,
                border: '1px solid var(--ws-border)',
                maxHeight: 400, overflow: 'auto',
              }}>
                {stripAnsi(tc.inline_diff).split('\n').map((line, i) => {
                  const isAdd = line.startsWith('+') && !line.startsWith('+++')
                  const isDel = line.startsWith('-') && !line.startsWith('---')
                  const isHunk = line.startsWith('@@')
                  const c = isAdd ? 'var(--ws-success)' :
                            isDel ? 'var(--ws-danger)' :
                            isHunk ? 'var(--ws-accent)' : 'var(--ws-text)'
                  return (
                    <div key={i} style={{ color: c }}>{line || ' '}</div>
                  )
                })}
              </pre>
            </Field>
          )}

          {!tc.summary && !tc.error && !tc.inline_diff && (!tc.progress || tc.progress.length === 0) && (
            <div className="mono text-[0.65rem] py-8 text-center"
              style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
              {tc.status === 'running' ? 'ejecutándose…' : 'sin output capturado'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="mono text-[0.55rem] uppercase tracking-widest mb-1.5"
        style={{ color: 'var(--ws-text-muted)', opacity: 0.7 }}>
        {label}
      </div>
      {children}
    </div>
  )
}
