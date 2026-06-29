import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getClusters, getGallery, getPhotos, getPhotosByCluster } from '../api/gallery'
import { PeopleRow } from './PeopleRow'
import { PhotoGrid } from './PhotoGrid'
import { Lightbox } from './Lightbox'
import type { Photo } from '../types'

interface Props {
  onLogout: () => void
}

interface LightboxState {
  photos: Photo[]
  index: number
}

export function GalleryView({ onLogout }: Props) {
  const [activeCluster, setActiveCluster] = useState<number | null>(null)
  const [lightbox, setLightbox] = useState<LightboxState | null>(null)

  const { data: gallery, isLoading: galleryLoading } = useQuery({
    queryKey: ['gallery'],
    queryFn: getGallery,
  })

  const { data: allPhotos = [], isLoading: photosLoading } = useQuery({
    queryKey: ['photos'],
    queryFn: getPhotos,
  })

  // 403 means no consent → treat as empty. We retry:false to avoid spam.
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => getClusters().catch(() => []),
    retry: false,
  })

  const { data: clusterPhotos, isLoading: clusterLoading } = useQuery({
    queryKey: ['photos-by-cluster', activeCluster],
    queryFn: () => getPhotosByCluster(activeCluster!),
    enabled: activeCluster !== null,
  })

  const displayPhotos = activeCluster !== null ? (clusterPhotos ?? []) : allPhotos
  const isLoading = photosLoading || (activeCluster !== null && clusterLoading)

  const openLightbox = (index: number) => setLightbox({ photos: displayPhotos, index })

  const handleClusterSelect = (clusterId: number | null) => {
    setActiveCluster(clusterId)
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Sticky header */}
      <header className="sticky top-0 z-20 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/60">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5 mr-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            {galleryLoading ? (
              <div className="h-4 w-32 bg-zinc-800 rounded animate-pulse" />
            ) : (
              <h1 className="text-white font-medium text-sm truncate">{gallery?.title}</h1>
            )}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Photo count */}
          {!isLoading && (
            <span className="text-zinc-500 text-xs tabular-nums hidden sm:block">
              {displayPhotos.length} photo{displayPhotos.length !== 1 ? 's' : ''}
              {activeCluster !== null && ' in filter'}
            </span>
          )}

          {/* Sign out */}
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 text-zinc-500 hover:text-white text-sm transition-colors ml-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      {/* People row (only when clusters exist) */}
      <PeopleRow
        clusters={clusters}
        allPhotos={allPhotos}
        activeCluster={activeCluster}
        onSelect={handleClusterSelect}
      />

      {/* Photo grid */}
      <main>
        <PhotoGrid
          photos={displayPhotos}
          onOpenLightbox={openLightbox}
          loading={isLoading}
        />
      </main>

      {/* Lightbox */}
      {lightbox && (
        <Lightbox
          photos={lightbox.photos}
          initialIndex={lightbox.index}
          onClose={() => setLightbox(null)}
        />
      )}
    </div>
  )
}
