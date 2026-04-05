import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: 'dist/stats.html',
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8923,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 200,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query', 'zustand'],
          'markdown-vendor': [
            'react-markdown',
            'remark-gfm',
            'rehype-sanitize',
            'rehype-slug',
          ],
          'wavesurfer-vendor': ['wavesurfer.js', '@wavesurfer/react'],
          'i18n-vendor': [
            'i18next',
            'react-i18next',
            'i18next-http-backend',
            'i18next-browser-languagedetector',
          ],
        },
      },
    },
  },
})
