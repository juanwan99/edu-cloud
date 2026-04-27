/**
 * JointExamPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template sections (page header, stats row, filter bar, data table, empty state, create modal)
 *  3. API calls (listJointExams, createJointExam, distributeExam, forceCompleteExam)
 *  4. State & computed mappings (STATUS_MAP, SUBJECT_OPTIONS, stats, canCreate, canManage)
 *  5. CRUD operations (create flow, distribute, force complete)
 *  6. Error handling (try-catch in loadExams, handleCreate, handleDistribute, handleForceComplete)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../JointExamPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('JointExamPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../JointExamPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('JointExamPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('联考管理')
    expect(content).toContain('跨校联合考试的创建、下发与成绩管理')
  })

  it('contains stats row with three stat cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('总联考数')
    expect(content).toContain('进行中')
    expect(content).toContain('已完成')
  })

  it('contains status filter bar with radio buttons', () => {
    expect(content).toContain('class="filter-bar"')
    expect(content).toContain('n-radio-group')
    expect(content).toContain('n-radio-button')
    expect(content).toContain('value="draft"')
    expect(content).toContain('value="active"')
    expect(content).toContain('value="done"')
  })

  it('contains data table with pagination', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="exams"')
    expect(content).toContain('pageSize: 15')
  })

  it('contains empty state with guidance', () => {
    expect(content).toContain('class="empty-state"')
    expect(content).toContain('n-empty')
    expect(content).toContain('暂无联考数据')
    expect(content).toContain('创建第一个联考')
    expect(content).toContain('联考由具有创建权限的管理员发起')
  })

  it('contains create modal with form', () => {
    expect(content).toContain('n-modal')
    expect(content).toContain('创建联考')
    expect(content).toContain('联考名称')
    expect(content).toContain('考试科目')
    expect(content).toContain('n-select')
    expect(content).toContain(':options="SUBJECT_OPTIONS"')
  })
})

describe('JointExamPage API calls', () => {
  it('imports listJointExams from jointExams API', () => {
    expect(content).toContain("listJointExams")
    expect(content).toContain("from '../api/jointExams.js'")
  })

  it('imports createJointExam', () => {
    expect(content).toContain('createJointExam')
  })

  it('imports distributeExam', () => {
    expect(content).toContain('distributeExam')
  })

  it('imports forceCompleteExam', () => {
    expect(content).toContain('forceCompleteExam')
  })

  it('calls listJointExams with status params in loadExams', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function handleCreate')
    )
    expect(loadBlock).toContain('listJointExams(params)')
    expect(loadBlock).toContain('params.status = statusFilter.value')
  })
})

describe('JointExamPage state and computed mappings', () => {
  it('defines STATUS_MAP with 5 statuses', () => {
    expect(content).toContain("draft: { label: '草稿', type: 'default' }")
    expect(content).toContain("active: { label: '进行中', type: 'info' }")
    expect(content).toContain("distributing: { label: '下发中', type: 'warning' }")
    expect(content).toContain("done: { label: '已完成', type: 'success' }")
    expect(content).toContain("archived: { label: '已归档', type: 'default' }")
  })

  it('defines SUBJECT_OPTIONS with 9 subjects', () => {
    const optionsMatch = content.match(/SUBJECT_OPTIONS\s*=\s*\[([\s\S]*?)\]/m)
    expect(optionsMatch).not.toBeNull()
    const optionsBlock = optionsMatch[1]
    expect(optionsBlock).toContain("'chinese'")
    expect(optionsBlock).toContain("'math'")
    expect(optionsBlock).toContain("'english'")
    expect(optionsBlock).toContain("'physics'")
    expect(optionsBlock).toContain("'chemistry'")
    expect(optionsBlock).toContain("'biology'")
    expect(optionsBlock).toContain("'politics'")
    expect(optionsBlock).toContain("'history'")
    expect(optionsBlock).toContain("'geography'")
  })

  it('computes stats from exams list', () => {
    expect(content).toContain('stats.total')
    expect(content).toContain('stats.active')
    expect(content).toContain('stats.done')
    expect(content).toContain("e.status === 'active'")
    expect(content).toContain("e.status === 'done'")
  })

  it('computes canCreate from permission check', () => {
    expect(content).toContain("auth.checkPermission('create_joint_exam')")
  })

  it('computes canManage from permission check', () => {
    expect(content).toContain("auth.checkPermission('manage_joint_exam')")
  })

  it('defines columns with expected keys', () => {
    expect(content).toContain("title: '联考名称'")
    expect(content).toContain("title: '状态'")
    expect(content).toContain("title: '科目'")
    expect(content).toContain("title: '参与校数'")
    expect(content).toContain("title: '进度'")
    expect(content).toContain("title: '创建时间'")
    expect(content).toContain("title: '操作'")
  })
})

describe('JointExamPage CRUD operations', () => {
  it('handleCreate validates subjects selection', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDistribute')
    )
    expect(createBlock).toContain('form.value.selectedSubjects.length')
    expect(createBlock).toContain("message.warning('请至少选择一个科目')")
  })

  it('handleCreate builds subjects array with code and name', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDistribute')
    )
    expect(createBlock).toContain('form.value.selectedSubjects.map')
    expect(createBlock).toContain('SUBJECT_NAME_MAP[code]')
  })

  it('handleCreate sends correct payload', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDistribute')
    )
    expect(createBlock).toContain('createJointExam({')
    expect(createBlock).toContain('name: form.value.name')
    expect(createBlock).toContain('description: form.value.description')
    expect(createBlock).toContain('creator_school_id: schoolId')
  })

  it('handleCreate resets form and shows success on completion', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDistribute')
    )
    expect(createBlock).toContain("message.success('联考创建成功')")
    expect(createBlock).toContain('showCreate.value = false')
    expect(createBlock).toContain("selectedSubjects: []")
  })

  it('handleDistribute calls distributeExam and reloads', () => {
    const distributeBlock = content.slice(
      content.indexOf('async function handleDistribute'),
      content.indexOf('async function handleForceComplete')
    )
    expect(distributeBlock).toContain('distributeExam(examId)')
    expect(distributeBlock).toContain("message.success('联考已下发')")
    expect(distributeBlock).toContain('loadExams()')
  })

  it('handleForceComplete calls forceCompleteExam and reloads', () => {
    const forceCompleteBlock = content.slice(
      content.indexOf('async function handleForceComplete'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(forceCompleteBlock).toContain('forceCompleteExam(examId)')
    expect(forceCompleteBlock).toContain("message.success('联考已强制截止')")
    expect(forceCompleteBlock).toContain('loadExams()')
  })

  it('distribute button requires draft status and manage permission', () => {
    expect(content).toContain("canManage.value && row.status === 'draft'")
    expect(content).toContain('确认下发此联考？下发后各参与校将收到通知。')
  })

  it('force complete button requires active status and manage permission', () => {
    expect(content).toContain("canManage.value && row.status === 'active'")
    expect(content).toContain('确认强制截止？未提交数据的学校将无法继续提交。')
  })
})

describe('JointExamPage error handling', () => {
  it('loadExams wraps API call in try-catch-finally', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function handleCreate')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch')
    expect(loadBlock).toContain('} finally {')
    expect(loadBlock).toContain('loading.value = false')
  })

  it('loadExams falls back to empty array on error', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function handleCreate')
    )
    expect(loadBlock).toContain('exams.value = []')
  })

  it('handleCreate shows error message on failure', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleDistribute')
    )
    expect(createBlock).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('handleDistribute shows error message on failure', () => {
    const distributeBlock = content.slice(
      content.indexOf('async function handleDistribute'),
      content.indexOf('async function handleForceComplete')
    )
    expect(distributeBlock).toContain("e.response?.data?.detail || '下发失败'")
  })

  it('handleForceComplete shows error message on failure', () => {
    const forceCompleteBlock = content.slice(
      content.indexOf('async function handleForceComplete'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(forceCompleteBlock).toContain("e.response?.data?.detail || '截止失败'")
  })
})

describe('JointExamPage lifecycle', () => {
  it('calls loadExams on mount', () => {
    expect(content).toContain('onMounted(loadExams)')
  })

  it('imports required Vue and router APIs', () => {
    expect(content).toContain("import { h, ref, computed, onMounted } from 'vue'")
    expect(content).toContain("import { useRouter } from 'vue-router'")
    expect(content).toContain("import { useMessage } from 'naive-ui'")
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
  })
})

describe('JointExamPage styles', () => {
  it('uses grid layout for stats row', () => {
    const styleMatch = content.match(/\.stats-row\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('grid-template-columns')
    expect(styleMatch[0]).toContain('repeat(3, 1fr)')
  })

  it('has responsive breakpoint for stats row', () => {
    expect(content).toContain('@media (max-width: 768px)')
    expect(content).toContain('grid-template-columns: 1fr')
  })
})
