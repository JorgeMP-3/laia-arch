import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const isTauri = process.env.TAURI_ENV_PLATFORM !== undefined

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Tauri expects a specific dev server port
  server: isTauri
    ? { port: 5173, strictPort: true }
    : {
        port: 5173,
        proxy: {
          '/api': {
            target: 'http://localhost:8077',
            ws: true,
          },
        },
      },
  // Tauri apps should not use hash-based routing interference
  clearScreen: false,
  envPrefix: ['VITE_', 'TAURI_'],
})
