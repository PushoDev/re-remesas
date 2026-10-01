import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Lerd's nginx proxies https://re-re.test here; Vite rejects unknown
    // Host headers by default, so it must be allow-listed.
    allowedHosts: ['re-re.test'],
  },
})
