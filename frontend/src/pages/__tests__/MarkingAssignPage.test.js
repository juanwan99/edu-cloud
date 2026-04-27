/**
 * MarkingAssignPage tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains stats row (stat-card, n-statistic)
 *  3. No hardcoded light-theme colors
 *  4. Per-question card layout with multi-teacher support
 *  5. Teacher workload badge present (teacherWorkload)
 *  6. Delete assignment and answer_count support
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
    expect(content).toContain('assignedQuestionCount')
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

describe('MarkingAssignPage per-question card layout', () => {
  it('has question-card elements', () => {
    expect(content).toContain('class="question-card"')
  })

  it('has add-teacher-row for new assignment', () => {
    expect(content).toContain('class="add-teacher-row"')
  })

  it('has getAssignsForQuestion helper', () => {
    expect(content).toContain('getAssignsForQuestion')
  })

  it('has getTeacherName helper', () => {
    expect(content).toContain('getTeacherName')
  })

  it('supports answer_count in assign request', () => {
    expect(content).toContain('answer_count')
  })
})

describe('MarkingAssignPage delete assignment', () => {
  it('has removeAssign function', () => {
    expect(content).toContain('removeAssign')
  })

  it('calls DELETE endpoint', () => {
    expect(content).toContain("client.delete(`/marking/assignments/")
  })
})

describe('MarkingAssignPage my-assignments columns', () => {
  it('has answer_count column', () => {
    expect(content).toContain("key: 'answer_count'")
  })

  it('has graded_count column', () => {
    expect(content).toContain("key: 'graded_count'")
  })
})
