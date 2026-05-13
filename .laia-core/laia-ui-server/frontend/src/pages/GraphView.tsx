import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useChatContext } from '../App'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ChevronLeft, X, Edit2, Eye, EyeOff } from 'lucide-react'
import { api } from '../lib/api'
import type { GraphData } from '../lib/api'
import { kindNodeColor, kindClass, KIND_NODE_COLOR } from '../lib/kind'

type NodeData = { label: string; kind: string }

function hexWithAlpha(hex: string, alpha: number) {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const KIND_ORDER: Record<string, number> = {
  index: 0, project: 1, topic: 2, important: 3,
  doc: 4, script: 5, reference: 6, 'agent-note': 7, 'agent-plan': 8, 'agent-log': 9, 'agent-node': 10, detail: 11,
}

const NODE_W    = 175
const NODE_H    = 40
const GAP_H     = 60
const GAP_V     = 20
const ROW_H     = 220
const CHILD_ROW = 160
const SECTION   = 100

/**
 * Semantic zone layout:
 *
 *  [topic-children] [topics] [left-projects] [INDEX] [right-projects] [orphan-docs/refs] [scripts] [agent]
 *                                                     [important ↓]
 *
 * Each project mirrors the same zone structure for its own children.
 */
function semanticZoneLayout(
  rawNodes: GraphData['nodes'],
  rawEdges: GraphData['edges'],
): RFNode<NodeData>[] {
  if (rawNodes.length === 0) return []

  const pos    = new Map<string, { x: number; y: number }>()
  const srcPos = new Map<string, Position>()
  const tgtPos = new Map<string, Position>()

  // Write position only once per node (first-write wins)
  function sp(id: string, x: number, y: number, src: Position, tgt: Position) {
    if (pos.has(id)) return
    pos.set(id, { x, y }); srcPos.set(id, src); tgtPos.set(id, tgt)
  }

  const isAgent = (k: string) => k === 'agent-note' || k === 'agent-plan' || k === 'agent-log' || k === 'agent-node'

  // Build adjacency map (parent → children)
  const childrenOf = new Map<string, string[]>()
  for (const n of rawNodes) childrenOf.set(n.id, [])
  for (const e of rawEdges) childrenOf.get(e.source)?.push(e.target)
  const nodeById = new Map(rawNodes.map(n => [n.id, n]))

  // ── index ──────────────────────────────────────────────────────────────────
  const indexNode = rawNodes.find(n => n.kind === 'index')
  if (indexNode) sp(indexNode.id, 0, 0, Position.Bottom, Position.Top)

  // ── project ownership: BFS from each project ──────────────────────────────
  const projectNodes = rawNodes.filter(n => n.kind === 'project')
  const projectOwnership = new Map<string, string>()
  for (const proj of projectNodes) {
    const q = [proj.id]; let h = 0
    while (h < q.length) {
      const id = q[h++]
      for (const child of childrenOf.get(id) ?? [])
        if (!projectOwnership.has(child) && child !== proj.id)
          { projectOwnership.set(child, proj.id); q.push(child) }
    }
  }

  // ── topic ownership: BFS from each topic ──────────────────────────────────
  const topicNodes = rawNodes.filter(n => n.kind === 'topic')
  const topicOwnership = new Map<string, string>()
  for (const topic of topicNodes) {
    const q = [topic.id]; let h = 0
    while (h < q.length) {
      const id = q[h++]
      for (const child of childrenOf.get(id) ?? []) {
        const cn = nodeById.get(child)
        if (!cn || cn.kind === 'project' || cn.kind === 'topic' || cn.kind === 'index') continue
        if (!topicOwnership.has(child)) { topicOwnership.set(child, topic.id); q.push(child) }
      }
    }
  }

  // ── compute extents per project ───────────────────────────────────────────
  // lExtent = horizontal space needed LEFT  of the project's left edge
  // rExtent = horizontal space needed RIGHT of the project's right edge
  const projExtents = new Map<string, { lExtent: number; rExtent: number }>()
  for (const proj of projectNodes) {
    const ownedTopics = topicNodes.filter(n => projectOwnership.get(n.id) === proj.id)
    const maxKids = ownedTopics.reduce((mx, t) => {
      const c = (childrenOf.get(t.id) ?? []).filter(cid => {
        const cn = nodeById.get(cid)
        return cn && cn.kind !== 'project' && cn.kind !== 'topic' && cn.kind !== 'index'
      }).length
      return Math.max(mx, c)
    }, 0)
    const lExtent = ownedTopics.length > 0
      ? SECTION + (maxKids + 1) * (NODE_W + GAP_H) + GAP_H
      : SECTION
    const hasDocs  = rawNodes.some(n => (n.kind === 'doc' || n.kind === 'reference') && projectOwnership.get(n.id) === proj.id && !topicOwnership.has(n.id))
    const hasScrip = rawNodes.some(n => n.kind === 'script' && projectOwnership.get(n.id) === proj.id)
    const hasAgent = rawNodes.some(n => isAgent(n.kind) && projectOwnership.get(n.id) === proj.id)
    const numR     = (hasDocs ? 1 : 0) + (hasScrip ? 1 : 0) + (hasAgent ? 1 : 0)
    const rExtent  = numR > 0 ? SECTION + numR * (NODE_W + GAP_H) + GAP_H : SECTION
    projExtents.set(proj.id, { lExtent, rExtent })
  }

  // ── split & place projects with dynamic spacing ───────────────────────────
  const sortedProjs = [...projectNodes].sort((a, b) => a.id.localeCompare(b.id))
  const half    = Math.ceil(sortedProjs.length / 2)
  const leftPs  = sortedProjs.slice(0, half).reverse() // closest to center first
  const rightPs = sortedProjs.slice(half)
  const projPos = new Map<string, { x: number; y: number }>()

  // Left side: cursor tracks the next available right boundary
  let cursorR = -GAP_H; let leftBound = -GAP_H
  for (const proj of leftPs) {
    const { lExtent, rExtent } = projExtents.get(proj.id)!
    const px = cursorR - rExtent - NODE_W
    const p = { x: px, y: ROW_H }
    pos.set(proj.id, p); projPos.set(proj.id, p)
    srcPos.set(proj.id, Position.Bottom); tgtPos.set(proj.id, Position.Top)
    leftBound = px - lExtent; cursorR = leftBound - GAP_H
  }

  // Right side: cursor tracks the next available left boundary
  let cursorL = NODE_W + GAP_H; let rightBound = NODE_W + GAP_H
  for (const proj of rightPs) {
    const { lExtent, rExtent } = projExtents.get(proj.id)!
    const px = cursorL + lExtent
    const p = { x: px, y: ROW_H }
    pos.set(proj.id, p); projPos.set(proj.id, p)
    srcPos.set(proj.id, Position.Bottom); tgtPos.set(proj.id, Position.Top)
    rightBound = px + NODE_W + rExtent; cursorL = rightBound + GAP_H
  }

  // ── global topics ──────────────────────────────────────────────────────────
  const globalTopics = topicNodes
    .filter(n => !projectOwnership.has(n.id))
    .sort((a, b) => a.id.localeCompare(b.id))
  const xTopics = leftBound < -GAP_H ? leftBound - SECTION - NODE_W : -SECTION - NODE_W
  const topicPos = new Map<string, { x: number; y: number }>()
  for (let i = 0; i < globalTopics.length; i++) {
    const p = { x: xTopics, y: ROW_H + i * (NODE_H + GAP_V) }
    pos.set(globalTopics[i].id, p); topicPos.set(globalTopics[i].id, p)
    srcPos.set(globalTopics[i].id, Position.Left); tgtPos.set(globalTopics[i].id, Position.Right)
  }

  // ── global topic children ─────────────────────────────────────────────────
  const isStructural = (k: string) => k === 'project' || k === 'topic' || k === 'index'
  for (const topic of globalTopics) {
    const tp = topicPos.get(topic.id)!
    ;(childrenOf.get(topic.id) ?? [])
      .filter(cid => { const cn = nodeById.get(cid); return cn && !isStructural(cn.kind) })
      .sort((a, b) => a.localeCompare(b))
      .forEach((cid, j) => sp(cid, tp.x - (j + 1) * (NODE_W + GAP_H), tp.y, Position.Left, Position.Right))
  }

  // ── global important ──────────────────────────────────────────────────────
  rawNodes
    .filter(n => n.kind === 'important' && !projectOwnership.has(n.id))
    .sort((a, b) => a.id.localeCompare(b.id))
    .forEach((n, i) => sp(n.id, 0, ROW_H * 2 + i * (NODE_H + GAP_V), Position.Bottom, Position.Top))

  // ── right-side orphan columns (sequential, only non-empty) ───────────────
  const xOBase = rightBound > NODE_W + GAP_H ? rightBound + SECTION : NODE_W + SECTION
  let xCol = xOBase

  const orphanDocs = rawNodes
    .filter(n => (n.kind === 'doc' || n.kind === 'reference') && !projectOwnership.has(n.id) && !topicOwnership.has(n.id))
    .sort((a, b) => a.id.localeCompare(b.id))
  if (orphanDocs.length) {
    orphanDocs.forEach((n, i) => sp(n.id, xCol, ROW_H + i * (NODE_H + GAP_V), Position.Right, Position.Left))
    xCol += NODE_W + GAP_H
  }

  rawNodes
    .filter(n => n.kind === 'script' && !projectOwnership.has(n.id))
    .sort((a, b) => a.id.localeCompare(b.id))
    .forEach((n, i) => { sp(n.id, xCol, ROW_H + i * (NODE_H + GAP_V), Position.Right, Position.Left) })
  const hasGlobalScripts = rawNodes.some(n => n.kind === 'script' && !projectOwnership.has(n.id))
  if (hasGlobalScripts) xCol += NODE_W + GAP_H

  rawNodes
    .filter(n => isAgent(n.kind) && !projectOwnership.has(n.id))
    .sort((a, b) => a.id.localeCompare(b.id))
    .forEach((n, i) => sp(n.id, xCol, ROW_H + i * (NODE_H + GAP_V), Position.Right, Position.Left))

  // ── sub-layout within each project ────────────────────────────────────────
  for (const proj of projectNodes) {
    const { x: px, y: py } = projPos.get(proj.id)!

    // Topics → left column
    const ownedTopics = topicNodes
      .filter(n => projectOwnership.get(n.id) === proj.id)
      .sort((a, b) => a.id.localeCompare(b.id))
    const xPT = px - SECTION - NODE_W
    const ownedTopicPos = new Map<string, { x: number; y: number }>()
    ownedTopics.forEach((t, i) => {
      if (pos.has(t.id)) return
      const p = { x: xPT, y: py + CHILD_ROW + i * (NODE_H + GAP_V) }
      pos.set(t.id, p); ownedTopicPos.set(t.id, p)
      srcPos.set(t.id, Position.Left); tgtPos.set(t.id, Position.Right)
    })

    // Children of project topics
    for (const topic of ownedTopics) {
      const tp = ownedTopicPos.get(topic.id); if (!tp) continue
      ;(childrenOf.get(topic.id) ?? [])
        .filter(cid => { const cn = nodeById.get(cid); return cn && !isStructural(cn.kind) })
        .sort((a, b) => a.localeCompare(b))
        .forEach((cid, j) => sp(cid, tp.x - (j + 1) * (NODE_W + GAP_H), tp.y, Position.Left, Position.Right))
    }

    // Right-side columns: sequential, skip empty buckets
    let xPR = px + NODE_W + SECTION

    const pDocs = rawNodes
      .filter(n => (n.kind === 'doc' || n.kind === 'reference') && projectOwnership.get(n.id) === proj.id && !topicOwnership.has(n.id))
      .sort((a, b) => a.id.localeCompare(b.id))
    if (pDocs.length) {
      pDocs.forEach((n, i) => sp(n.id, xPR, py + CHILD_ROW + i * (NODE_H + GAP_V), Position.Right, Position.Left))
      xPR += NODE_W + GAP_H
    }

    const pScripts = rawNodes
      .filter(n => n.kind === 'script' && projectOwnership.get(n.id) === proj.id)
      .sort((a, b) => a.id.localeCompare(b.id))
    if (pScripts.length) {
      pScripts.forEach((n, i) => sp(n.id, xPR, py + CHILD_ROW + i * (NODE_H + GAP_V), Position.Right, Position.Left))
      xPR += NODE_W + GAP_H
    }

    rawNodes
      .filter(n => isAgent(n.kind) && projectOwnership.get(n.id) === proj.id)
      .sort((a, b) => a.id.localeCompare(b.id))
      .forEach((n, i) => sp(n.id, xPR, py + CHILD_ROW + i * (NODE_H + GAP_V), Position.Right, Position.Left))

    // Important → below project center
    rawNodes
      .filter(n => n.kind === 'important' && projectOwnership.get(n.id) === proj.id)
      .sort((a, b) => a.id.localeCompare(b.id))
      .forEach((n, i) => sp(n.id, px, py + CHILD_ROW + i * (NODE_H + GAP_V), Position.Bottom, Position.Top))
  }

  // ── fallback for any unpositioned nodes ───────────────────────────────────
  let fbX = 0
  for (const n of rawNodes) {
    if (!pos.has(n.id)) {
      pos.set(n.id, { x: fbX, y: ROW_H * 4 })
      srcPos.set(n.id, Position.Bottom); tgtPos.set(n.id, Position.Top)
      fbX += NODE_W + GAP_H
    }
  }

  // ── build React Flow nodes ────────────────────────────────────────────────
  return rawNodes.map(n => {
    const color = kindNodeColor(n.kind)
    return {
      id: n.id,
      data: { label: n.label, kind: n.kind },
      position: pos.get(n.id)!,
      sourcePosition: srcPos.get(n.id) ?? Position.Bottom,
      targetPosition: tgtPos.get(n.id) ?? Position.Top,
      style: {
        background: `linear-gradient(135deg, ${hexWithAlpha(color, 0.2)}, ${hexWithAlpha(color, 0.08)})`,
        color: '#fff',
        border: `1px solid ${hexWithAlpha(color, 0.55)}`,
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 500,
        padding: '8px 12px',
        width: NODE_W,
        whiteSpace: 'nowrap' as const,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        boxShadow: `0 4px 16px -4px ${hexWithAlpha(color, 0.4)}, 0 1px 0 rgba(255,255,255,0.07) inset`,
      },
    }
  })
}

export default function GraphView() {
  const { ws } = useParams<{ ws: string }>()
  const navigate = useNavigate()
  const [raw, setRaw] = useState<GraphData | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode<NodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([])
  const [panel, setPanel] = useState<(NodeData & { id: string }) | null>(null)
  const [loading, setLoading] = useState(true)
  const [hiddenKinds, setHiddenKinds] = useState<Set<string>>(new Set())
  const [showLabels, setShowLabels] = useState(false)

  const { setNodeContext } = useChatContext()

  useEffect(() => {
    if (!ws) return
    let cancelled = false
    const sync = () => {
      if (cancelled) return
      api.getGraph(ws)
        .then(data => { if (!cancelled) setRaw(data) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    sync()
    const id = setInterval(sync, 10000)
    return () => { cancelled = true; clearInterval(id) }
  }, [ws])

  // Sync selected node with chat context
  useEffect(() => {
    if (panel) {
      setNodeContext({ title: panel.label, slug: panel.id, kind: panel.kind })
    } else {
      setNodeContext(null)
    }
  }, [panel, setNodeContext])

  useEffect(() => {
    if (!raw) return
    const visibleNodes = raw.nodes.filter(n => !hiddenKinds.has(n.kind))
    const visibleIds = new Set(visibleNodes.map(n => n.id))
    const visibleEdges = raw.edges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))

    setNodes(semanticZoneLayout(visibleNodes, visibleEdges))
    setEdges(
      visibleEdges.map((e, i) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        label: showLabels ? e.rel : undefined,
        animated: false,
        style: { stroke: 'rgba(255,196,90,0.28)', strokeWidth: 1.3 },
        labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 500 },
        labelBgStyle: { fill: '#0a0a0a', fillOpacity: 0.9 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: 'rgba(255,196,90,0.35)',
          width: 12,
          height: 12,
        },
      })),
    )
  }, [raw, hiddenKinds, showLabels, setNodes, setEdges])

  const onNodeClick: NodeMouseHandler<RFNode<NodeData>> = useCallback((_e, node) => {
    setPanel({ id: node.id, label: node.data.label, kind: node.data.kind })
  }, [])

  const kindCounts = useMemo(() => {
    const m: Record<string, number> = {}
    if (raw) for (const n of raw.nodes) m[n.kind] = (m[n.kind] ?? 0) + 1
    return m
  }, [raw])

  const toggleKind = (k: string) => {
    setHiddenKinds(s => {
      const n = new Set(s)
      if (n.has(k)) n.delete(k); else n.add(k)
      return n
    })
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      <div
        className="flex items-center gap-3 px-5 py-3 backdrop-blur-xl z-10"
        style={{ borderBottom: '1px solid var(--border)', background: 'rgba(5,5,5,0.85)' }}
      >
        <button
          onClick={() => navigate(`/ws/${ws}`)}
          className="btn-ghost flex items-center justify-center h-9 w-9 rounded-lg text-slate-300"
        >
          <ChevronLeft size={18} />
        </button>

        <div className="flex items-center gap-1.5 text-sm">
          <button onClick={() => navigate('/')} className="text-slate-600 hover:text-slate-300 transition-colors text-xs font-bold">LAIA</button>
          <span className="text-slate-700 text-xs">/</span>
          <button onClick={() => navigate('/workspaces')} className="text-slate-500 hover:text-slate-300 transition-colors text-xs">Nexus</button>
          <span className="text-slate-700 text-xs">/</span>
          <button onClick={() => navigate(`/ws/${ws}`)} className="text-slate-400 hover:text-slate-200 transition-colors text-xs">{ws}</button>
          <span className="text-slate-700 text-xs">/</span>
          <span className="text-white text-xs font-medium">Grafo</span>
        </div>

        {raw && (
          <div className="ml-3 flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="tabular-nums">{raw.nodes.length} nodos</span>
            <span className="text-slate-700">·</span>
            <span className="tabular-nums">{raw.edges.length} enlaces</span>
          </div>
        )}
        {loading && <span className="text-slate-500 text-xs">Cargando…</span>}

        <button
          onClick={() => setShowLabels(v => !v)}
          className="btn-ghost ml-auto flex items-center gap-2 px-3 h-9 rounded-lg text-xs text-slate-300"
        >
          {showLabels ? <EyeOff size={13} /> : <Eye size={13} />}
          {showLabels ? 'Ocultar' : 'Mostrar'} etiquetas
        </button>
      </div>

      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={() => setPanel(null)}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          proOptions={{ hideAttribution: false }}
        >
          <Background variant={BackgroundVariant.Dots} color="rgba(255,196,90,0.06)" gap={24} size={1} />
          <Controls showInteractive={false} position="bottom-left" />
          <MiniMap
            nodeColor={n => kindNodeColor((n.data as NodeData).kind)}
            nodeStrokeWidth={0}
            maskColor="rgba(5,5,5,0.78)"
            style={{ background: 'rgba(10,10,10,0.85)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}
            position="top-right"
          />
        </ReactFlow>

        {/* Kind filter legend */}
        {raw && Object.keys(kindCounts).length > 0 && (
          <div className="absolute top-4 left-4 glass rounded-xl p-3 min-w-44 fade-up">
            <div className="text-[0.62rem] uppercase tracking-wider font-semibold mb-2 px-1" style={{ color: 'var(--text-muted)' }}>
              Tipos — click para filtrar
            </div>
            <div className="flex flex-col gap-0.5">
              {Object.keys(kindCounts)
                .sort((a, b) => (KIND_ORDER[a] ?? 99) - (KIND_ORDER[b] ?? 99))
                .map(k => {
                  const hidden = hiddenKinds.has(k)
                  return (
                    <button
                      key={k}
                      onClick={() => toggleKind(k)}
                      className={`flex items-center gap-2 px-2 py-1 rounded-md text-xs transition-all ${hidden ? 'opacity-35' : ''}`}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,196,90,0.06)')}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{
                          background: KIND_NODE_COLOR[k] ?? '#64748b',
                          boxShadow: `0 0 5px ${hexWithAlpha(KIND_NODE_COLOR[k] ?? '#64748b', 0.6)}`,
                        }}
                      />
                      <span className="text-slate-200 flex-1 text-left">{k}</span>
                      <span className="tabular-nums" style={{ color: 'var(--text-muted)' }}>{kindCounts[k]}</span>
                    </button>
                  )
                })}
            </div>
          </div>
        )}

        {/* Node detail panel */}
        {panel && (
          <div className="absolute top-4 right-4 w-72 glass rounded-2xl p-5 shadow-2xl shadow-black/60 z-10 fade-up">
            <div className="flex items-start justify-between mb-4">
              <span className={`chip ${kindClass(panel.kind)}`}>{panel.kind}</span>
              <button onClick={() => setPanel(null)} className="text-slate-500 hover:text-amber-300 transition-colors">
                <X size={16} />
              </button>
            </div>
            <p className="text-white text-base font-semibold mb-1 leading-snug tracking-tight">{panel.label}</p>
            <p className="mono text-xs mb-5 break-all" style={{ color: 'var(--text-muted)' }}>{panel.id}</p>
            <button
              onClick={() => navigate(`/ws/${ws}/nodes/${panel.id}`)}
              className="btn-primary flex items-center justify-center gap-2 w-full px-3 py-2 rounded-lg text-white text-sm font-medium"
            >
              <Edit2 size={13} /> Editar nodo
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
