import { useState } from 'react'
import { clearAuth as _clearAuth, getStoredGalleryId, getToken, setAuth as _setAuth } from '../api/client'

export function useAuth() {
  const [token, setToken] = useState<string | null>(getToken)
  const [galleryId, setGalleryId] = useState<string | null>(getStoredGalleryId)

  const setAuth = (newToken: string, newGalleryId: string) => {
    _setAuth(newToken, newGalleryId)
    setToken(newToken)
    setGalleryId(newGalleryId)
  }

  const clearAuth = () => {
    _clearAuth()
    setToken(null)
    setGalleryId(null)
  }

  return { token, galleryId, setAuth, clearAuth }
}
