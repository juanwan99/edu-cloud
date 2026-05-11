import { describe, it, expect } from 'vitest'

describe('parent-tokens.css', () => {
  it('exports expected CSS custom property names', async () => {
    const css = await import('../../../assets/styles/parent-tokens.css?raw')
    expect(css.default).toContain('--p-bg-base')
    expect(css.default).toContain('--p-surface-1')
    expect(css.default).toContain('--p-surface-2')
    expect(css.default).toContain('--p-text-1')
    expect(css.default).toContain('--p-color-accent')
    expect(css.default).toContain('[data-theme="light"]')
    expect(css.default).toContain('[data-theme="dark"]')
  })

  it('contains typography and spacing tokens', async () => {
    const css = await import('../../../assets/styles/parent-tokens.css?raw')
    expect(css.default).toContain('--p-fs-hero')
    expect(css.default).toContain('--p-fs-body')
    expect(css.default).toContain('--p-space-4')
    expect(css.default).toContain('--p-ease')
  })
})
