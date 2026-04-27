/**
 * ExamDetailPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains tab structure (5 tabs + 2 modals)
 *  3. API calls (getExam, listSubjects, createSubject, getRubric, upsertRubric)
 *  4. State/data processing (PRESET_SUBJECTS, statusMap, subjectOptions, availablePresetSubjects)
 *  5. Error handling (try-catch in loadExam, handleBatchCreateSubjects, openRubric, handleSaveRubric)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ExamDetailPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ExamDetailPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ExamDetailPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ExamDetailPage template tab structure', () => {
  it('contains 5 tab panes', () => {
    expect(content).toContain('name="subjects" tab="科目管理"')
    expect(content).toContain('name="card" tab="答题卡制作"')
    expect(content).toContain('name="visual-editor" tab="可视化编辑"')
    expect(content).toContain('name="answers" tab="标准答案"')
    expect(content).toContain('name="questions" tab="题目管理"')
  })

  it('renders child tab components', () => {
    expect(content).toContain('<SubjectsTab')
    expect(content).toContain('<CardMakerTab')
    expect(content).toContain('<VisualEditorTab')
    expect(content).toContain('<AnswersTab')
    expect(content).toContain('<QuestionsTab')
  })

  it('has active tab binding', () => {
    expect(content).toContain('v-model:value="activeTab"')
    expect(content).toContain("const activeTab = ref('subjects')")
  })

  it('shows loading spinner while loading', () => {
    expect(content).toContain('v-if="loading"')
    expect(content).toContain('n-spin')
  })

  it('has back button to exam list', () => {
    expect(content).toContain("$router.push('/exams')")
    expect(content).toContain('← 返回考试列表')
  })
})

describe('ExamDetailPage modals', () => {
  it('contains subject modal with checkbox group', () => {
    expect(content).toContain('v-model:show="showSubjectModal"')
    expect(content).toContain("title=\"添加科目\"")
    expect(content).toContain('n-checkbox-group')
    expect(content).toContain('v-model:value="selectedSubjectCodes"')
  })

  it('contains rubric modal with form', () => {
    expect(content).toContain('v-model:show="showRubricModal"')
    expect(content).toContain("title=\"评分标准\"")
    expect(content).toContain('rubricForm.criteria')
    expect(content).toContain('rubricForm.reference_answer')
  })

  it('shows empty message when all preset subjects are added', () => {
    expect(content).toContain('所有常用科目已添加')
  })
})

describe('ExamDetailPage API calls', () => {
  it('imports API modules', () => {
    expect(content).toContain("import { getExam } from '../api/exams'")
    expect(content).toContain("import { listSubjects, createSubject } from '../api/subjects'")
    expect(content).toContain("import { getRubric, upsertRubric } from '../api/rubrics'")
  })

  it('loads exam and subjects in parallel on mount', () => {
    expect(content).toContain('Promise.all([getExam(examId), listSubjects(examId)])')
    expect(content).toContain('onMounted(loadExam)')
  })

  it('calls createSubject per selected code in batch create', () => {
    expect(content).toContain('await createSubject(examId, { name: s.name, code: s.code })')
  })

  it('calls getRubric to load rubric data', () => {
    expect(content).toContain('await getRubric(questionId)')
  })

  it('calls upsertRubric to save rubric', () => {
    expect(content).toContain('await upsertRubric({')
    expect(content).toContain('question_id: rubricForm.questionId')
  })
})

describe('ExamDetailPage PRESET_SUBJECTS', () => {
  it('defines 10 preset subjects with name and code', () => {
    const presetBlock = content.slice(
      content.indexOf('const PRESET_SUBJECTS'),
      content.indexOf('const selectedSubjectCodes')
    )
    expect(presetBlock).toContain("{ name: '语文', code: 'YW' }")
    expect(presetBlock).toContain("{ name: '数学', code: 'SX' }")
    expect(presetBlock).toContain("{ name: '英语', code: 'YY' }")
    expect(presetBlock).toContain("{ name: '物理', code: 'WL' }")
    expect(presetBlock).toContain("{ name: '化学', code: 'HX' }")
    expect(presetBlock).toContain("{ name: '生物', code: 'SW' }")
    expect(presetBlock).toContain("{ name: '政治', code: 'ZZ' }")
    expect(presetBlock).toContain("{ name: '历史', code: 'LS' }")
    expect(presetBlock).toContain("{ name: '地理', code: 'DL' }")
    expect(presetBlock).toContain("{ name: '技术', code: 'JS' }")
  })

  it('computes availablePresetSubjects by filtering existing codes', () => {
    expect(content).toContain('const existing = new Set(subjects.value.map(s => s.code))')
    expect(content).toContain('PRESET_SUBJECTS.filter(s => !existing.has(s.code))')
  })
})

describe('ExamDetailPage statusMap', () => {
  it('maps 5 exam statuses to label and type', () => {
    expect(content).toContain("draft: { label: '草稿', type: 'default' }")
    expect(content).toContain("scanning: { label: '扫描中', type: 'info' }")
    expect(content).toContain("grading: { label: '批改中', type: 'warning' }")
    expect(content).toContain("reviewing: { label: '复核中', type: 'warning' }")
    expect(content).toContain("completed: { label: '已完成', type: 'success' }")
  })

  it('has statusLabel and statusType helper functions', () => {
    expect(content).toContain("const statusLabel = (s) => statusMap[s]?.label || s")
    expect(content).toContain("const statusType = (s) => statusMap[s]?.type || 'default'")
  })
})

describe('ExamDetailPage subjectOptions computed', () => {
  it('maps subjects to label/value options', () => {
    expect(content).toContain('subjects.value.map((s) => ({ label: `${s.name} (${s.code})`, value: s.id }))')
  })
})

describe('ExamDetailPage handleBatchCreateSubjects', () => {
  it('guards against empty selection', () => {
    expect(content).toContain('if (selectedSubjectCodes.value.length === 0) return')
  })

  it('tracks success count and shows message', () => {
    const batchBlock = content.slice(
      content.indexOf('async function handleBatchCreateSubjects'),
      content.indexOf('async function openRubric')
    )
    expect(batchBlock).toContain('ok++')
    expect(batchBlock).toContain('message.success(`成功添加 ${ok} 个科目`)')
  })

  it('reloads exam after batch create', () => {
    const batchBlock = content.slice(
      content.indexOf('async function handleBatchCreateSubjects'),
      content.indexOf('async function openRubric')
    )
    expect(batchBlock).toContain('await loadExam()')
  })
})

describe('ExamDetailPage cross-tab navigation', () => {
  it('handleGoToEditor switches to visual-editor tab', () => {
    expect(content).toContain("activeTab.value = 'visual-editor'")
    expect(content).toContain('visualEditorSubjectId.value = subjectId')
  })

  it('handleConfirmAnswers sets pending questions and switches tab', () => {
    expect(content).toContain('pendingQuestionsForEditor.value = questions')
    expect(content).toContain("message.success('题型数据已填充到编辑器，请检查后导出 PDF')")
  })
})

describe('ExamDetailPage error handling', () => {
  it('wraps loadExam in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExam'),
      content.indexOf('function openSubjectModal')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('loading.value = false')
  })

  it('wraps individual subject creation in try-catch', () => {
    const batchBlock = content.slice(
      content.indexOf('for (const s of toAdd)'),
      content.indexOf('if (ok > 0)')
    )
    expect(batchBlock).toContain('try {')
    expect(batchBlock).toContain('} catch (e) {')
    expect(batchBlock).toContain("e.response?.data?.detail || '未知错误'")
  })

  it('handles 404 gracefully when loading rubric', () => {
    expect(content).toContain("if (e.response?.status !== 404) message.error('加载评分标准失败')")
  })

  it('validates rubric JSON before saving', () => {
    expect(content).toContain('criteria = JSON.parse(rubricForm.criteria)')
    expect(content).toContain("message.error('评分细则必须是合法 JSON')")
  })
})
