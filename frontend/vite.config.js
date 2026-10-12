import path from 'node:path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import frappeui from 'frappe-ui/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => ({
  define: {
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
  },
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        indexHtmlPath: '../onechat/www/onechat.html',
        emptyOutDir: true,
      },
    }),
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'script-defer',
      workbox: {
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,svg,png,woff2}'],
        navigateFallback: null,
      },
      manifest: false,
    }),
  ],
  server: {
    allowedHosts: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      'tailwind.config.js': path.resolve(__dirname, 'tailwind.config.js'),
    },
    dedupe: ['vue'],
  },
  build: {
    outDir: '../onechat/public/frontend',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
  optimizeDeps: {
    exclude: mode === 'production' ? [] : ['frappe-ui'],
  },
}))
