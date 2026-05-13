import { useState } from 'react'
import { saveTauriConfig, initServerUrl } from '../lib/tauri'
import { setApiBase } from '../lib/api'

interface Props {
  onDone: (serverUrl: string, role: string) => void
}

export default function Setup({ onDone }: Props) {
  const [url, setUrl] = useState('http://mac-mini.local:8077')
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')

  async function handleSave() {
    const cleaned = url.trim().replace(/\/$/, '')
    if (!cleaned) {
      setError('Introduce una URL válida')
      return
    }

    setTesting(true)
    setError('')

    try {
      const res = await fetch(`${cleaned}/api/agent/status`, { signal: AbortSignal.timeout(4000) })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      setApiBase(cleaned)
      await saveTauriConfig({ server_url: cleaned, role: 'admin' })

      // Reload config to confirm it was saved
      await initServerUrl()
      onDone(cleaned, 'admin')
    } catch (e) {
      setError(`No se pudo conectar a ${cleaned} — verifica la URL y que el servidor esté activo.`)
    } finally {
      setTesting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center"
      style={{ background: 'var(--bg, #0a0a0a)', color: 'var(--text-main, #f0f0f0)' }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-8 flex flex-col gap-6"
        style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        {/* Logo */}
        <div className="flex flex-col items-center gap-2">
          <span
            className="text-5xl font-black tracking-tight"
            style={{
              color: 'var(--brand, #ffc45a)',
            }}
          >
            LAIA
          </span>
          <p className="text-sm opacity-50 text-center">
            Conecta con tu servidor LAIA para comenzar
          </p>
        </div>

        {/* URL input */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium opacity-60 uppercase tracking-widest">
            URL del servidor
          </label>
          <input
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
            placeholder="http://mac-mini.local:8077"
            className="w-full rounded-lg px-4 py-3 text-sm outline-none"
            style={{
              background: 'rgba(255,255,255,0.07)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'var(--text-main, #f0f0f0)',
            }}
            autoFocus
          />
          {error && (
            <p className="text-xs" style={{ color: '#ff6b6b' }}>
              {error}
            </p>
          )}
          <p className="text-xs opacity-40">
            Asegúrate de que el Mac mini está encendido y el servidor activo (puerto 8077).
          </p>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          disabled={testing}
          className="w-full rounded-xl py-3 text-sm font-semibold transition-opacity disabled:opacity-50"
          style={{
            background: 'linear-gradient(135deg, #ffd580 0%, #ff9a3c 100%)',
            color: '#1a1a1a',
          }}
        >
          {testing ? 'Verificando conexión…' : 'Conectar'}
        </button>
      </div>
    </div>
  )
}
