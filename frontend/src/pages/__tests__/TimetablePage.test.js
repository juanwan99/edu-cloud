/**
 * TimetablePage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key UI sections (stats, filters, grid, subject stats, edit modal)
 *  3. Data fetching calls correct API methods from academic.js / students.js / teachers.js
 *  4. CRUD operations (save timetable, edit/remove/copy/paste slots)
 *  5. Conflict detection logic
 *  6. Error handling (try-catch wrappers)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../TimetablePage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('TimetablePage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../TimetablePage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('TimetablePage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('课程表')
    expect(content).toContain('按班级查看和编辑课程表')
  })

  it('contains statistics grid with 4 columns', () => {
    expect(content).toContain('<n-grid :cols="4"')
    expect(content).toContain('<n-statistic label="已排课班级"')
    expect(content).toContain('<n-statistic label="覆盖率"')
    expect(content).toContain('<n-statistic label="当前班级课时"')
    expect(content).toContain('<n-statistic label="空余时段"')
  })

  it('contains grade and class select filters', () => {
    expect(content).toContain('v-model:value="selectedGrade"')
    expect(content).toContain('v-model:value="selectedClassId"')
    expect(content).toContain('placeholder="选择年级"')
    expect(content).toContain('placeholder="选择班级"')
  })

  it('contains save, edit, cancel buttons', () => {
    expect(content).toContain('保存课表')
    expect(content).toContain('handleSave')
    expect(content).toContain('editing = true')
    expect(content).toContain('cancelEdit')
  })

  it('contains timetable grid with weekday headers', () => {
    expect(content).toContain('class="timetable-grid"')
    expect(content).toContain('v-for="d in weekdays"')
    expect(content).toContain('v-for="p in classPeriods"')
  })

  it('contains slot content elements', () => {
    expect(content).toContain('class="slot-content"')
    expect(content).toContain('class="slot-subject"')
    expect(content).toContain('class="slot-teacher"')
    expect(content).toContain('class="slot-empty"')
  })

  it('contains conflict icon indicator', () => {
    expect(content).toContain('class="conflict-icon"')
    expect(content).toContain('getConflict')
  })

  it('contains paste target styling', () => {
    expect(content).toContain('slot-paste-target')
    expect(content).toContain('clipboardSlot')
  })

  it('contains subject stats section', () => {
    expect(content).toContain('class="subject-stats"')
    expect(content).toContain('class="stats-label"')
    expect(content).toContain('subjectSlotStats')
  })

  it('contains slot edit modal', () => {
    expect(content).toContain('v-model:show="showSlotEdit"')
    expect(content).toContain('title="设置课程"')
    expect(content).toContain('placeholder="选择科目"')
    expect(content).toContain('placeholder="选择教师"')
  })

  it('contains clear and copy buttons in modal', () => {
    expect(content).toContain('清除此节')
    expect(content).toContain('复制此节')
  })

  it('contains conflict alert in modal', () => {
    expect(content).toContain('slotEditConflict')
    expect(content).toContain('<n-alert')
  })

  it('contains empty state fallback', () => {
    expect(content).toContain('<n-empty')
    expect(content).toContain('选择年级和班级查看课表')
  })

  it('contains loading spinner', () => {
    expect(content).toContain('<n-spin :show="loading">')
  })
})

describe('TimetablePage data fetching', () => {
  it('imports API methods from academic.js', () => {
    expect(content).toContain("import { getCurrentSemester, getPeriods, getTimetable, saveTimetable, getTimetableStats }")
    expect(content).toContain("from '../api/academic.js'")
  })

  it('imports listClasses from students.js', () => {
    expect(content).toContain("import { listClasses } from '../api/students.js'")
  })

  it('imports listTeachers from teachers.js', () => {
    expect(content).toContain("import { listTeachers } from '../api/teachers.js'")
  })

  it('calls getCurrentSemester, listClasses, listTeachers in init', () => {
    const initBlock = content.slice(
      content.indexOf('async function init'),
      content.indexOf('watch(editing')
    )
    expect(initBlock).toContain('getCurrentSemester()')
    expect(initBlock).toContain('listClasses()')
    expect(initBlock).toContain('listTeachers()')
    expect(initBlock).toContain('Promise.all')
  })

  it('calls getPeriods after getting current semester', () => {
    const initBlock = content.slice(
      content.indexOf('async function init'),
      content.indexOf('watch(editing')
    )
    expect(initBlock).toContain('await getPeriods(semRes.data.id)')
  })

  it('calls getTimetable when loading class timetable', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadTimetable'),
      content.indexOf('async function loadStats')
    )
    expect(loadBlock).toContain('await getTimetable(')
    expect(loadBlock).toContain('semester_id: semesterId.value')
    expect(loadBlock).toContain('class_id: selectedClassId.value')
  })

  it('calls getTimetableStats for statistics', () => {
    const statsBlock = content.slice(
      content.indexOf('async function loadStats'),
      content.indexOf('async function loadAllClassTimetables')
    )
    expect(statsBlock).toContain('await getTimetableStats(params)')
  })

  it('loads all class timetables for conflict detection', () => {
    expect(content).toContain('async function loadAllClassTimetables')
    expect(content).toContain('Promise.all(promises)')
  })

  it('calls init on mount', () => {
    expect(content).toContain('onMounted(init)')
  })
})

describe('TimetablePage CRUD operations', () => {
  it('calls saveTimetable in handleSave', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSave'),
      content.indexOf('async function init')
    )
    expect(saveBlock).toContain('await saveTimetable(selectedClassId.value')
    expect(saveBlock).toContain('semester_id: semesterId.value')
  })

  it('maps slot data on save with correct fields', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSave'),
      content.indexOf('async function init')
    )
    expect(saveBlock).toContain('weekday: s.weekday')
    expect(saveBlock).toContain('period_id: s.period_id')
    expect(saveBlock).toContain('subject_code: s.subject_code')
    expect(saveBlock).toContain('teacher_id: s.teacher_id')
  })

  it('confirms slot editing via confirmSlot', () => {
    const confirmBlock = content.slice(
      content.indexOf('function confirmSlot'),
      content.indexOf('function removeSlot')
    )
    expect(confirmBlock).toContain('slots.value.push(slot)')
    expect(confirmBlock).toContain('slots.value[idx] = slot')
    expect(confirmBlock).toContain('showSlotEdit.value = false')
  })

  it('removes a slot via removeSlot', () => {
    const removeBlock = content.slice(
      content.indexOf('function removeSlot'),
      content.indexOf('function copySlot')
    )
    expect(removeBlock).toContain('slots.value = slots.value.filter')
    expect(removeBlock).toContain('showSlotEdit.value = false')
  })

  it('copies a slot via copySlot', () => {
    const copyBlock = content.slice(
      content.indexOf('function copySlot'),
      content.indexOf('function cancelEdit')
    )
    expect(copyBlock).toContain('clipboardSlot.value = {')
    expect(copyBlock).toContain('subject_code: existing.subject_code')
    expect(copyBlock).toContain('已复制，点击空格粘贴')
  })

  it('handles paste on empty slot click', () => {
    const clickBlock = content.slice(
      content.indexOf('function onSlotClick'),
      content.indexOf('function openSlotEdit')
    )
    expect(clickBlock).toContain('clipboardSlot.value && !getSlot')
    expect(clickBlock).toContain('slots.value.push(slot)')
    expect(clickBlock).toContain('clipboardSlot.value = null')
    expect(clickBlock).toContain('已粘贴')
  })

  it('resets editing and clipboard on cancel', () => {
    const cancelBlock = content.slice(
      content.indexOf('function cancelEdit'),
      content.indexOf('async function loadTimetable')
    )
    expect(cancelBlock).toContain('editing.value = false')
    expect(cancelBlock).toContain('clipboardSlot.value = null')
    expect(cancelBlock).toContain('loadTimetable()')
  })

  it('validates subject and teacher before confirm', () => {
    const confirmBlock = content.slice(
      content.indexOf('function confirmSlot'),
      content.indexOf('function removeSlot')
    )
    expect(confirmBlock).toContain('!slotForm.value.subject_code || !slotForm.value.teacher_id')
    expect(confirmBlock).toContain('请选择科目和教师')
  })
})

describe('TimetablePage subject and weekday definitions', () => {
  it('defines weekdays Monday through Friday', () => {
    expect(content).toContain("{ value: 1, label: '周一' }")
    expect(content).toContain("{ value: 2, label: '周二' }")
    expect(content).toContain("{ value: 3, label: '周三' }")
    expect(content).toContain("{ value: 4, label: '周四' }")
    expect(content).toContain("{ value: 5, label: '周五' }")
  })

  it('defines 14 subject codes', () => {
    const subjectMatches = content.match(/\{ code: '[A-Z]+', label: '[一-鿿]+' \}/g)
    expect(subjectMatches).not.toBeNull()
    expect(subjectMatches.length).toBe(14)
  })

  it('includes core subjects', () => {
    expect(content).toContain("code: 'YW', label: '语文'")
    expect(content).toContain("code: 'SX', label: '数学'")
    expect(content).toContain("code: 'YY', label: '英语'")
  })
})

describe('TimetablePage conflict detection', () => {
  it('has getConflict function checking teacher overlap', () => {
    const conflictBlock = content.slice(
      content.indexOf('function getConflict(weekday, periodId)'),
      content.indexOf('const slotEditConflict')
    )
    expect(conflictBlock).toContain('slot.teacher_id')
    expect(conflictBlock).toContain('allClassTimetables.value')
    expect(conflictBlock).toContain('在该节次已排')
  })

  it('has slotEditConflict computed for modal', () => {
    expect(content).toContain('const slotEditConflict = computed')
    expect(content).toContain('在该节次已排')
  })

  it('loads all class timetables when editing starts', () => {
    expect(content).toContain('watch(editing')
    expect(content).toContain('loadAllClassTimetables()')
  })
})

describe('TimetablePage computed properties', () => {
  it('computes gradeOptions from classes', () => {
    expect(content).toContain('const gradeOptions = computed')
    expect(content).toContain('classes.value.map(c => c.grade)')
  })

  it('computes classOptions filtered by selected grade', () => {
    expect(content).toContain('const classOptions = computed')
    expect(content).toContain('c.grade === selectedGrade.value')
  })

  it('computes coveragePercent from stats', () => {
    expect(content).toContain('const coveragePercent = computed')
    expect(content).toContain('timetableStats.value.coverage_rate')
  })

  it('computes emptySlotCount from total minus filled', () => {
    expect(content).toContain('const emptySlotCount = computed')
    expect(content).toContain('classPeriodSlots.value.length * weekdays.length')
  })

  it('computes subjectSlotStats for subject hour counts', () => {
    expect(content).toContain('const subjectSlotStats = computed')
    expect(content).toContain('counts[s.subject_code]')
  })
})

describe('TimetablePage CSS classes', () => {
  it('defines timetable grid styles', () => {
    expect(content).toContain('.timetable-grid')
    expect(content).toContain('.period-name')
    expect(content).toContain('.period-time')
  })

  it('defines slot cell styles', () => {
    expect(content).toContain('.slot-cell')
    expect(content).toContain('.slot-cell-empty')
    expect(content).toContain('.slot-cell-conflict')
  })

  it('defines break row styles', () => {
    expect(content).toContain('.break-row')
    expect(content).toContain('.break-label')
  })
})

describe('TimetablePage error handling', () => {
  it('wraps loadTimetable in try-catch', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadTimetable'),
      content.indexOf('async function loadStats')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch')
    expect(loadBlock).toContain('加载课表失败')
  })

  it('wraps handleSave in try-catch', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSave'),
      content.indexOf('async function init')
    )
    expect(saveBlock).toContain('try {')
    expect(saveBlock).toContain('} catch')
    expect(saveBlock).toContain('保存失败')
  })

  it('wraps init in try-catch', () => {
    const initBlock = content.slice(
      content.indexOf('async function init'),
      content.indexOf('watch(editing')
    )
    expect(initBlock).toContain('try {')
    expect(initBlock).toContain('} catch')
    expect(initBlock).toContain('初始化失败')
  })

  it('handles listTeachers failure gracefully in init', () => {
    const initBlock = content.slice(
      content.indexOf('async function init'),
      content.indexOf('watch(editing')
    )
    expect(initBlock).toContain("listTeachers().catch(() => ({ data: [] }))")
  })

  it('handles stats load failure silently', () => {
    const statsBlock = content.slice(
      content.indexOf('async function loadStats'),
      content.indexOf('async function loadAllClassTimetables')
    )
    expect(statsBlock).toContain('} catch')
  })

  it('uses e.response?.data?.detail fallback on save error', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSave'),
      content.indexOf('async function init')
    )
    expect(saveBlock).toContain("e.response?.data?.detail || '保存失败'")
  })
})
