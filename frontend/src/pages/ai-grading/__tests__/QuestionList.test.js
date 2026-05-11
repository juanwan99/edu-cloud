/**
 * QuestionList.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (panel, question items, tags, progress)
 *   3. Props definition (4 props)
 *   4. Emits definition (4 emits)
 *   5. Loading and empty states
 *   6. Score editing inline
 *   7. Status tags (content, answer, rubric)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../QuestionList.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('QuestionList smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../QuestionList.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('QuestionList template - panel structure', () => {
  it('has left-panel container', () => {
    expect(src).toContain('class="left-panel"')
  })

  it('has panel title', () => {
    expect(src).toContain('panel-title')
    expect(src).toContain('主观题列表')
  })

  it('shows loading state', () => {
    expect(src).toContain('v-if="loading"')
    expect(src).toContain('loading-tip')
    expect(src).toContain('加载中...')
  })

  it('shows empty state', () => {
    expect(src).toContain('暂无主观题')
    expect(src).toContain('empty-tip')
  })
})

describe('QuestionList template - question items', () => {
  it('iterates over questions', () => {
    expect(src).toContain('v-for="q in questions"')
    expect(src).toContain(':key="q.question_id"')
    expect(src).toContain('question-item')
  })

  it('highlights active item', () => {
    expect(src).toContain("{ active: selectedQuestionId === q.question_id }")
  })

  it('emits select on click', () => {
    expect(src).toContain("$emit('select', q)")
  })

  it('shows question number', () => {
    expect(src).toContain('q-num')
    expect(src).toContain('q.name || q.question_name')
  })

  it('shows question type label', () => {
    expect(src).toContain("q.question_type === 'essay' ? '主观题' : '填空题'")
  })
})

describe('QuestionList template - score editing', () => {
  it('shows score display when not editing', () => {
    expect(src).toContain('editingScoreId !== q.question_id')
    expect(src).toContain('q-score editable')
    expect(src).toContain('q.max_score')
  })

  it('emits start-edit-score on score click', () => {
    expect(src).toContain("$emit('start-edit-score', q)")
  })

  it('shows input number when editing', () => {
    expect(src).toContain('n-input-number')
    expect(src).toContain(':value="q.max_score"')
    expect(src).toContain(':min="0"')
    expect(src).toContain(':max="200"')
  })

  it('emits update-score-value on input change', () => {
    expect(src).toContain("$emit('update-score-value', q, v)")
  })

  it('emits save-score on blur and enter', () => {
    expect(src).toContain("$emit('save-score', q)")
  })
})

describe('QuestionList template - status tags', () => {
  it('has content status tag', () => {
    expect(src).toContain("q.has_content ? '题干' : '无题干'")
    expect(src).toContain('content_image_count')
  })

  it('has answer status tag', () => {
    expect(src).toContain("q.has_answer ? '答案' : '无答案'")
    expect(src).toContain('answer_image_count')
  })

  it('has rubric status tag', () => {
    expect(src).toContain("q.has_rubric ? '细则' : '无细则'")
  })

  it('uses ok and warn classes for tags', () => {
    expect(src).toContain("q.has_content ? 'ok' : 'warn'")
    expect(src).toContain("q.has_answer ? 'ok' : 'warn'")
    expect(src).toContain("q.has_rubric ? 'ok' : 'warn'")
  })
})

describe('QuestionList template - progress', () => {
  it('shows grading progress when available', () => {
    expect(src).toContain('q.answer_count')
    expect(src).toContain('q.ai_scored_count')
    expect(src).toContain('AI已评')
  })
})

describe('QuestionList imports', () => {
  it('imports NInputNumber from naive-ui', () => {
    expect(src).toContain('NInputNumber')
  })
})

describe('QuestionList props', () => {
  it('defines questions as Array', () => {
    expect(src).toContain('questions: { type: Array, default: () => [] }')
  })

  it('defines selectedQuestionId', () => {
    expect(src).toContain('selectedQuestionId: { type: [String, Number], default: null }')
  })

  it('defines editingScoreId', () => {
    expect(src).toContain('editingScoreId: { type: [String, Number], default: null }')
  })

  it('defines loading as Boolean', () => {
    expect(src).toContain('loading: { type: Boolean, default: false }')
  })
})

describe('QuestionList emits', () => {
  it('declares all 4 emits', () => {
    expect(src).toContain("'select'")
    expect(src).toContain("'start-edit-score'")
    expect(src).toContain("'save-score'")
    expect(src).toContain("'update-score-value'")
  })
})
