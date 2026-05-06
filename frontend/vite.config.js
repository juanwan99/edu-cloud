import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

function findGitPath(startDir) {
  let dir = startDir
  while (true) {
    const candidate = join(dir, '.git')
    if (existsSync(candidate)) return candidate
    const parent = dirname(dir)
    if (parent === dir) return null
    dir = parent
  }
}

function resolveGitDir(gitPath) {
  if (statSync(gitPath).isDirectory()) return gitPath
  const content = readFileSync(gitPath, 'utf-8').trim()
  const match = content.match(/^gitdir:\s*(.+)$/)
  if (!match) return null
  return resolve(dirname(gitPath), match[1])
}

function readGitHashFromFiles() {
  const gitPath = findGitPath(projectRoot)
  if (!gitPath) return null

  const gitDir = resolveGitDir(gitPath)
  if (!gitDir) return null

  const head = readFileSync(join(gitDir, 'HEAD'), 'utf-8').trim()
  if (!head.startsWith('ref: ')) return head.slice(0, 7)

  const ref = head.slice(5)
  const refPath = join(gitDir, ref)
  if (existsSync(refPath)) return readFileSync(refPath, 'utf-8').trim().slice(0, 7)

  const packedRefsPath = join(gitDir, 'packed-refs')
  if (!existsSync(packedRefsPath)) return null

  const packedRef = readFileSync(packedRefsPath, 'utf-8')
    .split('\n')
    .find((line) => line.endsWith(` ${ref}`))
  return packedRef ? packedRef.split(' ')[0].slice(0, 7) : null
}

function getGitHash() {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: projectRoot, encoding: 'utf-8' }).trim()
  } catch {
    try {
      const hash = readGitHashFromFiles()
      return /^[0-9a-f]{7,}$/i.test(hash) ? hash.toLowerCase() : 'unknown'
    } catch {
      return 'unknown'
    }
  }
}

function isSourceDirty() {
  try {
    execSync('git diff --quiet HEAD -- src/ vite.config.js package.json index.html', { cwd: projectRoot })
    return false
  } catch { return true }
}

const buildId = `build-${Date.now()}`
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:9000'

function generateVersionJson() {
  return {
    name: 'generate-version-json',
    closeBundle() {
      const distDir = join(projectRoot, 'dist')
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
        execSync('chmod -R o+rX dist/', { cwd: projectRoot })
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
    host: '127.0.0.1',
    port: 8080,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/uploads': {
        target: apiProxyTarget,
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
