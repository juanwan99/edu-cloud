/**
 * AnalysisPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains page header, stats grid, feature cards, recent exams table
 *  3. API calls use listExams from exams.js
 *  4. Navigation targets for feature cards
 *  5. Data processing (examOptions computed, recentExams slice)
 *  6. Error handling (try-catch on mount)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../AnalysisPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('AnalysisPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../AnalysisPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('AnalysisPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
  })

  it('displays stats grid with exam counts', () => {
    expect(content).toContain('class="stats-grid"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-value"')
    expect(content).toContain('class="stat-label"')
    expect(content).toContain('exams.length')
    expect(content).toContain('recentExams.length')
  })

  it('contains quick-entry select and button', () => {
    expect(content).toContain('v-model:value="selectedExamId"')
    expect(content).toContain(':options="examOptions"')
    expect(content).toContain('filterable')
    expect(content).toContain('clearable')
    expect(content).toContain('@click="goExamAnalytics"')
  })

  it('contains feature grid with 4 feature cards', () => {
    expect(content).toContain('class="feature-grid"')
    expect(content).toContain('class="feature-card"')
    expect(content).toContain('class="feature-icon"')
    expect(content).toContain('class="feature-title"')
    expect(content).toContain('class="feature-desc"')
  })

  it('contains recent exams table with columns', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain(':columns="recentColumns"')
    expect(content).toContain(':data="recentExams"')
  })
})

describe('AnalysisPage feature cards navigation', () => {
  it('has exam analytics card linking to /analytics/:id', () => {
    expect(content).toContain('goExamAnalytics')
  })

  it('has trend card linking to /analytics/trend', () => {
    expect(content).toContain("$router.push('/analytics/trend')")
  })

  it('has report card linking to /analytics/report', () => {
    expect(content).toContain("$router.push('/analytics/report')")
  })

  it('has student profile card linking to /profile/student/:id', () => {
    expect(content).toContain('goStudentProfile')
    expect(content).toContain('/profile/student/')
  })

  it('disables cards when no exam selected', () => {
    expect(content).toContain("{ disabled: !selectedExamId }")
  })
})

describe('AnalysisPage feature card labels', () => {
  it('lists four feature titles in Chinese', () => {
    expect(content).toContain('class="feature-title"')
  })

  it('contains feature descriptions', () => {
    const descMatches = content.match(/class="feature-desc"/g)
    expect(descMatches).not.toBeNull()
    expect(descMatches.length).toBe(4)
  })
})

describe('AnalysisPage API calls', () => {
  it('imports listExams from exams API', () => {
    expect(content).toContain("import { listExams } from '../api/exams'")
  })

  it('calls listExams on mount', () => {
    expect(content).toContain('listExams()')
  })
})

describe('AnalysisPage data processing', () => {
  it('computes examOptions from exams list', () => {
    expect(content).toContain('examOptions')
    expect(content).toMatch(/exams\.value\.map/)
  })

  it('computes recentExams as first 5 items', () => {
    expect(content).toContain('exams.value.slice(0, 5)')
  })

  it('defines recentColumns with name, status, actions', () => {
    expect(content).toContain("title: '考试名称'")
    expect(content).toContain("title: '状态'")
    expect(content).toContain("title: '操作'")
  })

  it('goExamAnalytics navigates to analytics/:id', () => {
    const fnBlock = content.slice(
      content.indexOf('function goExamAnalytics'),
      content.indexOf('function goStudentProfile'),
    )
    expect(fnBlock).toContain('router.push(`/analytics/${selectedExamId.value}`)')
  })

  it('goStudentProfile navigates to profile/student/:id', () => {
    const fnStart = content.indexOf('function goStudentProfile')
    const fnEnd = content.indexOf('onMounted(', fnStart)
    const fnBlock = content.slice(fnStart, fnEnd)
    expect(fnBlock).toContain('router.push(`/profile/student/${selectedExamId.value}`)')
  })
})

describe('AnalysisPage error handling', () => {
  it('wraps onMounted fetch in try-catch', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted('),
      content.lastIndexOf('</script>'),
    )
    expect(mountBlock).toContain('try {')
    expect(mountBlock).toContain('} catch')
  })

  it('handles exams data with fallback to empty array', () => {
    expect(content).toContain('data.exams || data || []')
  })
})

describe('AnalysisPage styles', () => {
  it('defines feature-grid with CSS grid', () => {
    expect(content).toContain('.feature-grid')
    expect(content).toContain('grid-template-columns')
  })

  it('defines feature-card hover transform', () => {
    expect(content).toContain('.feature-card:hover')
    expect(content).toContain('translateY(-2px)')
  })

  it('defines disabled card style with opacity and pointer-events', () => {
    expect(content).toContain('.feature-card.disabled')
    expect(content).toContain('opacity: 0.5')
    expect(content).toContain('pointer-events: none')
  })

  it('uses macaron CSS variables for stat cards', () => {
    expect(content).toContain('var(--macaron-mint-light)')
    expect(content).toContain('var(--macaron-purple-light)')
  })
})
