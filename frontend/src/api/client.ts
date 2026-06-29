const TOKEN_KEY = 'gallery_token'
const GALLERY_KEY = 'gallery_id'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setAuth(token: string, galleryId: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
  sessionStorage.setItem(GALLERY_KEY, galleryId)
}

export function clearAuth(): void {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(GALLERY_KEY)
}

export function getStoredGalleryId(): string | null {
  return sessionStorage.getItem(GALLERY_KEY)
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const res = await fetch(path, { ...options, headers })

  if (res.status === 401) {
    // Token expired — clear auth and reload to show login screen.
    clearAuth()
    window.location.reload()
    throw new ApiError(401, 'Session expired')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, (body as { detail?: string }).detail ?? res.statusText)
  }

  return res.json() as Promise<T>
}

export async function apiFetchBlob(path: string): Promise<string> {
  const token = getToken()
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) { clearAuth(); window.location.reload(); throw new ApiError(401, 'Session expired') }
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
