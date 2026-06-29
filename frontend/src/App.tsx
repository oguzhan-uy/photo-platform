import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GalleryLanding } from './components/GalleryLanding'
import { LoginScreen } from './components/LoginScreen'
import { GalleryView } from './components/GalleryView'
import { AdminLoginScreen } from './components/admin/AdminLoginScreen'
import { AdminLayout } from './components/admin/AdminLayout'
import { ClientsPanel } from './components/admin/ClientsPanel'
import { GalleriesPanel } from './components/admin/GalleriesPanel'
import { GalleryDetailPanel } from './components/admin/GalleryDetailPanel'
import { DeletionLogPanel } from './components/admin/DeletionLogPanel'
import { useAuth } from './hooks/useAuth'
import { useAdminAuth } from './hooks/useAdminAuth'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function ClientApp() {
  const { token, galleryId, setAuth, clearAuth } = useAuth()

  const urlParams = new URLSearchParams(window.location.search)
  const urlGalleryId = urlParams.get('g')

  const handleLogout = () => {
    queryClient.clear()
    clearAuth()
  }

  if (!token || !galleryId) {
    // Deep-link via ?g=<id> still goes straight to the passcode form.
    if (urlGalleryId) {
      return <LoginScreen urlGalleryId={urlGalleryId} onLogin={setAuth} />
    }
    return <GalleryLanding onLogin={setAuth} />
  }

  return <GalleryView onLogout={handleLogout} />
}

function AdminApp() {
  const { token, setToken, clearToken } = useAdminAuth()

  const handleLogout = () => {
    queryClient.clear()
    clearToken()
  }

  if (!token) {
    return <AdminLoginScreen onLogin={setToken} />
  }

  return (
    <Routes>
      <Route element={<AdminLayout onLogout={handleLogout} />}>
        <Route index element={<Navigate to="/admin/clients" replace />} />
        <Route path="clients" element={<ClientsPanel />} />
        <Route path="galleries" element={<GalleriesPanel />} />
        <Route path="galleries/:id" element={<GalleryDetailPanel />} />
        <Route path="log" element={<DeletionLogPanel />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/app">
        <Routes>
          <Route path="/admin/*" element={<AdminApp />} />
          <Route path="/*" element={<ClientApp />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
