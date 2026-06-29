import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // In dev, proxy API calls to the FastAPI server so there are no CORS issues.
  server: {
    port: 5173,
    proxy: {
      '/access':    'http://localhost:8000',
      '/me':        'http://localhost:8000',
      '/galleries': 'http://localhost:8000',
      '/health':    'http://localhost:8000',
      '/admin': {
        target: 'http://localhost:8000',
        bypass(req) {
          // Browser navigations include text/html — serve index.html so React Router handles them
          const accept = req.headers['accept'] ?? ''
          if (accept.includes('text/html')) return '/index.html'
          return null
        },
      },
    },
  },
  build: {
    // Output to frontend-dist/ at the repo root so Dockerfile and FastAPI can find it.
    outDir: '../frontend-dist',
    emptyOutDir: true,
  },
})
