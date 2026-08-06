import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const devApiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://localhost:5000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: devApiTarget, changeOrigin: true },
      '/health': { target: devApiTarget, changeOrigin: true },
    },
  },
})
