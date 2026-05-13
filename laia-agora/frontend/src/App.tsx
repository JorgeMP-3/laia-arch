import { useState, createContext, useContext, useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation, useNavigate, Navigate } from 'react-router-dom'
import { NeuralBackground } from './components/NeuralBackground'
import Home from './pages/Home'
import WorkspaceList from './pages/WorkspaceList'
import NodeBrowser from './pages/NodeBrowser'
import NodeEditor from './pages/NodeEditor'
import GraphView from './pages/GraphView'
import ContextEnginePage from './pages/ContextEnginePage'
import Login from './pages/Login'
import Setup from './pages/Setup'
import { initServerUrl } from './lib/tauri'
import { toolForPath } from './lib/toolRegistry'
import { isLoggedIn, getAuth, clearAuth } from './lib/auth'

// ── Chat context — shares current node/page context with the chat ──────────────
interface ChatContextValue {
  nodeContext: { title: string; slug: string; kind: string } | null
  setNodeContext: (c: { title: string; slug: string; kind: string } | null) => void
}
const ChatContext = createContext<ChatContextValue>({
  nodeContext: null,
  setNodeContext: () => {},
})
export const useChatContext = () => useContext(ChatContext)

function Header() {
  const navigate = useNavigate()
  const auth = getAuth()

  function handleLogout() {
    clearAuth()
    navigate('/login', { replace: true })
  }

  return (
    <header
      style={{ background: 'rgba(5,5,5,0.75)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}
      className="sticky top-0 z-30 backdrop-blur-xl"
    >
      <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center gap-1">
        <button
          onClick={() => navigate('/')}
          className="group font-semibold tracking-tight text-sm hover:opacity-80 transition-opacity"
        >
          <span className="font-black" style={{ color: 'var(--brand)' }}>
            AGORA
          </span>
        </button>
        <span className="text-slate-700 text-sm mx-1.5">·</span>
        <button
          onClick={() => navigate('/workspaces')}
          className="text-sm font-medium hover:opacity-80 transition-opacity"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--brand)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          Nexus
        </button>

        <div className="ml-auto flex items-center gap-4">
          {auth && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {auth.username}
            </span>
          )}
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: 'var(--brand)', boxShadow: '0 0 8px rgba(255,196,90,0.6)' }}
            />
            <span>online</span>
          </div>
          <button
            onClick={handleLogout}
            className="text-xs hover:opacity-80 transition-opacity"
            style={{ color: 'var(--text-muted)' }}
          >
            Salir
          </button>
        </div>
      </div>
    </header>
  )
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />
  return <>{children}</>
}

function Layout() {
  const loc = useLocation()
  const [nodeContext, setNodeContext] = useState<{ title: string; slug: string; kind: string } | null>(null)
  const currentTool = toolForPath(loc.pathname)

  const isHome = loc.pathname === '/'
  const isGraph = loc.pathname.includes('/graph')
  const isLogin = loc.pathname === '/login'

  const hideHeader = isHome || isGraph || isLogin
  const hasOfficialAgentChat = currentTool?.capabilities.includes('agentChat') ?? false

  return (
    <ChatContext.Provider value={{ nodeContext, setNodeContext }}>
      <div className="app-bg" style={{ color: 'var(--text-main)' }}>
        <NeuralBackground />
        {!hideHeader && <Header />}
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
          <Route path="/workspaces" element={<RequireAuth><WorkspaceList /></RequireAuth>} />
          <Route path="/ws/:ws" element={<RequireAuth><NodeBrowser /></RequireAuth>} />
          <Route path="/ws/:ws/new" element={<RequireAuth><NodeEditor /></RequireAuth>} />
          <Route path="/ws/:ws/nodes/:slug" element={<RequireAuth><NodeEditor /></RequireAuth>} />
          <Route path="/ws/:ws/graph" element={<RequireAuth><GraphView /></RequireAuth>} />
          <Route path="/context-engine" element={<RequireAuth><ContextEnginePage /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {!hasOfficialAgentChat && null}
      </div>
    </ChatContext.Provider>
  )
}

export default function App() {
  const [ready, setReady] = useState(false)
  const [needsSetup, setNeedsSetup] = useState(false)

  useEffect(() => {
    initServerUrl().then(({ needsSetup }) => {
      setNeedsSetup(needsSetup)
      setReady(true)
    })
  }, [])

  if (!ready) return null

  if (needsSetup) {
    return <Setup onDone={() => setNeedsSetup(false)} />
  }

  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}
