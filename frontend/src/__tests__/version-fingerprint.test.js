import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

describe('version fingerprint', () => {
  it('BUILD_TIME is defined and looks like ISO timestamp', () => {
    expect(typeof __BUILD_TIME__).toBe('string')
    expect(__BUILD_TIME__).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  it('GIT_HASH is defined and is 7+ char hex', () => {
    expect(typeof __GIT_HASH__).toBe('string')
    expect(__GIT_HASH__).toMatch(/^[0-9a-f]{7,}$/)
  })

  it('SOURCE_DIRTY is a boolean string', () => {
    expect(typeof __SOURCE_DIRTY__).toBe('string')
    expect(['true', 'false']).toContain(__SOURCE_DIRTY__)
  })

  it('BUILD_ID is defined and starts with build-', () => {
    expect(typeof __BUILD_ID__).toBe('string')
    expect(__BUILD_ID__).toMatch(/^build-\d+$/)
  })
})

describe('frontend build delivery safety', () => {
  const viteConfig = readFileSync('vite.config.js', 'utf-8')

  it('backs up the currently served dist inside the existing Vite build lifecycle', () => {
    expect(viteConfig).toContain("name: 'backup-dist-before-build'")
    expect(viteConfig).toContain("apply: 'build'")
    expect(viteConfig).toContain('configResolved()')
    expect(viteConfig).toContain('FRONTEND_DIST_BACKUP_DIR')
    expect(viteConfig).toContain('backupDistBeforeBuild(),')
  })
})
