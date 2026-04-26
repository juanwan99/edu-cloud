/**
 * MarkingAssignPage enhancement tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains stats row (stat-card, n-statistic)
 *  3. No hardcoded light-theme colors (#f0f0f0, #f5f5f5, #888, white)
 *  4. Batch assign UI elements present (batch-bar, checked)
 *  5. Teacher workload badge present (teacherWorkload)
 *  6. NDataTable used for question list (n-data-table / questionColumns)
 *  7. Script contains required computed properties
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../MarkingAssignPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('MarkingAssignPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../MarkingAssignPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('MarkingAssignPage dark-theme compliance', () => {
  it('has no hardcoded #f0f0f0 borders', () => {
    expect(content).not.toContain('#f0f0f0')
  })

  it('has no hardcoded #f5f5f5 borders', () => {
    expect(content).not.toContain('#f5f5f5')
  })

  it('has no hardcoded #888 text color in inline styles', () => {
    // Allow #888 in JS string values but not in style attributes
    const templateSection = content.split('<script')[0]
    expect(templateSection).not.toContain('color: #888')
  })

  it('uses CSS variables or rgba for borders', () => {
    expect(content).toMatch(/var\(--color-border/)
  })

  it('uses CSS variables or rgba for muted text', () => {
    expect(content).toMatch(/var\(--color-text-muted|rgba\(/)
  })
})

describe('MarkingAssignPage statistics section', () => {
  it('contains stats-row with stat-card', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
  })

  it('contains n-statistic components', () => {
    expect(content).toContain('n-statistic')
  })

  it('shows assigned count / total', () => {
    expect(content).toContain('assignedCount')
    expect(content).toContain('totalQuestionCount')
  })

  it('shows participating teacher count', () => {
    expect(content).toContain('participatingTeacherCount')
  })

  it('shows unassigned count', () => {
    expect(content).toContain('unassignedCount')
  })
})

describe('MarkingAssignPage teacher workload', () => {
  it('has teacherWorkload computed property', () => {
    expect(content).toContain('teacherWorkload')
  })

  it('displays workload count per teacher', () => {
    expect(content).toContain('teacherWorkload[t.id]')
  })
})

describe('MarkingAssignPage batch assign', () => {
  it('has batch-bar floating element', () => {
    expect(content).toContain('class="batch-bar"')
  })

  it('has checkedKeys state', () => {
    expect(content).toContain('checkedKeys')
  })

  it('has batchTeacherId state', () => {
    expect(content).toContain('batchTeacherId')
  })

  it('has handleBatchAssign function', () => {
    expect(content).toContain('handleBatchAssign')
  })

  it('uses Promise.all for batch API calls', () => {
    expect(content).toContain('Promise.all')
  })
})

describe('MarkingAssignPage NDataTable for questions', () => {
  it('uses n-data-table for question list', () => {
    const templateSection = content.split('<script')[0]
    // Manager view should have n-data-table for questions (not just teacher view)
    const dataTableCount = (templateSection.match(/n-data-table/g) || []).length
    expect(dataTableCount).toBeGreaterThanOrEqual(2) // questions table + my-assignments table
  })

  it('has questionColumns with selection type', () => {
    expect(content).toContain('questionColumns')
    expect(content).toContain("type: 'selection'")
  })

  it('questionColumns includes subject, score, and assignee', () => {
    expect(content).toContain("key: 'subjectName'")
    expect(content).toContain("key: 'maxScore'")
    expect(content).toContain("key: 'assignee'")
  })
})
