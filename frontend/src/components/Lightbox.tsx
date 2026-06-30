import { useEffect, useCallback, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetchBlob } from '../api/client'
import type { Photo } from '../types'

interface Props {
  photos: Photo[]
  initialIndex: number
  onClose: () => void
}

function usePhotoBlob(photoId: string, enabled = true) {
  return useQuery({
    queryKey: ['photo-blob', photoId],
    queryFn: () => apiFetchBlob(`/me/photos/${photoId}/data`),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })
}

export function Lightbox({ photos, initialIndex, onClose }: Props) {
  const [index, setIndex] = useState(initialIndex)
  const photo = photos[index]

  const canPrev = index > 0
  const canNext = index < photos.length - 1

  const prev = useCallback(() => setIndex(i => Math.max(0, i - 1)), [])
  const next = useCallback(() => setIndex(i => Math.min(photos.length - 1, i + 1)), [photos.length])

  const { data: blobUrl, isLoading } = usePhotoBlob(photo.id)
  // Pre-fetch adjacent photos
  usePhotoBlob(photos[index + 1]?.id, canNext)
  usePhotoBlob(photos[index - 1]?.id, canPrev)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center animate-fade-in"
      onClick={onClose}
    >
      <div className="absolute top-4 right-4 flex items-center gap-2">
        {blobUrl && (
          <a
            href={blobUrl}
            download={`photo-${photo.id}.jpg`}
            onClick={e => e.stopPropagation()}
            className="text-white/60 hover:text-white transition-colors p-2 rounded-full hover:bg-white/10"
            aria-label="Download"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </a>
        )}
        <button
          className="text-white/60 hover:text-white transition-colors p-2 rounded-full hover:bg-white/10"
          onClick={onClose}
          aria-label="Close"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="absolute top-4 left-1/2 -translate-x-1/2 text-white/50 text-sm tabular-nums">
        {index + 1} / {photos.length}
      </div>

      {canPrev && (
        <button
          className="absolute left-3 top-1/2 -translate-y-1/2 text-white/60 hover:text-white transition-colors p-3 rounded-full hover:bg-white/10 hidden sm:flex"
          onClick={e => { e.stopPropagation(); prev() }}
          aria-label="Previous"
        >
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {canNext && (
        <button
          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/60 hover:text-white transition-colors p-3 rounded-full hover:bg-white/10 hidden sm:flex"
          onClick={e => { e.stopPropagation(); next() }}
          aria-label="Next"
        >
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      <div
        className="relative max-w-[90vw] max-h-[85vh] flex items-center justify-center"
        onClick={e => e.stopPropagation()}
      >
        {isLoading ? (
          <div className="w-64 h-64 flex items-center justify-center">
            <svg className="animate-spin w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : blobUrl ? (
          <img
            key={photo.id}
            src={blobUrl}
            alt=""
            draggable={false}
            className="max-w-full max-h-[85vh] object-contain rounded-sm shadow-2xl animate-fade-in"
            style={photo.width && photo.height ? { aspectRatio: `${photo.width}/${photo.height}` } : undefined}
          />
        ) : null}
      </div>

      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-3 sm:hidden">
        <button onClick={e => { e.stopPropagation(); prev() }} disabled={!canPrev}
          className="text-white/40 disabled:opacity-20 hover:text-white/80 transition-colors p-2">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button onClick={e => { e.stopPropagation(); next() }} disabled={!canNext}
          className="text-white/40 disabled:opacity-20 hover:text-white/80 transition-colors p-2">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  )
}
