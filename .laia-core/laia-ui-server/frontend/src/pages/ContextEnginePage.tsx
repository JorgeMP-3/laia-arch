import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronLeft, ChevronDown, Search, Settings2,
  Copy, Check, Terminal, GitBranch, BookOpen, RefreshCw, Loader2, Tag,
} from 'lucide-react'
import { api } from '../lib/api'
import type {
  ContextEngineConfig, InjectedData, InjectedNode,
  PrefetchData, PrefetchNodesData, SkillsData, SkillEntry,
} from '../lib/api'
import { kindClass } from '../lib/kind'

type Tab = 'session' | 'skills' | 'prefetch' | 'config'

// ── Small reusable pieces ─────────────────────────────────────────────────────

function CopyButton({ text, size = 'sm' }: { text: string; size?: 'sm' | 'xs' }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 rounded-lg transition-all"
      style={{
        padding: size === 'sm' ? '4px 10px' : '3px 8px',
        fontSize: size === 'sm' ? '0.7rem' : '0.65rem',
        background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.05)',
        color: copied ? '#4ade80' : 'var(--text-muted)',
      }}
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? 'Copiado' : 'Copiar'}
    </button>
  )
}

function CharBar({ used, max, pct }: { used: number; max: number; pct: number }) {
  const color = pct > 90 ? '#ef4444' : pct > 70 ? '#fbbf24' : '#22c55e'
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-28 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono tabular-nums" style={{ color }}>
        {used.toLocaleString('es-ES')} / {max.toLocaleString('es-ES')}
      </span>
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({pct}%)</span>
    </div>
  )
}

function SectionHeader({ children, border = true }: { children: React.ReactNode; border?: boolean }) {
  return (
    <div
      className="px-5 py-3 flex items-center gap-2"
      style={{ borderBottom: border ? '1px solid rgba(255,255,255,0.06)' : 'none' }}
    >
      {children}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-[0.65rem] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
      {children}
    </span>
  )
}

// ── Node row: manages its own expanded state (fixes the useState-in-map bug) ──

function NodeRow({ node }: { node: InjectedNode }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="border-b last:border-0" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-3 px-5 py-3 text-left transition-colors"
        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
        onMouseLeave={e => (e.currentTarget.style.background = '')}
      >
        <ChevronDown
          size={12}
          className="shrink-0 text-slate-600 transition-transform"
          style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
        <span className="flex-1 min-w-0 text-sm text-white font-medium truncate">{node.title}</span>
        <span className={`chip text-[0.62rem] ${kindClass(node.kind)}`}>{node.kind}</span>
        <span className="text-[0.65rem] font-mono tabular-nums shrink-0" style={{ color: 'var(--text-muted)' }}>
          {node.chars.toLocaleString('es-ES')} ch
        </span>
      </button>
      {expanded && (
        <div className="px-5 pb-4">
          <pre
            className="text-xs text-slate-400 font-mono whitespace-pre-wrap leading-relaxed rounded-xl p-4 overflow-y-auto"
            style={{ maxHeight: 220, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.05)' }}
          >
            {node.content}
          </pre>
        </div>
      )}
    </div>
  )
}

function WorkspaceGroup({
  workspace, nodes, activeWorkspace,
}: { workspace: string; nodes: InjectedNode[]; activeWorkspace: string }) {
  const [open, setOpen] = useState(true)
  const isActive = workspace === activeWorkspace
  return (
    <div className="border-b last:border-0" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2.5 px-5 py-3 text-left transition-colors"
        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
        onMouseLeave={e => (e.currentTarget.style.background = '')}
      >
        <ChevronDown
          size={12}
          className="shrink-0 text-slate-600 transition-transform"
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
        <span className="text-sm font-semibold text-white">{workspace}</span>
        {isActive && (
          <span
            className="text-[0.58rem] uppercase tracking-widest px-1.5 py-0.5 rounded-full font-semibold"
            style={{ background: 'rgba(255,196,90,0.12)', color: 'var(--brand)', border: '1px solid rgba(255,196,90,0.25)' }}
          >
            activo
          </span>
        )}
        <span className="ml-auto text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          {nodes.length} nodo{nodes.length !== 1 ? 's' : ''}
        </span>
      </button>
      {open && nodes.map((node, i) => <NodeRow key={i} node={node} />)}
    </div>
  )
}

// ── Skill card ────────────────────────────────────────────────────────────────

function SkillCategorySection({ category, skills }: { category: string; skills: SkillEntry[] }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="border-b last:border-0" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2.5 px-5 py-3 text-left"
        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
        onMouseLeave={e => (e.currentTarget.style.background = '')}
      >
        <ChevronDown
          size={12}
          className="shrink-0 text-slate-600 transition-transform"
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
        <span className="text-sm font-semibold text-white">{category}</span>
        <span className="ml-auto text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          {skills.length}
        </span>
      </button>
      {open && (
        <div className="pb-1">
          {skills.map((s, i) => (
            <div
              key={i}
              className="px-5 py-2.5 flex items-start gap-3 border-b last:border-0"
              style={{ borderColor: 'rgba(255,255,255,0.03)' }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <span className="text-sm text-white font-medium">{s.name}</span>
                  {s.tags.slice(0, 3).map((t, ti) => (
                    <span
                      key={ti}
                      className="text-[0.58rem] px-1.5 py-0.5 rounded-full"
                      style={{ background: 'rgba(255,196,90,0.08)', color: 'rgba(255,196,90,0.7)', border: '1px solid rgba(255,196,90,0.15)' }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
                {s.description && (
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>{s.description}</p>
                )}
              </div>
              <span className="text-[0.62rem] font-mono shrink-0 mt-0.5" style={{ color: 'rgba(255,255,255,0.2)' }}>
                {s.path}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Prefetch result row ───────────────────────────────────────────────────────

function PrefetchRow({ result }: { result: PrefetchData['results'][number] }) {
  const [expanded, setExpanded] = useState(false)
  const color = result.score >= 0.8 ? '#4ade80' : result.score >= 0.5 ? '#fbbf24' : '#94a3b8'
  return (
    <div className="border-b last:border-0" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-3 px-5 py-3 text-left"
        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
        onMouseLeave={e => (e.currentTarget.style.background = '')}
      >
        <ChevronDown
          size={12}
          className="shrink-0 text-slate-600 transition-transform"
          style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)' }}
        />
        <span className="flex-1 min-w-0 text-sm text-white font-medium truncate">{result.title}</span>
        <span
          className="text-[0.65rem] font-mono px-1.5 py-0.5 rounded shrink-0"
          style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}
        >
          {result.workspace}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-14 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <div className="h-full rounded-full" style={{ width: `${Math.min(result.score * 100, 100)}%`, background: color }} />
          </div>
          <span className="text-xs font-mono tabular-nums" style={{ color }}>{result.score.toFixed(2)}</span>
        </div>
      </button>
      {expanded && result.content && (
        <div className="px-5 pb-4">
          <pre
            className="text-xs text-slate-400 font-mono whitespace-pre-wrap leading-relaxed rounded-xl p-4 overflow-y-auto"
            style={{ maxHeight: 180, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.05)' }}
          >
            {result.content}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Syntax-highlighted instruction block ─────────────────────────────────────
// Data comes from our own Python code (hardcoded strings), so this is safe.

function highlight(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/`([^`]+)`/g, '<span style="color:#ffc45a;background:rgba(255,196,90,0.1);padding:1px 5px;border-radius:4px;font-family:monospace">$1</span>')
    .replace(/\bworkspace_\w+\b/g, '<span style="color:#c084fc;font-family:monospace">$&</span>')
    .replace(/workspace\.db|context\/|docs\/db-export\//g, '<span style="color:#4ade80;font-family:monospace">$&</span>')
    .replace(/\[WORKSPACES?[^\n]+]/g, '<span style="color:#fde68a;font-weight:600">$&</span>')
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ContextEnginePage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('session')
  const [config, setConfig] = useState<ContextEngineConfig | null>(null)
  const [injected, setInjected] = useState<InjectedData | null>(null)
  const [prefetchNodes, setPrefetchNodes] = useState<PrefetchNodesData | null>(null)
  const [skills, setSkills] = useState<SkillsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const [query, setQuery] = useState('')
  const [prefetchResults, setPrefetchResults] = useState<PrefetchData | null>(null)
  const [searching, setSearching] = useState(false)
  const [instructionOpen, setInstructionOpen] = useState(true)

  const searchRef = useRef<HTMLInputElement>(null)
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined)

  const loadAll = useCallback(async () => {
    try {
      const [cfg, inj, pfn, sk] = await Promise.all([
        api.getContextEngineConfig(),
        api.getContextEngineInjected(),
        api.getContextEnginePrefetchNodes(),
        api.getContextEngineSkills(),
      ])
      setConfig(cfg)
      setInjected(inj)
      setPrefetchNodes(pfn)
      setSkills(sk)
    } catch { /* show stale data */ }
  }, [])

  useEffect(() => {
    setLoading(true)
    loadAll().finally(() => setLoading(false))
  }, [loadAll])

  const refresh = async () => {
    setRefreshing(true)
    await loadAll()
    setRefreshing(false)
  }

  const runSearch = (q: string) => {
    clearTimeout(debounce.current)
    if (!q.trim()) { setPrefetchResults(null); return }
    debounce.current = setTimeout(async () => {
      setSearching(true)
      try { setPrefetchResults(await api.simulatePrefetch(q)) }
      catch { setPrefetchResults(null) }
      finally { setSearching(false) }
    }, 350)
  }

  const modeLabel = injected ? ({
    'index': 'Solo index',
    'all-indexes': 'Todos los índices',
  }[injected.inject_mode] ?? injected.inject_mode) : ''

  const configuredWorkspaces = config
    ? (config.workspaces?.length
      ? config.workspaces
      : Array.from(new Set([
        config.workspace,
        ...Object.keys(injected?.nodes_by_workspace ?? {}),
        ...(prefetchNodes?.nodes.map(node => node.workspace) ?? []),
      ])).filter(Boolean))
    : []
  const activeWorkspaces = config
    ? (config.active_workspaces?.length ? config.active_workspaces : [config.workspace]).filter(Boolean)
    : []
  const injectionModes = [
    {
      mode: 'index',
      title: 'Solo index',
      meta: 'Bajo contexto · bajo demanda',
      description: 'Inyecta únicamente el nodo index del workspace activo. Projects, topics e important se buscan con workspace_search_nodes cuando hacen falta.',
      ideal: 'Ideal: workspaces grandes, navegación limpia y contexto inicial pequeño',
    },
    {
      mode: 'all-indexes',
      title: 'Todos los índices',
      meta: 'Multi-workspace · lectura cruzada',
      description: 'Inyecta el nodo index de todos los workspaces configurados. El contenido detallado sigue cargándose bajo demanda con búsqueda y lectura de nodos.',
      ideal: 'Ideal: comparar proyectos, coordinar workspaces y mantener contexto global ligero',
    },
  ]

  const toggleActiveWorkspace = async (workspace: string) => {
    if (!config) return
    const current = config.active_workspaces?.length ? config.active_workspaces : [config.workspace]
    const next = current.includes(workspace)
      ? current.filter(name => name !== workspace)
      : [...current, workspace]
    setConfig({ ...config, active_workspaces: next })
    try {
      const result = await api.toggleWorkspaceActive(workspace)
      setConfig(result)
    } catch {
      setConfig(config)
    }
  }

  const TABS: { id: Tab; icon: React.ReactNode; label: string; count?: number }[] = [
    { id: 'session', icon: <Terminal size={13} />, label: 'Sesión' },
    { id: 'skills', icon: <BookOpen size={13} />, label: 'Skills', count: skills?.total },
    { id: 'prefetch', icon: <Search size={13} />, label: 'Prefetch' },
    { id: 'config', icon: <Settings2 size={13} />, label: 'Config' },
  ]

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="glass rounded-2xl p-12 flex items-center justify-center gap-3 text-slate-500 text-sm">
          <Loader2 size={16} className="animate-spin" /> Cargando contexto…
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">

      {/* Page header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/')}
          className="btn-ghost flex items-center justify-center h-9 w-9 rounded-lg"
          style={{ color: 'var(--text-muted)' }}
        >
          <ChevronLeft size={18} />
        </button>
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl shadow-lg ring-1 ring-white/10"
          style={{ background: 'linear-gradient(135deg, #7c3aed, #6d28d9, #4f46e5)' }}
        >
          <Terminal size={17} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white tracking-tight">Context Engine</h1>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Todo lo que se inyecta al agente — sesión, skills, prefetch
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="btn-ghost flex items-center gap-2 px-3 h-9 rounded-lg text-sm disabled:opacity-50"
          style={{ color: 'var(--text-muted)' }}
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">Refrescar</span>
        </button>
      </div>

      {/* Stats bar */}
      {injected && (
        <div className="flex flex-wrap gap-3 mb-6">
          <div className="glass rounded-xl px-4 py-2.5 flex items-center gap-2">
            <span className="text-[0.62rem] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Workspace</span>
            <span className="text-sm text-white font-mono font-semibold">{injected.workspace}</span>
          </div>
          <div className="glass rounded-xl px-4 py-2.5 flex items-center gap-2">
            <span className="text-[0.62rem] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Modo</span>
            <span className="text-sm font-semibold" style={{ color: 'var(--brand)' }}>{modeLabel}</span>
          </div>
          <div className="glass rounded-xl px-4 py-2.5 flex items-center gap-3 flex-1 min-w-64">
            <span className="text-[0.62rem] uppercase tracking-wider font-semibold shrink-0" style={{ color: 'var(--text-muted)' }}>Chars</span>
            <CharBar used={injected.total_chars} max={injected.max_chars} pct={injected.pct_used} />
          </div>
          <div className="glass rounded-xl px-4 py-2.5 flex items-center gap-2">
            <span className="text-[0.62rem] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>Nodos</span>
            <span className="text-sm text-white font-semibold">{injected.nodes_injected.length}</span>
          </div>
        </div>
      )}

      {/* Tab nav */}
      <div
        className="flex items-center gap-1 mb-6 p-1 rounded-xl"
        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
      >
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex items-center gap-1.5 px-4 h-9 rounded-lg text-xs font-medium transition-all"
            style={tab === t.id
              ? { background: 'rgba(255,196,90,0.12)', color: 'var(--brand)' }
              : { color: 'var(--text-muted)' }}
            onMouseEnter={e => { if (tab !== t.id) e.currentTarget.style.color = '#fff' }}
            onMouseLeave={e => { if (tab !== t.id) e.currentTarget.style.color = 'var(--text-muted)' }}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && (
              <span
                className="ml-0.5 text-[0.58rem] px-1.5 py-0.5 rounded-full font-mono"
                style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-muted)' }}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab: session ──────────────────────────────────────────────────────── */}
      {tab === 'session' && injected && (
        <div className="space-y-4">
          {/* System instruction */}
          <div className="glass rounded-2xl overflow-hidden">
            <button
              onClick={() => setInstructionOpen(v => !v)}
              className="w-full flex items-center gap-3 px-5 py-3.5 text-left transition-colors"
              style={{ borderBottom: instructionOpen ? '1px solid rgba(255,255,255,0.06)' : 'none' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')}
              onMouseLeave={e => (e.currentTarget.style.background = '')}
            >
              <Terminal size={13} style={{ color: 'var(--brand)' }} />
              <SectionLabel>Instrucción del sistema</SectionLabel>
              <span className="ml-auto text-[0.65rem] font-mono" style={{ color: 'var(--text-muted)' }}>
                {injected.instruction_chars.toLocaleString('es-ES')} chars
              </span>
              <span onClick={e => e.stopPropagation()}>
                <CopyButton text={injected.instruction} size="xs" />
              </span>
              <ChevronDown
                size={13}
                className="text-slate-600 transition-transform shrink-0"
                style={{ transform: instructionOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}
              />
            </button>
            {instructionOpen && (
              <div className="px-5 py-4">
                <pre
                  className="text-sm font-mono whitespace-pre-wrap leading-relaxed"
                  style={{ color: '#cbd5e1' }}
                  dangerouslySetInnerHTML={{ __html: highlight(injected.instruction) }}
                />
              </div>
            )}
          </div>

          {/* Nodes by workspace */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <GitBranch size={13} style={{ color: 'var(--text-muted)' }} />
              <SectionLabel>Nodos inyectados al inicio de sesión</SectionLabel>
            </SectionHeader>
            {Object.entries(injected.nodes_by_workspace).map(([ws, nodes]) => (
              <WorkspaceGroup key={ws} workspace={ws} nodes={nodes} activeWorkspace={injected.workspace} />
            ))}
            {injected.nodes_injected.length === 0 && (
              <p className="px-5 py-6 text-sm text-center" style={{ color: 'var(--text-muted)' }}>
                Sin nodos inyectados en este modo
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: skills ───────────────────────────────────────────────────────── */}
      {tab === 'skills' && skills && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="glass rounded-xl px-5 py-3 flex items-center gap-3">
            <BookOpen size={14} style={{ color: 'var(--brand)' }} />
            <span className="text-sm text-white font-semibold">{skills.total} skills disponibles</span>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              · {Object.keys(skills.by_category).length} categorías · todos indexados en el system prompt
            </span>
          </div>

          {/* By category */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <Tag size={13} style={{ color: 'var(--text-muted)' }} />
              <SectionLabel>Categorías</SectionLabel>
            </SectionHeader>
            {Object.entries(skills.by_category)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([cat, catSkills]) => (
                <SkillCategorySection key={cat} category={cat} skills={catSkills} />
              ))}
          </div>
        </div>
      )}

      {/* ── Tab: prefetch ─────────────────────────────────────────────────────── */}
      {tab === 'prefetch' && (
        <div className="space-y-4">
          {/* Search input */}
          <div className="glass rounded-2xl p-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-muted)' }} />
                <input
                  ref={searchRef}
                  value={query}
                  onChange={e => { setQuery(e.target.value); runSearch(e.target.value) }}
                  onKeyDown={e => e.key === 'Escape' && (setQuery(''), setPrefetchResults(null))}
                  placeholder="Escribe para simular qué nodos se cargarían…"
                  className="field w-full pl-11 pr-4 py-3 rounded-xl text-sm"
                  autoFocus
                />
              </div>
              {searching && <Loader2 size={16} className="animate-spin self-center" style={{ color: 'var(--text-muted)' }} />}
            </div>
            <p className="text-xs mt-2 px-1" style={{ color: 'var(--text-muted)' }}>
              Simula el prefetch dinámico: qué nodos cargaría el agente antes de responder a esta consulta.
            </p>
          </div>

          {/* Results */}
          {prefetchResults && (
            <div className="glass rounded-2xl overflow-hidden">
              <SectionHeader>
                <SectionLabel>
                  {prefetchResults.results.length > 0
                    ? `${prefetchResults.results.length} nodo${prefetchResults.results.length !== 1 ? 's' : ''} — score normalizado`
                    : 'Sin resultados para esta consulta'}
                </SectionLabel>
              </SectionHeader>
              {prefetchResults.results.map((r, i) => <PrefetchRow key={i} result={r} />)}
            </div>
          )}

          {/* Available nodes pool */}
          {prefetchNodes && prefetchNodes.nodes.length > 0 && (
            <div className="glass rounded-2xl overflow-hidden">
              <SectionHeader>
                <SectionLabel>Pool disponible — {prefetchNodes.nodes.length} nodos</SectionLabel>
              </SectionHeader>
              <div>
                {prefetchNodes.nodes.slice(0, 30).map((n, i) => (
                  <div
                    key={i}
                    className="px-5 py-2 flex items-center gap-3 border-b last:border-0"
                    style={{ borderColor: 'rgba(255,255,255,0.03)' }}
                  >
                    <span
                      className="text-[0.62rem] font-mono px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}
                    >
                      {n.workspace}
                    </span>
                    <span className="text-sm text-slate-300 flex-1 truncate">{n.title}</span>
                    <span className={`chip text-[0.62rem] shrink-0 ${kindClass(n.kind)}`}>{n.kind}</span>
                  </div>
                ))}
                {prefetchNodes.nodes.length > 30 && (
                  <div className="px-5 py-3 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                    +{prefetchNodes.nodes.length - 30} más — usa la búsqueda
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: config ───────────────────────────────────────────────────────── */}
      {tab === 'config' && config && (
        <div className="space-y-4">
          {/* Active values */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <Settings2 size={13} style={{ color: 'var(--text-muted)' }} />
              <SectionLabel>Configuración activa</SectionLabel>
            </SectionHeader>
            {([
              { key: 'workspace', label: 'Workspace activo', value: config.workspace },
              { key: 'inject_mode', label: 'Modo de inyección', value: config.inject_mode },
              { key: 'max_chars', label: 'Límite de caracteres', value: config.max_chars.toLocaleString('es-ES') },
            ] as const).map(({ key, label, value }) => (
              <div
                key={key}
                className="px-5 py-3.5 flex items-center gap-4 border-b last:border-0"
                style={{ borderColor: 'rgba(255,255,255,0.05)' }}
              >
                <span className="flex-1 text-sm text-white font-medium">{label}</span>
                <span className="font-mono text-sm font-semibold" style={{ color: 'var(--brand)' }}>{value}</span>
              </div>
            ))}
          </div>

          {/* Editable workspaces */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <GitBranch size={13} style={{ color: 'var(--text-muted)' }} />
              <SectionLabel>Workspaces editables</SectionLabel>
            </SectionHeader>
            {configuredWorkspaces.map(workspace => {
              const editable = activeWorkspaces.includes(workspace)
              return (
                <div
                  key={workspace}
                  className="px-5 py-3.5 flex items-center gap-3 border-b last:border-0"
                  style={{ borderColor: 'rgba(255,255,255,0.05)' }}
                >
                  <span className="flex-1 min-w-0 text-sm text-white font-mono font-semibold truncate">
                    {workspace}
                  </span>
                  <span
                    className="text-[0.58rem] uppercase tracking-widest px-2 py-1 rounded-full font-semibold shrink-0"
                    style={editable
                      ? { background: 'rgba(34,197,94,0.12)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.25)' }
                      : { background: 'rgba(148,163,184,0.08)', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.18)' }}
                  >
                    {editable ? 'EDITABLE' : 'SOLO LECTURA'}
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={editable}
                    onClick={() => void toggleActiveWorkspace(workspace)}
                    className="relative h-6 w-11 rounded-full transition-colors shrink-0"
                    style={{ background: editable ? 'rgba(34,197,94,0.55)' : 'rgba(148,163,184,0.18)' }}
                  >
                    <span
                      className="absolute top-1 h-4 w-4 rounded-full bg-white transition-all shadow"
                      style={{ left: editable ? 23 : 4 }}
                    />
                  </button>
                </div>
              )
            })}
            {configuredWorkspaces.length === 0 && (
              <p className="px-5 py-6 text-sm text-center" style={{ color: 'var(--text-muted)' }}>
                Sin workspaces configurados
              </p>
            )}
          </div>

          {/* Mode explanation */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <SectionLabel>Modo de inyección</SectionLabel>
            </SectionHeader>
            {injectionModes.map(mode => {
              const isActive = config.inject_mode === mode.mode
              return (
                <div
                  key={mode.mode}
                  className="px-5 py-4 border-b last:border-0"
                  style={{
                    borderColor: 'rgba(255,255,255,0.05)',
                    background: isActive ? 'rgba(255,196,90,0.04)' : 'transparent',
                  }}
                >
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="text-sm font-semibold text-white">{mode.title}</span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{mode.meta}</span>
                    {isActive && (
                      <span
                        className="text-[0.58rem] uppercase tracking-widest px-1.5 py-0.5 rounded-full font-semibold"
                        style={{ background: 'rgba(255,196,90,0.12)', color: 'var(--brand)', border: '1px solid rgba(255,196,90,0.25)' }}
                      >
                        activo
                      </span>
                    )}
                  </div>
                  <p className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
                    {mode.description}
                  </p>
                  <p className="text-xs" style={{ color: isActive ? 'rgba(74,222,128,0.75)' : 'rgba(148,163,184,0.7)' }}>{mode.ideal}</p>
                </div>
              )
            })}
          </div>

          {/* YAML snippet */}
          <div className="glass rounded-2xl overflow-hidden">
            <SectionHeader>
              <SectionLabel>config.yaml — fragmento copiable</SectionLabel>
              <span className="ml-auto">
                <CopyButton
                  text={`plugins:\n  workspace-context:\n    workspace: ${config.workspace}\n    inject_mode: ${config.inject_mode}\n    max_chars: ${config.max_chars}\n    active_workspaces:\n${activeWorkspaces.map(ws => `    - ${ws}`).join('\n') || '    - '}\n    workspaces:\n${configuredWorkspaces.map(ws => `    - ${ws}`).join('\n') || '    - '}`}
                />
              </span>
            </SectionHeader>
            <div className="px-5 py-4">
              <pre
                className="text-xs font-mono leading-relaxed rounded-xl p-4"
                style={{
                  background: 'rgba(0,0,0,0.45)',
                  border: '1px solid rgba(255,255,255,0.05)',
                  color: '#cbd5e1',
                }}
              >
{`plugins:
  workspace-context:
    workspace: `}<span style={{ color: 'var(--brand)' }}>{config.workspace}</span>{`
    inject_mode: `}<span style={{ color: '#4ade80' }}>{config.inject_mode}</span>{`
    max_chars: `}<span style={{ color: '#818cf8' }}>{config.max_chars}</span>{`
    active_workspaces:
${activeWorkspaces.map(ws => `    - ${ws}`).join('\n') || '    - '}
    workspaces:
${configuredWorkspaces.map(ws => `    - ${ws}`).join('\n') || '    - '}`}
              </pre>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
