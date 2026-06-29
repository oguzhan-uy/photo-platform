import { useState } from 'react'
import { getAdminToken, setAdminToken, clearAdminToken } from '../api/admin'

export function useAdminAuth() {
  const [token, setTokenState] = useState<string | null>(getAdminToken)

  const setToken = (t: string) => {
    setAdminToken(t)
    setTokenState(t)
  }

  const clearToken = () => {
    clearAdminToken()
    setTokenState(null)
  }

  return { token, setToken, clearToken }
}
