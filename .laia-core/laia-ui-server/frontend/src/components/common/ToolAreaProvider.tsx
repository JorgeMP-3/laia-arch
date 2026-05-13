import type { ReactNode } from 'react'
import { AgentProvider } from '../../lib/agentRuntime'
import { ToolContextInjector } from './ToolContextInjector'
import type { ToolContextProfile } from './ToolContextInjector'

export interface ToolAreaProfile<S = void> {
  areaId: string
  appContext: string
  dynamicContext?: ToolContextProfile<S>
}

interface Props<S> {
  profile: ToolAreaProfile<S>
  state: S
  children: ReactNode
}

export function ToolAreaProvider<S>({ profile, state, children }: Props<S>) {
  return (
    <AgentProvider areaId={profile.areaId} appContext={profile.appContext}>
      {profile.dynamicContext && (
        <ToolContextInjector profile={profile.dynamicContext} state={state} />
      )}
      {children}
    </AgentProvider>
  )
}
