import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/dashboard/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Build a single-page app that can be served from the gateway
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  server: {
    port: 3001,
    proxy: {
      '/mobile': 'http://localhost:8081',
      '/api': 'http://localhost:4800',
    },
  },
})
