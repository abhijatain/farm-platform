import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Vite stays public through ONE ngrok tunnel; FastAPI stays local.
    // Never use allowedHosts: true on an exposed development server.
    allowedHosts: ['stoneware-refining-flatfoot.ngrok-free.dev'],
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/tiler': {
        target: 'http://127.0.0.1:8081',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/tiler/, ''),
      },
    },
  },
})
