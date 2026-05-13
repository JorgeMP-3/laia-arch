/* ────────────────────────────────────────────────────────────────────────────
   PROMPT DIALOG
   Generic overlay for clarify / sudo / secret prompts emitted by the runtime.
   Approvals have their own richer ApprovalDialog.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react'
import { Eye, EyeOff, MessageCircleQuestion, ShieldCheck } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'

export function PromptDialog() {
  const { pendingPrompt, respondPrompt, setPendingPrompt } = useAgent()
  const [value, setValue] = useState('')
  const [reveal, setReveal] = useState(false)

  useEffect(() => { setValue(''); setReveal(false) }, [pendingPrompt?.requestId])

  if (!pendingPrompt) return null
  if (pendingPrompt.kind === 'approval') return null  // approval has its own dialog

  const isPassword = pendingPrompt.kind === 'sudo' || pendingPrompt.kind === 'secret'
  const Icon = pendingPrompt.kind === 'clarify' ? MessageCircleQuestion : ShieldCheck
  const accent =
    pendingPrompt.kind === 'sudo' ? 'var(--ws-warning)' :
    pendingPrompt.kind === 'secret' ? 'var(--ws-violet)' :
    'var(--ws-accent)'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
    >
      <div className="ws-card" style={{ width: '100%', maxWidth: 520, borderColor: `${accent}33` }}>
        <div className="ws-card-header">
          <div className="flex items-center gap-2">
            <Icon size={13} style={{ color: accent }} />
            <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: accent }}>
              {pendingPrompt.kind}
            </span>
          </div>
          <button type="button" onClick={() => setPendingPrompt(null)} className="ws-pill" style={{ padding: '3px 6px' }}>
            cerrar
          </button>
        </div>

        <div style={{ padding: 16 }}>
          <p className="text-sm mb-3" style={{ color: 'var(--ws-text)' }}>
            {pendingPrompt.question || 'El runtime pide una respuesta.'}
          </p>

          {pendingPrompt.choices && pendingPrompt.choices.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {pendingPrompt.choices.map(c => (
                <button
                  key={c}
                  type="button"
                  onClick={() => respondPrompt(c)}
                  className="btn-primary px-3 py-1.5 text-xs rounded-md"
                >
                  {c}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-stretch gap-2">
              <input
                autoFocus
                type={isPassword && !reveal ? 'password' : 'text'}
                value={value}
                onChange={e => setValue(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && value) respondPrompt(value) }}
                placeholder={isPassword ? '••••••••' : 'Tu respuesta…'}
                className="field flex-1 text-sm"
                style={{ padding: '8px 12px', borderRadius: 8 }}
              />
              {isPassword && (
                <button
                  type="button"
                  onClick={() => setReveal(r => !r)}
                  className="ws-pill"
                  style={{ padding: '0 12px' }}
                  title={reveal ? 'Ocultar' : 'Mostrar'}
                >
                  {reveal ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              )}
              <button
                type="button"
                onClick={() => value && respondPrompt(value)}
                className="btn-primary px-4 py-2 text-xs rounded-md"
                disabled={!value}
              >
                Enviar
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
