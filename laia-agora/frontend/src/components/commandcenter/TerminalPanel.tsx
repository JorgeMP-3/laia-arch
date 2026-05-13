import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { X } from 'lucide-react'
import { terminalWsUrl } from '../../lib/terminalApi'
import type { TerminalInfo } from '../../lib/terminalApi'

export interface TerminalPanelHandle {
  inject: (text: string, pressEnter?: boolean) => void
}

interface Props {
  info: TerminalInfo
  onKill: (id: string) => void
  onExit?: (id: string, code: number) => void
}

export const TerminalPanel = forwardRef<TerminalPanelHandle, Props>(
  function TerminalPanel({ info, onKill, onExit }, ref) {
    const mountRef = useRef<HTMLDivElement>(null)
    const wsRef = useRef<WebSocket | null>(null)
    const [alive, setAlive] = useState(info.alive)

    useImperativeHandle(ref, () => ({
      inject(text: string, pressEnter = true) {
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) return
        const payload = text + (pressEnter ? '\r' : '')
        const bytes = new TextEncoder().encode(payload)
        const b64 = btoa(String.fromCharCode(...bytes))
        ws.send(JSON.stringify({ t: 'i', d: b64 }))
      },
    }))

    useEffect(() => {
      const el = mountRef.current
      if (!el) return

      let destroyed = false
      let ws: WebSocket | null = null
      let ro: ResizeObserver | null = null

      const term = new Terminal({
        theme: {
          background: '#060400',
          foreground: '#e6edf3',
          cursor: '#ffc45a',
          cursorAccent: '#000',
          selectionBackground: 'rgba(255,196,90,0.25)',
          // ANSI normal colors
          black: '#1e1e2e',
          red: '#f38ba8',
          green: '#a6e3a1',
          yellow: '#f9e2af',
          blue: '#89b4fa',
          magenta: '#cba6f7',
          cyan: '#89dceb',
          white: '#cdd6f4',
          // ANSI bright colors
          brightBlack: '#585b70',
          brightRed: '#f38ba8',
          brightGreen: '#a6e3a1',
          brightYellow: '#f9e2af',
          brightBlue: '#89b4fa',
          brightMagenta: '#cba6f7',
          brightCyan: '#89dceb',
          brightWhite: '#ffffff',
        },
        fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, monospace",
        fontSize: 12,
        lineHeight: 1.4,
        cursorBlink: true,
        convertEol: true,
        scrollback: 5000,
      })
      const fit = new FitAddon()
      term.loadAddon(fit)

      // Defer open + fit until the browser has painted and flex layout is settled
      const raf = requestAnimationFrame(() => {
        if (destroyed) return
        term.open(el)
        fit.fit()

        ws = new WebSocket(terminalWsUrl(info.id))
        wsRef.current = ws

        ws.onopen = () => {
          fit.fit()
          ws!.send(JSON.stringify({ t: 'r', cols: term.cols, rows: term.rows }))
        }

        ws.onmessage = (ev) => {
          let frame: { t: string; d?: string; code?: number }
          try { frame = JSON.parse(ev.data as string) } catch { return }
          if (frame.t === 'o' && frame.d) {
            const bytes = Uint8Array.from(atob(frame.d), c => c.charCodeAt(0))
            term.write(bytes)
          } else if (frame.t === 'exit') {
            setAlive(false)
            term.writeln(`\r\n\x1b[33m[process exited: ${frame.code ?? '?'}]\x1b[0m`)
            onExit?.(info.id, frame.code ?? -1)
          }
        }

        ws.onclose = () => setAlive(false)

        term.onData(data => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return
          const bytes = new TextEncoder().encode(data)
          const b64 = btoa(String.fromCharCode(...bytes))
          ws.send(JSON.stringify({ t: 'i', d: b64 }))
        })

        ro = new ResizeObserver(() => {
          fit.fit()
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ t: 'r', cols: term.cols, rows: term.rows }))
          }
        })
        ro.observe(el)
      })

      return () => {
        destroyed = true
        cancelAnimationFrame(raf)
        ro?.disconnect()
        ws?.close()
        term.dispose()
      }
    }, [info.id])

    const roleColor: Record<string, string> = {
      'claude-code-planner': '#60a5fa',
      'codex-worker': '#60a5fa',
      'opencode-worker': '#a78bfa',
      'bash': '#9ca3af',
    }
    const dotColor = alive ? (roleColor[info.agent_type] ?? '#4ade80') : '#6b7280'

    return (
      <div style={{
        display: 'flex', flexDirection: 'column', height: '100%',
        border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
        overflow: 'hidden', background: '#060400',
      }}>
        <div style={{
          height: 36, flexShrink: 0, display: 'flex', alignItems: 'center',
          gap: 8, padding: '0 12px',
          background: 'rgba(0,0,0,0.35)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
            background: dotColor,
            boxShadow: alive ? `0 0 6px ${dotColor}` : 'none',
            animation: alive ? 'cc-dot-pulse 2s ease-in-out infinite' : 'none',
          }} />
          <span style={{
            fontFamily: 'monospace', fontSize: '0.62rem', color: '#ffc45a',
            textTransform: 'uppercase', letterSpacing: '0.08em',
            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            display: 'flex', flexDirection: 'column', gap: 1,
          }}>
            {info.label || info.agent_type}
            {info.label && info.label !== info.agent_type && (
              <span style={{ fontSize: '0.5rem', color: '#6b7280', textTransform: 'none', letterSpacing: 0 }}>
                {info.agent_type}
              </span>
            )}
          </span>
          <span style={{ fontFamily: 'monospace', fontSize: '0.55rem', color: '#6b7280' }}>
            {info.id}
          </span>
          <button
            type="button"
            onClick={() => onKill(info.id)}
            title="Kill & close"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 22, height: 22, borderRadius: 4, border: '1px solid rgba(252,165,165,0.25)',
              background: 'transparent', color: '#f87171', cursor: 'pointer', flexShrink: 0,
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(153,27,27,0.25)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
          >
            <X size={11} />
          </button>
        </div>
        <div ref={mountRef} style={{ flex: 1, overflow: 'hidden', padding: 4 }} />
      </div>
    )
  }
)
