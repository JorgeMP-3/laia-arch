import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Search, Plus, Network, ChevronLeft, Boxes, SlidersHorizontal, X } from 'lucide-react'
import { api } from '../lib/api'
import type { NodeSummary, SearchResult } from '../lib/api'
import { Toast } from '../components/Toast'
import type { ToastMessage } from '../components/Toast'
import { WorkspaceActions } from '../components/WorkspaceActions'
import { kindClass, ALL_KINDS } from '../lib/kind'
import { relativeTime } from '../lib/time'

type Row = NodeSummary | SearchResult

const GRADIENTS = [
  'from-amber-400 via-orange-400 to-yellow-300',
  'from-emerald-400 via-teal-500 to-cyan-500',
  'from-pink-500 via-rose-500 to-orange-400',
  'from-amber-500 via-yellow-400 to-lime-400',
  'from-violet-500 via-fuchsia-500 to-pink-500',
  'from-amber-400 via-amber-300 to-yellow-200',
  'from-lime-400 via-emerald-500 to-teal-600',
]
function gradientFor(name: string) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return GRADIENTS[h % GRADIENTS.length]
}

export default function NodeBrowser() {
  const { ws } = useParams<{ ws: string }>()
  const navigate = useNavigate()
  const [nodes, setNodes] = useState<NodeSummary[]>([])
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [kindFilter, setKindFilter] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const searchRef = useRef<HTMLInputElement>(null)
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined)
  const toastId = useRef(0)

  const dismissToast = useCallback((id: number) => {
    setToasts(items => items.filter(item => item.id !== id))
  }, [])

  const pushToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = ++toastId.current
    setToasts(items => [...items, { ...toast, id }])
    window.setTimeout(() => dismissToast(id), 5200)
  }, [dismissToast])

  const loadNodes = useCallback(async () => {
    if (!ws) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const loaded = await api.getNodes(ws)
      setNodes(loaded)
    } catch (error) {
      pushToast({
        tone: 'error',
        title: 'No se pudieron cargar los nodos',
        message: error instanceof Error ? error.message : String(error),
      })
    } finally {
      setLoading(false)
    }
  }, [pushToast, ws])

  useEffect(() => {
    void loadNodes()
    const id = setInterval(() => { void loadNodes() }, 8000)
    return () => clearInterval(id)
  }, [loadNodes])

  // Global keyboard shortcut: "/" focuses search
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const handleSearch = (q: string) => {
    setQuery(q)
    clearTimeout(debounce.current)
    if (!q.trim()) { setResults(null); return }
    debounce.current = setTimeout(async () => {
      if (!ws) return
      const r = await api.searchNodes(ws, q).catch(() => [])
      setResults(r)
    }, 300)
  }

  const baseRows: Row[] = results ?? nodes
  const rows = useMemo(
    () => kindFilter ? baseRows.filter(r => r.kind === kindFilter) : baseRows,
    [baseRows, kindFilter]
  )
  const isSearch = results !== null

  const kindCounts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const n of nodes) m[n.kind] = (m[n.kind] ?? 0) + 1
    return m
  }, [nodes])

  return (
    <>
      <Toast items={toasts} onDismiss={dismissToast} />
      <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-7">
        <button
          onClick={() => navigate('/workspaces')}
          className="btn-ghost flex items-center justify-center h-9 w-9 rounded-lg text-slate-300 hover:text-white"
          aria-label="Volver"
        >
          <ChevronLeft size={18} />
        </button>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${ws ? gradientFor(ws) : ''} shadow-lg ring-1 ring-white/15`}>
          <span className="text-white font-bold text-sm uppercase">{ws?.slice(0, 2)}</span>
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white tracking-tight truncate">{ws}</h1>
          <p className="text-xs text-slate-500">{nodes.length} nodos</p>
        </div>
        <button
          onClick={() => navigate(`/ws/${ws}/graph`)}
          className="btn-ghost flex items-center gap-2 px-3.5 h-9 rounded-lg text-sm text-slate-200"
        >
          <Network size={15} /> <span className="hidden sm:inline">Grafo</span>
        </button>
        {ws && (
          <WorkspaceActions
            ws={ws}
            onToast={pushToast}
            onMigrated={() => { void loadNodes() }}
          />
        )}
        <button
          onClick={() => navigate(`/ws/${ws}/new`)}
          className="btn-primary flex items-center gap-2 px-4 h-9 rounded-lg text-sm text-white font-medium"
        >
          <Plus size={15} /> <span>Nuevo nodo</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        <input
          ref={searchRef}
          value={query}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Buscar en título, contenido, tags…"
          className="field w-full pl-11 pr-20 py-3 rounded-xl text-sm"
        />
        {query ? (
          <button
            onClick={() => handleSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 h-6 w-6 flex items-center justify-center rounded text-slate-500 hover:text-white hover:bg-slate-700/60"
          >
            <X size={13} />
          </button>
        ) : (
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[0.65rem] rounded font-mono" style={{ color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)' }}>/</kbd>
        )}
      </div>

      {/* Kind filter chips */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <div className="flex items-center gap-1.5 text-xs text-slate-500 mr-1">
          <SlidersHorizontal size={12} /> Filtrar:
        </div>
        <button
          onClick={() => setKindFilter(null)}
          className={`chip transition-colors ring-1 ring-inset ${!kindFilter ? 'text-white' : 'hover:text-white'}`}
          style={!kindFilter ? { background: 'rgba(255,196,90,0.12)', borderColor: 'rgba(255,196,90,0.35)', color: '#fff' } : { background: 'rgba(255,255,255,0.04)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
        >
          Todos <span className="tabular-nums opacity-70">{nodes.length}</span>
        </button>
        {ALL_KINDS.filter(k => kindCounts[k]).map(k => (
          <button
            key={k}
            onClick={() => setKindFilter(kindFilter === k ? null : k)}
            className={`chip transition-all ${kindFilter === k ? kindClass(k) : 'ring-1 ring-inset hover:text-white'}`}
            style={kindFilter === k ? {} : { background: 'rgba(255,255,255,0.04)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
          >
            {k} <span className="tabular-nums opacity-70">{kindCounts[k]}</span>
          </button>
        ))}
      </div>

      {/* Body */}
      {loading ? (
        <div className="glass rounded-2xl p-10 text-center text-slate-400 text-sm">Cargando nodos…</div>
      ) : (
        <>
          <div className="text-xs text-slate-500 mb-3 flex items-center gap-1.5">
            <Boxes size={12} />
            {isSearch ? `${rows.length} resultados` : `${rows.length} nodos${kindFilter ? ` · ${kindFilter}` : ''}`}
          </div>
          <div className="glass rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700/60 text-[0.68rem] text-slate-400 uppercase tracking-wider">
                  <th className="text-left px-5 py-3 w-32">Tipo</th>
                  <th className="text-left px-5 py-3">Título</th>
                  <th className="text-left px-5 py-3 hidden md:table-cell w-56">Slug</th>
                  <th className="text-left px-5 py-3 hidden lg:table-cell w-32">Actualizado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr
                    key={row.slug}
                    onClick={() => navigate(`/ws/${ws}/nodes/${row.slug}`)}
                    className={`group cursor-pointer transition-colors border-b last:border-0 ${i % 2 === 1 ? '' : ''}`}
                    style={{ borderColor: 'rgba(255,255,255,0.06)', background: i % 2 === 1 ? 'rgba(255,255,255,0.015)' : undefined }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,196,90,0.04)')}
                    onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 1 ? 'rgba(255,255,255,0.015)' : '')}
                  >
                    <td className="px-5 py-3.5">
                      <span className={`chip ${kindClass(row.kind)}`}>
                        {row.kind}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="text-white font-medium group-hover:text-amber-200 transition-colors truncate">{row.title}</div>
                      {row.summary && (
                        <div className="text-xs text-slate-500 mt-0.5 truncate">{row.summary}</div>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 mono text-xs hidden md:table-cell truncate">{row.slug}</td>
                    <td className="px-5 py-3.5 text-slate-500 text-xs hidden lg:table-cell">
                      {'updated_at' in row ? relativeTime(row.updated_at) : ''}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-14 text-center text-slate-500">
                      {isSearch ? 'Sin resultados para esta búsqueda' : kindFilter ? `No hay nodos de tipo "${kindFilter}"` : 'Workspace vacío — crea tu primer nodo'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
      </div>

    </>
  )
}
