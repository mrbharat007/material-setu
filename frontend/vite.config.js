import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard talks to the FastAPI backend at VITE_API (default http://localhost:8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: '127.0.0.1' },
})
