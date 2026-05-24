/**
 * StudentsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains page header, filters, table, modals
 *  3. API calls for CRUD and import/export
 *  4. Form fields and validation
 *  5. Error handling patterns
 *  6. Filter and search logic
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../StudentsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('StudentsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../StudentsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('StudentsPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('学生管理')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('管理学生信息，支持 Excel 批量导入')
  })

  it('contains action buttons for export, import, and create', () => {
    expect(content).toContain('导出 Excel')
    expect(content).toContain('导入 Excel')
    expect(content).toContain('添加学生')
  })

  it('contains filter selects for grade, class, selection, and subject', () => {
    expect(content).toContain('v-model:value="filterGrade"')
    expect(content).toContain('v-model:value="filterClassId"')
    expect(content).toContain('v-model:value="filterSelectionId"')
    expect(content).toContain('v-model:value="filterSubjectCode"')
    expect(content).toContain('placeholder="按年级筛选"')
    expect(content).toContain('placeholder="按班级筛选"')
    expect(content).toContain('placeholder="按选课组合筛选"')
    expect(content).toContain('placeholder="按学科筛选"')
  })

  it('contains search input for name search', () => {
    expect(content).toContain('v-model:value="searchQuery"')
    expect(content).toContain('placeholder="搜索姓名"')
  })

  it('contains data table with pagination', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="students"')
    expect(content).toContain('pageSize: 50')
  })

  it('contains create student modal', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="添加学生"')
  })

  it('contains edit student modal', () => {
    expect(content).toContain('v-model:show="showEdit"')
    expect(content).toContain('title="编辑学生"')
  })

  it('contains import modal with file upload', () => {
    expect(content).toContain('v-model:show="showImport"')
    expect(content).toContain('title="导入学生（Excel）"')
    expect(content).toContain('accept=".xlsx,.xls"')
  })
})

describe('StudentsPage API calls', () => {
  it('imports all student API functions', () => {
    expect(content).toContain('listStudents')
    expect(content).toContain('createStudent')
    expect(content).toContain('updateStudent')
    expect(content).toContain('deleteStudent')
    expect(content).toContain('importStudents')
    expect(content).toContain('exportStudents')
  })

  it('imports reference data APIs', () => {
    expect(content).toContain('listClasses')
    expect(content).toContain('listGrades')
    expect(content).toContain('listSelections')
  })

  it('calls loadStudents with filter params', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadStudents'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('params.grade = filterGrade.value')
    expect(fnBlock).toContain('params.class_id = filterClassId.value')
    expect(fnBlock).toContain('params.selection_id = filterSelectionId.value')
    expect(fnBlock).toContain('params.subject_code = filterSubjectCode.value')
    expect(fnBlock).toContain('params.q = searchQuery.value')
    expect(fnBlock).toContain('await listStudents(params)')
  })

  it('loads all reference data on mount', () => {
    expect(content).toContain('await Promise.all([loadGrades(), loadClasses()')
    expect(content).toContain('loadSelections()')
    expect(content).toContain('await loadStudents()')
  })
})

describe('StudentsPage CRUD operations', () => {
  it('validates name and student_number before create', () => {
    expect(content).toContain("if (!createForm.name || !createForm.student_number)")
    expect(content).toContain("message.warning('姓名和学号为必填')")
  })

  it('calls createStudent API', () => {
    expect(content).toContain('await createStudent(createForm)')
    expect(content).toContain("message.success('添加成功')")
  })

  it('calls updateStudent API with editing ID', () => {
    expect(content).toContain('await updateStudent(editingId.value, editForm)')
    expect(content).toContain("message.success('更新成功')")
  })

  it('shows delete confirmation dialog', () => {
    expect(content).toContain("title: '确认删除'")
    expect(content).toContain('await deleteStudent(row.id)')
    expect(content).toContain("message.success('已删除')")
  })

  it('resets create form after successful creation', () => {
    expect(content).toContain("Object.assign(createForm, { name: '', student_number: '', class_id: null")
  })
})

describe('StudentsPage import/export', () => {
  it('handles import with class and grade params', () => {
    expect(content).toContain('await importStudents(importFile.value, { classId: importClassId.value, grade: importGrade.value })')
  })

  it('displays import result summary', () => {
    expect(content).toContain('`新增 ${data.created} 人`')
    expect(content).toContain('data.updated')
    expect(content).toContain('data.skipped')
    expect(content).toContain('data.class_not_found')
    expect(content).toContain('data.selection_not_found')
  })

  it('supports template and data export options', () => {
    expect(content).toContain("{ label: '导出标准模板（空表）', key: 'template' }")
    expect(content).toContain("{ label: '导出现有学生数据', key: 'data' }")
  })

  it('calls exportStudents and triggers download', () => {
    expect(content).toContain('await exportStudents(params)')
    expect(content).toContain('URL.createObjectURL(data)')
    expect(content).toContain("a.download = key === 'template' ? 'students_template.xlsx' : 'students.xlsx'")
  })
})

describe('StudentsPage error handling', () => {
  it('handles create error with detail message', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function openEdit')
    )
    expect(createBlock).toContain("message.error(e.response?.data?.detail || '添加失败')")
  })

  it('handles update error with detail message', () => {
    const updateBlock = content.slice(
      content.indexOf('async function handleUpdate'),
      content.indexOf('function handleDelete')
    )
    expect(updateBlock).toContain("message.error(e.response?.data?.detail || '更新失败')")
  })

  it('handles delete error with detail message', () => {
    expect(content).toContain("message.error(e.response?.data?.detail || '删除失败')")
  })

  it('handles import error with detail message', () => {
    const importBlock = content.slice(
      content.indexOf('async function handleImport'),
      content.indexOf('const exportOptions')
    )
    expect(importBlock).toContain("message.error(e.response?.data?.detail || '导入失败')")
  })
})

describe('StudentsPage search debounce', () => {
  it('debounces search with 300ms timeout', () => {
    expect(content).toContain('searchTimer = setTimeout(loadStudents, 300)')
    expect(content).toContain('clearTimeout(searchTimer)')
  })
})

describe('StudentsPage subject labels', () => {
  it('defines subject code to label mapping', () => {
    expect(content).toContain("YW: '语文'")
    expect(content).toContain("SX: '数学'")
    expect(content).toContain("YY: '英语'")
    expect(content).toContain("WL: '物理'")
    expect(content).toContain("HX: '化学'")
  })
})

describe('StudentsPage table columns', () => {
  it('defines columns for name, student_number, grade, class, gender, selection, actions', () => {
    expect(content).toContain("title: '姓名', key: 'name'")
    expect(content).toContain("title: '学号', key: 'student_number'")
    expect(content).toContain("title: '年级', key: 'grade'")
    expect(content).toContain("title: '班级', key: 'class_id'")
    expect(content).toContain("title: '性别', key: 'gender'")
    expect(content).toContain("title: '选课组合', key: 'selection_id'")
    expect(content).toContain("title: '操作', key: 'actions'")
  })

  it('includes profile, edit, and delete action buttons', () => {
    expect(content).toContain("{ default: () => '画像' }")
    expect(content).toContain("{ default: () => '编辑' }")
    expect(content).toContain("{ default: () => '删除' }")
  })
})


describe('StudentsPage action permission policy', () => {
  it('gates roster mutation actions behind manage_scheduling', () => {
    expect(content).toContain("const normalizedRole = computed(() => normalizeRole(auth.currentRole?.role || ''))")
    expect(content).toContain("const canManageStudents = computed(() => hasPermission(normalizedRole.value, 'manage_scheduling'))")
    expect(content).toContain('v-if="canManageStudents"')
    expect(content).toContain('if (canManageStudents.value) {')
  })

  it('guards create, update, delete, import, and export handlers programmatically', () => {
    expect(content).toContain('if (!canManageStudents.value) return')
  })
})
