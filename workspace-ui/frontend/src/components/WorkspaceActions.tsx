import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Database, Download, Loader2, MoreVertical, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { ApiError } from '../lib/api'
import type { CleanExportsResult, LegacyMigrationResult, MarkdownExportResult } from '../lib/api'
import type { ToastMessage } from './Toast'

type ActionKey = 'export' | 'clean' | 'migrate'
type ToastInput = Omit<ToastMessage, 'id'>

interface WorkspaceActionsProps {
  ws: string
  onToast: (toast: ToastInput) => void
  onMigrated: () => void
}

interface ConfirmState {
  key: ActionKey
  title: string
  message: string
  confirmLabel: string
  danger?: boolean
}

const confirmByAction: Record<ActionKey, ConfirmState> = {
  export: {
    key: 'export',
    title: 'Exportar a Markdown',
    message: 'Se regenerarán los exports derivados desde la base SQLite del workspace.',
    confirmLabel: 'Exportar',
  },
  clean: {
    key: 'clean',
    title: 'Limpiar exports',
    message: 'Antes de borrar exports derivados, el backend verificará que la DB contiene la información mínima esperada.',
    confirmLabel: 'Limpiar',
    danger: true,
  },
  migrate: {
    key: 'migrate',
    title: 'Migrar legacy a DB',
    message: 'Se importarán archivos legacy a SQLite y el backend devolverá el manifiesto de migración.',
    confirmLabel: 'Migrar',
  },
}

function summarizeExport(result: MarkdownExportResult) {
  const contextWritten = result.context.written.length
  const contextRemoved = result.context.removed.length
  const organizedWritten = result.organized.written.length
  const organizedRemoved = result.organized.removed.length
  return `Context: ${contextWritten} escritos, ${contextRemoved} retirados. Organizado: ${organizedWritten} escritos, ${organizedRemoved} retirados.`
}

function summarizeClean(result: CleanExportsResult) {
  return `${result.deleted.length} rutas eliminadas. DB verificada con ${result.verification.node_count} nodos.`
}

function summarizeMigration(result: LegacyMigrationResult) {
  const manifest = result.manifest
  const status = manifest.verified ? 'DB verificada' : 'DB incompleta'
  return `${manifest.imported.length} importados, ${manifest.moved.length} movidos, ${manifest.removed.length} legacy retirados. ${status} con ${manifest.node_count} nodos.`
}

export function WorkspaceActions({ ws, onToast, onMigrated }: WorkspaceActionsProps) {
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)
  const [running, setRunning] = useState<ActionKey | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('pointerdown', onPointerDown)
    return () => window.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const startAction = (key: ActionKey) => {
    setConfirm(confirmByAction[key])
    setOpen(false)
  }

  const runConfirmed = async () => {
    if (!confirm) return
    setRunning(confirm.key)
    try {
      if (confirm.key === 'export') {
        const result = await api.exportMarkdown(ws)
        onToast({ tone: 'success', title: 'Markdown exportado', message: summarizeExport(result) })
      } else if (confirm.key === 'clean') {
        const result = await api.cleanExports(ws)
        onToast({ tone: 'success', title: 'Exports limpiados', message: summarizeClean(result) })
      } else {
        const result = await api.migrateLegacy(ws)
        onToast({ tone: result.manifest.verified ? 'success' : 'info', title: 'Migración completada', message: summarizeMigration(result) })
        onMigrated()
      }
      setConfirm(null)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const title = error instanceof ApiError && error.status === 409 ? 'DB incompleta' : 'Acción fallida'
      onToast({ tone: 'error', title, message })
    } finally {
      setRunning(null)
    }
  }

  const busy = running !== null

  return (
    <>
      <div ref={menuRef} className="relative">
        <button
          onClick={() => setOpen(value => !value)}
          disabled={busy}
          className="btn-ghost flex h-9 w-9 items-center justify-center rounded-lg text-slate-200 disabled:opacity-50"
          aria-label="Acciones del workspace"
          aria-expanded={open}
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <MoreVertical size={16} />}
        </button>
        {open && (
          <div
            className="absolute right-0 top-11 z-40 w-56 overflow-hidden rounded-xl p-1.5 shadow-2xl fade-up"
            style={{ background: 'rgba(10,10,10,0.95)', border: '1px solid var(--border)', backdropFilter: 'blur(12px)' }}
          >
            <ActionButton icon={<Download size={15} />} label="Exportar a Markdown" onClick={() => startAction('export')} />
            <ActionButton icon={<Trash2 size={15} />} label="Limpiar exports" onClick={() => startAction('clean')} danger />
            <ActionButton icon={<Database size={15} />} label="Migrar legacy a DB" onClick={() => startAction('migrate')} />
          </div>
        )}
      </div>

      {confirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4" style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}>
          <div className="w-full max-w-md rounded-xl p-5 shadow-2xl glass fade-up">
            <div className="mb-4 flex items-start gap-3">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${confirm.danger ? 'bg-red-500/15 text-red-200' : ''}`} style={!confirm.danger ? { background: 'rgba(255,196,90,0.12)', color: 'var(--brand)' } : {}}>
                {confirm.danger ? <Trash2 size={17} /> : <Database size={17} />}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold text-white">{confirm.title}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-400">{confirm.message}</p>
              </div>
              <button
                onClick={() => setConfirm(null)}
                disabled={busy}
                className="rounded p-1 text-slate-500 hover:bg-white/10 hover:text-white disabled:opacity-50"
                aria-label="Cerrar confirmación"
              >
                <X size={15} />
              </button>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirm(null)}
                disabled={busy}
                className="btn-ghost h-9 rounded-lg px-3 text-sm text-slate-200 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={runConfirmed}
                disabled={busy}
                className={`${confirm.danger ? 'btn-danger-ghost bg-red-950/30' : 'btn-primary'} flex h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium disabled:opacity-50`}
              >
                {busy && <Loader2 size={14} className="animate-spin" />}
                {confirm.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function ActionButton({ icon, label, onClick, danger = false }: { icon: ReactNode; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`flex h-9 w-full items-center gap-2 rounded-md px-2.5 text-left text-sm transition-colors ${danger ? 'text-red-300 hover:bg-red-500/10' : 'text-white hover:bg-white/8'}`}
      onMouseEnter={e => { if (!danger) e.currentTarget.style.background = 'rgba(255,196,90,0.07)' }}
      onMouseLeave={e => { if (!danger) e.currentTarget.style.background = '' }}
    >
      <span style={{ color: danger ? '#f87171' : 'var(--brand)' }}>{icon}</span>
      <span>{label}</span>
    </button>
  )
}
