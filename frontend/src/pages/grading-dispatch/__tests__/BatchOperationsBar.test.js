import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const content = readFileSync(resolve(__dirname, '../BatchOperationsBar.vue'), 'utf-8')

describe('BatchOperationsBar smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../BatchOperationsBar.vue')
    expect(mod.default).toBeTruthy()
  }, 30000)
})

describe('BatchOperationsBar template', () => {
  it('has batch-bar class', () => {
    expect(content).toContain('class="batch-bar"')
  })
  it('shows batch detect button for managers', () => {
    expect(content).toContain('canManageAll')
    expect(content).toContain('一键全科检测')
    expect(content).toContain("$emit('batch-detect')")
  })
  it('shows detectable count', () => {
    expect(content).toContain('detectableCount')
    expect(content).toContain('科待检测')
  })
  it('shows selected count', () => {
    expect(content).toContain('selectedCount')
    expect(content).toContain('已选')
  })
  it('has batch-cut and batch-grade buttons', () => {
    expect(content).toContain("$emit('batch-cut')")
    expect(content).toContain('批量切割')
    expect(content).toContain("$emit('batch-grade')")
    expect(content).toContain('批量 AI 阅卷')
  })
})

describe('BatchOperationsBar props', () => {
  it('defines all 7 props', () => {
    expect(content).toContain('canManageAll:')
    expect(content).toContain('detectableCount:')
    expect(content).toContain('batchDetectLoading:')
    expect(content).toContain('batchProgressText:')
    expect(content).toContain('selectedCount:')
    expect(content).toContain('canBatchCut:')
    expect(content).toContain('canBatchGrade:')
  })
  it('defines 3 emits', () => {
    expect(content).toContain("'batch-detect'")
    expect(content).toContain("'batch-cut'")
    expect(content).toContain("'batch-grade'")
  })
})
