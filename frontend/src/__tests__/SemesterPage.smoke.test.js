/**
 * SemesterPage smoke test.
 *
 * Verifies the enhanced SemesterPage.vue:
 *   1. Can be imported (no syntax/import errors)
 *   2. Template includes key enhancement markers (stats, timeline, edit modal)
 *   3. Imports all required API functions
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const semesterPath = resolve(__dirname, '../pages/SemesterPage.vue')
const content = readFileSync(semesterPath, 'utf-8')

describe('SemesterPage smoke', () => {
  it('SemesterPage.vue can be imported', async () => {
    const mod = await import('../pages/SemesterPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SemesterPage enhancement markers', () => {
  it('has statistics cards (NStatistic)', () => {
    expect(content).toContain('n-statistic')
    expect(content).toContain('当前学期')
    expect(content).toContain('剩余天数')
    expect(content).toContain('已配置节次')
  })

  it('has semester timeline (NTimeline)', () => {
    expect(content).toContain('n-timeline')
    expect(content).toContain('n-timeline-item')
  })

  it('has current semester row highlight', () => {
    expect(content).toContain('row-class-name')
    expect(content).toContain('semester-current-row')
  })

  it('has edit semester modal', () => {
    expect(content).toContain('编辑学期')
    expect(content).toContain('showEdit')
    expect(content).toContain('handleEdit')
  })

  it('imports updateSemester and setPeriods API', () => {
    expect(content).toContain('updateSemester')
    expect(content).toContain('setPeriods')
  })

  it('has inline period time editing (NTimePicker)', () => {
    expect(content).toContain('NTimePicker')
    expect(content).toContain('timeToTimestamp')
    expect(content).toContain('timestampToTime')
  })

  it('has add/delete period buttons', () => {
    expect(content).toContain('handleAddPeriod')
    expect(content).toContain('handleDeletePeriod')
    expect(content).toContain('添加节次')
  })

  it('has activate button for non-current semesters', () => {
    expect(content).toContain('handleActivate')
    expect(content).toContain('设为当前')
  })

  it('uses auth store for school_id', () => {
    expect(content).toContain('useAuthStore')
    expect(content).toContain('school_id')
  })
})
