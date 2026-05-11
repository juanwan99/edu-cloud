import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const cssContent = readFileSync(
  join(__dirname, '../../../assets/styles/parent-tokens.css'),
  'utf-8'
)

describe('parent-tokens.css', () => {
  it('exports expected CSS custom property names', () => {
    expect(cssContent).toContain('--p-bg-base')
    expect(cssContent).toContain('--p-surface-1')
    expect(cssContent).toContain('--p-surface-2')
    expect(cssContent).toContain('--p-text-1')
    expect(cssContent).toContain('--p-color-accent')
    expect(cssContent).toContain('[data-theme="light"]')
    expect(cssContent).toContain('[data-theme="dark"]')
  })

  it('contains typography and spacing tokens', () => {
    expect(cssContent).toContain('--p-fs-hero')
    expect(cssContent).toContain('--p-fs-body')
    expect(cssContent).toContain('--p-space-4')
    expect(cssContent).toContain('--p-ease')
  })
})
