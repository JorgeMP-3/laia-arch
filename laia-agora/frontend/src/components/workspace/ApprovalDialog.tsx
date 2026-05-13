/* ────────────────────────────────────────────────────────────────────────────
   APPROVAL DIALOG
   Triggered when the agent emits an approval.request event for a dangerous
   command. Lets the user:
     • Approve once / approve for session / deny
     • Ask for an explanation (uses prompt.btw — runs in parallel without
       unblocking the agent, with full conversation history but no tools)
     • Ask for safer alternatives
   When an explanation is requested, the dialog stays open and shows the
   answer inline, so the user can read and decide without losing the approval.
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Loader2, MessagesSquare, Shield, X } from 'lucide-react'
import { useAgent } from '../../lib/agentRuntime'

export function ApprovalDialog() {
  const { pendingPrompt, respondPrompt, send, messages, setPendingPrompt } = useAgent()
  const [waitingFor, setWaitingFor] = useState<'explain' | 'alternative' | null>(null)
  const [answer, setAnswer] = useState<string>('')
  // Snapshot the count of assistant messages so we know when a NEW one arrives
  // (prompt.btw replies via btw.complete which the runtime appends as assistant role).
  const messageCountAtAskRef = useRef<number>(0)

  // Detect when a btw answer arrives by watching for new assistant messages
  useEffect(() => {
    if (waitingFor === null) return
    const assistantMsgs = messages.filter(m => m.role === 'assistant' && m.id.startsWith('btw'))
    if (assistantMsgs.length > messageCountAtAskRef.current) {
      const latest = assistantMsgs[assistantMsgs.length - 1]
      setAnswer(latest.content)
      setWaitingFor(null)
    }
  }, [messages, waitingFor])

  if (!pendingPrompt || pendingPrompt.kind !== 'approval') return null

  function ask(kind: 'explain' | 'alternative') {
    const prompt = kind === 'explain'
      ? `Explícame qué hace exactamente este comando, qué efectos tendrá, y por qué lo necesitas:\n\n\`${pendingPrompt!.command}\``
      : `No me convence ejecutar este comando:\n\n\`${pendingPrompt!.command}\`\n\n¿Hay alguna alternativa más segura? Si no la hay, dímelo y razonamos.`
    // Snapshot count BEFORE sending so we can detect the new reply.
    messageCountAtAskRef.current = messages.filter(m => m.role === 'assistant' && m.id.startsWith('btw')).length
    setAnswer('')
    setWaitingFor(kind)
    send('prompt.btw', { text: prompt })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)' }}
    >
      <div
        className="ws-card flex flex-col"
        style={{ width: '100%', maxWidth: 620, maxHeight: '85vh', borderColor: 'rgba(252, 165, 165, 0.32)' }}
      >
        <div className="ws-card-header" style={{ background: 'rgba(252, 165, 165, 0.06)' }}>
          <div className="flex items-center gap-2">
            <AlertTriangle size={13} style={{ color: 'var(--ws-danger)' }} />
            <span className="mono text-[0.6rem] uppercase tracking-widest" style={{ color: 'var(--ws-danger)' }}>
              comando peligroso
            </span>
          </div>
          <button type="button" onClick={() => setPendingPrompt(null)} className="ws-pill" style={{ padding: '3px 6px' }}
            title="Cerrar (la aprobación sigue pendiente — se mantendrá en la pestaña Approvals)">
            <X size={11} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          <p className="text-sm mb-3" style={{ color: 'var(--ws-text)' }}>
            {pendingPrompt.question || 'El agente pide aprobación para ejecutar:'}
          </p>

          {pendingPrompt.command && (
            <pre
              className="mono text-xs p-3 rounded mb-3 overflow-auto"
              style={{
                background: 'rgba(0,0,0,0.4)',
                color: 'var(--ws-text)',
                border: '1px solid var(--ws-border)',
                maxHeight: 200,
              }}
            >
              {pendingPrompt.command}
            </pre>
          )}

          {pendingPrompt.reason && (
            <div className="text-[0.72rem] mb-3" style={{ color: 'var(--ws-text-muted)' }}>
              <span className="mono uppercase tracking-widest text-[0.55rem]" style={{ color: 'var(--ws-warning)' }}>
                razón:
              </span>{' '}
              {pendingPrompt.reason}
            </div>
          )}

          {(waitingFor || answer) && (
            <div
              className="rounded-md p-3 mb-3"
              style={{
                background: 'rgba(196, 181, 253, 0.06)',
                border: '1px solid rgba(196, 181, 253, 0.22)',
              }}
            >
              <div className="mono text-[0.55rem] uppercase tracking-widest mb-2 flex items-center gap-1.5"
                style={{ color: 'var(--ws-violet)' }}>
                {waitingFor && <Loader2 size={11} className="animate-spin" />}
                {waitingFor === 'explain' ? 'explicación del agente' :
                 waitingFor === 'alternative' ? 'alternativa propuesta' :
                 answer ? 'respuesta del agente' : ''}
              </div>
              {waitingFor && !answer && (
                <div className="text-[0.7rem]" style={{ color: 'var(--ws-text-muted)' }}>
                  consultando al modelo (sin tools, no afecta el estado del agente)…
                </div>
              )}
              {answer && (
                <div className="text-[0.78rem] leading-relaxed whitespace-pre-wrap"
                  style={{ color: 'var(--ws-text)' }}>
                  {answer}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2 p-3" style={{ borderTop: '1px solid var(--ws-border)' }}>
          <button
            type="button"
            onClick={() => respondPrompt('once')}
            className="btn-primary flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs"
          >
            <Check size={12} /> Aprobar una vez
          </button>
          <button
            type="button"
            onClick={() => respondPrompt('session')}
            className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs"
            style={{ color: 'var(--ws-accent)' }}
          >
            <Shield size={12} /> Para esta sesión
          </button>
          <button
            type="button"
            onClick={() => ask('explain')}
            className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs"
            disabled={waitingFor !== null}
            style={{ color: 'var(--ws-violet)', opacity: waitingFor === 'explain' ? 0.5 : 1 }}
          >
            <MessagesSquare size={12} /> Explica
          </button>
          <button
            type="button"
            onClick={() => ask('alternative')}
            className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs"
            disabled={waitingFor !== null}
            style={{ color: 'var(--ws-warning)', opacity: waitingFor === 'alternative' ? 0.5 : 1 }}
          >
            <MessagesSquare size={12} /> ¿Alternativa?
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => respondPrompt('deny')}
            className="btn-danger-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs"
          >
            <X size={12} /> Denegar
          </button>
        </div>
      </div>
    </div>
  )
}
