import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  base: '/static/dist/',
  build: {
    outDir: resolve(rootDir, '../static/dist'),
    emptyOutDir: true,
    sourcemap: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      input: resolve(rootDir, 'index.html'),
      output: {
        entryFileNames: 'assets/satria.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith('.css') ? 'assets/satria.css' : 'assets/[name]-[hash][extname]',
        manualChunks: (id) => {
          if (id.includes('recharts')) return 'chart-engine'
          if (id.includes('@react-three') || id.includes('/three/')) return 'spatial-engine'
          if (id.includes('react') || id.includes('zustand') || id.includes('lucide-react')) return 'react-runtime'
          return undefined
        },
      },
    },
  },
})
