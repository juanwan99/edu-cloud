import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const content = readFileSync(resolve(__dirname, '../ScanSection.vue'), 'utf-8')

describe('ScanSection smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ScanSection.vue')
    expect(mod.default).toBeTruthy()
  }, 30000)
})

describe('ScanSection template', () => {
  it('has scan-section root class', () => {
    expect(content).toContain('class="scan-section"')
  })
  it('has collapsible header with toggle', () => {
    expect(content).toContain('scan-header')
    expect(content).toContain('scan-toggle')
    expect(content).toContain('expanded = !expanded')
  })
  it('shows subject count hint', () => {
    expect(content).toContain('已识别')
    expect(content).toContain('scanResults.length')
    expect(content).toContain('个科目')
  })
  it('has pick-folder button', () => {
    expect(content).toContain("$emit('pick-folder')")
    expect(content).toContain('选择扫描文件夹')
  })
  it('has scan-dir button', () => {
    expect(content).toContain("$emit('scan-dir')")
    expect(content).toContain('识别科目')
  })
  it('shows upload hint when no scanRootDir', () => {
    expect(content).toContain('upload-hint')
    expect(content).toContain('按科目子文件夹组织')
  })
})

describe('ScanSection props', () => {
  it('defines scanRootDir prop', () => {
    expect(content).toContain("scanRootDir: { type: String")
  })
  it('defines scanLoading prop', () => {
    expect(content).toContain("scanLoading: { type: Boolean")
  })
  it('defines scanResults prop', () => {
    expect(content).toContain("scanResults: { type: Array")
  })
  it('defines uploadLoading and uploadProgress props', () => {
    expect(content).toContain("uploadLoading: { type: Boolean")
    expect(content).toContain("uploadProgress: { type: String")
  })
})

describe('ScanSection behavior', () => {
  it('auto-collapses when scanResults arrive', () => {
    expect(content).toContain('watch(() => props.scanResults')
    expect(content).toContain('expanded.value = false')
  })
  it('shows loading state with progress', () => {
    expect(content).toContain('uploadLoading')
    expect(content).toContain('uploadProgress')
  })
})
