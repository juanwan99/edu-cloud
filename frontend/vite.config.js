import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'

function fixDistPermissions() {
  return {
    name: 'fix-dist-permissions',
    closeBundle() {
      try {
        execSync('chmod -R o+rX dist/', { cwd: fileURLToPath(new URL('.', import.meta.url)) })
      } catch {}
    },
  }
}

export default defineConfig({
  plugins: [vue(), fixDistPermissions()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'naive-ui': ['naive-ui'],
          'echarts': ['echarts', 'vue-echarts'],
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'marked-katex': ['marked', 'katex'],
          'antv-g6': ['@antv/g6'],
          'html2canvas': ['html2canvas'],
        },
      },
    },
  },
  test: {
    environment: 'happy-dom',
    globals: true,
  },
})
