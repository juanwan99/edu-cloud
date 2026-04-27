/**
 * TeachersPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains page header, filters, table, modals
 *  3. API calls for CRUD and import/export
 *  4. Role and subject label mappings
 *  5. Error handling patterns
 *  6. Platform admin cross-school logic
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../TeachersPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('TeachersPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../TeachersPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('TeachersPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('教师管理')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('管理教师档案、学科与班级分配，支持 Excel 批量导入导出')
  })

  it('contains action buttons', () => {
    expect(content).toContain('下载导入模板')
    expect(content).toContain('导出花名册')
    expect(content).toContain('导入 Excel')
    expect(content).toContain('添加教师')
  })

  it('contains school select for platform admin', () => {
    expect(content).toContain('data-testid="school-select"')
    expect(content).toContain('v-model:value="selectedSchool"')
  })

  it('contains search input for name or account', () => {
    expect(content).toContain('v-model:value="searchQuery"')
    expect(content).toContain('placeholder="搜索姓名或账号"')
  })

  it('contains teacher count tag', () => {
    expect(content).toContain('teachers.length')
  })

  it('contains data table with scroll and pagination', () => {
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="teachers"')
    expect(content).toContain('pageSize: 50')
    expect(content).toContain(':scroll-x="1200"')
  })

  it('contains form modal for create/edit', () => {
    expect(content).toContain('v-model:show="showForm"')
    expect(content).toContain("editingId ? '编辑教师' : '添加教师'")
  })

  it('contains import modal with role selector and file upload', () => {
    expect(content).toContain('v-model:show="showImport"')
    expect(content).toContain('title="导入教师（Excel）"')
    expect(content).toContain('v-model:value="importRole"')
    expect(content).toContain('accept=".xlsx,.xls"')
  })
})

describe('TeachersPage form fields', () => {
  it('includes all teacher profile fields in the form', () => {
    expect(content).toContain('v-model:value="form.display_name"')
    expect(content).toContain('v-model:value="form.username"')
    expect(content).toContain('v-model:value="form.password"')
    expect(content).toContain('v-model:value="form.gender"')
    expect(content).toContain('v-model:value="form.phone"')
    expect(content).toContain('v-model:value="form.office_phone"')
    expect(content).toContain('v-model:value="form.email"')
    expect(content).toContain('v-model:value="form.employee_id"')
    expect(content).toContain('v-model:value="form.id_card"')
    expect(content).toContain('v-model:value="form.title"')
    expect(content).toContain('v-model:value="form.hire_date"')
    expect(content).toContain('v-model:value="form.education"')
    expect(content).toContain('v-model:value="form.university"')
    expect(content).toContain('v-model:value="form.notes"')
  })

  it('includes role, subject, and class assignment fields for create', () => {
    expect(content).toContain('v-model:value="form.roles"')
    expect(content).toContain('v-model:value="form.subject_codes"')
    expect(content).toContain('v-model:value="form.class_ids"')
  })

  it('includes is_active toggle for edit mode', () => {
    expect(content).toContain('v-model:value="form.is_active"')
    expect(content).toContain('v-if="editingId"')
  })
})

describe('TeachersPage API calls', () => {
  it('imports all teacher API functions', () => {
    expect(content).toContain('listTeachers')
    expect(content).toContain('createTeacher')
    expect(content).toContain('updateTeacher')
    expect(content).toContain('deleteTeacher')
    expect(content).toContain('importTeachers')
    expect(content).toContain('exportTeachers')
    expect(content).toContain('downloadTemplate')
  })

  it('imports school listing for platform admin', () => {
    expect(content).toContain("import { listSchools } from '../api/schools'")
  })

  it('loads teachers with optional search and school params', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadTeachers'),
      content.indexOf('async function loadClasses')
    )
    expect(fnBlock).toContain('params.q = searchQuery.value')
    expect(fnBlock).toContain('params.school_id = selectedSchool.value')
    expect(fnBlock).toContain('await listTeachers(params)')
  })

  it('loads classes via client.get with school_id param', () => {
    expect(content).toContain("client.get('/classes'")
  })
})

describe('TeachersPage role labels', () => {
  it('defines complete role label mapping', () => {
    expect(content).toContain("subject_teacher: '科任教师'")
    expect(content).toContain("homeroom_teacher: '班主任'")
    expect(content).toContain("teaching_research_leader: '教研组长'")
    expect(content).toContain("grade_leader: '年级组长'")
    expect(content).toContain("lesson_prep_leader: '备课组长'")
    expect(content).toContain("principal: '校长'")
    expect(content).toContain("academic_director: '教务主任'")
    expect(content).toContain("district_admin: '区管理员'")
  })
})

describe('TeachersPage subject labels', () => {
  it('defines subject code to label mapping', () => {
    expect(content).toContain("YW: '语文'")
    expect(content).toContain("SX: '数学'")
    expect(content).toContain("YY: '英语'")
    expect(content).toContain("WL: '物理'")
    expect(content).toContain("HX: '化学'")
    expect(content).toContain("SW: '生物'")
    expect(content).toContain("TY: '体育'")
  })
})

describe('TeachersPage CRUD operations', () => {
  it('validates display_name is required for save', () => {
    expect(content).toContain("if (!form.display_name) { message.warning('姓名为必填')")
  })

  it('validates username is required for new teacher', () => {
    expect(content).toContain("if (!editingId.value && !form.username) { message.warning('用户名为必填')")
  })

  it('calls createTeacher for new entries', () => {
    expect(content).toContain('await createTeacher(payload)')
    expect(content).toContain("message.success('添加成功')")
  })

  it('calls updateTeacher for existing entries', () => {
    expect(content).toContain('await updateTeacher(editingId.value, payload)')
    expect(content).toContain("message.success('更新成功')")
  })

  it('shows delete confirmation with teacher name', () => {
    expect(content).toContain("title: '确认删除'")
    expect(content).toContain('确定要删除教师')
    expect(content).toContain('row.display_name')
    expect(content).toContain('await deleteTeacher(row.id)')
  })

  it('sets default password as 123456', () => {
    expect(content).toContain("password: '123456'")
  })

  it('sets default role as subject_teacher', () => {
    expect(content).toContain("roles: ['subject_teacher']")
  })
})

describe('TeachersPage import/export', () => {
  it('calls importTeachers with file and role', () => {
    expect(content).toContain('await importTeachers(importFile.value, importRole.value)')
  })

  it('displays import result counts', () => {
    expect(content).toContain('data.created')
    expect(content).toContain('data.updated')
    expect(content).toContain('data.skipped')
  })

  it('calls downloadTemplate for template download', () => {
    expect(content).toContain('await downloadTemplate(schoolParams())')
  })

  it('calls exportTeachers for roster export', () => {
    expect(content).toContain('await exportTeachers(schoolParams())')
  })

  it('uses triggerDownload utility for file download', () => {
    expect(content).toContain('function triggerDownload(blob, filename)')
    expect(content).toContain('URL.createObjectURL(blob)')
  })
})

describe('TeachersPage error handling', () => {
  it('handles save error with detail fallback', () => {
    expect(content).toContain("message.error(e.response?.data?.detail || '操作失败')")
  })

  it('handles delete error with detail fallback', () => {
    const deleteBlock = content.slice(
      content.indexOf('function handleDelete'),
      content.indexOf('function handleFileChange')
    )
    expect(deleteBlock).toContain("message.error(e.response?.data?.detail || '删除失败')")
  })

  it('handles import error with detail fallback', () => {
    const importBlock = content.slice(
      content.indexOf('async function handleImport'),
      content.indexOf('function triggerDownload')
    )
    expect(importBlock).toContain("message.error(e.response?.data?.detail || '导入失败')")
  })
})

describe('TeachersPage platform admin features', () => {
  it('computes isPlatformAdmin from auth store', () => {
    expect(content).toContain("auth.currentRole?.role === 'platform_admin'")
  })

  it('provides cross-school role options for platform admin', () => {
    expect(content).toContain('ROLE_OPTIONS_CROSS_SCHOOL')
    expect(content).toContain("{ label: '校长', value: 'principal' }")
    expect(content).toContain("{ label: '教务主任', value: 'academic_director' }")
  })

  it('sets school_id on payload for platform admin creates', () => {
    expect(content).toContain('payload.school_id = selectedSchool.value')
  })

  it('defaults to principal role for platform admin creates', () => {
    expect(content).toContain("form.roles = ['principal']")
  })
})

describe('TeachersPage search debounce', () => {
  it('debounces search with 300ms timeout', () => {
    expect(content).toContain('searchTimer = setTimeout(loadTeachers, 300)')
    expect(content).toContain('clearTimeout(searchTimer)')
  })
})

describe('TeachersPage education options', () => {
  it('defines education level options', () => {
    expect(content).toContain("{ label: '大专', value: '大专' }")
    expect(content).toContain("{ label: '本科', value: '本科' }")
    expect(content).toContain("{ label: '硕士', value: '硕士' }")
    expect(content).toContain("{ label: '博士', value: '博士' }")
  })
})

describe('TeachersPage table columns', () => {
  it('defines key columns with fixed positioning', () => {
    expect(content).toContain("title: '姓名', key: 'display_name'")
    expect(content).toContain("fixed: 'left'")
    expect(content).toContain("title: '操作', key: 'actions'")
    expect(content).toContain("fixed: 'right'")
  })
})
