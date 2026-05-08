import { useState, createContext, useContext, useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { NeuralBackground } from './components/NeuralBackground'
import Home from './pages/Home'
import WorkspaceList from './pages/WorkspaceList'
import NodeBrowser from './pages/NodeBrowser'
import NodeEditor from './pages/NodeEditor'
import GraphView from './pages/GraphView'
import ContextEnginePage from './pages/ContextEnginePage'
import CommandCenter from './pages/CommandCenter'
import Setup from './pages/Setup'
import { initServerUrl } from './lib/tauri'
import { toolForPath } from './lib/toolRegistry'

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
          <span
            className="font-black"
            style={{
              color: 'var(--brand)',
            }}
          >
            LAIA
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

        <div className="ml-auto flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--brand)', boxShadow: '0 0 8px rgba(255,196,90,0.6)' }}
          />
          <span>API online</span>
        </div>
      </div>
    </header>
  )
}

function Layout() {
  const loc = useLocation()
  const [nodeContext, setNodeContext] = useState<{ title: string; slug: string; kind: string } | null>(null)
  const currentTool = toolForPath(loc.pathname)

  const isHome = loc.pathname === '/'
  const isGraph = loc.pathname.includes('/graph')
  const isCommandCenter = loc.pathname === '/command-center'

  const hideHeader = isHome || isGraph || isCommandCenter
  const hasOfficialAgentChat = currentTool?.capabilities.includes('agentChat') ?? false

  return (
    <ChatContext.Provider value={{ nodeContext, setNodeContext }}>
      <div className="app-bg" style={{ color: 'var(--text-main)' }}>
        <NeuralBackground />
        {!hideHeader && <Header />}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/workspaces" element={<WorkspaceList />} />
          <Route path="/ws/:ws" element={<NodeBrowser />} />
          <Route path="/ws/:ws/new" element={<NodeEditor />} />
          <Route path="/ws/:ws/nodes/:slug" element={<NodeEditor />} />
          <Route path="/ws/:ws/graph" element={<GraphView />} />
          <Route path="/context-engine" element={<ContextEnginePage />} />
          <Route path="/command-center" element={<CommandCenter />} />
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
    return (
      <Setup
        onDone={() => {
          setNeedsSetup(false)
        }}
      />
    )
  }

  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}
