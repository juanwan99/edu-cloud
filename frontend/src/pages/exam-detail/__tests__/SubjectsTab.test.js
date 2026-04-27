import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const content = readFileSync(resolve(__dirname, '../SubjectsTab.vue'), 'utf-8')

describe('SubjectsTab smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../SubjectsTab.vue')
    expect(mod.default).toBeTruthy()
  }, 30000)
})

describe('SubjectsTab template', () => {
  it('has add subject button', () => {
    expect(content).toContain('添加科目')
    expect(content).toContain("$emit('open-subject-modal')")
  })
  it('uses n-data-table', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain('subjectColumns')
  })
})

describe('SubjectsTab columns', () => {
  it('defines name and code columns', () => {
    expect(content).toContain("title: '科目名称'")
    expect(content).toContain("key: 'name'")
    expect(content).toContain("title: '代码'")
    expect(content).toContain("key: 'code'")
  })
})

describe('SubjectsTab props', () => {
  it('requires subjects array', () => {
    expect(content).toContain('subjects: { type: Array, required: true }')
  })
})
