import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Boxes, GitBranch, Clock, ArrowUpRight, Layers, ChevronLeft } from 'lucide-react'
import { api } from '../lib/api'
import type { Workspace } from '../lib/api'
import { relativeTime } from '../lib/time'

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

export default function WorkspaceList() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    const sync = () => {
      if (cancelled) return
      api.getWorkspaces()
        .then(ws => { if (!cancelled) setWorkspaces(ws) })
        .catch(e => { if (!cancelled) setError(e.message) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    sync()
    const id = setInterval(sync, 8000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const totals = useMemo(() => workspaces.reduce(
    (acc, w) => ({ nodes: acc.nodes + w.node_count, edges: acc.edges + w.edge_count }),
    { nodes: 0, edges: 0 }
  ), [workspaces])

  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      {/* Hero */}
      <div className="mb-10 fade-up">
        <button
          onClick={() => navigate('/')}
          className="btn-ghost inline-flex items-center gap-1.5 text-xs mb-6 px-2 h-7 rounded-lg"
          style={{ color: 'var(--text-muted)' }}
        >
          <ChevronLeft size={13} /> LAIA
        </button>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight mb-3">
          <span className="text-gradient">Nexus</span>
        </h1>
        <p className="text-slate-400 max-w-2xl leading-relaxed">
          Cada workspace es una base de conocimiento con sus nodos y las relaciones entre ellos.
          Explora, edita o visualiza el grafo.
        </p>

        {/* Stats bar */}
        {!loading && !error && workspaces.length > 0 && (
          <div className="mt-7 grid grid-cols-3 gap-3 max-w-xl">
            <Stat icon={<Layers size={15} />} label="Workspaces" value={workspaces.length} />
            <Stat icon={<Boxes size={15} />}  label="Nodos totales" value={totals.nodes} />
            <Stat icon={<GitBranch size={15} />} label="Enlaces"  value={totals.edges} />
          </div>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass rounded-2xl h-44 animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <div className="glass rounded-2xl p-6 text-red-300">Error: {error}</div>
      ) : workspaces.length === 0 ? (
        <div className="glass rounded-2xl p-10 text-center text-slate-400">
          No hay workspaces todavía.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {workspaces.map((ws, i) => (
            <button
              key={ws.name}
              onClick={() => navigate(`/ws/${ws.name}`)}
              style={{ animationDelay: `${i * 45}ms` }}
              className="group fade-up text-left glass glass-hover rounded-2xl p-5 relative overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-2xl"
            >
              {/* Gradient glow corner */}
              <div className={`absolute -top-16 -right-16 w-40 h-40 rounded-full bg-gradient-to-br ${gradientFor(ws.name)} opacity-15 group-hover:opacity-30 blur-2xl transition-opacity`} />

              <div className="relative flex items-start justify-between mb-4">
                <div className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${gradientFor(ws.name)} shadow-lg ring-1 ring-white/15`}>
                  <span className="text-white font-bold text-sm uppercase tracking-wide">
                    {ws.name.slice(0, 2)}
                  </span>
                </div>
                <ArrowUpRight size={18} className="text-slate-500 group-hover:text-amber-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </div>

              <h3 className="relative text-lg font-semibold text-white group-hover:text-amber-100 transition-colors mb-1 tracking-tight truncate">
                {ws.name}
              </h3>
              <p className="relative text-xs text-slate-500 flex items-center gap-1.5 mb-4">
                <Clock size={11} />
                {relativeTime(ws.updated_at)}
              </p>

              <div className="relative flex gap-4 pt-4 border-t border-slate-700/50">
                <div className="flex items-center gap-1.5 text-xs">
                  <Boxes size={13} className="text-slate-400" />
                  <span className="text-slate-300 font-semibold tabular-nums">{ws.node_count}</span>
                  <span className="text-slate-500">nodos</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs">
                  <GitBranch size={13} className="text-slate-400" />
                  <span className="text-slate-300 font-semibold tabular-nums">{ws.edge_count}</span>
                  <span className="text-slate-500">enlaces</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="glass rounded-xl px-4 py-3">
      <div className="flex items-center gap-1.5 text-[0.65rem] uppercase tracking-wider text-slate-500 mb-1">
        <span className="text-slate-400">{icon}</span>
        {label}
      </div>
      <div className="text-xl font-semibold text-white tabular-nums">{value.toLocaleString('es-ES')}</div>
    </div>
  )
}
