import { describe, it, expect } from 'vitest'
import { getSubjectColumns, getClassColumns, getStudentColumns, fmt, pct, formatDelta } from '../useTableColumns'

describe('useTableColumns', () => {
  describe('fmt', () => {
    it('formats numbers', () => {
      expect(fmt(82.5)).toBe('82.5')
      expect(fmt(100)).toBe('100')
      expect(fmt(null)).toBe('-')
      expect(fmt(undefined)).toBe('-')
    })
  })

  describe('pct', () => {
    it('formats rates as percentages', () => {
      expect(pct(0.825)).toBe('83%')
      expect(pct(1)).toBe('100%')
      expect(pct(null)).toBe('-')
    })
  })

  describe('formatDelta', () => {
    it('formats rank changes', () => {
      expect(formatDelta(3)).toBe('进 3')
      expect(formatDelta(-2)).toBe('退 2')
      expect(formatDelta(0)).toBe('持平')
      expect(formatDelta(null)).toBe('-')
    })
  })

  describe('getSubjectColumns', () => {
    it('returns 9 columns', () => {
      const cols = getSubjectColumns()
      expect(cols).toHaveLength(9)
      expect(cols[0].title).toBe('科目')
      expect(cols.map(c => c.title)).toContain('得分率')
    })
  })

  describe('getClassColumns', () => {
    it('returns 9 columns with rank', () => {
      const cols = getClassColumns()
      expect(cols).toHaveLength(9)
      expect(cols[0].title).toBe('排名')
    })
  })

  describe('getStudentColumns', () => {
    it('includes dynamic subject columns', () => {
      const subjects = [
        { subject_name: '语文', subject_code: 'YW' },
        { subject_name: '数学', subject_code: 'SX' },
      ]
      const cols = getStudentColumns(subjects)
      const titles = cols.map(c => c.title)
      expect(titles).toContain('语文')
      expect(titles).toContain('数学')
      expect(titles).toContain('排名')
      expect(titles).toContain('班级进退')
    })

    it('handles null subjects', () => {
      const cols = getStudentColumns(null)
      expect(cols.map(c => c.title)).not.toContain('语文')
      expect(cols.length).toBeGreaterThan(5)
    })
  })
})
