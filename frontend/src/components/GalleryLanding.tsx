import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPublicGalleries, accessGallery } from '../api/gallery'
import { ApiError } from '../api/client'
import type { PublicGallery } from '../types'

interface Props {
  onLogin: (token: string, galleryId: string) => void
}

interface PasscodeModalProps {
  gallery: PublicGallery
  onLogin: (token: string, galleryId: string) => void
  onClose: () => void
}

function PasscodeModal({ gallery, onLogin, onClose }: PasscodeModalProps) {
  const [passcode, setPasscode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!passcode.trim()) return
    setError(null)
    setLoading(true)
    try {
      const res = await accessGallery(gallery.id, passcode.trim())
      onLogin(res.token, res.gallery_id)
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? 'Incorrect access code.'
        : 'Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-zinc-900 rounded-2xl p-6 border border-zinc-800 shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-white font-semibold text-base">{gallery.title}</h2>
            <p className="text-zinc-500 text-xs mt-0.5">Enter your access code to view this gallery</p>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-600 hover:text-white transition-colors p-1"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            value={passcode}
            onChange={e => setPasscode(e.target.value)}
            placeholder="Access code"
            required
            autoFocus
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white
                       placeholder-zinc-500 text-sm focus:outline-none focus:ring-2
                       focus:ring-indigo-500 focus:border-transparent transition"
          />

          {error && (
            <div className="bg-red-950/50 border border-red-800/50 rounded-xl px-4 py-3">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !passcode.trim()}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50
                       disabled:cursor-not-allowed text-white font-medium rounded-xl
                       py-3 text-sm transition-colors"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Opening…
              </span>
            ) : 'Open Gallery'}
          </button>
        </form>
      </div>
    </div>
  )
}

function GalleryCard({ gallery, onClick }: { gallery: PublicGallery; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="group relative overflow-hidden rounded-2xl bg-zinc-900 border border-zinc-800
                 hover:border-zinc-600 transition-all duration-300 hover:scale-[1.02]
                 hover:shadow-2xl hover:shadow-black/60 text-left w-full aspect-[3/4]"
    >
      {/* Cover image (blurred) */}
      {gallery.has_cover ? (
        <img
          src={`/galleries/${gallery.id}/cover`}
          alt=""
          draggable={false}
          className="absolute inset-0 w-full h-full object-cover blur-[3px] scale-105
                     brightness-75 group-hover:brightness-60 transition-all duration-300"
        />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-zinc-800 to-zinc-900" />
      )}

      {/* Lock icon centered */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
        <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm border border-white/20
                        flex items-center justify-center group-hover:bg-white/15 transition-colors">
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <span className="text-white/80 text-xs font-medium tracking-wide">Enter access code</span>
      </div>

      {/* Title bar at bottom */}
      <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
        <p className="text-white font-semibold text-sm truncate">{gallery.title}</p>
      </div>
    </button>
  )
}

export function GalleryLanding({ onLogin }: Props) {
  const [selected, setSelected] = useState<PublicGallery | null>(null)

  const { data: galleries = [], isLoading } = useQuery({
    queryKey: ['public-galleries'],
    queryFn: getPublicGalleries,
    staleTime: 60 * 1000,
  })

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Subtle grid background */}
      <div
        className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.8) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.8) 1px,transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative max-w-4xl mx-auto px-4 py-16">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-indigo-600 rounded-2xl mb-5">
            <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Your Galleries</h1>
          <p className="text-zinc-400 text-sm">Select your gallery and enter your access code</p>
        </div>

        {/* Gallery grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="aspect-[4/3] rounded-2xl bg-zinc-800 animate-pulse" />
            ))}
          </div>
        ) : galleries.length === 0 ? (
          <div className="text-center py-24">
            <p className="text-zinc-500 text-sm">No galleries available yet.</p>
            <p className="text-zinc-600 text-xs mt-1">Contact your photographer for access.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {galleries.map(g => (
              <GalleryCard key={g.id} gallery={g} onClick={() => setSelected(g)} />
            ))}
          </div>
        )}

        <p className="text-center text-zinc-700 text-xs mt-10">
          Don't see your gallery? Contact your photographer.
        </p>
      </div>

      {/* Passcode modal */}
      {selected && (
        <PasscodeModal
          gallery={selected}
          onLogin={onLogin}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
