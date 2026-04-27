/**
 * ErrorBookPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains student select, status filter, stats cards, table, detail modal
 *  3. API calls for error book and stats
 *  4. Status map definitions
 *  5. Error handling patterns
 *  6. Detail modal content structure
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ErrorBookPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ErrorBookPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ErrorBookPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ErrorBookPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('错题本')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('查看学生错题记录与掌握情况')
  })

  it('contains student selector with remote search', () => {
    expect(content).toContain('v-model:value="selectedStudentId"')
    expect(content).toContain('filterable')
    expect(content).toContain('remote')
    expect(content).toContain('placeholder="搜索学生姓名或学号..."')
  })

  it('contains status filter radio buttons', () => {
    expect(content).toContain('v-model:value="statusFilter"')
    expect(content).toContain('value="">全部')
    expect(content).toContain('value="unmastered">未掌握')
    expect(content).toContain('value="practicing">练习中')
    expect(content).toContain('value="mastered">已掌握')
  })

  it('contains stats grid cards', () => {
    expect(content).toContain('class="stats-grid"')
    expect(content).toContain('stats.unmastered')
    expect(content).toContain('stats.practicing')
    expect(content).toContain('stats.mastered')
    expect(content).toContain('stats.total')
  })

  it('contains stat card labels', () => {
    expect(content).toContain('class="stat-label">未掌握')
    expect(content).toContain('class="stat-label">练习中')
    expect(content).toContain('class="stat-label">已掌握')
    expect(content).toContain('class="stat-label">总计')
  })

  it('contains data table for error records', () => {
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="errors"')
    expect(content).toContain('pageSize: 20')
  })

  it('contains empty states for no selection and no data', () => {
    expect(content).toContain('description="暂无错题记录"')
    expect(content).toContain('description="请先选择学生"')
  })

  it('contains detail modal', () => {
    expect(content).toContain('v-model:show="detailVisible"')
    expect(content).toContain('title="错题详情"')
  })
})

describe('ErrorBookPage detail modal content', () => {
  it('shows exam name and question ID', () => {
    expect(content).toContain('class="detail-label">考试')
    expect(content).toContain('class="detail-label">题目 ID')
    expect(content).toContain('detailRow.question_id')
  })

  it('shows score as student_score / max_score', () => {
    expect(content).toContain('class="detail-label">得分')
    expect(content).toContain('detailRow.student_score')
    expect(content).toContain('detailRow.max_score')
  })

  it('shows mastery status with tag', () => {
    expect(content).toContain('class="detail-label">掌握状态')
    expect(content).toContain('STATUS_MAP[detailRow.mastery_status]')
  })

  it('shows error type, retry count, and starred status', () => {
    expect(content).toContain('class="detail-label">错误类型')
    expect(content).toContain('class="detail-label">重做次数')
    expect(content).toContain('class="detail-label">收藏')
    expect(content).toContain("detailRow.is_starred ? '★ 已收藏' : '未收藏'")
  })

  it('shows AI feedback section when available', () => {
    expect(content).toContain('v-if="detailRow.ai_feedback"')
    expect(content).toContain('AI 反馈')
    expect(content).toContain('class="detail-feedback"')
  })

  it('shows knowledge point IDs when available', () => {
    expect(content).toContain("v-if=\"detailRow.knowledge_point_ids?.length\"")
    expect(content).toContain('关联知识点')
  })
})

describe('ErrorBookPage status map', () => {
  it('defines STATUS_MAP with correct labels and types', () => {
    expect(content).toContain("unmastered: { label: '未掌握', type: 'error' }")
    expect(content).toContain("practicing: { label: '练习中', type: 'warning' }")
    expect(content).toContain("mastered: { label: '已掌握', type: 'success' }")
  })
})

describe('ErrorBookPage API calls', () => {
  it('imports error book and stats APIs', () => {
    expect(content).toContain("import { getStudentErrorBook, getErrorBookStats } from '../api/bank.js'")
  })

  it('imports student listing API', () => {
    expect(content).toContain("import { listStudents } from '../api/students.js'")
  })

  it('imports client for exam name resolution', () => {
    expect(content).toContain("import client from '../api/client.js'")
  })

  it('calls getStudentErrorBook and getErrorBookStats in parallel', () => {
    expect(content).toContain('await Promise.all([')
    expect(content).toContain('getStudentErrorBook(selectedStudentId.value, params)')
    expect(content).toContain('getErrorBookStats(selectedStudentId.value)')
  })

  it('resolves exam names from /exams endpoint', () => {
    expect(content).toContain("client.get('/exams', { params: { limit: 50 } })")
  })

  it('searches students on mount with empty query', () => {
    expect(content).toContain("await searchStudents('')")
  })

  it('supports route query parameter for pre-selected student', () => {
    expect(content).toContain('route.query.studentId')
    expect(content).toContain('selectedStudentId.value = qStudent')
  })
})

describe('ErrorBookPage error handling', () => {
  it('wraps loadErrorBook in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadErrorBook'),
      content.indexOf('onMounted(')
    )
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('errors.value = []')
    expect(fnBlock).toContain('stats.value = null')
  })

  it('wraps searchStudents in try-catch with empty fallback', () => {
    const fnBlock = content.slice(
      content.indexOf('async function searchStudents'),
      content.indexOf('function onStudentSearch')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('studentOptions.value = []')
  })

  it('silently handles exam name resolution failure', () => {
    expect(content).toContain('/* exam names unavailable */')
  })
})

describe('ErrorBookPage table columns', () => {
  it('defines columns for exam, score, error type, status, AI feedback, retry, starred', () => {
    expect(content).toContain("title: '考试'")
    expect(content).toContain("title: '得分'")
    expect(content).toContain("title: '错误类型'")
    expect(content).toContain("title: '状态'")
    expect(content).toContain("title: 'AI 反馈'")
    expect(content).toContain("title: '重做'")
    expect(content).toContain("title: '收藏'")
  })

  it('renders score with progress bar', () => {
    expect(content).toContain('NProgress')
    expect(content).toContain('Math.round(row.student_score / row.max_score * 100)')
  })
})
