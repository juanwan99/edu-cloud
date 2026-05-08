/**
 * CardEditor & export.js API path tests — R3-02 fix
 *
 * Verifies that CardEditor.vue and card-editor/export.js use the unified
 * Axios client (baseURL /api/v1) instead of raw fetch. Uses static analysis
 * (grep-style) to catch regressions without needing to mount Vue components.
 *
 * N-M02/M03: migrated from fetch to Axios client — paths no longer contain
 * /api/v1 prefix (handled by client.baseURL).
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

/** Find client.get/post/put/delete('path') calls */
function findClientCalls(source) {
  const matches = []
  // client.method('path') or client.method(`path`)
  const regex = /client\.(get|post|put|delete|patch)\(\s*[`'"]([^`'"]+)[`'"]/g
  let match
  while ((match = regex.exec(source)) !== null) {
    matches.push({ method: match[1], path: match[2].replace(/\$\{[^}]+\}/g, '{param}') })
  }
  return matches
}


describe('CardEditor.vue API paths', () => {
  const source = readSource('components/CardEditor.vue')
  const calls = findClientCalls(source)

  it('imports and uses Axios client', () => {
    expect(source).toContain("import client from '../api/client'")
    expect(calls.length).toBeGreaterThan(0)
  })

  it('no raw fetch calls to /api/ endpoints remain', () => {
    const fetchApiCalls = source.match(/fetch\(\s*[`'"](\/api\/[^`'"]+)[`'"]/g) || []
    expect(fetchApiCalls, 'Raw fetch calls to /api/ should be replaced by client').toEqual([])
  })

  it('references /card/ endpoints via client', () => {
    const cardPaths = calls.filter(c => c.path.includes('/card/'))
    expect(cardPaths.length).toBeGreaterThanOrEqual(1)
  })
})


describe('card-editor/export.js API paths', () => {
  const source = readSource('card-editor/export.js')
  const calls = findClientCalls(source)

  it('imports and uses Axios client', () => {
    expect(source).toContain("import client from '../api/client'")
    expect(calls.length).toBeGreaterThan(0)
  })

  it('no raw fetch calls to /api/ endpoints remain', () => {
    const fetchApiCalls = source.match(/fetch\(\s*[`'"](\/api\/[^`'"]+)[`'"]/g) || []
    expect(fetchApiCalls, 'Raw fetch calls to /api/ should be replaced by client').toEqual([])
  })

  it('references /card/export/ endpoints via client', () => {
    const exportPaths = calls.filter(c => c.path.includes('/card/export/'))
    expect(exportPaths.length).toBeGreaterThanOrEqual(2)  // pdf + skeleton
  })

  it('references /card/publish endpoint (F003 rewrite)', () => {
    const publishPaths = calls.filter(c => c.path.includes('/card/publish'))
    expect(publishPaths.length).toBeGreaterThanOrEqual(1)
  })
})
