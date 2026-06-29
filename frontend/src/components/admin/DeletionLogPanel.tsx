import { useQuery } from '@tanstack/react-query'
import { getDeletionLog } from '../../api/admin'

export function DeletionLogPanel() {
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['admin', 'deletion-log'],
    queryFn: () => getDeletionLog(100),
  })

  return (
    <div>
      <h2 className="text-white text-xl font-semibold mb-6">Deletion Log</h2>

      {isLoading ? (
        <p className="text-neutral-500 text-sm">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-neutral-500 text-sm">No deletion events yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-xs border-b border-neutral-800">
              <th className="text-left pb-2 font-medium">Event</th>
              <th className="text-left pb-2 font-medium">Target</th>
              <th className="text-left pb-2 font-medium">Target ID</th>
              <th className="text-left pb-2 font-medium">Photos</th>
              <th className="text-left pb-2 font-medium">Faces</th>
              <th className="text-left pb-2 font-medium">R2 objects</th>
              <th className="text-left pb-2 font-medium">By</th>
              <th className="text-left pb-2 font-medium">At</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/60">
            {entries.map(e => (
              <tr key={e.id}>
                <td className="py-2.5">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    e.event_type === 'client_delete' ? 'bg-red-900/40 text-red-400' :
                    e.event_type === 'consent_revoke' ? 'bg-orange-900/40 text-orange-400' :
                    'bg-neutral-800 text-neutral-400'
                  }`}>
                    {e.event_type}
                  </span>
                </td>
                <td className="py-2.5 text-neutral-400 text-xs">{e.target_type}</td>
                <td className="py-2.5 text-neutral-500 font-mono text-xs">{e.target_id.slice(0, 8)}…</td>
                <td className="py-2.5 text-neutral-400 text-xs">{e.purged_photos}</td>
                <td className="py-2.5 text-neutral-400 text-xs">{e.purged_faces}</td>
                <td className="py-2.5 text-neutral-400 text-xs">{e.purged_r2_objects}</td>
                <td className="py-2.5 text-neutral-500 text-xs">{e.executed_by}</td>
                <td className="py-2.5 text-neutral-500 text-xs">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
