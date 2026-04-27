/**
 * AnswersTab.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (subject select, answer grid, batch add bar)
 *   3. API imports (listQuestions, createQuestion, updateQuestion)
 *   4. Props definition (subjectOptions)
 *   5. Reactive state and computed properties
 *   6. Error handling in async functions
 *   7. Multi-choice toggle logic
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../AnswersTab.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('AnswersTab smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../AnswersTab.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('AnswersTab template structure', () => {
  it('has subject select with v-model', () => {
    expect(src).toContain('v-model:value="ansSubjectId"')
    expect(src).toContain(':options="subjectOptions"')
    expect(src).toContain('选择科目')
  })

  it('has filled count tag', () => {
    expect(src).toContain('ansFilledCount')
    expect(src).toContain('已填')
  })

  it('has save all button', () => {
    expect(src).toContain('保存全部')
    expect(src).toContain(':loading="ansSaving"')
    expect(src).toContain('handleSaveAnswers')
  })

  it('has batch add choices bar', () => {
    expect(src).toContain('add-choices-bar')
    expect(src).toContain('ansAddFrom')
    expect(src).toContain('ansAddTo')
    expect(src).toContain('ansAddType')
    expect(src).toContain('ansAddScore')
    expect(src).toContain('ansAddOptions')
    expect(src).toContain('handleBatchAddChoices')
  })

  it('has answer grid with answer items', () => {
    expect(src).toContain('answer-grid')
    expect(src).toContain('answer-item')
    expect(src).toContain('v-for="q in ansChoiceQuestions"')
  })

  it('supports single choice and multi choice options', () => {
    expect(src).toContain("q.question_type === 'choice'")
    expect(src).toContain('ansOptionList(q)')
    expect(src).toContain('opt-btn')
    expect(src).toContain('class="opt-btn multi"')
  })

  it('has clear button per answer', () => {
    expect(src).toContain('skip-btn')
    expect(src).toContain('清除')
  })

  it('shows loading spinner', () => {
    expect(src).toContain('ansLoading')
    expect(src).toContain('n-spin')
  })

  it('shows empty states', () => {
    expect(src).toContain('请选择科目')
    expect(src).toContain('暂无选择题，请用上方工具栏添加')
  })
})

describe('AnswersTab API imports', () => {
  it('imports listQuestions from questions API', () => {
    expect(src).toContain("import { listQuestions, createQuestion, updateQuestion } from '../../api/questions'")
  })

  it('uses useMessage from naive-ui', () => {
    expect(src).toContain("import { useMessage } from 'naive-ui'")
  })
})

describe('AnswersTab props', () => {
  it('defines subjectOptions as required Array prop', () => {
    expect(src).toContain('subjectOptions: { type: Array, required: true }')
  })
})

describe('AnswersTab reactive state', () => {
  it('has ansSubjectId ref', () => {
    expect(src).toContain('const ansSubjectId = ref(null)')
  })

  it('has ansAllQuestions ref', () => {
    expect(src).toContain('const ansAllQuestions = ref([])')
  })

  it('has ansAnswers reactive', () => {
    expect(src).toContain('const ansAnswers = reactive({})')
  })

  it('has loading and saving state', () => {
    expect(src).toContain('const ansLoading = ref(false)')
    expect(src).toContain('const ansSaving = ref(false)')
  })

  it('has ansChoiceQuestions computed filtering choice types', () => {
    expect(src).toContain('ansChoiceQuestions')
    expect(src).toContain("q.question_type === 'choice' || q.question_type === 'multi_choice'")
  })

  it('has ansFilledCount computed', () => {
    expect(src).toContain('ansFilledCount')
    expect(src).toContain('ansAnswers[q.id]')
  })
})

describe('AnswersTab ansOptionList function', () => {
  it('generates options from ABCDEFGH based on count', () => {
    expect(src).toContain('function ansOptionList(q)')
    expect(src).toContain("'ABCDEFGH'.slice(0, count).split('')")
  })

  it('defaults to 4 options', () => {
    expect(src).toContain('q.options_count || 4')
  })
})

describe('AnswersTab toggleMulti function', () => {
  it('defines toggleMulti for multi-choice toggling', () => {
    expect(src).toContain('function toggleMulti(qid, opt)')
  })

  it('sorts selections alphabetically', () => {
    expect(src).toContain('cur.sort()')
    expect(src).toContain("cur.join('')")
  })
})

describe('AnswersTab loadAnswerQuestions', () => {
  it('calls listQuestions with subjectId', () => {
    expect(src).toContain('async function loadAnswerQuestions(subjectId)')
    expect(src).toContain('await listQuestions(subjectId)')
  })

  it('sorts questions by numeric name', () => {
    expect(src).toContain('parseInt(a.name)')
    expect(src).toContain('parseInt(b.name)')
  })

  it('populates ansAnswers from correct_answer', () => {
    expect(src).toContain("q.correct_answer || ''")
  })

  it('has error handling with catch', () => {
    expect(src).toContain('} catch {')
    expect(src).toContain('ansAllQuestions.value = []')
  })
})

describe('AnswersTab handleBatchAddChoices', () => {
  it('validates range before adding', () => {
    expect(src).toContain('请正确填写起止题号')
  })

  it('skips existing question names', () => {
    expect(src).toContain('existingNames.has(name)')
  })

  it('calls createQuestion for each new question', () => {
    expect(src).toContain('await createQuestion({')
    expect(src).toContain('subject_id: ansSubjectId.value')
    expect(src).toContain('question_type: ansAddType.value')
  })

  it('shows success or info message after adding', () => {
    expect(src).toContain('已添加')
    expect(src).toContain('道选择题')
    expect(src).toContain('所有题号已存在')
  })
})

describe('AnswersTab handleSaveAnswers', () => {
  it('warns when no answers to save', () => {
    expect(src).toContain('没有需要保存的答案')
  })

  it('skips unchanged answers', () => {
    expect(src).toContain("ansAnswers[q.id] === (q.correct_answer || '')")
  })

  it('calls updateQuestion with correct_answer', () => {
    expect(src).toContain('await updateQuestion(q.id, { correct_answer: ansAnswers[q.id] })')
  })

  it('shows per-question error on failure', () => {
    expect(src).toContain('题保存失败')
  })

  it('shows success or no-change message', () => {
    expect(src).toContain('已保存')
    expect(src).toContain('题标准答案')
    expect(src).toContain('无变更')
  })
})
