const KEY = 'agora_auth'

interface AuthData {
  username: string
  token: string // base64(username:password)
}

export function saveAuth(username: string, password: string): void {
  const token = btoa(`${username}:${password}`)
  sessionStorage.setItem(KEY, JSON.stringify({ username, token }))
}

export function getAuth(): AuthData | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    return JSON.parse(raw) as AuthData
  } catch {
    return null
  }
}

export function clearAuth(): void {
  sessionStorage.removeItem(KEY)
}

export function isLoggedIn(): boolean {
  return getAuth() !== null
}

export function authHeader(): Record<string, string> {
  const auth = getAuth()
  if (!auth) return {}
  return { Authorization: `Basic ${auth.token}` }
}
