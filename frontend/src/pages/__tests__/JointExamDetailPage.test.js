/**
 * JointExamDetailPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template sections (header, tabs, info card, participants, rankings, comparison, add-school modal)
 *  3. API calls (getJointExam, addParticipant, removeParticipant, distributeExam, etc.)
 *  4. State & computed mappings (STATUS_MAP, statusLabel, statusType, subjectNames, canManage)
 *  5. CRUD operations (add/remove school, distribute, force complete)
 *  6. Error handling (try-catch in loadExam, loadRankings, loadComparison)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../JointExamDetailPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('JointExamDetailPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../JointExamDetailPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('JointExamDetailPage template sections', () => {
  it('contains page header with back link and title', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain("$router.push('/joint-exams')")
    expect(content).toContain('返回联考列表')
    expect(content).toContain("exam?.name || '加载中...'")
  })

  it('contains tabs with info, rankings, and comparison', () => {
    expect(content).toContain('n-tabs')
    expect(content).toContain('n-tab-pane')
    expect(content).toContain('name="info"')
    expect(content).toContain('tab="考试信息"')
    expect(content).toContain('name="rankings"')
    expect(content).toContain('tab="成绩排名"')
    expect(content).toContain('name="comparison"')
    expect(content).toContain('tab="校际对比"')
  })

  it('contains info card with basic information fields', () => {
    expect(content).toContain('class="info-card"')
    expect(content).toContain('基本信息')
    expect(content).toContain('class="info-row"')
    expect(content).toContain('联考名称')
    expect(content).toContain('statusLabel')
    expect(content).toContain('subjectNames')
  })

  it('contains participant school section', () => {
    expect(content).toContain('参与学校')
    expect(content).toContain(':columns="participantColumns"')
    expect(content).toContain("exam.participants || []")
    expect(content).toContain('添加学校')
  })

  it('contains rankings data table and empty state', () => {
    expect(content).toContain(':columns="rankingColumns"')
    expect(content).toContain(':data="rankings"')
    expect(content).toContain('pageSize: 20')
    expect(content).toContain('暂无排名数据')
  })

  it('contains comparison data table and empty state', () => {
    expect(content).toContain(':columns="comparisonColumns"')
    expect(content).toContain(':data="comparison"')
    expect(content).toContain('暂无校际对比数据')
  })

  it('contains add-school modal with input', () => {
    expect(content).toContain('n-modal')
    expect(content).toContain('添加参与学校')
    expect(content).toContain('v-model:value="newSchoolId"')
    expect(content).toContain("placeholder=\"输入学校 ID\"")
  })

  it('contains action buttons for distribute and force complete', () => {
    expect(content).toContain("exam.status === 'active'")
    expect(content).toContain('下发考试')
    expect(content).toContain("exam.status !== 'done'")
    expect(content).toContain('强制完成')
  })
})

describe('JointExamDetailPage API calls', () => {
  it('imports all required API functions', () => {
    expect(content).toContain('getJointExam')
    expect(content).toContain('addParticipant')
    expect(content).toContain('removeParticipant')
    expect(content).toContain('distributeExam')
    expect(content).toContain('forceCompleteExam')
    expect(content).toContain('getExamRankings')
    expect(content).toContain('getSchoolComparison')
    expect(content).toContain("from '../api/jointExams.js'")
  })

  it('loadExam calls getJointExam with route param id', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadExam'),
      content.indexOf('async function loadRankings')
    )
    expect(loadBlock).toContain('getJointExam(route.params.id)')
    expect(loadBlock).toContain('exam.value = data')
  })

  it('loadRankings calls getExamRankings with route param id', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadRankings'),
      content.indexOf('async function loadComparison')
    )
    expect(loadBlock).toContain('getExamRankings(route.params.id)')
    expect(loadBlock).toContain('rankings.value')
  })

  it('loadComparison calls getSchoolComparison with route param id', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadComparison'),
      content.indexOf('async function handleAddSchool')
    )
    expect(loadBlock).toContain('getSchoolComparison(route.params.id)')
    expect(loadBlock).toContain('comparison.value')
  })
})

describe('JointExamDetailPage state and computed mappings', () => {
  it('defines STATUS_MAP with 5 statuses', () => {
    expect(content).toContain("draft: { label: '草稿', type: 'default' }")
    expect(content).toContain("active: { label: '进行中', type: 'info' }")
    expect(content).toContain("distributing: { label: '下发中', type: 'warning' }")
    expect(content).toContain("done: { label: '已完成', type: 'success' }")
    expect(content).toContain("archived: { label: '已归档', type: 'default' }")
  })

  it('computes statusLabel from STATUS_MAP', () => {
    expect(content).toContain("STATUS_MAP[exam.value?.status]?.label")
  })

  it('computes statusType from STATUS_MAP', () => {
    expect(content).toContain("STATUS_MAP[exam.value?.status]?.type")
  })

  it('computes subjectNames by joining subject names', () => {
    const subjectBlock = content.slice(
      content.indexOf('const subjectNames'),
      content.indexOf('const participantColumns')
    )
    expect(subjectBlock).toContain("exam.value?.subjects")
    expect(subjectBlock).toContain("s.name || s.code")
    expect(subjectBlock).toContain(".join('、')")
  })

  it('computes canManage from permission check', () => {
    expect(content).toContain("auth.checkPermission('manage_joint_exam')")
  })

  it('defines participantColumns with school_id, status, actions', () => {
    expect(content).toContain("title: '学校ID'")
    expect(content).toContain("key: 'school_id'")
    expect(content).toContain("key: 'status'")
  })

  it('defines rankingColumns with rank, student, school, score', () => {
    expect(content).toContain("title: '排名'")
    expect(content).toContain("key: 'rank'")
    expect(content).toContain("title: '学生'")
    expect(content).toContain("key: 'student_number'")
    expect(content).toContain("title: '总分'")
    expect(content).toContain("key: 'total_score'")
  })

  it('defines comparisonColumns with school stats', () => {
    expect(content).toContain("key: 'school_name'")
    expect(content).toContain("key: 'avg_score'")
    expect(content).toContain("key: 'max_score'")
    expect(content).toContain("key: 'min_score'")
    expect(content).toContain("key: 'student_count'")
  })
})

describe('JointExamDetailPage CRUD operations', () => {
  it('handleAddSchool validates non-empty schoolId', () => {
    const addBlock = content.slice(
      content.indexOf('async function handleAddSchool'),
      content.indexOf('async function handleRemoveSchool')
    )
    expect(addBlock).toContain('if (!newSchoolId.value) return')
  })

  it('handleAddSchool calls addParticipant and reloads', () => {
    const addBlock = content.slice(
      content.indexOf('async function handleAddSchool'),
      content.indexOf('async function handleRemoveSchool')
    )
    expect(addBlock).toContain('addParticipant(route.params.id, newSchoolId.value)')
    expect(addBlock).toContain('showAddSchool.value = false')
    expect(addBlock).toContain("newSchoolId.value = ''")
    expect(addBlock).toContain('loadExam()')
  })

  it('handleRemoveSchool calls removeParticipant and reloads', () => {
    const removeBlock = content.slice(
      content.indexOf('async function handleRemoveSchool'),
      content.indexOf('async function handleDistribute')
    )
    expect(removeBlock).toContain('removeParticipant(route.params.id, schoolId)')
    expect(removeBlock).toContain('loadExam()')
  })

  it('handleDistribute calls distributeExam and reloads', () => {
    const distributeBlock = content.slice(
      content.indexOf('async function handleDistribute'),
      content.indexOf('async function handleForceComplete')
    )
    expect(distributeBlock).toContain('distributeExam(route.params.id)')
    expect(distributeBlock).toContain('loadExam()')
  })

  it('handleForceComplete calls forceCompleteExam and reloads', () => {
    const forceBlock = content.slice(
      content.indexOf('async function handleForceComplete'),
      content.indexOf('onMounted(() => {')
    )
    expect(forceBlock).toContain('forceCompleteExam(route.params.id)')
    expect(forceBlock).toContain('loadExam()')
  })

  it('participant remove button only visible for managers', () => {
    expect(content).toContain('canManage.value')
    expect(content).toContain("() => '移除'")
  })
})

describe('JointExamDetailPage error handling', () => {
  it('loadExam wraps API call in try-finally', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadExam'),
      content.indexOf('async function loadRankings')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} finally {')
    expect(loadBlock).toContain('loading.value = false')
  })

  it('loadRankings wraps API call in try-catch', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadRankings'),
      content.indexOf('async function loadComparison')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch')
    expect(loadBlock).toContain('rankings.value = []')
  })

  it('loadComparison wraps API call in try-catch', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadComparison'),
      content.indexOf('async function handleAddSchool')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch')
    expect(loadBlock).toContain('comparison.value = []')
  })

  it('loadRankings falls back to empty array on non-array response', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadRankings'),
      content.indexOf('async function loadComparison')
    )
    expect(loadBlock).toContain('Array.isArray(data) ? data : []')
  })

  it('loadComparison falls back to empty array on non-array response', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadComparison'),
      content.indexOf('async function handleAddSchool')
    )
    expect(loadBlock).toContain('Array.isArray(data) ? data : []')
  })
})

describe('JointExamDetailPage lifecycle', () => {
  it('calls loadExam, loadRankings, loadComparison on mount', () => {
    const mountBlock = content.slice(content.indexOf('onMounted('))
    expect(mountBlock).toContain('loadExam()')
    expect(mountBlock).toContain('loadRankings()')
    expect(mountBlock).toContain('loadComparison()')
  })

  it('imports required Vue and router APIs', () => {
    expect(content).toContain("import { h, ref, computed, onMounted } from 'vue'")
    expect(content).toContain("import { useRoute } from 'vue-router'")
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
  })
})

describe('JointExamDetailPage styles', () => {
  it('defines info-card styles', () => {
    const styleMatch = content.match(/\.info-card\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('padding')
    expect(styleMatch[0]).toContain('border-radius')
  })

  it('defines info-row styles with flex layout', () => {
    const styleMatch = content.match(/\.info-row\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    expect(styleMatch[0]).toContain('display: flex')
    expect(styleMatch[0]).toContain('justify-content: space-between')
  })
})
