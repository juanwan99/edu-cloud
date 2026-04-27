/**
 * SubjectSelectionsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains combo grid, stats, existing selections, edit modal
 *  3. Combo generation logic (3+1+2 model)
 *  4. API calls for CRUD operations
 *  5. Error handling patterns
 *  6. Toggle, batch create, and edit operations
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../SubjectSelectionsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('SubjectSelectionsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../SubjectSelectionsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SubjectSelectionsPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('选考组合')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('管理学校提供的选考科目组合（新高考 3+1+2）')
  })

  it('contains batch add button with count', () => {
    expect(content).toContain('@click="handleBatchCreate"')
    expect(content).toContain('toAdd.length')
    expect(content).toContain('批量添加')
  })

  it('contains summary statistics cards', () => {
    expect(content).toContain('label="已启用组合"')
    expect(content).toContain('activeCount')
    expect(content).toContain('label="总组合数"')
    expect(content).toContain('selections.length')
    expect(content).toContain('label="已分配学生"')
    expect(content).toContain('totalAssigned')
  })

  it('contains combo grid with checkbox cards', () => {
    expect(content).toContain('class="combo-grid"')
    expect(content).toContain('class="combo-card"')
    expect(content).toContain('class="combo-header"')
    expect(content).toContain('class="combo-name"')
    expect(content).toContain(':class="{ added: combo.exists, checked: combo.checked }"')
  })

  it('shows "added" tag for existing combos', () => {
    expect(content).toContain('v-if="combo.exists"')
    expect(content).toContain('>已添加<')
  })

  it('contains existing selections section', () => {
    expect(content).toContain('已添加的组合')
    expect(content).toContain('v-for="s in selections"')
  })

  it('contains toggle switch for active status', () => {
    expect(content).toContain('n-switch')
    expect(content).toContain(':value="s.is_active"')
    expect(content).toContain('handleToggle(s.id, v)')
  })

  it('contains edit and delete actions for each selection', () => {
    expect(content).toContain('@click="openEdit(s)"')
    expect(content).toContain('>编辑<')
    expect(content).toContain('handleDelete(s.id)')
    expect(content).toContain('>删除<')
    expect(content).toContain('n-popconfirm')
  })

  it('contains edit name modal', () => {
    expect(content).toContain('v-model:show="editVisible"')
    expect(content).toContain('title="编辑组合名称"')
    expect(content).toContain('v-model:value="editName"')
  })
})

describe('SubjectSelectionsPage combo generation (3+1+2 model)', () => {
  it('defines subjects for the 3+1+2 model', () => {
    expect(content).toContain("physics: '物理'")
    expect(content).toContain("history: '历史'")
    expect(content).toContain("chemistry: '化学'")
    expect(content).toContain("biology: '生物'")
    expect(content).toContain("politics: '政治'")
    expect(content).toContain("geography: '地理'")
  })

  it('defines first choices as physics and history', () => {
    expect(content).toContain("const FIRST_CHOICES = ['physics', 'history']")
  })

  it('defines second choices as chemistry, biology, politics, geography', () => {
    expect(content).toContain("const SECOND_CHOICES = ['chemistry', 'biology', 'politics', 'geography']")
  })

  it('generates combos with nested loops for first + two second choices', () => {
    const fnBlock = content.slice(
      content.indexOf('function generateCombos'),
      content.indexOf('const auth')
    )
    expect(fnBlock).toContain('for (const first of FIRST_CHOICES)')
    expect(fnBlock).toContain('for (let i = 0; i < SECOND_CHOICES.length; i++)')
    expect(fnBlock).toContain('for (let j = i + 1; j < SECOND_CHOICES.length; j++)')
    expect(fnBlock).toContain('[first, SECOND_CHOICES[i], SECOND_CHOICES[j]]')
  })

  it('generates combo names from subject labels', () => {
    expect(content).toContain('codes.map(c => SUBJECTS[c])')
    expect(content).toContain("labels.join('')")
  })
})

describe('SubjectSelectionsPage API calls', () => {
  it('imports selection CRUD APIs', () => {
    expect(content).toContain("import { getSelections, createSelection, updateSelection, deleteSelection } from '../api/subjectSelections.js'")
  })

  it('imports student listing for student counts', () => {
    expect(content).toContain("import { listStudents } from '../api/students.js'")
  })

  it('loads selections from school ID', () => {
    expect(content).toContain('await getSelections(schoolId())')
    expect(content).toContain('selections.value = data')
  })

  it('gets school ID from auth store', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
    expect(content).toContain('auth.currentRole?.school_id')
  })
})

describe('SubjectSelectionsPage CRUD operations', () => {
  it('batch creates selections with mode 3+1+2', () => {
    expect(content).toContain("await createSelection(schoolId(), { name: combo.name, subject_codes: combo.codes, mode: '3+1+2' })")
  })

  it('shows batch create success count', () => {
    expect(content).toContain('`成功添加 ${ok} 个组合`')
  })

  it('toggles active status via updateSelection', () => {
    expect(content).toContain('await updateSelection(schoolId(), id, { is_active: active })')
  })

  it('deletes selection and shows success', () => {
    expect(content).toContain('await deleteSelection(schoolId(), id)')
    expect(content).toContain("message.success('已删除')")
  })

  it('validates edit name is not empty', () => {
    expect(content).toContain("if (!editName.value.trim())")
    expect(content).toContain("message.warning('名称不能为空')")
  })

  it('updates selection name via handleEditSave', () => {
    expect(content).toContain('await updateSelection(schoolId(), editId.value, { name: editName.value.trim() })')
    expect(content).toContain("message.success('已更新')")
  })
})

describe('SubjectSelectionsPage state management', () => {
  it('computes toAdd as checked but not existing combos', () => {
    expect(content).toContain('allCombos.value.filter(c => c.checked && !c.exists)')
  })

  it('computes activeCount from active selections', () => {
    expect(content).toContain('selections.value.filter(s => s.is_active).length')
  })

  it('computes totalAssigned from student counts', () => {
    expect(content).toContain('Object.values(studentCounts.value).reduce((sum, n) => sum + n, 0)')
  })

  it('syncs exists state from loaded selections', () => {
    const fnBlock = content.slice(
      content.indexOf('function syncExistsState'),
      content.indexOf('async function loadStudentCounts')
    )
    expect(fnBlock).toContain('new Set(selections.value.map(s => s.name))')
    expect(fnBlock).toContain('combo.exists = existingNames.has(combo.name)')
    expect(fnBlock).toContain('combo.checked = false')
  })

  it('prevents toggling already-existing combos', () => {
    expect(content).toContain('if (combo.exists) return')
    expect(content).toContain('combo.checked = !combo.checked')
  })
})

describe('SubjectSelectionsPage student counts', () => {
  it('loads student counts per selection', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadStudentCounts'),
      content.indexOf('async function loadData')
    )
    expect(fnBlock).toContain("await listStudents({ selection_id: s.id })")
    expect(fnBlock).toContain('Array.isArray(data) ? data.length : 0')
    expect(fnBlock).toContain('await Promise.all(promises)')
  })
})

describe('SubjectSelectionsPage error handling', () => {
  it('handles loadData failure with error message', () => {
    expect(content).toContain("message.error('加载失败')")
  })

  it('handles batch create individual failures', () => {
    expect(content).toContain("message.error(`${combo.name}: ${e.response?.data?.detail || '创建失败'}`)")
  })

  it('handles toggle failure', () => {
    expect(content).toContain("message.error('操作失败')")
  })

  it('handles delete failure', () => {
    expect(content).toContain("message.error('删除失败')")
  })

  it('handles edit save failure with detail fallback', () => {
    expect(content).toContain("message.error(e.response?.data?.detail || '更新失败')")
  })
})

describe('SubjectSelectionsPage mode tag types', () => {
  it('maps mode to tag type', () => {
    expect(content).toContain("if (mode === '3+1+2') return 'success'")
    expect(content).toContain("if (mode === '3+3') return 'info'")
    expect(content).toContain("return 'warning'")
  })
})
