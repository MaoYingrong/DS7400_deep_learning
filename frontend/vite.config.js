import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// Requests to /api are forwarded to the FastAPI backend (see ../backend), so the browser sees one origin.
const api = { '/api': 'http://localhost:8000' }
export default defineConfig({
  plugins: [react()],
  server: { proxy: api },
  preview: { proxy: api },
})
