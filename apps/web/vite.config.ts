import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Allow the configured HTTPS ngrok hostname for Firebase phone OTP testing.
    // Keep this specific; avoid exposing the development server to all hosts.
    allowedHosts: ['stoneware-refining-flatfoot.ngrok-free.dev'],
  },
})
