import { FaceCircle } from './FaceCircle'
import type { Cluster, Photo } from '../types'

interface Props {
  clusters: Cluster[]
  allPhotos: Photo[]
  activeCluster: number | null
  onSelect: (clusterId: number | null) => void
}

export function PeopleRow({ clusters, allPhotos, activeCluster, onSelect }: Props) {
  if (clusters.length === 0) return null

  const photoById = new Map(allPhotos.map(p => [p.id, p]))

  return (
    <div className="bg-zinc-950 border-b border-zinc-800/60">
      <div className="max-w-7xl mx-auto px-4 pt-4">
        <div className="flex items-center gap-1 mb-3">
          <svg className="w-3.5 h-3.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">People</span>
        </div>
      </div>

      {/* Scroll container is intentionally outside max-w-7xl so it spans the full width */}
      <div className="overflow-x-auto pb-4">
        <div className="flex gap-4 px-4 w-max">
          {/* "All" chip */}
          <button
            onClick={() => onSelect(null)}
            className="flex flex-col items-center gap-2 flex-shrink-0 group"
          >
            <div
              className={`flex items-center justify-center rounded-full transition-all duration-200
                ${activeCluster === null
                  ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-zinc-950 bg-indigo-600 scale-110'
                  : 'ring-1 ring-zinc-700 bg-zinc-800 group-hover:ring-zinc-500'
                }`}
              style={{ width: 56, height: 56 }}
            >
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </div>
            <span className={`text-xs transition-colors
              ${activeCluster === null ? 'text-indigo-400 font-medium' : 'text-zinc-500 group-hover:text-zinc-300'}`}>
              All
            </span>
          </button>

          {clusters.map(cluster => (
            <FaceCircle
              key={cluster.cluster_id}
              cluster={cluster}
              representativePhoto={photoById.get(cluster.representative_photo_id)}
              isActive={activeCluster === cluster.cluster_id}
              onClick={() =>
                onSelect(activeCluster === cluster.cluster_id ? null : cluster.cluster_id)
              }
            />
          ))}
        </div>
      </div>
    </div>
  )

}
