import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Lerd's nginx proxies https://re-re.test here; Vite rejects unknown
    // Host headers by default, so it must be allow-listed.
    allowedHosts: ['re-re.test'],
    // The browser only talks to https://re-re.test; /api is forwarded to
    // Django. Same origin means the httpOnly refresh cookie is first-party
    // (no cross-site cookie issues) and no CORS is needed in the browser.
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
