/* ────────────────────────────────────────────────────────────────────────────
   HOME — LAIA landing + transition + Workspace
   ----------------------------------------------------------------------------
   Two stacked sections in one scroll:
     1) LANDING (top, dark amber theme)         → hero "LAIA" + app cards
     2) THRESHOLD (dramatic warp transition)    → grid tilt, scanline, color
     3) WORKSPACE (bottom, dark cyan theme)     → full agent control center

   The transition is driven by `scrollProgress` (0 → 1). Edit the numeric
   stops below to retime fades. The two themes coexist in the same DOM tree;
   the Workspace lives inside `.workspace-theme` so its CSS variables take
   over (see index.css).
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUp,
  Boxes,
  ChevronDown,
  ChevronRight,
  Cpu,
  GitBranch,
  Layers,
  Network,
  Terminal,
  Zap,
} from 'lucide-react'
import { api } from '../lib/api'
import type { ContextEngineConfig, InjectedData, Workspace as WorkspaceMeta } from '../lib/api'
import { Workspace } from '../components/workspace/Workspace'
import { ToolShell } from '../components/common/ToolShell'
import { workspaceToolArea } from '../lib/contexts/workspaceContext'

interface AppDef {
  id: string
  name: string
  tagline: string
  description: string
  icon: ReactNode
  href?: string
  status: 'active' | 'soon'
  gradient: string
  accentColor?: string
}

const APPS: AppDef[] = [
  {
    id: 'core',
    name: 'Core',
    tagline: 'Agent Control',
    description: 'Runtime, sesiones, comandos, modelos y modos. Todo lo que controla a Laia en un solo panel.',
    icon: <Cpu size={22} />,
    status: 'active',
    href: '#workspace',
    gradient: 'from-cyan-300 via-cyan-400 to-teal-500',
    accentColor: '#67e8f9',
  },
  {
    id: 'nexus',
    name: 'Nexus',
    tagline: 'Knowledge Graph',
    description: 'Workspaces con nodos y relaciones. Navega, edita y visualiza tu base de conocimiento en grafo.',
    icon: <Network size={22} />,
    href: '/workspaces',
    status: 'active',
    gradient: 'from-amber-400 via-orange-400 to-yellow-300',
    accentColor: '#ffc45a',
  },
  {
    id: 'memoria',
    name: 'Context Engine',
    tagline: 'Injected Context',
    description: 'Ver qué nodos e instrucciones se inyectan al agente en cada sesión. Simular prefetch y diagnosticar el flujo DB-first.',
    icon: <Terminal size={22} />,
    href: '/context-engine',
    status: 'active',
    gradient: 'from-violet-400 via-purple-500 to-indigo-500',
    accentColor: '#a78bfa',
  },
  {
    id: 'command-center',
    name: 'Command Center',
    tagline: 'Multi-Agent Control',
    description: 'LAIA + sub-agentes en paralelo. Cada agente en su propio terminal PTY. Inyecta prompts desde el panel principal.',
    icon: <Layers size={22} />,
    href: '/command-center',
    status: 'active',
    gradient: 'from-green-400 via-emerald-400 to-teal-400',
    accentColor: '#34d399',
  },
]

function clamp(n: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, n))
}

function AppCard({
  app,
  delay,
  onClick,
  stats,
}: {
  app: AppDef
  delay: number
  onClick?: () => void
  stats?: { icon: ReactNode; label: string }[]
}) {
  const isActive = app.status === 'active'
  const accent = app.accentColor ?? 'var(--brand)'
  return (
    <button
      onClick={onClick}
      disabled={!isActive}
      style={{ animationDelay: `${delay}ms` }}
      className={`fade-up group relative flex min-h-56 flex-col overflow-hidden rounded-xl p-5 text-left transition-all duration-200 ${
        isActive ? 'glass glass-hover cursor-pointer hover:-translate-y-1 hover:shadow-2xl' : 'glass cursor-default opacity-40'
      }`}
    >
      <div
        className={`absolute -right-16 -top-16 h-44 w-44 rounded-full bg-gradient-to-br ${app.gradient} blur-2xl transition-opacity duration-300 ${
          isActive ? 'opacity-20 group-hover:opacity-30' : 'opacity-5'
        }`}
      />
      <div className="relative mb-4 flex items-start justify-between">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${app.gradient} shadow-lg ring-1 ring-white/15`}
          style={{
            color: '#fff',
            opacity: isActive ? 0.95 : 0.55,
          }}
        >
          {app.icon}
        </div>
        {isActive ? (
          <ChevronRight size={16} className="text-slate-500 transition-all group-hover:translate-x-0.5" style={{ color: accent }} />
        ) : (
          <span
            className="rounded-full px-2 py-0.5 text-[0.6rem] uppercase tracking-widest"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}
          >
            soon
          </span>
        )}
      </div>
      <h3 className="relative mb-0.5 text-base font-bold tracking-tight text-white">{app.name}</h3>
      <p className="relative mb-2.5 text-[0.63rem] font-semibold uppercase tracking-widest" style={{ color: isActive ? accent : 'var(--text-muted)' }}>
        {app.tagline}
      </p>
      <p className="relative text-xs leading-relaxed text-slate-500">{app.description}</p>
      {stats && stats.length > 0 && (
        <div className="relative mt-auto flex flex-wrap gap-3 pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          {stats.map((stat, i) => (
            <span key={i} className="flex items-center gap-1 text-[0.65rem] text-slate-400">
              <span className="text-slate-500">{stat.icon}</span>
              {stat.label}
            </span>
          ))}
        </div>
      )}
      {(!stats || stats.length === 0) && (
        <div className="relative mt-auto pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <span className="text-[0.65rem] uppercase tracking-widest" style={{ color: accent }}>
            Disponible
          </span>
        </div>
      )}
    </button>
  )
}

export default function Home() {
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([])
  const [ctxConfig, setCtxConfig] = useState<ContextEngineConfig | null>(null)
  const [ctxInjected, setCtxInjected] = useState<InjectedData | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [scrollProgress, setScrollProgress] = useState(0)

  useEffect(() => {
    let cancelled = false
    const sync = () => {
      if (cancelled) return
      Promise.all([
        api.getWorkspaces(),
        api.getContextEngineConfig(),
        api.getContextEngineInjected(),
      ])
        .then(([ws, cfg, inj]) => {
          if (cancelled) return
          setWorkspaces(ws)
          setCtxConfig(cfg)
          setCtxInjected(inj)
        })
        .catch(() => { if (!cancelled) setWorkspaces([]) })
        .finally(() => { if (!cancelled) setLoaded(true) })
    }
    sync()
    const id = setInterval(sync, 10000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual'
    window.scrollTo(0, 0)
  }, [])

  useEffect(() => {
    const onScroll = () => setScrollProgress(clamp(window.scrollY / Math.max(1, window.innerHeight * 0.95)))
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Lock body scroll once the workspace is fully visible (no accidental scrolling)
  useEffect(() => {
    if (scrollProgress >= 0.98) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [scrollProgress])

  function enterWorkspace() {
    window.scrollTo({ top: window.innerHeight, behavior: 'smooth' })
  }

  function backToHome() {
    document.body.style.overflow = ''
    requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    })
  }

  const totalNodes = workspaces.reduce((sum, ws) => sum + ws.node_count, 0)
  const totalEdges = workspaces.reduce((sum, ws) => sum + ws.edge_count, 0)
  const contextMode = 'index'

  const appStats = useMemo(() => ({
    nexus: loaded ? [
      { icon: <Layers size={11} />, label: `${workspaces.length} workspaces` },
      { icon: <Boxes size={11} />, label: `${totalNodes} nodos` },
      { icon: <GitBranch size={11} />, label: `${totalEdges} enlaces` },
    ] : undefined,
    memoria: ctxInjected && ctxConfig ? [
      { icon: <Terminal size={11} />, label: contextMode },
      { icon: <Boxes size={11} />, label: `${ctxInjected.nodes_injected.length} nodos` },
      { icon: <Zap size={11} />, label: `${ctxInjected.pct_used}% chars` },
    ] : undefined,
  }), [contextMode, ctxConfig, ctxInjected, loaded, totalEdges, totalNodes, workspaces.length])

  return (
    <ToolShell profile={workspaceToolArea} state={undefined} style={{ minHeight: '100vh' }}>
      <div className="relative">

        {/* ──────────────────────────────────────────────────────────────────
           SECTION 1 · LAIA LANDING (intro)
           Dark amber palette. The grid behind warps as the user scrolls.
        ────────────────────────────────────────────────────────────────── */}
        <section
          className="relative z-10 flex flex-col items-center justify-center px-5"
          style={{
            minHeight: '100vh',
            opacity: 1 - scrollProgress * 0.7,
            transform: `translateY(${-scrollProgress * 80}px) scale(${1 - scrollProgress * 0.06})`,
            pointerEvents: scrollProgress > 0.6 ? 'none' : 'auto',
          }}
        >
          {/* Perspective grid: tilts and dives as you scroll */}
          <div
            className="pointer-events-none fixed inset-0"
            style={{
              opacity: 0.18 + scrollProgress * 0.32,
              backgroundImage: `
                linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)
              `,
              backgroundSize: '72px 72px',
              transform: `perspective(900px) rotateX(${scrollProgress * 55}deg) translateY(${scrollProgress * -160}px) scale(${1 + scrollProgress * 0.4})`,
              transformOrigin: '50% 0%',
              zIndex: 0,
            }}
          />

          <div className="fade-up text-center relative z-10">
            <h1
              className="select-none leading-none flex flex-col items-center"
              style={{ fontFamily: "'Space Grotesk', sans-serif" }}
            >
              <span
                className="text-9xl sm:text-[11rem]"
                style={{
                  fontWeight: 700,
                  letterSpacing: '0.18em',
                  color: '#ffc45a',
                }}
              >
                LAIA
              </span>
              <span
                className="text-2xl sm:text-3xl"
                style={{
                  fontWeight: 300,
                  fontStyle: 'italic',
                  letterSpacing: '1.1em',
                  marginTop: '-0.1em',
                  background: 'linear-gradient(135deg, #67e8f9 0%, #a78bfa 40%, #34d399 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                ARCH
              </span>
            </h1>
            <p className="mt-5 text-sm font-medium uppercase tracking-widest text-slate-500">
              Local AI Agent Infrastructure
            </p>
          </div>

          <div className="mt-14 mb-10 grid w-full max-w-5xl grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 relative z-10">
            {APPS.map((app, i) => (
              <AppCard
                key={app.id}
                app={app}
                delay={i * 80}
                onClick={app.href === '#workspace' ? enterWorkspace : (app.href ? () => navigate(app.href!) : undefined)}
                stats={app.id === 'nexus' ? appStats.nexus : app.id === 'memoria' ? appStats.memoria : undefined}
              />
            ))}
          </div>

          <button
            type="button"
            onClick={enterWorkspace}
            className="absolute bottom-8 flex flex-col items-center gap-2 text-[0.65rem] uppercase tracking-widest cursor-pointer"
            style={{ color: 'rgba(255,255,255,0.4)' }}
          >
            <div className="h-12 w-px" style={{ background: 'linear-gradient(transparent, rgba(255,196,90,0.55))' }} />
            <span>Enter control space</span>
            <ChevronDown size={13} className="animate-bounce" style={{ color: 'var(--brand)' }} />
          </button>
        </section>

        {/* ──────────────────────────────────────────────────────────────────
           SECTION 2 · BLIND TRANSITION
           12 venetian-blind strips sweep top→bottom, closing over the hero.
           Once fully shut they fade out, revealing the workspace below.
           Pure amber brand — no cyan anywhere.
        ────────────────────────────────────────────────────────────────── */}
        {Array.from({ length: 12 }, (_, i) => {
          const start = 0.18 + i * (0.50 / 11)
          const end   = start + 0.13
          const sy    = clamp((scrollProgress - start) / (end - start))
          const fade  = 1 - clamp((scrollProgress - 0.83) / 0.12)
          return (
            <div
              key={i}
              className="pointer-events-none fixed inset-x-0 z-20"
              style={{
                top: `${(i / 12) * 100}vh`,
                height: `${100 / 12}vh`,
                transformOrigin: 'top',
                transform: `scaleY(${sy})`,
                opacity: fade,
                background: i % 2 === 0 ? '#060402' : '#070503',
                borderTop: sy > 0.02 ? '1px solid rgba(255,196,90,0.18)' : 'none',
                boxShadow: sy > 0.02 ? 'inset 0 1px 0 rgba(255,196,90,0.06)' : 'none',
              }}
            />
          )
        })}

        {/* ──────────────────────────────────────────────────────────────────
           SECTION 3 · WORKSPACE (control center)
           Renders behind the blinds; revealed when they fade out.
           Lives inside .workspace-theme so CSS variables flip.
        ────────────────────────────────────────────────────────────────── */}
        <section
          id="workspace"
          className="relative z-10"
          style={{
            opacity: clamp((scrollProgress - 0.42) / 0.43),
            transform: `translateY(${(1 - clamp((scrollProgress - 0.45) / 0.38)) * 50}px)`,
          }}
        >
          <Workspace />
        </section>

        {/* Floating "back to home" button — visible once workspace is in view */}
        {scrollProgress > 0.5 && (
          <button
            type="button"
            onClick={backToHome}
            title="Volver al inicio"
            style={{
              position: 'fixed',
              top: 16,
              right: 16,
              zIndex: 100,
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: 'rgba(20, 14, 4, 0.85)',
              border: '1px solid rgba(255, 196, 90, 0.25)',
              color: '#ffc45a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              backdropFilter: 'blur(10px)',
              boxShadow: '0 4px 14px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,196,90,0.08) inset',
              transition: 'all 160ms cubic-bezier(0.22, 1, 0.36, 1)',
              opacity: clamp((scrollProgress - 0.5) / 0.3),
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(40, 28, 8, 0.92)'
              e.currentTarget.style.borderColor = 'rgba(255, 196, 90, 0.5)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(20, 14, 4, 0.85)'
              e.currentTarget.style.borderColor = 'rgba(255, 196, 90, 0.25)'
            }}
          >
            <ArrowUp size={16} />
          </button>
        )}
      </div>
    </ToolShell>
  )
}
