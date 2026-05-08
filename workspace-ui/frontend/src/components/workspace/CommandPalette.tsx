/* ────────────────────────────────────────────────────────────────────────────
   COMMAND PALETTE  (⌘K)
   Searchable list of every slash command exposed by hermes-agent.
   Click → executes via /api/agent/commands/execute.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'
import type { CommandDef } from '../../lib/api'
import { api } from '../../lib/api'

interface Props { open: boolean; onClose: () => void }

export function CommandPalette({ open, onClose }: Props) {
  const { commands, sessionId, refreshCommands } = useAgent()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 50)
      if (commands.length === 0) refreshCommands()
    }
  }, [open, commands.length, refreshCommands])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    if (!q) return commands.slice(0, 60)
    return commands.filter(c =>
      c.name.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q) ||
      c.aliases.some(a => a.toLowerCase().includes(q)) ||
      c.category.toLowerCase().includes(q)
    ).slice(0, 60)
  }, [commands, query])

  const grouped = useMemo(() => {
    const m: Record<string, CommandDef[]> = {}
    for (const cmd of filtered) {
      const cat = cmd.category || 'Other'
      if (!m[cat]) m[cat] = []
      m[cat].push(cmd)
    }
    return m
  }, [filtered])

  async function execute(cmd: CommandDef) {
    try { await api.executeCommand(`/${cmd.name}`, sessionId || undefined) } catch { /* ignore */ }
    onClose()
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="ws-card w-full max-w-2xl"
        style={{ maxHeight: '70vh', display: 'flex', flexDirection: 'column' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: 12, borderBottom: '1px solid var(--ws-border)' }}>
          <div className="relative">
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--ws-text-muted)' }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => { setQuery(e.target.value); setActive(0) }}
              onKeyDown={e => {
                if (e.key === 'ArrowDown') { e.preventDefault(); setActive(i => Math.min(i + 1, filtered.length - 1)) }
                else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => Math.max(i - 1, 0)) }
                else if (e.key === 'Enter') { e.preventDefault(); if (filtered[active]) execute(filtered[active]) }
              }}
              placeholder="Buscar comandos…  (↑↓ navegar · Enter ejecutar · Esc cerrar)"
              className="field w-full text-sm"
              style={{ padding: '10px 12px 10px 32px', borderRadius: 8 }}
            />
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {Object.entries(grouped).map(([category, list]) => (
            <div key={category} style={{ marginBottom: 8 }}>
              <div className="mono text-[0.55rem] uppercase tracking-widest px-2 py-1.5"
                style={{ color: 'var(--ws-text-muted)', opacity: 0.6 }}>
                {category}
              </div>
              {list.map(cmd => {
                const idx = filtered.indexOf(cmd)
                const isActive = idx === active
                return (
                  <button
                    key={cmd.name}
                    type="button"
                    onClick={() => execute(cmd)}
                    onMouseEnter={() => setActive(idx)}
                    className="block w-full text-left px-3 py-2 rounded-md transition-colors"
                    style={{
                      background: isActive ? 'rgba(255, 196, 90, 0.08)' : 'transparent',
                      border: `1px solid ${isActive ? 'rgba(255, 196, 90, 0.25)' : 'transparent'}`,
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="mono text-sm" style={{ color: isActive ? 'var(--ws-accent)' : 'var(--ws-text)' }}>
                        /{cmd.name}
                      </span>
                      {cmd.aliases.length > 0 && (
                        <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)', opacity: 0.55 }}>
                          {cmd.aliases.map(a => `/${a}`).join(' ')}
                        </span>
                      )}
                    </div>
                    <div className="text-[0.7rem] mt-0.5" style={{ color: 'var(--ws-text-muted)' }}>
                      {cmd.description}
                    </div>
                  </button>
                )
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-10 mono text-[0.65rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)', opacity: 0.5 }}>
              sin resultados
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
