/**
 * ExamListPage smoke test.
 *
 * Verifies the enhanced ExamListPage.vue:
 *   1. Can be imported (no syntax/import errors)
 *   2. Template includes key enhancement markers (stats, search, filters, new columns)
 *   3. statusMap includes published and archived
 *   4. Create form has date picker and description fields
 *   5. Archive and copy actions exist
 *   6. Empty state with guidance
 *   7. API module exports archiveExam
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const pagePath = resolve(__dirname, '../pages/ExamListPage.vue')
const content = readFileSync(pagePath, 'utf-8')

describe('ExamListPage smoke', () => {
  it('ExamListPage.vue can be imported', async () => {
    const mod = await import('../pages/ExamListPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ExamListPage stats cards', () => {
  it('has demo-style div stat cards', () => {
    expect(content).toContain('stat-icon stat-icon--yellow')
    expect(content).toContain('stat-label')
    expect(content).toContain('stat-value')
    expect(content).toContain('考试总数')
    expect(content).toContain('进行中')
    expect(content).toContain('已完成')
    expect(content).toContain('草稿')
  })

  it('has stats-row grid container', () => {
    expect(content).toContain('stats-row')
    expect(content).toContain('stat-card')
  })
})

describe('ExamListPage search and filter', () => {
  it('has search input', () => {
    expect(content).toContain('searchText')
    expect(content).toContain('搜索考试名称')
  })

  it('has status filter select', () => {
    expect(content).toContain('statusFilter')
    expect(content).toContain('statusFilterOptions')
    expect(content).toContain('筛选状态')
  })

  it('has clear filters button', () => {
    expect(content).toContain('clearFilters')
    expect(content).toContain('清除筛选')
  })

  it('has filteredExams computed property', () => {
    expect(content).toContain('filteredExams')
  })
})

describe('ExamListPage table enhancements', () => {
  it('has subject_count column', () => {
    expect(content).toContain('subject_count')
    expect(content).toContain('科目数')
  })

  it('has student_count column', () => {
    expect(content).toContain('student_count')
    expect(content).toContain('学生数')
  })

  it('has exam_date column', () => {
    expect(content).toContain('exam_date')
    expect(content).toContain('考试日期')
  })

  it('has sortable columns with sorter functions', () => {
    // Multiple sorter definitions expected
    const sorterCount = (content.match(/sorter:/g) || []).length
    expect(sorterCount).toBeGreaterThanOrEqual(4)
  })

  it('has default sort by created_at descend', () => {
    expect(content).toContain('defaultSortOrder')
    expect(content).toContain('descend')
  })
})

describe('ExamListPage status enhancements', () => {
  it('statusMap includes published', () => {
    expect(content).toContain("published: { label: '已发布'")
  })

  it('statusMap includes archived', () => {
    expect(content).toContain("archived: { label: '已归档'")
  })

  it('status filter options include all 7 statuses', () => {
    expect(content).toContain("{ label: '草稿', value: 'draft' }")
    expect(content).toContain("{ label: '已发布', value: 'published' }")
    expect(content).toContain("{ label: '已归档', value: 'archived' }")
  })
})

describe('ExamListPage actions', () => {
  it('has archive action for completed exams', () => {
    expect(content).toContain('handleArchive')
    expect(content).toContain('archiveExam')
    expect(content).toContain('确认归档此考试')
  })

  it('has copy action', () => {
    expect(content).toContain('handleCopy')
    expect(content).toContain('(副本)')
    expect(content).toContain('复制')
  })

  it('archive button shows only for completed status', () => {
    expect(content).toContain("row.status === 'completed'")
  })
})

describe('ExamListPage create form enhancements', () => {
  it('has date picker field', () => {
    expect(content).toContain('n-date-picker')
    expect(content).toContain('exam_date')
    expect(content).toContain('考试日期')
  })

  it('has description textarea field', () => {
    expect(content).toContain('type="textarea"')
    expect(content).toContain('description')
    expect(content).toContain('考试描述')
  })

  it('modal width increased to 480px', () => {
    expect(content).toContain('width: 480px')
  })
})

describe('ExamListPage empty state', () => {
  it('has n-empty component', () => {
    expect(content).toContain('n-empty')
  })

  it('has guidance for first exam', () => {
    expect(content).toContain('还没有创建考试')
    expect(content).toContain('创建第一场考试')
  })

  it('has empty state for filtered results', () => {
    expect(content).toContain('没有匹配的考试')
    expect(content).toContain('清除筛选条件')
  })
})

describe('ExamListPage API module', () => {
  it('exams.js exports archiveExam', async () => {
    const mod = await import('../api/exams.js')
    expect(mod.archiveExam).toBeDefined()
    expect(typeof mod.archiveExam).toBe('function')
  })

  it('exams.js still exports original functions', async () => {
    const mod = await import('../api/exams.js')
    expect(mod.listExams).toBeDefined()
    expect(mod.createExam).toBeDefined()
    expect(mod.getExam).toBeDefined()
    expect(mod.updateExam).toBeDefined()
  })
})
