import { useQuery } from '@tanstack/react-query'
import { getPhotoFaces } from '../api/gallery'
import { apiFetchBlob } from '../api/client'
import { computeFaceCrop } from '../lib/faceCrop'
import type { Cluster, Photo } from '../types'

const CIRCLE_SIZE = 56

interface Props {
  cluster: Cluster
  representativePhoto: Photo | undefined
  isActive: boolean
  onClick: () => void
}

export function FaceCircle({ cluster, representativePhoto, isActive, onClick }: Props) {
  const { data: blobUrl } = useQuery({
    queryKey: ['face-photo-blob', cluster.representative_photo_id],
    queryFn: () => apiFetchBlob(`/me/photos/${cluster.representative_photo_id}/data`),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })

  const { data: faces } = useQuery({
    queryKey: ['photo-faces', cluster.representative_photo_id],
    queryFn: () => getPhotoFaces(cluster.representative_photo_id),
    staleTime: Infinity, // face bboxes never change
  })

  const firstFace = faces?.[0]
  const cropStyle =
    firstFace && representativePhoto
      ? computeFaceCrop(representativePhoto, firstFace, CIRCLE_SIZE)
      : null

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-2 flex-shrink-0 group"
      title={`Person ${cluster.cluster_id + 1} · ${cluster.face_count} photo${cluster.face_count !== 1 ? 's' : ''}`}
    >
      {/* Face circle */}
      <div
        className={`relative overflow-hidden rounded-full transition-all duration-200
          ${isActive
            ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-zinc-950 scale-110'
            : 'ring-1 ring-zinc-700 group-hover:ring-zinc-500'
          }`}
        style={{ width: CIRCLE_SIZE, height: CIRCLE_SIZE }}
      >
        {blobUrl ? (
          <img
            src={blobUrl}
            alt=""
            draggable={false}
            style={cropStyle ?? { width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div className="w-full h-full bg-zinc-800 animate-pulse" />
        )}
      </div>

      {/* Count badge */}
      <span className={`text-xs tabular-nums transition-colors
        ${isActive ? 'text-indigo-400 font-medium' : 'text-zinc-500 group-hover:text-zinc-300'}`}>
        {cluster.face_count}
      </span>
    </button>
  )
}
