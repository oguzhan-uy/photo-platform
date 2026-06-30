import type {
  ClientOut,
  DeletionLogOut,
  GalleryOut,
  PhotoConfirmOut,
  PhotoOut,
} from '../types'

const ADMIN_TOKEN_KEY = 'admin_token'

export function getAdminToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY)
}

export function setAdminToken(token: string): void {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token)
}

export function clearAdminToken(): void {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY)
}

class AdminApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

async function adminFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAdminToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const res = await fetch(path, { ...options, headers })

  if (res.status === 401) {
    clearAdminToken()
    window.location.href = '/admin'
    throw new AdminApiError(401, 'Session expired')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new AdminApiError(res.status, (body as { detail?: string }).detail ?? res.statusText)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function adminFetchBlob(path: string): Promise<string> {
  const token = getAdminToken()
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) { clearAdminToken(); window.location.href = '/admin'; throw new AdminApiError(401, 'Session expired') }
  if (!res.ok) throw new AdminApiError(res.status, res.statusText)
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

// Clients
export const listClients = () => adminFetch<ClientOut[]>('/admin/clients')

export const createClient = (data: { display_name: string; contact?: string }) =>
  adminFetch<ClientOut>('/admin/clients', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const deleteClient = (clientId: string) =>
  adminFetch<void>(`/admin/clients/${clientId}`, { method: 'DELETE' })

export const patchConsent = (clientId: string, consent_biometric: boolean) =>
  adminFetch<ClientOut>(`/admin/clients/${clientId}/consent`, {
    method: 'PATCH',
    body: JSON.stringify({ consent_biometric }),
  })

// Galleries
export const listGalleries = () => adminFetch<GalleryOut[]>('/admin/galleries')

export const createGallery = (data: {
  client_id: string
  title: string
  passcode: string
  published: boolean
  expires_at?: string | null
}) =>
  adminFetch<GalleryOut>('/admin/galleries', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Photos
export const listPhotos = (galleryId: string) =>
  adminFetch<PhotoOut[]>(`/admin/galleries/${galleryId}/photos`)

export const uploadPhoto = (galleryId: string, file: File): Promise<PhotoConfirmOut> => {
  const form = new FormData()
  form.append('file', file)
  const token = getAdminToken()
  return fetch(`/admin/galleries/${galleryId}/photos/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  }).then(async res => {
    if (res.status === 401) { clearAdminToken(); window.location.href = '/admin'; throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error((body as { detail?: string }).detail ?? res.statusText)
    }
    return res.json()
  })
}

export const deletePhoto = (photoId: string) =>
  adminFetch<void>(`/admin/photos/${photoId}`, { method: 'DELETE' })

export const deleteAllPhotos = (galleryId: string) =>
  adminFetch<{ deleted: number }>(`/admin/galleries/${galleryId}/photos`, { method: 'DELETE' })

// Clustering
export const triggerClustering = (galleryId: string) =>
  adminFetch<{ job_id: string; gallery_id: string }>(
    `/admin/galleries/${galleryId}/cluster`,
    { method: 'POST' },
  )

export const resetGalleryFaces = (galleryId: string) =>
  adminFetch<{ deleted_faces: number; embed_jobs_queued: number }>(
    `/admin/galleries/${galleryId}/faces`,
    { method: 'DELETE' },
  )

export const setCoverPhoto = (galleryId: string, photoId: string) =>
  adminFetch<{ gallery_id: string; cover_photo_id: string }>(
    `/admin/galleries/${galleryId}/cover`,
    { method: 'PATCH', body: JSON.stringify({ photo_id: photoId }) },
  )

// Deletion log
export const getDeletionLog = (limit = 100) =>
  adminFetch<DeletionLogOut[]>(`/admin/deletion-log?limit=${limit}`)
