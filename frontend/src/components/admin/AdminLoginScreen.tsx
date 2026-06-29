import { useState } from 'react'
import { setAdminToken, listClients } from '../../api/admin'

interface Props {
  onLogin: (token: string) => void
}

export function AdminLoginScreen({ onLogin }: Props) {
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      setAdminToken(token)
      await listClients()
      onLogin(token)
    } catch (err: unknown) {
      setAdminToken('')
      const status = (err as { status?: number }).status
      setError(status === 401 ? 'Invalid admin token.' : 'Connection error — is the API running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-white text-2xl font-semibold mb-1 text-center">Admin</h1>
        <p className="text-neutral-500 text-sm text-center mb-8">Photographer panel</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-neutral-400 text-sm mb-1.5">Admin token</label>
            <input
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              placeholder="Bearer token from .env"
              className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2.5 text-white placeholder-neutral-600 focus:outline-none focus:border-neutral-500 text-sm"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !token}
            className="w-full bg-white text-black rounded-lg py-2.5 text-sm font-medium hover:bg-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Verifying…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
