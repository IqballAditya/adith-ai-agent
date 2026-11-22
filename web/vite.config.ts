import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/terminal': {
        target: 'ws://localhost:8090',
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
    },
  },
})
