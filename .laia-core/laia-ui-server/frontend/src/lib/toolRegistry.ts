import { createElement, type ReactNode } from 'react'
import { Boxes, Cpu, Network, Terminal, Zap } from 'lucide-react'
import { commandCenterToolArea } from './contexts/commandCenterContext'
import { workspaceToolArea } from './contexts/workspaceContext'
import type { ToolAreaProfile } from '../components/common/ToolAreaProvider'

export type ToolCapability =
  | 'agentChat'
  | 'terminalPty'
  | 'workspaceDb'
  | 'contextEngine'
  | 'fileEdits'
  | 'approvals'

export interface LaiaToolDefinition<S = any> {
  areaId: string
  route: string
  label: string
  tagline: string
  description: string
  icon: ReactNode
  status: 'active' | 'soon'
  capabilities: ToolCapability[]
  toolArea?: ToolAreaProfile<S>
}

export const LAIA_TOOLS: LaiaToolDefinition[] = [
  {
    areaId: 'workspace',
    route: '/',
    label: 'Core',
    tagline: 'Agent Control',
    description: 'Runtime, sesiones, comandos, modelos y modos. Todo lo que controla a Laia en un solo panel.',
    icon: createElement(Cpu, { size: 22 }),
    status: 'active',
    capabilities: ['agentChat', 'fileEdits', 'approvals'],
    toolArea: workspaceToolArea,
  },
  {
    areaId: 'nexus',
    route: '/workspaces',
    label: 'Nexus',
    tagline: 'Knowledge Graph',
    description: 'Workspaces con nodos y relaciones. Base de conocimiento DB-first.',
    icon: createElement(Network, { size: 22 }),
    status: 'active',
    capabilities: ['workspaceDb'],
  },
  {
    areaId: 'context-engine',
    route: '/context-engine',
    label: 'Memoria',
    tagline: 'Context Engine',
    description: 'Diagnóstico y configuración de la inyección de contexto por turno.',
    icon: createElement(Boxes, { size: 22 }),
    status: 'active',
    capabilities: ['contextEngine', 'workspaceDb'],
  },
  {
    areaId: 'command-center',
    route: '/command-center',
    label: 'Command Center',
    tagline: 'Multi-Agent PTY',
    description: 'Orquestación de agentes PTY en paralelo con contexto aislado.',
    icon: createElement(Terminal, { size: 22 }),
    status: 'active',
    capabilities: ['agentChat', 'terminalPty'],
    toolArea: commandCenterToolArea,
  },
  {
    areaId: 'automations',
    route: '/automations',
    label: 'Automations',
    tagline: 'Soon',
    description: 'Automatizaciones y tareas programadas.',
    icon: createElement(Zap, { size: 22 }),
    status: 'soon',
    capabilities: [],
  },
]

export function toolForPath(pathname: string): LaiaToolDefinition | undefined {
  const exact = LAIA_TOOLS.find(tool => tool.route === pathname)
  if (exact) return exact
  if (pathname.startsWith('/ws/')) return LAIA_TOOLS.find(tool => tool.areaId === 'nexus')
  return LAIA_TOOLS.find(tool => tool.areaId === 'workspace')
}
