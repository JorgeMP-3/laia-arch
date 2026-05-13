import { useEffect, useRef } from 'react'
import { useAgent } from '../../lib/agentRuntime'

export interface ToolContextProfile<S> {
  toolId: string
  getConnectText: (state: S) => string
  getDeltaText?: (state: S) => string
  stateHash: (state: S) => string
}

interface Props<S> {
  profile: ToolContextProfile<S>
  state: S
}

// Sentinel used by ChatStream to render context messages as compact cards
// instead of regular user bubbles. Format stored in messages: [__CTX__:toolId]\n{text}
export const CTX_SENTINEL = '__CTX__'

export function ToolContextInjector<S>({ profile, state }: Props<S>) {
  const { connection, sessionId, submitContext } = useAgent()
  const injectedHashRef = useRef('')
  const sessionIdRef = useRef('')

  // Reset on disconnect so reconnect gets a fresh full injection
  useEffect(() => {
    if (connection !== 'online') {
      injectedHashRef.current = ''
    }
  }, [connection])

  useEffect(() => {
    if (sessionId !== sessionIdRef.current) {
      sessionIdRef.current = sessionId
      injectedHashRef.current = ''
    }
  }, [sessionId])

  useEffect(() => {
    if (connection !== 'online') return

    const hash = profile.stateHash(state)
    if (hash === injectedHashRef.current) return

    const prevHash = injectedHashRef.current
    injectedHashRef.current = hash

    if (prevHash === '') {
      submitContext(profile.toolId, profile.getConnectText(state))
    } else {
      submitContext(profile.toolId, profile.getDeltaText?.(state) ?? profile.getConnectText(state))
    }
  }, [connection, sessionId, state, profile, submitContext])

  return null
}
