import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const EU_BACKEND = 'http://35.240.110.205'
const proxyTarget = { target: EU_BACKEND, changeOrigin: true }

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],

  server: {
    proxy: {
      '/auth':      proxyTarget,
      '/journeys':  proxyTarget,
      '/route':     proxyTarget,
      '/routes':    proxyTarget,
      '/authority': proxyTarget,
      '/admin':     proxyTarget,
    },
  },
})
