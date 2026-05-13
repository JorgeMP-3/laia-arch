/* ────────────────────────────────────────────────────────────────────────────
   SESSIONS RAIL (left sidebar)
   List of past + current agent sessions. Click resumes, "+" creates new.
   Width: 240px.
──────────────────────────────────────────────────────────────────────────── */
import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ListRestart, Loader2, MessageCircle, Plus, Search } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'
import type { AgentSession } from '../../lib/api'

interface SessionsRailProfile {
  title?: string
  searchPlaceholder?: string
  emptyLabel?: string
  newSessionTitle?: string
  refreshTitle?: string
  getTitle?: (session: AgentSession) => ReactNode
  getMeta?: (session: AgentSession) => ReactNode
  getSearchText?: (session: AgentSession) => string
}

interface Props {
  profile?: SessionsRailProfile
}

const DEFAULT_PROFILE: Required<Pick<SessionsRailProfile, 'title' | 'searchPlaceholder' | 'emptyLabel' | 'newSessionTitle' | 'refreshTitle'>> = {
  title: 'sesiones',
  searchPlaceholder: 'Buscar...',
  emptyLabel: 'sin sesiones',
  newSessionTitle: 'Nueva sesion',
  refreshTitle: 'Recargar',
}

export function SessionsRail({ profile = {} }: Props) {
  const { sessions, sessionId, sessionsLoading, sessionAction, refreshSessions, resumeSession, newSession } = useAgent()
  const [query, setQuery] = useState('')
  const cfg = { ...DEFAULT_PROFILE, ...profile }

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    if (!q) return sessions
    return sessions.filter(s => {
      const custom = profile.getSearchText?.(s)
      const text = custom ?? [
        s.title,
        s.preview,
        s.session_id,
        s.session_key,
        s.id,
        s.source,
      ].filter(Boolean).join(' ')
      return text.toLowerCase().includes(q)
    })
  }, [sessions, query, profile])

  async function handleNewSession() {
    await newSession()
  }

  async function resume(sessionKey: string) {
    await resumeSession(sessionKey)
    refreshSessions()
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(255,196,90,0.08)', background: 'rgba(255,196,90,0.005)', overflow: 'hidden' }}>
      <div style={{ height: 40, padding: '0 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, background: 'rgba(0,0,0,0.1)' }}>
        <div className="flex items-center gap-2">
            {sessionAction ? <Loader2 size={12} className="animate-spin" style={{ color: 'var(--ws-accent)' }} /> : <MessageCircle size={12} style={{ color: 'var(--ws-accent)' }} />}
          <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
            {cfg.title}
          </span>
          <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)', opacity: 0.55 }}>
            {sessions.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => refreshSessions()}
            className="ws-pill"
            style={{ padding: '2px 6px' }}
            title={cfg.refreshTitle}
            disabled={!!sessionAction}
          >
            {sessionAction === 'refresh' ? <Loader2 size={10} className="animate-spin" /> : <ListRestart size={10} />}
          </button>
          <button
            type="button"
            onClick={handleNewSession}
            className="ws-pill"
            data-active="true"
            style={{ padding: '2px 6px' }}
            title={cfg.newSessionTitle}
            disabled={!!sessionAction}
          >
            {sessionAction === 'new' ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
          </button>
        </div>
      </div>

      <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--ws-border)' }}>
        <div className="relative">
          <Search size={11} style={{
            position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--ws-text-muted)',
          }} />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={cfg.searchPlaceholder}
            className="field w-full text-[0.7rem]"
            style={{ padding: '5px 8px 5px 24px', borderRadius: 8 }}
          />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 6 }}>
        {sessionsLoading && sessions.length === 0 ? (
          <Loading label="cargando sesiones" />
        ) : filtered.length === 0 ? (
          <div className="text-center mono text-[0.6rem] uppercase tracking-widest py-6" style={{ color: 'var(--ws-text-muted)', opacity: 0.5 }}>
            {cfg.emptyLabel}
          </div>
        ) : (
          filtered.map((s, idx) => {
            const active = s.session_id === sessionId
            const key = s.session_key || s.session_id || s.id || String(idx)
            return (
              <button
                key={key}
                type="button"
                onClick={() => key && resume(key)}
                disabled={!!sessionAction}
                className="block w-full text-left rounded-md px-2.5 py-2 mb-1 transition-colors"
                style={{
                  borderLeft: `2px solid ${active ? 'var(--ws-accent)' : 'transparent'}`,
                  background: active ? 'rgba(255,196,90,0.06)' : 'transparent',
                  borderTop: 'none', borderRight: 'none', borderBottom: 'none',
                  borderRadius: 0,
                  opacity: sessionAction === 'resume' && !active ? 0.55 : 1,
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.025)' }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
              >
                <div className="text-[0.72rem] font-medium truncate" style={{ color: active ? 'var(--ws-accent)' : 'var(--ws-text)' }}>
                  {sessionTitle(s, profile)}
                </div>
                <div className="mono text-[0.55rem] mt-0.5 flex items-center gap-1.5" style={{ color: 'var(--ws-text-muted)', opacity: 0.7 }}>
                  {profile.getMeta?.(s) ?? (
                    <>
                      {s.message_count !== undefined && <span>{s.message_count} msg</span>}
                      {s.updated_at && <span>· {formatRel(s.updated_at)}</span>}
                    </>
                  )}
                </div>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

function Loading({ label }: { label: string }) {
  return (
    <div className="text-center mono text-[0.6rem] uppercase tracking-widest py-6 flex items-center justify-center gap-2" style={{ color: 'var(--ws-text-muted)', opacity: 0.65 }}>
      <Loader2 size={11} className="animate-spin" />
      {label}
    </div>
  )
}

function sessionTitle(session: AgentSession, profile: SessionsRailProfile): ReactNode {
  const custom = profile.getTitle?.(session)
  if (custom !== undefined && custom !== null) return custom
  return session.title || session.preview?.slice(0, 40) || '(generando titulo...)'
}

function formatRel(value: string | number): string {
  try {
    const d = typeof value === 'number'
      ? new Date(value < 10_000_000_000 ? value * 1000 : value)
      : new Date(value)
    const diff = (Date.now() - d.getTime()) / 1000
    if (diff < 60) return 'ahora'
    if (diff < 3600) return `${Math.floor(diff / 60)}m`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`
    if (diff < 604800) return `${Math.floor(diff / 86400)}d`
    return d.toLocaleDateString()
  } catch { return '' }
}
