import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const content = readFileSync(resolve(__dirname, '../ExamSubjectSelector.vue'), 'utf-8')

describe('ExamSubjectSelector smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ExamSubjectSelector.vue')
    expect(mod.default).toBeTruthy()
  }, 30000)
})

describe('ExamSubjectSelector template', () => {
  it('has selector-bar layout', () => {
    expect(content).toContain('class="selector-bar"')
  })
  it('has exam select', () => {
    expect(content).toContain('选择考试')
    expect(content).toContain('examOptions')
  })
  it('has subject select conditional on examId', () => {
    expect(content).toContain('v-if="examId"')
    expect(content).toContain('选择科目')
    expect(content).toContain('subjectOptions')
  })
  it('emits v-model updates', () => {
    expect(content).toContain("$emit('update:examId'")
    expect(content).toContain("$emit('update:subjectId'")
  })
})

describe('ExamSubjectSelector props', () => {
  it('defines examId and subjectId', () => {
    expect(content).toContain('examId:')
    expect(content).toContain('subjectId:')
  })
  it('defines options and loading props', () => {
    expect(content).toContain('examOptions:')
    expect(content).toContain('subjectOptions:')
    expect(content).toContain('loadingExams:')
    expect(content).toContain('loadingSubjects:')
  })
})
