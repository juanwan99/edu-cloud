/**
 * HomeworkPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key CSS classes and UI structure
 *  3. Data fetching calls correct API methods from homework.js
 *  4. Status mapping: draft/active/expired/closed -> Chinese text and tag types
 *  5. CRUD operations: create/publish/close/delete buttons and logic
 *  6. Error handling: try-catch wrapping in async functions
 *  7. Filter controls and subject/type mappings
 *  8. Remedial (post-exam push) workflow
 *  9. Content detail modal
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../HomeworkPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('HomeworkPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../HomeworkPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('HomeworkPage template structure', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('作业管理')
    expect(content).toContain('布置、发布、批改作业')
  })

  it('has create and remedial action buttons', () => {
    expect(content).toContain('布置作业')
    expect(content).toContain('考后推送')
    expect(content).toContain('showCreate = true')
    expect(content).toContain('showRemedial = true')
  })

  it('contains filter selects for status, subject, and class', () => {
    expect(content).toContain('v-model:value="filterStatus"')
    expect(content).toContain('v-model:value="filterSubject"')
    expect(content).toContain('v-model:value="filterClass"')
    expect(content).toContain(':options="statusOptions"')
    expect(content).toContain(':options="subjectOptions"')
    expect(content).toContain(':options="classOptions"')
  })

  it('has a data table with loading spinner', () => {
    expect(content).toContain('<n-spin :show="loading">')
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="tasks"')
  })

  it('contains create homework modal with form fields', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="布置作业"')
    expect(content).toContain('v-model:value="form.title"')
    expect(content).toContain('v-model:value="form.subject_code"')
    expect(content).toContain('v-model:value="form.class_id"')
    expect(content).toContain('v-model:value="form.task_type"')
    expect(content).toContain('v-model:value="form.deadline_ts"')
    expect(content).toContain('v-model:value="form.content"')
  })

  it('contains submissions modal with stats tags', () => {
    expect(content).toContain('v-model:show="showSubmissions"')
    expect(content).toContain('title="提交情况"')
    expect(content).toContain('taskStats.total')
    expect(content).toContain('taskStats.pending')
    expect(content).toContain('taskStats.submitted')
    expect(content).toContain('taskStats.graded')
    expect(content).toContain('taskStats.avg_score')
  })

  it('contains remedial modal with exam select and preview', () => {
    expect(content).toContain('v-model:show="showRemedial"')
    expect(content).toContain('title="考后推送"')
    expect(content).toContain('v-model:value="remedialForm.exam_id"')
    expect(content).toContain('v-model:value="remedialForm.class_id"')
    expect(content).toContain('remedialPreview')
  })

  it('contains content detail modal for associated questions', () => {
    expect(content).toContain('v-model:show="showContentDetail"')
    expect(content).toContain('title="关联题目"')
    expect(content).toContain('contentDetailQuestions')
  })
})

describe('HomeworkPage API imports', () => {
  it('imports task CRUD methods from homework.js', () => {
    expect(content).toContain("import { listTasks, createTask, publishTask, closeTask, deleteTask, listSubmissions, gradeSingle, createFromExam, getContentDetail } from '../api/homework.js'")
  })

  it('imports listClasses from students.js', () => {
    expect(content).toContain("import { listClasses } from '../api/students.js'")
  })

  it('imports listExams from exams.js', () => {
    expect(content).toContain("import { listExams } from '../api/exams.js'")
  })
})

describe('HomeworkPage status mapping', () => {
  it('defines statusLabel with all 4 states in Chinese', () => {
    expect(content).toContain("draft: '草稿'")
    expect(content).toContain("active: '进行中'")
    expect(content).toContain("expired: '已截止'")
    expect(content).toContain("closed: '已关闭'")
  })

  it('defines statusColor mapping to Naive UI tag types', () => {
    expect(content).toContain("draft: 'default'")
    expect(content).toContain("active: 'success'")
    expect(content).toContain("expired: 'warning'")
    expect(content).toContain("closed: 'error'")
  })

  it('renders status column with NTag using statusColor and statusLabel', () => {
    expect(content).toContain('statusColor[row.status]')
    expect(content).toContain('statusLabel[row.status]')
  })

  it('defines statusOptions for filter select', () => {
    expect(content).toContain("{ value: 'draft', label: '草稿' }")
    expect(content).toContain("{ value: 'active', label: '进行中' }")
    expect(content).toContain("{ value: 'expired', label: '已截止' }")
    expect(content).toContain("{ value: 'closed', label: '已关闭' }")
  })
})

describe('HomeworkPage type mapping', () => {
  it('defines typeLabel for task types', () => {
    expect(content).toContain("regular: '常规'")
    expect(content).toContain("pre_exam: '考前'")
    expect(content).toContain("post_exam: '考后'")
    expect(content).toContain("remedial: '补救'")
  })

  it('defines radio options for task types in create form', () => {
    expect(content).toContain('<n-radio value="regular">常规作业</n-radio>')
    expect(content).toContain('<n-radio value="pre_exam">考前练习</n-radio>')
    expect(content).toContain('<n-radio value="post_exam">考后巩固</n-radio>')
  })
})

describe('HomeworkPage subject definitions', () => {
  it('defines all 9 subjects with codes and Chinese labels', () => {
    const subjects = [
      ['YW', '语文'], ['SX', '数学'], ['YY', '英语'],
      ['WL', '物理'], ['HX', '化学'], ['SW', '生物'],
      ['ZZ', '政治'], ['LS', '历史'], ['DL', '地理'],
    ]
    for (const [code, label] of subjects) {
      expect(content).toContain(`value: '${code}', label: '${label}'`)
    }
  })
})

describe('HomeworkPage CRUD operations', () => {
  it('calls createTask in handleCreate', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handlePublish')
    )
    expect(fnBlock).toContain('await createTask(payload)')
    expect(fnBlock).toContain("message.success('作业创建成功')")
  })

  it('validates title and subject before create', () => {
    expect(content).toContain("if (!form.value.title || !form.value.subject_code)")
    expect(content).toContain("message.warning('请填写标题和科目')")
  })

  it('resets form after successful create', () => {
    expect(content).toContain("form.value = { title: '', subject_code: '', class_id: '', task_type: 'regular', deadline_ts: null, content: '' }")
  })

  it('calls publishTask in handlePublish', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handlePublish'),
      content.indexOf('async function handleClose')
    )
    expect(fnBlock).toContain('await publishTask(row.id)')
    expect(fnBlock).toContain("message.success('作业已发布')")
  })

  it('calls closeTask in handleClose', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleClose'),
      content.indexOf('async function handleDelete')
    )
    expect(fnBlock).toContain('await closeTask(row.id)')
    expect(fnBlock).toContain("message.success('作业已关闭')")
  })

  it('calls deleteTask with confirmation dialog', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('async function openSubmissions')
    )
    expect(fnBlock).toContain('dialog.warning')
    expect(fnBlock).toContain("title: '确认删除'")
    expect(fnBlock).toContain('await deleteTask(row.id)')
    expect(fnBlock).toContain("message.success('已删除')")
  })

  it('renders publish button only for draft status', () => {
    expect(content).toContain("row.status === 'draft' ? h(NButton, { text: true, type: 'success', size: 'small', onClick: () => handlePublish(row) }")
  })

  it('renders close button only for active status', () => {
    expect(content).toContain("row.status === 'active' ? h(NButton, { text: true, type: 'warning', size: 'small', onClick: () => handleClose(row) }")
  })

  it('renders delete button only for draft status', () => {
    expect(content).toContain("row.status === 'draft' ? h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleDelete(row) }")
  })
})

describe('HomeworkPage data fetching', () => {
  it('calls listTasks with filter params in loadTasks', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadTasks'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('await listTasks(params)')
    expect(fnBlock).toContain('params.status = filterStatus.value')
    expect(fnBlock).toContain('params.subject_code = filterSubject.value')
    expect(fnBlock).toContain('params.class_id = filterClass.value')
  })

  it('calls listSubmissions in openSubmissions', () => {
    const fnBlock = content.slice(
      content.indexOf('async function openSubmissions'),
      content.indexOf('async function handleExamSelect')
    )
    expect(fnBlock).toContain('await listSubmissions(row.id)')
  })

  it('computes submission stats including avg_score', () => {
    expect(content).toContain("pending: submissions.value.filter(s => s.status === 'pending').length")
    expect(content).toContain("submitted: submissions.value.filter(s => s.status === 'submitted').length")
    expect(content).toContain("graded: submissions.value.filter(s => s.status === 'graded').length")
    expect(content).toContain('s.score != null')
  })

  it('initializes with listClasses and listExams in init', () => {
    const fnBlock = content.slice(
      content.indexOf('async function init'),
      content.length
    )
    expect(fnBlock).toContain('listClasses()')
    expect(fnBlock).toContain('listExams()')
    expect(fnBlock).toContain('Promise.all')
  })

  it('calls init on mount', () => {
    expect(content).toContain('onMounted(init)')
  })

  it('reloads tasks after each mutation', () => {
    // After create, publish, close, delete - all call loadTasks()
    const handleCreate = content.slice(content.indexOf('async function handleCreate'), content.indexOf('async function handlePublish'))
    const handlePublish = content.slice(content.indexOf('async function handlePublish'), content.indexOf('async function handleClose'))
    const handleClose = content.slice(content.indexOf('async function handleClose'), content.indexOf('async function handleDelete'))
    const handleDelete = content.slice(content.indexOf('async function handleDelete'), content.indexOf('async function openSubmissions'))

    expect(handleCreate).toContain('await loadTasks()')
    expect(handlePublish).toContain('await loadTasks()')
    expect(handleClose).toContain('await loadTasks()')
    expect(handleDelete).toContain('await loadTasks()')
  })
})

describe('HomeworkPage error handling', () => {
  it('wraps loadTasks in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadTasks'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("message.error('加载作业失败')")
  })

  it('wraps handleCreate in try-catch with detail fallback', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handlePublish')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('wraps handlePublish in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handlePublish'),
      content.indexOf('async function handleClose')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("e.response?.data?.detail || '发布失败'")
  })

  it('wraps handleClose in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleClose'),
      content.indexOf('async function handleDelete')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("e.response?.data?.detail || '关闭失败'")
  })

  it('wraps handleDelete inner callback in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('async function openSubmissions')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('catch (e)')
    expect(fnBlock).toContain("e.response?.data?.detail || '删除失败'")
  })

  it('wraps openSubmissions in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function openSubmissions'),
      content.indexOf('async function handleExamSelect')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("message.error('加载提交列表失败')")
  })

  it('wraps handleCreateRemedial in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreateRemedial'),
      content.indexOf('async function openContentDetail')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('wraps openContentDetail in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function openContentDetail'),
      content.indexOf('async function init')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain("message.error('加载题目详情失败')")
  })

  it('init catches individual Promise failures gracefully', () => {
    const fnBlock = content.slice(
      content.indexOf('async function init'),
      content.length
    )
    expect(fnBlock).toContain('.catch(() => ({ data: [] }))')
  })
})

describe('HomeworkPage remedial workflow', () => {
  it('validates exam_id and class_id before creating remedial', () => {
    expect(content).toContain('!remedialForm.value.exam_id || !remedialForm.value.class_id')
    expect(content).toContain("message.warning('请选择考试和班级')")
  })

  it('calls createFromExam with exam_id and class_id', () => {
    expect(content).toContain('await createFromExam(remedialForm.value.exam_id, remedialForm.value.class_id)')
  })

  it('shows success message and resets form after remedial create', () => {
    expect(content).toContain("message.success('补救作业创建成功')")
    expect(content).toContain('remedialForm.value = { exam_id: null, class_id: null }')
    expect(content).toContain('remedialPreview.value = null')
  })

  it('sets remedialPreview on exam select', () => {
    expect(content).toContain('remedialPreview.value = { high_error_count:')
  })

  it('shows high error count in remedial preview', () => {
    expect(content).toContain('remedialPreview.high_error_count')
    expect(content).toContain('高错题')
  })
})

describe('HomeworkPage content detail', () => {
  it('calls getContentDetail to fetch question data', () => {
    expect(content).toContain('await getContentDetail(row.id)')
  })

  it('displays question type tags with correct type mapping', () => {
    expect(content).toContain("choice: '选择'")
    expect(content).toContain("fill: '填空'")
    expect(content).toContain("essay: '解答'")
  })

  it('shows empty state when no questions', () => {
    expect(content).toContain('!contentDetailQuestions.length')
    expect(content).toContain('暂无关联题目')
  })

  it('displays max_score and difficulty for each question', () => {
    expect(content).toContain('q.max_score')
    expect(content).toContain('q.difficulty')
  })
})

describe('HomeworkPage submission columns', () => {
  it('defines subColumns with student, status, submit_time, score, feedback', () => {
    expect(content).toContain("{ title: '学生', key: 'student_id'")
    expect(content).toContain("{ title: '提交时间', key: 'submit_time'")
    expect(content).toContain("{ title: '分数', key: 'score'")
    expect(content).toContain("{ title: '反馈', key: 'feedback'")
  })

  it('maps submission status to Chinese labels', () => {
    expect(content).toContain("pending: ['warning', '待提交']")
    expect(content).toContain("submitted: ['info', '已提交']")
    expect(content).toContain("graded: ['success', '已批改']")
  })
})

describe('HomeworkPage columns definition', () => {
  it('defines main table columns', () => {
    expect(content).toContain("{ title: '标题', key: 'title'")
    expect(content).toContain("{ title: '科目', key: 'subject_code'")
    expect(content).toContain("{ title: '类型', key: 'task_type'")
    expect(content).toContain("{ title: '状态', key: 'status'")
    expect(content).toContain("{ title: '班级', key: 'class_name'")
    expect(content).toContain("{ title: '截止', key: 'deadline'")
    expect(content).toContain("{ title: '创建', key: 'created_at'")
    expect(content).toContain("title: '操作', key: 'actions', width: 200,")
  })

  it('renders detail button for all rows', () => {
    expect(content).toContain("onClick: () => openSubmissions(row)")
    expect(content).toContain("default: () => '详情'")
  })

  it('renders question button only for remedial/post_exam types', () => {
    expect(content).toContain("row.task_type === 'remedial' || row.task_type === 'post_exam'")
    expect(content).toContain("onClick: () => openContentDetail(row)")
    expect(content).toContain("default: () => '题目'")
  })
})
