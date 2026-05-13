import type React from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: number
  tone: ToastTone
  title: string
  message?: string
}

interface ToastProps {
  items: ToastMessage[]
  onDismiss: (id: number) => void
}

const toneClass: Record<ToastTone, string> = {
  success: 'text-white',
  error: 'text-red-100',
  info: 'text-white',
}

const toneStyle: Record<ToastTone, React.CSSProperties> = {
  success: { background: 'rgba(255,196,90,0.12)', border: '1px solid rgba(255,196,90,0.3)', backdropFilter: 'blur(12px)' },
  error: { background: 'rgba(153,27,27,0.3)', border: '1px solid rgba(239,68,68,0.35)', backdropFilter: 'blur(12px)' },
  info: { background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', backdropFilter: 'blur(12px)' },
}

const iconClass: Record<ToastTone, string> = {
  success: 'text-amber-300',
  error: 'text-red-400',
  info: 'text-slate-300',
}

function ToastIcon({ tone }: { tone: ToastTone }) {
  const className = iconClass[tone]
  if (tone === 'success') return <CheckCircle2 size={16} className={className} />
  if (tone === 'error') return <AlertTriangle size={16} className={className} />
  return <Info size={16} className={className} />
}

export function Toast({ items, onDismiss }: ToastProps) {
  if (items.length === 0) return null

  return (
    <div className="fixed right-5 top-20 z-50 flex w-[min(24rem,calc(100vw-2.5rem))] flex-col gap-2">
      {items.map(item => (
        <div
          key={item.id}
          className={`fade-up rounded-lg px-3.5 py-3 shadow-2xl ${toneClass[item.tone]}`}
          style={toneStyle[item.tone]}
        >
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 shrink-0">
              <ToastIcon tone={item.tone} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold leading-5">{item.title}</div>
              {item.message && (
                <div className="mt-0.5 text-xs leading-5 text-slate-300">{item.message}</div>
              )}
            </div>
            <button
              onClick={() => onDismiss(item.id)}
              className="shrink-0 rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white"
              aria-label="Cerrar notificación"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
