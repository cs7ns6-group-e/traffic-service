import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const EU_BACKEND = 'http://35.240.110.205'
const proxyTarget = { target: EU_BACKEND, changeOrigin: true }

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  assetsInclude: ['**/*.svg', '**/*.csv'],
  server: {
    proxy: {
      '/auth':      proxyTarget,
      '/journeys':  proxyTarget,
      '/route':     proxyTarget,
      '/routes':    proxyTarget,
      '/conflicts': proxyTarget,
      '/search':    proxyTarget,
      '/authority': proxyTarget,
      '/admin':     proxyTarget,
      '/notify':    proxyTarget,
    },
  },
})
