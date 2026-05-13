/* ────────────────────────────────────────────────────────────────────────────
   DIFF MODAL
   Opened from chat or SidePanels:edits. Shows the unified diff for a single
   file edit. Strips ANSI color codes from gateway-rendered diffs and applies
   client-side syntax classes (ws-diff-add / ws-diff-del / ws-diff-hunk).
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useMemo, useState } from 'react'
import { Check, Copy, FileDiff, X } from 'lucide-react'
import type { FileEdit } from '../../lib/api'
import { api } from '../../lib/api'

interface Props {
  edit: FileEdit | null
  onClose: () => void
}

// Strip ANSI escape codes (gateway diffs come pre-colored for terminal output)
const ANSI_RE = /\x1B\[[0-9;]*[A-Za-z]/g
function stripAnsi(s: string): string { return s.replace(ANSI_RE, '') }

export function DiffModal({ edit, onClose }: Props) {
  const [diff, setDiff] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!edit) { setDiff(''); return }
    if (edit.diff) {
      setDiff(stripAnsi(edit.diff))
    } else {
      api.getFileEditDiff(edit.id)
        .then(d => setDiff(stripAnsi(d.diff || '')))
        .catch(() => setDiff(''))
    }
  }, [edit])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const stats = useMemo(() => {
    let added = 0, removed = 0
    for (const line of diff.split('\n')) {
      if (line.startsWith('+') && !line.startsWith('+++')) added++
      else if (line.startsWith('-') && !line.startsWith('---')) removed++
    }
    return { added, removed }
  }, [diff])

  if (!edit) return null

  async function copy() {
    try {
      await navigator.clipboard.writeText(diff)
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
        style={{ width: '90vw', maxWidth: 1100, height: '85vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="ws-card-header">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <FileDiff size={13} style={{ color: 'var(--ws-accent)' }} />
            <span className="ws-pill" data-active="true" style={{ padding: '1px 6px' }}>{edit.operation}</span>
            <span className="mono text-[0.7rem] truncate" style={{ color: 'var(--ws-text)' }}>{edit.path}</span>
            <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
              {new Date(edit.created_at).toLocaleString()}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {(stats.added > 0 || stats.removed > 0) && (
              <span className="mono text-[0.6rem] flex items-center gap-1.5">
                <span style={{ color: 'var(--ws-success)' }}>+{stats.added}</span>
                <span style={{ color: 'var(--ws-danger)' }}>−{stats.removed}</span>
              </span>
            )}
            <button
              type="button"
              onClick={copy}
              className="ws-pill"
              style={{ padding: '3px 8px', fontSize: '0.6rem' }}
              title="Copiar diff"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? 'copiado' : 'copy'}
            </button>
            <button type="button" onClick={onClose} className="ws-pill" style={{ padding: '3px 6px' }}>
              <X size={11} />
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 0, background: 'rgba(0,0,0,0.25)' }}>
          {diff ? (
            <pre className="mono text-xs leading-relaxed" style={{ whiteSpace: 'pre', margin: 0 }}>
              {diff.split('\n').map((line, i) => {
                const isAdd = line.startsWith('+') && !line.startsWith('+++')
                const isDel = line.startsWith('-') && !line.startsWith('---')
                const isHunk = line.startsWith('@@')
                const isHeader = line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff ')
                const cls =
                  isHunk ? 'ws-diff-hunk' :
                  isAdd ? 'ws-diff-add' :
                  isDel ? 'ws-diff-del' : ''
                const bg =
                  isAdd ? 'rgba(34,197,94,0.10)' :
                  isDel ? 'rgba(248,113,113,0.10)' :
                  isHunk ? 'rgba(255,196,90,0.06)' :
                  isHeader ? 'rgba(255,255,255,0.02)' : 'transparent'
                const borderL =
                  isAdd ? '2px solid rgba(34,197,94,0.5)' :
                  isDel ? '2px solid rgba(248,113,113,0.5)' :
                  isHunk ? '2px solid var(--ws-accent)' : '2px solid transparent'
                return (
                  <div
                    key={i}
                    className={cls}
                    style={{
                      paddingLeft: 12,
                      paddingRight: 12,
                      background: bg,
                      borderLeft: borderL,
                      color: isHeader ? 'var(--ws-text-muted)' : undefined,
                      opacity: isHeader ? 0.7 : 1,
                    }}
                  >
                    {line || ' '}
                  </div>
                )
              })}
            </pre>
          ) : (
            <div className="text-center py-10 mono text-[0.7rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
              sin diff disponible · operación: {edit.operation}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
