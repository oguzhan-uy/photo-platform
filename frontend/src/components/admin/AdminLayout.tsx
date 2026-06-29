import { NavLink, Outlet } from 'react-router-dom'

interface Props {
  onLogout: () => void
}

const navItem = 'block px-3 py-2 rounded-md text-sm transition-colors'
const active = 'bg-neutral-800 text-white'
const inactive = 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'

export function AdminLayout({ onLogout }: Props) {
  return (
    <div className="min-h-screen bg-neutral-950 flex">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 border-r border-neutral-800 flex flex-col">
        <div className="px-4 py-5 border-b border-neutral-800">
          <span className="text-white font-semibold text-sm">Admin Panel</span>
        </div>

        <nav className="flex-1 px-2 py-4 space-y-0.5">
          <NavLink
            to="/admin/clients"
            className={({ isActive }) => `${navItem} ${isActive ? active : inactive}`}
          >
            Clients
          </NavLink>
          <NavLink
            to="/admin/galleries"
            className={({ isActive }) => `${navItem} ${isActive ? active : inactive}`}
          >
            Galleries
          </NavLink>
          <NavLink
            to="/admin/log"
            className={({ isActive }) => `${navItem} ${isActive ? active : inactive}`}
          >
            Deletion Log
          </NavLink>
        </nav>

        <div className="px-2 py-4 border-t border-neutral-800">
          <button
            onClick={onLogout}
            className="w-full text-left px-3 py-2 rounded-md text-sm text-neutral-500 hover:text-white hover:bg-neutral-800/50 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
