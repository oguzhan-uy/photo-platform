import { useState, type FormEvent } from 'react'
import { accessGallery } from '../api/gallery'
import { ApiError } from '../api/client'

interface Props {
  urlGalleryId: string | null
  onLogin: (token: string, galleryId: string) => void
}

export function LoginScreen({ urlGalleryId, onLogin }: Props) {
  const [galleryId, setGalleryId] = useState(urlGalleryId ?? '')
  const [passcode, setPasscode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!galleryId.trim() || !passcode.trim()) return
    setError(null)
    setLoading(true)
    try {
      const res = await accessGallery(galleryId.trim(), passcode.trim())
      onLogin(res.token, res.gallery_id)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? 'Incorrect passcode.' : err.message)
      } else {
        setError('Gallery not found. Check the link and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      {/* Background subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.8) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.8) 1px,transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Logo / brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-indigo-600 rounded-2xl mb-4">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-white">Your Gallery</h1>
          <p className="text-zinc-400 text-sm mt-1">Enter your access code to view your photos</p>
        </div>

        {/* Card */}
        <div className="bg-zinc-900 rounded-2xl p-6 border border-zinc-800 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Gallery ID — only show if not provided in URL */}
            {!urlGalleryId && (
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Gallery ID
                </label>
                <input
                  type="text"
                  value={galleryId}
                  onChange={e => setGalleryId(e.target.value)}
                  placeholder="Paste the gallery link or ID"
                  required
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500
                             text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                Access code
              </label>
              <input
                type="password"
                value={passcode}
                onChange={e => setPasscode(e.target.value)}
                placeholder="Enter your passcode"
                required
                autoFocus={!!urlGalleryId}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500
                           text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>

            {error && (
              <div className="bg-red-950/50 border border-red-800/50 rounded-xl px-4 py-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !galleryId.trim() || !passcode.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed
                         text-white font-medium rounded-xl py-3 text-sm transition-colors"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Opening gallery…
                </span>
              ) : 'View Gallery'}
            </button>
          </form>
        </div>

        <p className="text-center text-zinc-600 text-xs mt-6">
          Don't have a code? Contact your photographer.
        </p>
      </div>
    </div>
  )
}
