import { useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listGalleries, listPhotos, uploadPhoto, deletePhoto, triggerClustering, listClients, setCoverPhoto, adminFetchBlob, resetGalleryFaces } from '../../api/admin'
import type { PhotoOut } from '../../types'

function AdminPhotoThumb({ galleryId, photoId }: { galleryId: string; photoId: string }) {
  const { data: blobUrl } = useQuery({
    queryKey: ['admin-thumb', galleryId, photoId],
    queryFn: () => adminFetchBlob(`/admin/galleries/${galleryId}/photos/${photoId}/data`),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })
  return blobUrl
    ? <img src={blobUrl} alt="" draggable={false} className="w-full h-full object-cover" />
    : <div className="w-full h-full bg-neutral-700 animate-pulse" />
}

type UploadStatus = 'queued' | 'uploading' | 'ready' | 'failed'
interface UploadEntry {
  file: File
  status: UploadStatus
  error?: string
}

const statusColor: Record<UploadStatus, string> = {
  queued: 'bg-neutral-700 text-neutral-300',
  uploading: 'bg-blue-900/50 text-blue-300',
  ready: 'bg-green-900/50 text-green-400',
  failed: 'bg-red-900/50 text-red-400',
}

export function GalleryDetailPanel() {
  const { id: galleryId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: galleries = [] } = useQuery({ queryKey: ['admin', 'galleries'], queryFn: listGalleries })
  const { data: clients = [] } = useQuery({ queryKey: ['admin', 'clients'], queryFn: listClients })
  const { data: photos = [], isLoading: photosLoading } = useQuery({
    queryKey: ['admin', 'photos', galleryId],
    queryFn: () => listPhotos(galleryId!),
    enabled: !!galleryId,
    refetchInterval: 5000,
  })

  const clusterMut = useMutation({ mutationFn: () => triggerClustering(galleryId!) })
  const resetFacesMut = useMutation({
    mutationFn: () => resetGalleryFaces(galleryId!),
    onSuccess: data => {
      setToast(`Face data reset — ${data.embed_jobs_queued} embed jobs queued`)
      setTimeout(() => setToast(null), 4000)
    },
  })
  const deleteMut = useMutation({
    mutationFn: deletePhoto,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'photos', galleryId] }),
  })
  const coverMut = useMutation({
    mutationFn: (photoId: string) => setCoverPhoto(galleryId!, photoId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'galleries'] })
      setToast('Cover photo updated')
      setTimeout(() => setToast(null), 2500)
    },
  })

  const [uploads, setUploads] = useState<UploadEntry[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [clusterStatus, setClusterStatus] = useState<string | null>(null)

  const gallery = galleries.find(g => g.id === galleryId)
  const client = clients.find(c => c.id === gallery?.client_id)

  const updateEntry = (index: number, patch: Partial<UploadEntry>) => {
    setUploads(prev => prev.map((e, i) => (i === index ? { ...e, ...patch } : e)))
  }

  const handleFiles = async (files: FileList) => {
    const entries: UploadEntry[] = Array.from(files).map(f => ({ file: f, status: 'queued' }))
    const startIndex = uploads.length
    setUploads(prev => [...prev, ...entries])

    for (let i = 0; i < entries.length; i++) {
      const idx = startIndex + i
      const file = entries[i].file
      try {
        updateEntry(idx, { status: 'uploading' })
        await uploadPhoto(galleryId!, file)
        updateEntry(idx, { status: 'ready' })
        void qc.invalidateQueries({ queryKey: ['admin', 'photos', galleryId] })
      } catch (err) {
        updateEntry(idx, { status: 'failed', error: (err as Error).message })
      }
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files)
  }

  const shareUrl = `${window.location.origin}/?g=${galleryId}`

  const copyShare = () => {
    void navigator.clipboard.writeText(shareUrl)
    setToast('Link copied!')
    setTimeout(() => setToast(null), 2000)
  }

  const handleCluster = () => {
    setClusterStatus('running')
    clusterMut.mutate(undefined, {
      onSuccess: () => {
        setTimeout(() => setClusterStatus('finished'), 4000)
      },
      onError: () => setClusterStatus('failed'),
    })
  }

  if (!gallery) {
    return (
      <div>
        <button onClick={() => navigate('/admin/galleries')} className="text-neutral-400 hover:text-white text-sm mb-4 block">
          ← Back to galleries
        </button>
        <p className="text-neutral-500 text-sm">Gallery not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <button onClick={() => navigate('/admin/galleries')} className="text-neutral-500 hover:text-white text-xs mb-3 block transition-colors">
          ← Galleries
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-white text-xl font-semibold">{gallery.title}</h2>
            <p className="text-neutral-500 text-sm mt-0.5">{client?.display_name ?? gallery.client_id.slice(0, 8)}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${gallery.published ? 'bg-green-900/40 text-green-400' : 'bg-neutral-800 text-neutral-500'}`}>
              {gallery.published ? 'Published' : 'Unpublished'}
            </span>
            <button
              onClick={copyShare}
              className="px-3 py-1.5 bg-neutral-800 text-neutral-300 text-xs rounded-lg hover:bg-neutral-700 transition-colors"
            >
              Copy share link
            </button>
            <button
              onClick={handleCluster}
              disabled={clusterMut.isPending || clusterStatus === 'running'}
              className="px-3 py-1.5 bg-neutral-800 text-neutral-300 text-xs rounded-lg hover:bg-neutral-700 disabled:opacity-40 transition-colors"
            >
              {clusterMut.isPending ? 'Queuing…' : 'Run clustering'}
            </button>
            <button
              onClick={() => { if (confirm('Delete all face data and re-run detection for this gallery?')) resetFacesMut.mutate() }}
              disabled={resetFacesMut.isPending}
              className="px-3 py-1.5 bg-neutral-800 text-red-400 text-xs rounded-lg hover:bg-red-950/40 disabled:opacity-40 transition-colors"
            >
              {resetFacesMut.isPending ? 'Resetting…' : 'Reset faces'}
            </button>
          </div>
        </div>

        {/* Clustering status banner */}
        {clusterStatus && (
          <div className={`mt-4 flex items-center justify-between gap-3 rounded-xl px-4 py-3 border ${
            clusterStatus === 'finished'
              ? 'bg-green-950/50 border-green-800/50'
              : clusterStatus === 'failed'
              ? 'bg-red-950/50 border-red-800/50'
              : 'bg-indigo-950/50 border-indigo-800/50'
          }`}>
            <div className="flex items-center gap-2.5">
              {clusterStatus === 'finished' ? (
                <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : clusterStatus === 'failed' ? (
                <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="animate-spin w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              <div>
                {clusterStatus === 'finished' && <p className="text-green-300 text-xs font-medium">Clustering complete — People row is ready</p>}
                {clusterStatus === 'failed' && <p className="text-red-300 text-xs font-medium">Clustering failed — check worker logs</p>}
                {clusterStatus !== 'finished' && clusterStatus !== 'failed' && (
                  <>
                    <p className="text-indigo-300 text-xs font-medium">Clustering in progress…</p>
                    <p className="text-indigo-500 text-xs mt-0.5">Status: {clusterStatus} — checking every 3 s</p>
                  </>
                )}
              </div>
            </div>
            <button onClick={() => setClusterStatus(null)} className="text-neutral-500 hover:text-neutral-300 text-xs transition-colors flex-shrink-0">
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Upload area */}
      <div>
        <h3 className="text-neutral-300 text-sm font-medium mb-3">Upload photos</h3>
        <div
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-neutral-700 rounded-xl p-10 text-center cursor-pointer hover:border-neutral-500 transition-colors"
        >
          <p className="text-neutral-400 text-sm">Drag & drop images here, or click to select</p>
          <p className="text-neutral-600 text-xs mt-1">JPEG, PNG, WebP — multiple files supported</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden"
            onChange={e => { if (e.target.files) void handleFiles(e.target.files); e.target.value = '' }}
          />
        </div>

        {uploads.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {uploads.map((u, i) => (
              <div key={i} className="flex items-center gap-3 bg-neutral-900 rounded-lg px-3 py-2">
                <span className="text-neutral-300 text-xs flex-1 truncate">{u.file.name}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor[u.status]}`}>
                  {u.status}
                </span>
                {u.error && <span className="text-red-400 text-xs truncate max-w-xs" title={u.error}>{u.error}</span>}
              </div>
            ))}
            <button
              onClick={() => setUploads([])}
              className="text-neutral-600 hover:text-neutral-400 text-xs transition-colors"
            >
              Clear list
            </button>
          </div>
        )}
      </div>

      {/* Photos grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-neutral-300 text-sm font-medium">
            Photos {photos.length > 0 && <span className="text-neutral-500">({photos.length})</span>}
          </h3>
          {gallery.cover_photo_id && (
            <span className="text-xs text-indigo-400 flex items-center gap-1">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Cover set
            </span>
          )}
        </div>
        {photosLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-lg bg-neutral-800 animate-pulse" />
            ))}
          </div>
        ) : photos.length === 0 ? (
          <p className="text-neutral-500 text-sm">No photos yet.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {(photos as PhotoOut[]).map(p => {
              const isCover = p.id === gallery.cover_photo_id
              const isReady = p.status === 'ready'
              return (
                <div key={p.id} className="group relative aspect-square rounded-lg overflow-hidden bg-neutral-800">
                  {/* Thumbnail */}
                  {isReady ? (
                    <AdminPhotoThumb galleryId={galleryId!} photoId={p.id} />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        p.status === 'failed' ? 'bg-red-900/40 text-red-400' :
                        p.status === 'processing' ? 'bg-yellow-900/40 text-yellow-300' :
                        'bg-neutral-700 text-neutral-400'
                      }`}>{p.status}</span>
                    </div>
                  )}

                  {/* Cover star badge */}
                  {isCover && (
                    <div className="absolute top-1.5 left-1.5 bg-indigo-600 rounded-full p-1">
                      <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                      </svg>
                    </div>
                  )}

                  {/* Hover overlay */}
                  {isReady && (
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-colors flex flex-col items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100">
                      {!isCover && (
                        <button
                          onClick={() => coverMut.mutate(p.id)}
                          disabled={coverMut.isPending}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                        >
                          Set as cover
                        </button>
                      )}
                      <button
                        onClick={() => { if (confirm('Delete this photo?')) deleteMut.mutate(p.id) }}
                        disabled={deleteMut.isPending}
                        className="bg-red-900/80 hover:bg-red-800 text-red-300 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-neutral-800 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
