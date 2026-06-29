import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listGalleries, createGallery, listClients } from '../../api/admin'

export function GalleriesPanel() {
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: galleries = [], isLoading } = useQuery({
    queryKey: ['admin', 'galleries'],
    queryFn: listGalleries,
  })
  const { data: clients = [] } = useQuery({
    queryKey: ['admin', 'clients'],
    queryFn: listClients,
  })

  const createMut = useMutation({
    mutationFn: createGallery,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['admin', 'galleries'] }) },
  })

  const [showForm, setShowForm] = useState(false)
  const [clientId, setClientId] = useState('')
  const [title, setTitle] = useState('')
  const [passcode, setPasscode] = useState('')
  const [published, setPublished] = useState(true)
  const [expiresAt, setExpiresAt] = useState('')

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMut.mutate(
      {
        client_id: clientId,
        title,
        passcode,
        published,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      },
      {
        onSuccess: () => {
          setClientId('')
          setTitle('')
          setPasscode('')
          setPublished(true)
          setExpiresAt('')
          setShowForm(false)
        },
      },
    )
  }

  const clientName = (id: string) => clients.find(c => c.id === id)?.display_name ?? id.slice(0, 8)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white text-xl font-semibold">Galleries</h2>
        <button
          onClick={() => setShowForm(v => !v)}
          className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-neutral-200 transition-colors"
        >
          {showForm ? 'Cancel' : '+ New gallery'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-3">
          <div>
            <label className="block text-neutral-400 text-xs mb-1">Client *</label>
            <select
              value={clientId}
              onChange={e => setClientId(e.target.value)}
              required
              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            >
              <option value="">Select a client…</option>
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.display_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1">Title *</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1">Passcode * (min 4 chars)</label>
            <input
              value={passcode}
              onChange={e => setPasscode(e.target.value)}
              required
              minLength={4}
              type="text"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-neutral-400 text-xs">Expires at</label>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={e => setExpiresAt(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={published}
              onChange={e => setPublished(e.target.checked)}
              className="accent-white"
            />
            <span className="text-neutral-400 text-sm">Published</span>
          </label>
          {createMut.error && (
            <p className="text-red-400 text-xs">{(createMut.error as Error).message}</p>
          )}
          <button
            type="submit"
            disabled={createMut.isPending}
            className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-neutral-200 disabled:opacity-40 transition-colors"
          >
            {createMut.isPending ? 'Creating…' : 'Create gallery'}
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-neutral-500 text-sm">Loading…</p>
      ) : galleries.length === 0 ? (
        <p className="text-neutral-500 text-sm">No galleries yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-xs border-b border-neutral-800">
              <th className="text-left pb-2 font-medium">Title</th>
              <th className="text-left pb-2 font-medium">Client</th>
              <th className="text-left pb-2 font-medium">Status</th>
              <th className="text-left pb-2 font-medium">Expires</th>
              <th className="text-left pb-2 font-medium">Created</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/60">
            {galleries.map(g => (
              <tr key={g.id} className="group">
                <td className="py-3 text-white">{g.title}</td>
                <td className="py-3 text-neutral-400">{clientName(g.client_id)}</td>
                <td className="py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${g.published ? 'bg-green-900/40 text-green-400' : 'bg-neutral-800 text-neutral-500'}`}>
                    {g.published ? 'Published' : 'Unpublished'}
                  </span>
                </td>
                <td className="py-3 text-neutral-500">
                  {g.expires_at ? new Date(g.expires_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-3 text-neutral-500">{new Date(g.created_at).toLocaleDateString()}</td>
                <td className="py-3 text-right">
                  <button
                    onClick={() => navigate(`/admin/galleries/${g.id}`)}
                    className="text-neutral-400 hover:text-white text-xs transition-colors"
                  >
                    Open →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
