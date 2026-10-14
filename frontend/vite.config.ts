import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The desk runs on :5173 and calls the FastAPI backend at http://localhost:8000 directly
// (the backend's CORS allows this origin). Override with VITE_API_BASE if needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    open: true,
  },
})
