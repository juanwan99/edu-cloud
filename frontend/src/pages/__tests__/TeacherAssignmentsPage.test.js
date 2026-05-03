/**
 * TeacherAssignmentsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains stats cards, filters, table, create modal
 *  3. API calls for assignments, summary, and reference data
 *  4. Subject code mapping
 *  5. CRUD operations and form validation
 *  6. Error handling patterns
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../TeacherAssignmentsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('TeacherAssignmentsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../TeacherAssignmentsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('TeacherAssignmentsPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('排课管理')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('管理教师排课信息，查看工作量统计')
  })

  it('contains create button', () => {
    expect(content).toContain('@click="openCreate"')
    expect(content).toContain('新增排课')
  })

  it('contains summary statistics cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-label">总排课数')
    expect(content).toContain('summaryStats.totalAssignments')
    expect(content).toContain('class="stat-label">已排课教师')
    expect(content).toContain('summaryStats.teacherCount')
    expect(content).toContain('class="stat-label">平均课时')
    expect(content).toContain('summaryStats.avgLoad')
    expect(content).not.toContain('n-statistic')
  })

  it('contains filter selects for semester, teacher, and subject', () => {
    expect(content).toContain('v-model:value="filterSemester"')
    expect(content).toContain('v-model:value="filterTeacherId"')
    expect(content).toContain('v-model:value="filterSubjectCode"')
    expect(content).toContain('placeholder="选择学期"')
    expect(content).toContain('placeholder="按教师筛选"')
    expect(content).toContain('placeholder="按科目筛选"')
  })

  it('contains data table with pagination', () => {
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="rows"')
    expect(content).toContain('pageSize: 20')
  })

  it('contains create modal with required form fields', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="新增排课"')
    expect(content).toContain('v-model:value="form.semester"')
    expect(content).toContain('v-model:value="form.user_id"')
    expect(content).toContain('v-model:value="form.subject_code"')
    expect(content).toContain('v-model:value="form.class_ids"')
  })

  it('disables subject select until teacher is chosen', () => {
    expect(content).toContain(':disabled="!form.user_id"')
  })
})

describe('TeacherAssignmentsPage subject mapping', () => {
  it('defines complete SUBJECTS array with codes and labels', () => {
    expect(content).toContain("{ code: 'YW', label: '语文' }")
    expect(content).toContain("{ code: 'SX', label: '数学' }")
    expect(content).toContain("{ code: 'YY', label: '英语' }")
    expect(content).toContain("{ code: 'WL', label: '物理' }")
    expect(content).toContain("{ code: 'HX', label: '化学' }")
    expect(content).toContain("{ code: 'SW', label: '生物' }")
    expect(content).toContain("{ code: 'ZZ', label: '政治' }")
    expect(content).toContain("{ code: 'LS', label: '历史' }")
    expect(content).toContain("{ code: 'DL', label: '地理' }")
  })

  it('creates SUBJECT_MAP from SUBJECTS array', () => {
    expect(content).toContain('Object.fromEntries(SUBJECTS.map(s => [s.code, s.label]))')
  })

  it('has subjectLabel fallback for unknown codes', () => {
    expect(content).toContain('return SUBJECT_MAP[code] || code')
  })
})

describe('TeacherAssignmentsPage API calls', () => {
  it('imports assignment API functions', () => {
    expect(content).toContain('getAssignments')
    expect(content).toContain('createAssignments')
    expect(content).toContain('deleteAssignment')
    expect(content).toContain('getAssignmentSummary')
  })

  it('imports reference data APIs', () => {
    expect(content).toContain("import { listTeachers } from '../api/teachers.js'")
    expect(content).toContain("import { listClasses } from '../api/students.js'")
    expect(content).toContain("import { listSemesters, getCurrentSemester } from '../api/academic.js'")
  })

  it('loads all reference data in parallel', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadRefData'),
      content.indexOf('async function loadData')
    )
    expect(fnBlock).toContain('listTeachers()')
    expect(fnBlock).toContain('listClasses()')
    expect(fnBlock).toContain('listSemesters()')
    expect(fnBlock).toContain('getCurrentSemester()')
    expect(fnBlock).toContain('await Promise.all(promises)')
  })

  it('loads assignments with filter params', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('async function loadSummary')
    )
    expect(fnBlock).toContain('params.semester = filterSemester.value')
    expect(fnBlock).toContain('params.user_id = filterTeacherId.value')
    expect(fnBlock).toContain('params.subject_code = filterSubjectCode.value')
    expect(fnBlock).toContain('await getAssignments(sid, params)')
  })

  it('loads summary stats and computes aggregates', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSummary'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('await getAssignmentSummary(sid, params)')
    expect(fnBlock).toContain('t.assignment_count')
    expect(fnBlock).toContain('data.length')
  })
})

describe('TeacherAssignmentsPage CRUD operations', () => {
  it('validates all required fields before create', () => {
    expect(content).toContain("!form.value.user_id || !form.value.subject_code || !form.value.semester || !form.value.class_ids.length")
    expect(content).toContain("message.warning('请填写所有必填项')")
  })

  it('calls createAssignments with school ID and form data', () => {
    expect(content).toContain('await createAssignments(schoolId(), {')
    expect(content).toContain('user_id: form.value.user_id')
    expect(content).toContain('class_ids: form.value.class_ids')
    expect(content).toContain('subject_code: form.value.subject_code')
    expect(content).toContain('semester: form.value.semester')
  })

  it('displays success message after creation', () => {
    expect(content).toContain("message.success('排课创建成功')")
  })

  it('calls deleteAssignment and shows success', () => {
    expect(content).toContain('await deleteAssignment(schoolId(), id)')
    expect(content).toContain("message.success('已删除')")
  })

  it('refreshes data and summary after create/delete', () => {
    expect(content).toContain('await Promise.all([loadData(), loadSummary()])')
  })
})

describe('TeacherAssignmentsPage teacher selection logic', () => {
  it('auto-selects subject when teacher has exactly one', () => {
    const fnBlock = content.slice(
      content.indexOf('function handleTeacherChange'),
      content.indexOf('function resetForm')
    )
    expect(fnBlock).toContain("t?.subject_codes?.length === 1")
    expect(fnBlock).toContain('form.value.subject_code = t.subject_codes[0]')
  })

  it('clears subject on teacher change', () => {
    expect(content).toContain('form.value.subject_code = null')
  })

  it('filters subject options by selected teacher', () => {
    expect(content).toContain('selectedTeacher.value')
    expect(content).toContain("t.subject_codes.map(code =>")
  })
})

describe('TeacherAssignmentsPage table columns', () => {
  it('defines columns for teacher, subject, class, semester, and actions', () => {
    expect(content).toContain("title: '教师'")
    expect(content).toContain("title: '科目'")
    expect(content).toContain("title: '班级'")
    expect(content).toContain("title: '学期'")
    expect(content).toContain("title: '操作'")
  })

  it('renders teacher name from teacherMap', () => {
    expect(content).toContain('teacherMap.value[row.user_id]')
  })

  it('renders class name from classMap', () => {
    expect(content).toContain('classMap.value[row.class_id]')
  })

  it('renders subject label from subjectLabel helper', () => {
    expect(content).toContain('subjectLabel(row.subject_code)')
  })
})

describe('TeacherAssignmentsPage error handling', () => {
  it('handles loadData error with message', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('async function loadSummary')
    )
    expect(fnBlock).toContain("message.error('加载排课数据失败')")
    expect(fnBlock).toContain('rows.value = []')
  })

  it('handles create error with detail fallback', () => {
    expect(content).toContain("message.error(e.response?.data?.detail || '创建失败')")
  })

  it('handles delete error silently', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('function openCreate')
    )
    expect(fnBlock).toContain("message.error('删除失败')")
  })

  it('silently handles summary load failure', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSummary'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('} catch {')
  })
})

describe('TeacherAssignmentsPage semester defaults', () => {
  it('sets default semester from current semester', () => {
    expect(content).toContain('currentSemesterId.value = r.data.semester || r.data.name')
    expect(content).toContain('filterSemester.value = currentSemesterId.value')
  })

  it('pre-fills create form with current or filtered semester', () => {
    const fnBlock = content.slice(
      content.indexOf('function openCreate'),
      content.indexOf('function handleTeacherChange')
    )
    expect(fnBlock).toContain('form.value.semester = currentSemesterId.value')
    expect(fnBlock).toContain('form.value.semester = filterSemester.value')
  })
})

describe('TeacherAssignmentsPage class sort', () => {
  it('sorts classes by grade then name in select options', () => {
    expect(content).toContain(".sort((a, b) => {")
    expect(content).toContain("(a.grade || '').localeCompare(b.grade || '')")
    expect(content).toContain("(a.name || '').localeCompare(b.name || '')")
  })
})
