import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  // Never expose private-GCS tiler endpoints over a public tunnel by default.
  // Opt in only for a short-lived development session with disposable data.
  const enableDevTilerProxy = env.ENABLE_DEV_TILER_PROXY === 'true'

  return {
    plugins: [react()],
    server: {
      // Keep the ngrok host allow-list narrow; never use allowedHosts: true.
      allowedHosts: ['stoneware-refining-flatfoot.ngrok-free.dev'],
      proxy: {
        '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        ...(enableDevTilerProxy ? {
          '/tiler': {
            target: 'http://127.0.0.1:8081',
            changeOrigin: true,
            rewrite: (path: string) => path.replace(/^\/tiler/, ''),
          },
        } : {}),
      },
    },
  }
})
