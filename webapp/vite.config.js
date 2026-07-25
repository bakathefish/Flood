import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves this repo's docs/ at /Flood/
  base: '/Flood/',
  plugins: [react()],
  build: {outDir: 'dist', chunkSizeWarningLimit: 1200},
})
