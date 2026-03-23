/**
 * CardEditor & export.js API path tests — R3-02 fix
 *
 * Verifies that all fetch calls in CardEditor.vue and card-editor/export.js
 * use the /api/v1/ prefix. Uses static analysis (grep-style) to catch
 * path regressions without needing to mount Vue components.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const srcDir = resolve(__dirname, '..')

function readSource(relativePath) {
  return readFileSync(resolve(srcDir, relativePath), 'utf-8')
}

function findFetchCalls(source) {
  // Match fetch('...') and fetch(`...`) patterns
  const matches = []
  const regex = /fetch\(\s*[`'"]([^`'"]+)[`'"]/g
  let match
  while ((match = regex.exec(source)) !== null) {
    matches.push(match[1])
  }
  // Also match template literal fetch calls with ${} interpolation
  const templateRegex = /fetch\(\s*`([^`]+)`/g
  while ((match = templateRegex.exec(source)) !== null) {
    const path = match[1].replace(/\$\{[^}]+\}/g, '{param}')
    if (!matches.includes(path) && !matches.some(m => path.startsWith(m.replace(/\$\{[^}]+\}/g, '{param}')))) {
      matches.push(path)
    }
  }
  return [...new Set(matches)]
}


describe('CardEditor.vue API paths', () => {
  const source = readSource('components/CardEditor.vue')
  const paths = findFetchCalls(source)

  it('has fetch calls to verify', () => {
    expect(paths.length).toBeGreaterThan(0)
  })

  it('all fetch paths use /api/v1/ prefix', () => {
    const wrongPaths = paths.filter(p =>
      p.startsWith('/api/') && !p.startsWith('/api/v1/')
    )
    expect(wrongPaths, `Found old /api/ paths without /v1/: ${wrongPaths.join(', ')}`).toEqual([])
  })

  it('references /api/v1/card/ endpoints', () => {
    const cardPaths = paths.filter(p => p.includes('/api/v1/card/'))
    expect(cardPaths.length).toBeGreaterThanOrEqual(2)  // tql-reference + editor-layout
  })
})


describe('card-editor/export.js API paths', () => {
  const source = readSource('card-editor/export.js')
  const paths = findFetchCalls(source)

  it('has fetch calls to verify', () => {
    expect(paths.length).toBeGreaterThan(0)
  })

  it('all fetch paths use /api/v1/ prefix', () => {
    const wrongPaths = paths.filter(p =>
      p.startsWith('/api/') && !p.startsWith('/api/v1/')
    )
    expect(wrongPaths, `Found old /api/ paths without /v1/: ${wrongPaths.join(', ')}`).toEqual([])
  })

  it('references /api/v1/card/export/ endpoints', () => {
    const exportPaths = paths.filter(p => p.includes('/api/v1/card/export/'))
    expect(exportPaths.length).toBeGreaterThanOrEqual(2)  // pdf + skeleton
  })

  it('references /api/v1/templates/ endpoint', () => {
    const tplPaths = paths.filter(p => p.includes('/api/v1/templates/'))
    expect(tplPaths.length).toBeGreaterThanOrEqual(1)
  })
})
