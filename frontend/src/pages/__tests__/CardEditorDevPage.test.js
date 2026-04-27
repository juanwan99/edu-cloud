import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const content = readFileSync(resolve(__dirname, '../CardEditorDevPage.vue'), 'utf-8')

describe('CardEditorDevPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../CardEditorDevPage.vue')
    expect(mod.default).toBeTruthy()
  }, 30000)
})

describe('CardEditorDevPage template', () => {
  it('has back button to exam detail', () => {
    expect(content).toContain('返回考试详情')
    expect(content).toContain('$router.push')
  })
  it('has subject selector', () => {
    expect(content).toContain('v-model="selectedSubject"')
    expect(content).toContain('v-for="s in subjects"')
  })
  it('renders CardEditor component', () => {
    expect(content).toContain('CardEditor')
    expect(content).toContain(':exam-id="examId"')
    expect(content).toContain(':subject-id="selectedSubject.id"')
  })
  it('shows empty state when no subject', () => {
    expect(content).toContain('选择科目后加载编辑器')
  })
})

describe('CardEditorDevPage data loading', () => {
  it('imports listSubjects API', () => {
    expect(content).toContain("import { listSubjects }")
  })
  it('loads subjects on mount', () => {
    expect(content).toContain('onMounted(async')
    expect(content).toContain('listSubjects(examId.value)')
  })
  it('supports query param subject preselection', () => {
    expect(content).toContain('route.query.subject')
  })
  it('loads exam name', () => {
    expect(content).toContain("client.get(`/exams/")
    expect(content).toContain('examName.value')
  })
})

describe('CardEditorDevPage error handling', () => {
  it('catches subject loading errors', () => {
    expect(content).toContain('加载科目失败')
  })
})
