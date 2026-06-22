import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
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
const distBackupLimit = Number.parseInt(process.env.FRONTEND_DIST_BACKUP_LIMIT || '20', 10)

function formatBackupStamp(date) {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
}

function resolveDistBackupRoot() {
  if (process.env.FRONTEND_DIST_BACKUP_DIR) return process.env.FRONTEND_DIST_BACKUP_DIR
  if (existsSync('/home/ops')) return '/home/ops/backups/edu-cloud/frontend-dist'
  return null
}

function readCurrentDistVersion(versionPath) {
  try {
    return JSON.parse(readFileSync(versionPath, 'utf-8'))
  } catch {
    return {}
  }
}

function pruneDistBackups(backupRoot) {
  if (!Number.isFinite(distBackupLimit) || distBackupLimit <= 0) return
  const backups = readdirSync(backupRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()

  for (const name of backups.slice(0, Math.max(0, backups.length - distBackupLimit))) {
    rmSync(join(backupRoot, name), { recursive: true, force: true })
  }
}

function backupDistBeforeBuild() {
  return {
    name: 'backup-dist-before-build',
    apply: 'build',
    configResolved() {
      const distDir = join(projectRoot, 'dist')
      const versionPath = join(distDir, 'version.json')
      const indexPath = join(distDir, 'index.html')
      if (!existsSync(versionPath) || !existsSync(indexPath)) return

      const backupRoot = resolveDistBackupRoot()
      if (!backupRoot) return

      const previousVersion = readCurrentDistVersion(versionPath)
      const previousBuildId = previousVersion.build_id || previousVersion.git_hash || 'unknown-build'
      const backupDir = join(backupRoot, `${formatBackupStamp(new Date())}-${previousBuildId}-before-${buildId}`)

      mkdirSync(backupDir, { recursive: true })
      cpSync(distDir, join(backupDir, 'dist'), {
        recursive: true,
        dereference: false,
        preserveTimestamps: true,
      })
      writeFileSync(join(backupDir, 'manifest.json'), JSON.stringify({
        created_at: new Date().toISOString(),
        reason: 'automatic backup before Vite overwrites frontend/dist',
        previous_version: previousVersion,
        next_build_id: buildId,
        project_root: projectRoot,
      }, null, 2) + '\n')
      pruneDistBackups(backupRoot)
      console.log(`[vite] backed up existing dist to ${backupDir}`)
    },
  }
}

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
      if (process.platform === 'win32') return
      try {
        execSync('chmod -R o+rX dist/', { cwd: projectRoot })
      } catch {}
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      imports: [
        { 'naive-ui': ['useDialog', 'useMessage', 'useNotification', 'useLoadingBar'] },
      ],
    }),
    Components({
      resolvers: [NaiveUiResolver()],
    }),
    backupDistBeforeBuild(),
    generateVersionJson(),
    fixDistPermissions(),
  ],
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
        manualChunks: (id) => {
          if (id.includes('node_modules/echarts/') || id.includes('node_modules/vue-echarts/')) return 'echarts';
          if (id.includes('node_modules/vue/') || id.includes('node_modules/vue-router/') || id.includes('node_modules/pinia/')) return 'vue-vendor';
          if (id.includes('node_modules/katex/')) return 'katex';
          if (id.includes('node_modules/@antv/g6/')) return 'antv-g6';
          if (id.includes('node_modules/html2canvas/')) return 'html2canvas';
        },
      },
    },
  },
  test: {
    environment: 'happy-dom',
    globals: true,
  },
})
