/**
 * QuestionsTab.vue source-text smoke tests.
 *
 * Covers:
 *   1. Smoke import
 *   2. Template structure (subject select, data table, add button)
 *   3. API imports (listQuestions, createQuestion, updateQuestion, deleteQuestion)
 *   4. Props definition (subjectOptions)
 *   5. Reactive state and computed
 *   6. CRUD operations (load, add, save, delete)
 *   7. Error handling
 *   8. Column definitions (editable cells)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const vuePath = resolve(__dirname, '../QuestionsTab.vue')
const src = readFileSync(vuePath, 'utf-8')

describe('QuestionsTab smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../QuestionsTab.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('QuestionsTab template structure', () => {
  it('has subject select with v-model', () => {
    expect(src).toContain('v-model:value="qmgSubjectId"')
    expect(src).toContain(':options="subjectOptions"')
    expect(src).toContain('选择科目')
  })

  it('shows question count and total score tag', () => {
    expect(src).toContain('qmgQuestions.length')
    expect(src).toContain('qmgTotalScore')
    expect(src).toContain('题 / 总分')
  })

  it('has add question button', () => {
    expect(src).toContain('添加题目')
    expect(src).toContain('handleAddQuestion')
    expect(src).toContain(':disabled="!qmgSubjectId"')
  })

  it('has data table with columns', () => {
    expect(src).toContain('n-data-table')
    expect(src).toContain(':columns="qmgColumns"')
    expect(src).toContain(':data="qmgQuestions"')
  })

  it('shows loading spinner', () => {
    expect(src).toContain('qmgLoading')
    expect(src).toContain('n-spin')
  })

  it('shows empty states', () => {
    expect(src).toContain('请选择科目')
    expect(src).toContain('暂无题目')
  })
})

describe('QuestionsTab API imports', () => {
  it('imports all 4 question CRUD functions', () => {
    expect(src).toContain("import { listQuestions, createQuestion, updateQuestion, deleteQuestion } from '../../api/questions'")
  })

  it('uses useMessage and useDialog', () => {
    expect(src).toContain('useMessage')
    expect(src).toContain('useDialog')
  })
})

describe('QuestionsTab props', () => {
  it('defines subjectOptions as required Array', () => {
    expect(src).toContain('subjectOptions: { type: Array, required: true }')
  })
})

describe('QuestionsTab reactive state', () => {
  it('has qmgSubjectId ref', () => {
    expect(src).toContain('const qmgSubjectId = ref(null)')
  })

  it('has qmgQuestions ref', () => {
    expect(src).toContain('const qmgQuestions = ref([])')
  })

  it('has qmgLoading ref', () => {
    expect(src).toContain('const qmgLoading = ref(false)')
  })

  it('has qmgTotalScore computed summing max_score', () => {
    expect(src).toContain('qmgTotalScore')
    expect(src).toContain('.reduce((s, q) => s + (q.max_score || 0), 0)')
  })
})

describe('QuestionsTab question type options', () => {
  it('has 4 question types', () => {
    expect(src).toContain("{ label: '单选', value: 'choice' }")
    expect(src).toContain("{ label: '多选', value: 'multi_choice' }")
    expect(src).toContain("{ label: '填空', value: 'fill_blank' }")
    expect(src).toContain("{ label: '主观', value: 'essay' }")
  })
})

describe('QuestionsTab loadQmgQuestions', () => {
  it('calls listQuestions with subjectId', () => {
    expect(src).toContain('async function loadQmgQuestions(subjectId)')
    expect(src).toContain('await listQuestions(subjectId)')
  })

  it('sorts by parsed name', () => {
    expect(src).toContain("parseInt(a.name) || 0) - (parseInt(b.name) || 0)")
  })

  it('has error handling', () => {
    expect(src).toContain('} catch { qmgQuestions.value = [] }')
  })
})

describe('QuestionsTab handleQmgSave', () => {
  it('calls updateQuestion with field and value', () => {
    expect(src).toContain('async function handleQmgSave(row, field, value)')
    expect(src).toContain('await updateQuestion(row.id, { [field]: value })')
  })

  it('shows success message on save', () => {
    expect(src).toContain("message.success('已保存')")
  })

  it('shows error detail on failure', () => {
    expect(src).toContain("e.response?.data?.detail || '保存失败'")
  })
})

describe('QuestionsTab handleDeleteQuestion', () => {
  it('calls deleteQuestion API', () => {
    expect(src).toContain('async function handleDeleteQuestion(row)')
    expect(src).toContain('await deleteQuestion(row.id)')
  })

  it('filters out deleted question from list', () => {
    expect(src).toContain('qmgQuestions.value = qmgQuestions.value.filter(q => q.id !== row.id)')
  })

  it('shows success message', () => {
    expect(src).toContain("message.success('已删除')")
  })

  it('shows error on failure', () => {
    expect(src).toContain("e.response?.data?.detail || '删除失败'")
  })
})

describe('QuestionsTab handleAddQuestion', () => {
  it('calculates next question name from max', () => {
    expect(src).toContain('Math.max(m, parseInt(q.name) || 0)')
    expect(src).toContain('String(maxName + 1)')
  })

  it('creates essay question with default score 5', () => {
    expect(src).toContain("question_type: 'essay'")
    expect(src).toContain('max_score: 5')
  })

  it('reloads questions after adding', () => {
    expect(src).toContain('await loadQmgQuestions(qmgSubjectId.value)')
  })

  it('shows success and error messages', () => {
    expect(src).toContain("message.success('已添加')")
    expect(src).toContain("e.response?.data?.detail || '添加失败'")
  })
})

describe('QuestionsTab column definitions', () => {
  it('has editable name column', () => {
    expect(src).toContain("title: '题号'")
    expect(src).toContain("key: 'name'")
    expect(src).toContain("handleQmgSave(row, 'name', row.name)")
  })

  it('has type column with NSelect', () => {
    expect(src).toContain("title: '类型'")
    expect(src).toContain("key: 'question_type'")
    expect(src).toContain('qTypeOptions')
  })

  it('has editable score column', () => {
    expect(src).toContain("title: '分值'")
    expect(src).toContain("key: 'max_score'")
    expect(src).toContain("handleQmgSave(row, 'max_score', row.max_score)")
  })

  it('has correct answer column for choice types', () => {
    expect(src).toContain("title: '正确答案'")
    expect(src).toContain("key: 'correct_answer'")
    expect(src).toContain("row.question_type !== 'choice' && row.question_type !== 'multi_choice'")
  })

  it('has content and answer presence columns', () => {
    expect(src).toContain("title: '题干'")
    expect(src).toContain("title: '答案'")
    expect(src).toContain('has_content')
    expect(src).toContain('has_answer')
  })

  it('has delete action with dialog confirmation', () => {
    expect(src).toContain('删除确认')
    expect(src).toContain('确定删除第')
    expect(src).toContain('handleDeleteQuestion(row)')
  })
})
