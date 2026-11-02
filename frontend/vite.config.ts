import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')) as { version: string }
const buildId = process.env.VITE_BUILD_ID || new Date().toISOString().replace(/\D/g, '').slice(0, 14)
const appVersion = process.env.VITE_APP_VERSION || pkg.version

/**
 * Пишет version.json и подставляет build id в service worker.
 * Клиент сравнивает __APP_BUILD__ с version.json и предлагает обновление.
 */
function buildMeta(): Plugin {
  return {
    name: 'build-meta',
    apply: 'build',
    closeBundle() {
      const dist = 'dist'
      writeFileSync(join(dist, 'version.json'), JSON.stringify({ version: appVersion, build: buildId }))
      const swPath = join(dist, 'sw.js')
      if (existsSync(swPath)) {
        writeFileSync(swPath, readFileSync(swPath, 'utf-8').replaceAll('__BUILD__', buildId))
      }
    },
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_BUILD__: JSON.stringify(buildId),
  },
  plugins: [react(), buildMeta()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
})
