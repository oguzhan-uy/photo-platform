import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listClients, createClient, deleteClient, patchConsent } from '../../api/admin'
import type { ClientOut } from '../../types'

export function ClientsPanel() {
  const qc = useQueryClient()
  const { data: clients = [], isLoading } = useQuery({ queryKey: ['admin', 'clients'], queryFn: listClients })

  const createMut = useMutation({
    mutationFn: createClient,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['admin', 'clients'] }) },
  })
  const consentMut = useMutation({
    mutationFn: ({ id, consent }: { id: string; consent: boolean }) => patchConsent(id, consent),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['admin', 'clients'] }) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteClient,
    onSuccess: () => {
      setConfirmDelete(null)
      void qc.invalidateQueries({ queryKey: ['admin', 'clients'] })
    },
  })

  const [showForm, setShowForm] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [contact, setContact] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<ClientOut | null>(null)
  const [confirmText, setConfirmText] = useState('')

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMut.mutate(
      { display_name: displayName, contact: contact || undefined },
      {
        onSuccess: () => {
          setDisplayName('')
          setContact('')
          setShowForm(false)
        },
      },
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white text-xl font-semibold">Clients</h2>
        <button
          onClick={() => setShowForm(v => !v)}
          className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-neutral-200 transition-colors"
        >
          {showForm ? 'Cancel' : '+ New client'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-3">
          <div>
            <label className="block text-neutral-400 text-xs mb-1">Display name *</label>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              required
              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1">Contact (email / phone)</label>
            <input
              value={contact}
              onChange={e => setContact(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-neutral-500"
            />
          </div>
          {createMut.error && (
            <p className="text-red-400 text-xs">{(createMut.error as Error).message}</p>
          )}
          <button
            type="submit"
            disabled={createMut.isPending}
            className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-neutral-200 disabled:opacity-40 transition-colors"
          >
            {createMut.isPending ? 'Creating…' : 'Create client'}
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-neutral-500 text-sm">Loading…</p>
      ) : clients.length === 0 ? (
        <p className="text-neutral-500 text-sm">No clients yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-xs border-b border-neutral-800">
              <th className="text-left pb-2 font-medium">Name</th>
              <th className="text-left pb-2 font-medium">Contact</th>
              <th className="text-left pb-2 font-medium">Biometric consent</th>
              <th className="text-left pb-2 font-medium">Created</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/60">
            {clients.map(c => (
              <tr key={c.id} className="group">
                <td className="py-3 text-white">{c.display_name}</td>
                <td className="py-3 text-neutral-400">{c.contact ?? '—'}</td>
                <td className="py-3">
                  <button
                    onClick={() => consentMut.mutate({ id: c.id, consent: !c.consent_biometric })}
                    className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                      c.consent_biometric
                        ? 'bg-green-900/50 text-green-400 hover:bg-red-900/50 hover:text-red-400'
                        : 'bg-neutral-800 text-neutral-400 hover:bg-green-900/50 hover:text-green-400'
                    }`}
                  >
                    {c.consent_biometric ? 'Granted' : 'Not granted'}
                  </button>
                </td>
                <td className="py-3 text-neutral-500">{new Date(c.created_at).toLocaleDateString()}</td>
                <td className="py-3 text-right">
                  <button
                    onClick={() => { setConfirmDelete(c); setConfirmText('') }}
                    className="text-neutral-600 hover:text-red-400 text-xs transition-colors"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Confirm delete modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-sm space-y-4">
            <h3 className="text-white font-semibold">Delete client?</h3>
            <p className="text-neutral-400 text-sm">
              This permanently deletes <span className="text-white">{confirmDelete.display_name}</span> and all
              their galleries, photos, and face data. This cannot be undone.
            </p>
            <div>
              <label className="block text-neutral-400 text-xs mb-1">Type DELETE to confirm</label>
              <input
                value={confirmText}
                onChange={e => setConfirmText(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-white text-sm focus:outline-none"
                autoFocus
              />
            </div>
            {deleteMut.error && (
              <p className="text-red-400 text-xs">{(deleteMut.error as Error).message}</p>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 px-4 py-2 bg-neutral-800 text-neutral-300 text-sm rounded-lg hover:bg-neutral-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMut.mutate(confirmDelete.id)}
                disabled={confirmText !== 'DELETE' || deleteMut.isPending}
                className="flex-1 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {deleteMut.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
