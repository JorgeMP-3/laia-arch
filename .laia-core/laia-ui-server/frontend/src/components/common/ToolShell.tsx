import type { CSSProperties, ReactNode } from 'react'
import { ToolAreaProvider } from './ToolAreaProvider'
import type { ToolAreaProfile } from './ToolAreaProvider'

interface Props<S> {
  profile: ToolAreaProfile<S>
  state: S
  children: ReactNode
  className?: string
  style?: CSSProperties
}

export function ToolShell<S>({ profile, state, children, className, style }: Props<S>) {
  return (
    <ToolAreaProvider profile={profile} state={state}>
      <div
        className={className}
        style={{
          minHeight: '100vh',
          ...style,
        }}
        data-tool-area={profile.areaId}
      >
        {children}
      </div>
    </ToolAreaProvider>
  )
}
