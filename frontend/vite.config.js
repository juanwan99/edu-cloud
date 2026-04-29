import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

function getGitHash() {
  try { return execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim() }
  catch { return 'unknown' }
}

function isSourceDirty() {
  try {
    execSync('git diff --quiet -- src/ vite.config.js package.json index.html', { cwd: fileURLToPath(new URL('.', import.meta.url)) })
    return false
  } catch { return true }
}

const buildId = `build-${Date.now()}`

function generateVersionJson() {
  return {
    name: 'generate-version-json',
    closeBundle() {
      const distDir = fileURLToPath(new URL('./dist', import.meta.url))
      const data = {
        build_time: new Date().toISOString(),
        git_hash: getGitHash(),
        source_dirty: isSourceDirty(),
        build_id: buildId,
      }
      writeFileSync(`${distDir}/version.json`, JSON.stringify(data, null, 2) + '\n')
    },
  }
}

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
  plugins: [vue(), generateVersionJson(), fixDistPermissions()],
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    __GIT_HASH__: JSON.stringify(getGitHash()),
    __SOURCE_DIRTY__: JSON.stringify(String(isSourceDirty())),
    __BUILD_ID__: JSON.stringify(buildId),
  },
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
