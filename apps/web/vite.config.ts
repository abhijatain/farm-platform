import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig(() => {
  return {
    plugins: [react()],
    server: {
      // Keep the ngrok host allow-list narrow; never use allowedHosts: true.
      allowedHosts: ['stoneware-refining-flatfoot.ngrok-free.dev'],
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
  }
})
