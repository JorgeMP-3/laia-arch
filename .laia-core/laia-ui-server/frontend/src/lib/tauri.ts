// Tauri detection + config IPC helpers
// These imports are no-ops when running in the browser (Tauri's tree-shaking handles it)
import { setApiBase } from './api'

interface AppConfig {
  server_url: string
  role: string
}

// True when running inside a Tauri webview
export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

export async function getTauriConfig(): Promise<AppConfig> {
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<AppConfig>('get_config')
}

export async function saveTauriConfig(config: AppConfig): Promise<void> {
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('set_config', { config })
}

export async function initServerUrl(): Promise<{ serverUrl: string; role: string; needsSetup: boolean }> {
  if (!isTauri()) {
    return { serverUrl: '', role: 'admin', needsSetup: false }
  }
  const config = await getTauriConfig()
  if (config.server_url) {
    setApiBase(config.server_url)
    return { serverUrl: config.server_url, role: config.role || 'admin', needsSetup: false }
  }
  return { serverUrl: '', role: 'admin', needsSetup: true }
}

export async function setAlwaysOnTop(value: boolean): Promise<void> {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('set_always_on_top', { value })
}

// Employee role helper — read from window global injected by Tauri or from config
export function isEmployeeRole(): boolean {
  return (window as unknown as Record<string, unknown>).__LAIA_ROLE__ === 'employee'
}
