import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Allow access via localhost, LAN IP, and Docker-published port
    allowedHosts: true,
    watch: {
      usePolling: true,
    },
  },
})
