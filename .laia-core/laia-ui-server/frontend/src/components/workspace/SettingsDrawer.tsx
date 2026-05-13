/* ────────────────────────────────────────────────────────────────────────────
   SETTINGS DRAWER
   Customization panel — palette, layout, panels.
   Persisted to localStorage under "laia.workspace.settings".
   Live-applies CSS variables on the .workspace-theme container.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react'
import { Calendar, Monitor, Palette, Plus, Settings2, Trash2, User, X } from 'lucide-react'
import { api } from '../../lib/api'
import { isTauri, setAlwaysOnTop } from '../../lib/tauri'

export interface WorkspaceSettings {
  accent: string
  accentDark: string
  bg: string
  bgElevated: string
  layout: 'three-col' | 'two-col-right' | 'two-col-left' | 'centered'
  showSessions: boolean
  showSidePanels: boolean
  density: 'compact' | 'comfortable'
}

export const DEFAULT_SETTINGS: WorkspaceSettings = {
  accent: '#ffc45a',
  accentDark: '#e0a830',
  bg: '#060400',
  bgElevated: '#0a0700',
  layout: 'three-col',
  showSessions: true,
  showSidePanels: true,
  density: 'comfortable',
}

const STORAGE_KEY = 'laia.workspace.settings.v2'

const PALETTES: { id: string; name: string; accent: string; accentDark: string; bg: string; bgElevated: string }[] = [
  { id: 'amber',   name: 'Amber (default)',      accent: '#ffc45a', accentDark: '#e0a830', bg: '#060400', bgElevated: '#0a0700' },
  { id: 'amber2',  name: 'Amber warm',          accent: '#fbbf24', accentDark: '#d97706', bg: '#0a0a0a', bgElevated: '#11110d' },
  { id: 'violet',  name: 'Violet',              accent: '#c4b5fd', accentDark: '#8b5cf6', bg: '#0c0a14', bgElevated: '#13101e' },
  { id: 'emerald', name: 'Emerald',             accent: '#86efac', accentDark: '#22c55e', bg: '#080d0a', bgElevated: '#0d1410' },
  { id: 'rose',    name: 'Rose',                accent: '#fda4af', accentDark: '#e11d48', bg: '#0e0a0d', bgElevated: '#15101a' },
]

const LAYOUTS: { id: WorkspaceSettings['layout']; label: string; cols: string }[] = [
  { id: 'three-col',     label: 'Tres columnas',                cols: '240px 1fr 320px' },
  { id: 'two-col-right', label: 'Solo trace (sin sesiones)',    cols: '1fr 320px' },
  { id: 'two-col-left',  label: 'Solo sesiones (sin paneles)',  cols: '240px 1fr' },
  { id: 'centered',      label: 'Solo chat',                    cols: '1fr' },
]

export function loadSettings(): WorkspaceSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) as Partial<WorkspaceSettings> }
  } catch { return DEFAULT_SETTINGS }
}

export function saveSettings(s: WorkspaceSettings) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)) } catch { /* ignore */ }
}

export function applySettings(s: WorkspaceSettings, root: HTMLElement | null = document.documentElement) {
  if (!root) return
  root.style.setProperty('--ws-accent', s.accent)
  root.style.setProperty('--ws-accent-dark', s.accentDark)
  root.style.setProperty('--ws-accent-glow', hexToRgba(s.accent, 0.32))
  root.style.setProperty('--ws-bg', s.bg)
  root.style.setProperty('--ws-bg-elevated', s.bgElevated)
  root.style.setProperty('--ws-border-strong', hexToRgba(s.accent, 0.18))
}

function hexToRgba(hex: string, alpha: number): string {
  const m = hex.replace('#', '').match(/.{1,2}/g)
  if (!m || m.length < 3) return `rgba(0,0,0,${alpha})`
  const [r, g, b] = m.slice(0, 3).map(s => parseInt(s, 16))
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function getLayoutCols(layout: WorkspaceSettings['layout'], showSessions: boolean, showSidePanels: boolean): string {
  // Effective columns derived from layout + visibility flags
  if (layout === 'centered') return '1fr'
  if (layout === 'two-col-left' || (!showSidePanels && showSessions)) return '240px 1fr'
  if (layout === 'two-col-right' || (showSidePanels && !showSessions)) return '1fr 320px'
  if (!showSidePanels && !showSessions) return '1fr'
  return '240px 1fr 320px'
}

interface Props {
  open: boolean
  onClose: () => void
  settings: WorkspaceSettings
  onChange: (s: WorkspaceSettings) => void
}

export function SettingsDrawer({ open, onClose, settings, onChange }: Props) {
  const [draft, setDraft] = useState<WorkspaceSettings>(settings)

  useEffect(() => { setDraft(settings) }, [settings, open])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function commit(next: Partial<WorkspaceSettings>) {
    const merged = { ...draft, ...next }
    setDraft(merged)
    onChange(merged)
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        className="ws-card flex flex-col"
        style={{
          width: '100%', maxWidth: 380, height: '100vh',
          borderLeftWidth: 1, borderRightWidth: 0, borderTopWidth: 0, borderBottomWidth: 0,
          borderRadius: 0,
        }}
        onClick={e => e.stopPropagation()}
      >
        <div className="ws-card-header">
          <div className="flex items-center gap-2">
            <Settings2 size={13} style={{ color: 'var(--ws-accent)' }} />
            <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-text-muted)' }}>
              personalizar workspace
            </span>
          </div>
          <button type="button" onClick={onClose} className="ws-pill" style={{ padding: '3px 6px' }}>
            <X size={11} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {/* PALETTE */}
          <Section icon={<Palette size={11} />} title="paleta">
            <div className="grid grid-cols-1 gap-2">
              {PALETTES.map(p => {
                const isActive = draft.accent === p.accent
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => commit({ accent: p.accent, accentDark: p.accentDark, bg: p.bg, bgElevated: p.bgElevated })}
                    className="flex items-center gap-2 p-2 rounded-md transition-colors"
                    style={{
                      background: isActive ? 'rgba(255,255,255,0.04)' : 'transparent',
                      border: `1px solid ${isActive ? p.accent : 'var(--ws-border)'}`,
                    }}
                  >
                    <span style={{ width: 16, height: 16, borderRadius: 4, background: p.accent, boxShadow: `0 0 8px ${p.accent}66` }} />
                    <span style={{ width: 16, height: 16, borderRadius: 4, background: p.bg, border: '1px solid var(--ws-border)' }} />
                    <span className="text-[0.72rem]" style={{ color: 'var(--ws-text)' }}>{p.name}</span>
                  </button>
                )
              })}
            </div>

            <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <ColorInput label="Acento" value={draft.accent} onChange={v => commit({ accent: v })} />
              <ColorInput label="Background" value={draft.bg} onChange={v => commit({ bg: v })} />
            </div>
          </Section>

          {/* LAYOUT */}
          <Section title="layout">
            <div className="flex flex-col gap-1">
              {LAYOUTS.map(l => (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => commit({ layout: l.id })}
                  className="flex items-center justify-between p-2 rounded-md text-left transition-colors"
                  style={{
                    background: draft.layout === l.id ? 'rgba(255,196,90,0.08)' : 'transparent',
                    border: `1px solid ${draft.layout === l.id ? 'rgba(255,196,90,0.25)' : 'var(--ws-border)'}`,
                  }}
                >
                  <span className="text-[0.72rem]" style={{ color: draft.layout === l.id ? 'var(--ws-accent)' : 'var(--ws-text)' }}>
                    {l.label}
                  </span>
                  <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
                    {l.cols}
                  </span>
                </button>
              ))}
            </div>
          </Section>

          {/* PANELS */}
          <Section title="paneles">
            <Toggle label="Sidebar de sesiones" on={draft.showSessions} onClick={() => commit({ showSessions: !draft.showSessions })} />
            <Toggle label="Panel de trace/edits" on={draft.showSidePanels} onClick={() => commit({ showSidePanels: !draft.showSidePanels })} />
          </Section>

          {/* DENSITY */}
          <Section title="densidad">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => commit({ density: 'compact' })}
                className="p-2 rounded-md text-[0.72rem]"
                style={{
                  background: draft.density === 'compact' ? 'rgba(255,196,90,0.08)' : 'transparent',
                  border: `1px solid ${draft.density === 'compact' ? 'rgba(255,196,90,0.25)' : 'var(--ws-border)'}`,
                  color: draft.density === 'compact' ? 'var(--ws-accent)' : 'var(--ws-text)',
                }}
              >
                Compacta
              </button>
              <button
                type="button"
                onClick={() => commit({ density: 'comfortable' })}
                className="p-2 rounded-md text-[0.72rem]"
                style={{
                  background: draft.density === 'comfortable' ? 'rgba(255,196,90,0.08)' : 'transparent',
                  border: `1px solid ${draft.density === 'comfortable' ? 'rgba(255,196,90,0.25)' : 'var(--ws-border)'}`,
                  color: draft.density === 'comfortable' ? 'var(--ws-accent)' : 'var(--ws-text)',
                }}
              >
                Cómoda
              </button>
            </div>
          </Section>

          {isTauri() && (
            <Section icon={<Monitor size={11} />} title="ventana">
              <WindowSection />
            </Section>
          )}

          <Section icon={<User size={11} />} title="personalidad">
            <PersonalitySection />
          </Section>

          <Section icon={<Calendar size={11} />} title="cron jobs">
            <CronSection />
          </Section>

          <Section title="restablecer">
            <button
              type="button"
              onClick={() => commit(DEFAULT_SETTINGS)}
              className="btn-ghost w-full p-2 rounded-md text-[0.72rem]"
              style={{ color: 'var(--ws-text-muted)' }}
            >
              Volver a valores por defecto
            </button>
          </Section>

          <div className="text-[0.6rem] mt-6 leading-relaxed" style={{ color: 'var(--ws-text-muted)', opacity: 0.55 }}>
            Los ajustes se guardan en este navegador. Para extender la paleta edita
            <span className="mono"> src/index.css </span>
            (variables <span className="mono">--ws-*</span>) o este componente para añadir más opciones.
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ icon, title, children }: { icon?: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div className="mono text-[0.55rem] uppercase tracking-widest mb-2 flex items-center gap-1.5" style={{ color: 'var(--ws-text-muted)' }}>
        {icon}{title}
      </div>
      {children}
    </div>
  )
}

function ColorInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[0.6rem]" style={{ color: 'var(--ws-text-muted)' }}>{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ width: 30, height: 28, border: '1px solid var(--ws-border)', borderRadius: 6, background: 'transparent' }}
        />
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          className="field text-[0.7rem] mono flex-1"
          style={{ padding: '4px 8px', borderRadius: 6 }}
        />
      </div>
    </label>
  )
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="flex items-center justify-between w-full p-2 rounded-md mb-1.5"
      style={{ border: '1px solid var(--ws-border)' }}>
      <span className="text-[0.72rem]" style={{ color: 'var(--ws-text)' }}>{label}</span>
      <span className="ws-toggle" data-on={on ? 'true' : 'false'} />
    </button>
  )
}

// ── Window controls (Tauri only) ─────────────────────────────────────────────

function WindowSection() {
  const [alwaysOnTop, setAlwaysOnTopState] = useState(false)

  async function toggle() {
    const next = !alwaysOnTop
    setAlwaysOnTopState(next)
    await setAlwaysOnTop(next)
  }

  return (
    <div className="flex flex-col gap-1">
      <Toggle label="Siempre encima (always on top)" on={alwaysOnTop} onClick={toggle} />
      <p className="text-[0.6rem] mt-0.5" style={{ color: 'var(--ws-text-muted)' }}>
        La ventana flotará sobre todas las demás apps. Atajo: <span className="mono">⌘⇧L</span> para mostrar/ocultar.
      </p>
    </div>
  )
}

// ── Personality picker ───────────────────────────────────────────────────────

interface PersonalityEntry { name: string; prompt_preview?: string }

function PersonalitySection() {
  const [items, setItems] = useState<PersonalityEntry[]>([])
  const [current, setCurrent] = useState<string>('')
  const [loading, setLoading] = useState(false)

  function refresh() {
    setLoading(true)
    api.getPersonalities()
      .then((d: Record<string, unknown>) => {
        const arr = (d.personalities as PersonalityEntry[]) || []
        setItems(arr)
        setCurrent(String(d.current || ''))
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  async function pick(name: string) {
    try { await api.setPersonality(name); setCurrent(name) } catch { /* ignore */ }
  }

  if (loading && items.length === 0) {
    return <div className="text-[0.65rem]" style={{ color: 'var(--ws-text-muted)' }}>cargando…</div>
  }
  if (items.length === 0) {
    return (
      <div className="text-[0.65rem]" style={{ color: 'var(--ws-text-muted)' }}>
        Sin personalidades configuradas. Añádelas en <span className="mono">~/.laia/config.yaml</span> bajo <span className="mono">agent.personalities</span>.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      {items.map(p => (
        <button
          key={p.name}
          type="button"
          onClick={() => pick(p.name)}
          className="flex flex-col items-start p-2 rounded-md text-left"
          style={{
            background: p.name === current ? 'rgba(196,181,253,0.08)' : 'transparent',
            border: `1px solid ${p.name === current ? 'rgba(196,181,253,0.3)' : 'var(--ws-border)'}`,
          }}
        >
          <span className="text-[0.72rem]" style={{ color: p.name === current ? 'var(--ws-violet)' : 'var(--ws-text)' }}>
            {p.name}
          </span>
          {p.prompt_preview && (
            <span className="text-[0.6rem] mt-0.5 line-clamp-2" style={{ color: 'var(--ws-text-muted)' }}>
              {p.prompt_preview}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

// ── Cron jobs panel ──────────────────────────────────────────────────────────

interface CronJob {
  id?: string
  name?: string
  schedule?: string
  prompt?: string
  status?: string
  enabled?: boolean
}

function CronSection() {
  const [jobs, setJobs] = useState<CronJob[]>([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newSchedule, setNewSchedule] = useState('')
  const [newPrompt, setNewPrompt] = useState('')

  function refresh() {
    setLoading(true)
    api.getCronJobs()
      .then((d: Record<string, unknown>) => {
        const arr = (d.jobs as CronJob[]) || (d.cronjobs as CronJob[]) || []
        setJobs(Array.isArray(arr) ? arr : [])
      })
      .catch(() => setJobs([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  async function createJob() {
    if (!newName || !newSchedule || !newPrompt) return
    try {
      await api.createCronJob(newSchedule, newPrompt, newName)
      setNewName(''); setNewSchedule(''); setNewPrompt(''); setShowAdd(false)
      refresh()
    } catch { /* ignore */ }
  }

  async function remove(jobId: string) {
    if (!confirm(`Eliminar tarea cron "${jobId}"?`)) return
    try { await api.deleteCronJob(jobId); refresh() } catch { /* ignore */ }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center mb-1">
        <span className="mono text-[0.55rem]" style={{ color: 'var(--ws-text-muted)' }}>
          {loading ? 'cargando…' : `${jobs.length} tareas`}
        </span>
        <button
          type="button"
          onClick={() => setShowAdd(s => !s)}
          className="ws-pill"
          style={{ padding: '2px 6px' }}
        >
          <Plus size={9} /> nueva
        </button>
      </div>

      {showAdd && (
        <div className="flex flex-col gap-1.5 p-2 rounded-md mb-1"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ws-border)' }}>
          <input
            type="text"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="nombre"
            className="field text-[0.7rem]"
            style={{ padding: '4px 8px', borderRadius: 6 }}
          />
          <input
            type="text"
            value={newSchedule}
            onChange={e => setNewSchedule(e.target.value)}
            placeholder="schedule  (e.g. 0 9 * * *)"
            className="field text-[0.7rem] mono"
            style={{ padding: '4px 8px', borderRadius: 6 }}
          />
          <textarea
            value={newPrompt}
            onChange={e => setNewPrompt(e.target.value)}
            placeholder="prompt al agente…"
            rows={2}
            className="field text-[0.7rem] resize-none"
            style={{ padding: '4px 8px', borderRadius: 6 }}
          />
          <div className="flex gap-1">
            <button
              type="button"
              onClick={createJob}
              disabled={!newName || !newSchedule || !newPrompt}
              className="btn-primary text-[0.65rem] flex-1 py-1 rounded"
            >
              crear
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="btn-ghost text-[0.65rem] px-3 py-1 rounded"
              style={{ color: 'var(--ws-text-muted)' }}
            >
              cancelar
            </button>
          </div>
        </div>
      )}

      {jobs.length === 0 && !loading && !showAdd && (
        <div className="text-[0.65rem] py-2" style={{ color: 'var(--ws-text-muted)' }}>
          Sin tareas programadas.
        </div>
      )}

      {jobs.map(j => (
        <div
          key={j.id || j.name}
          className="flex items-center justify-between gap-2 p-2 rounded-md"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--ws-border)' }}
        >
          <div className="flex-1 min-w-0">
            <div className="text-[0.7rem]" style={{ color: 'var(--ws-text)' }}>{j.name || j.id}</div>
            <div className="mono text-[0.55rem] truncate" style={{ color: 'var(--ws-text-muted)' }}>
              {j.schedule} · {j.status || (j.enabled ? 'on' : 'off')}
            </div>
          </div>
          <button
            type="button"
            onClick={() => remove(j.id || j.name || '')}
            className="ws-pill"
            style={{ padding: '2px 6px', color: 'var(--ws-danger)' }}
            title="Eliminar"
          >
            <Trash2 size={9} />
          </button>
        </div>
      ))}
    </div>
  )
}
