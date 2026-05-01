/**
 * MarkingProgressPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (toolbar, overall-card, subject-cards, table)
 *  3. API calls (getProgress, exportCsv, client.get /exams)
 *  4. State/data processing (remainingCount, subjectPercentage, questionColorBand, columns, autoRefresh)
 *  5. Error handling (try-catch in loadExams, loadProgress, handleExport)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../MarkingProgressPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('MarkingProgressPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../MarkingProgressPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('MarkingProgressPage template sections', () => {
  it('contains page header with back button', () => {
    expect(content).toContain("$router.push('/marking')")
    expect(content).toContain('← 返回阅卷')
    expect(content).toContain('阅卷进度')
  })

  it('contains toolbar with exam selector and export button', () => {
    expect(content).toContain('class="toolbar"')
    expect(content).toContain('v-model:value="selectedExamId"')
    expect(content).toContain('@update:value="loadProgress"')
    expect(content).toContain('导出成绩 CSV')
  })

  it('contains manual refresh button with spinning icon', () => {
    expect(content).toContain('@click="manualRefresh"')
    expect(content).toContain('RefreshCw')
    expect(content).toContain("{ 'spin-icon': refreshing }")
    expect(content).toContain('刷新')
  })

  it('contains auto-refresh toggle', () => {
    expect(content).toContain('class="auto-refresh-group"')
    expect(content).toContain('v-model:value="autoRefresh"')
    expect(content).toContain('自动刷新')
    expect(content).toContain('lastUpdateTime')
  })

  it('contains overall progress card', () => {
    expect(content).toContain('class="overall-card"')
    expect(content).toContain('progress.overall.graded')
    expect(content).toContain('progress.overall.total')
    expect(content).toContain('progress.overall.percentage')
    expect(content).toContain('remainingCount')
  })

  it('contains subject cards with progress circles', () => {
    expect(content).toContain('class="subject-card"')
    expect(content).toContain('v-for="subj in progress?.subjects || []"')
    expect(content).toContain('class="subject-header"')
    expect(content).toContain('subjectPercentage(subj)')
  })

  it('contains data table for questions', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain(':data="subj.questions"')
    expect(content).toContain(':columns="columns"')
  })
})

describe('MarkingProgressPage API calls', () => {
  it('imports getProgress and exportCsv from marking API', () => {
    expect(content).toContain("import { getProgress, exportCsv } from '../api/marking'")
  })

  it('imports client for direct exam fetch', () => {
    expect(content).toContain("import client from '../api/client'")
  })

  it('fetches exam list on mount', () => {
    expect(content).toContain("client.get('/exams')")
    expect(content).toContain('onMounted(loadExams)')
  })

  it('auto-selects first exam', () => {
    expect(content).toContain('selectedExamId.value = data[0].id')
    expect(content).toContain('await loadProgress(data[0].id)')
  })

  it('calls getProgress to load progress data', () => {
    expect(content).toContain('await getProgress(examId)')
    expect(content).toContain('progress.value = data')
  })

  it('calls exportCsv for CSV download', () => {
    expect(content).toContain('await exportCsv(selectedExamId.value)')
  })
})

describe('MarkingProgressPage remainingCount computed', () => {
  it('computes remaining as total minus graded', () => {
    expect(content).toContain('progress.value.overall.total - progress.value.overall.graded')
  })

  it('returns 0 when no progress data', () => {
    expect(content).toContain('if (!progress.value) return 0')
  })
})

describe('MarkingProgressPage subjectPercentage function', () => {
  it('calculates percentage from graded_count and total_answers', () => {
    expect(content).toContain('graded += q.graded_count')
    expect(content).toContain('total += q.total_answers')
    expect(content).toContain('Math.round(graded / total * 100)')
  })

  it('returns 0 for empty questions', () => {
    expect(content).toContain('if (!subj.questions || subj.questions.length === 0) return 0')
  })

  it('guards against division by zero', () => {
    expect(content).toContain('total > 0 ?')
  })
})

describe('MarkingProgressPage questionColorBand function', () => {
  it('returns green for 100% complete', () => {
    expect(content).toContain("if (pct >= 100) return '#2a9d8f'")
  })

  it('returns orange for 50%+ progress', () => {
    expect(content).toContain("if (pct >= 50) return '#f4a261'")
  })

  it('returns red for below 50%', () => {
    expect(content).toContain("return '#e76f51'")
  })

  it('applies color band via row border-left style', () => {
    expect(content).toContain('style: `border-left: 4px solid ${questionColorBand(row)};`')
  })
})

describe('MarkingProgressPage table columns', () => {
  it('defines 5 columns with correct keys', () => {
    expect(content).toContain("title: '题号', key: 'name', width: 120")
    expect(content).toContain("title: '满分', key: 'max_score', width: 80")
    expect(content).toContain("title: '已批', key: 'graded_count', width: 80")
    expect(content).toContain("title: '总数', key: 'total_answers', width: 80")
    expect(content).toContain("title: '进度'")
    expect(content).toContain("key: 'progress'")
  })

  it('renders progress column as NProgress line', () => {
    expect(content).toContain("type: 'line'")
    expect(content).toContain("indicatorPlacement: 'inside'")
  })
})

describe('MarkingProgressPage auto-refresh polling', () => {
  it('polls every 30 seconds', () => {
    expect(content).toContain('}, 30000)')
  })

  it('starts polling when autoRefresh is enabled', () => {
    expect(content).toContain('watch(autoRefresh, (val) => {')
    expect(content).toContain('startPolling()')
  })

  it('stops polling when autoRefresh is disabled', () => {
    const watchBlock = content.slice(
      content.indexOf('watch(autoRefresh'),
      content.indexOf('async function handleExport')
    )
    expect(watchBlock).toContain('stopPolling()')
  })

  it('stops polling on unmount', () => {
    expect(content).toContain('onUnmounted(() => {')
    expect(content).toContain('stopPolling()')
  })

  it('updates timestamp on data refresh', () => {
    expect(content).toContain('updateTimestamp()')
    expect(content).toContain("lastUpdateTime.value = `上次更新: ${hh}:${mm}:${ss}`")
  })
})

describe('MarkingProgressPage CSV export', () => {
  it('creates blob URL for download', () => {
    expect(content).toContain("URL.createObjectURL(new Blob([data], { type: 'text/csv' }))")
  })

  it('creates download link with scores.csv filename', () => {
    expect(content).toContain("a.download = 'scores.csv'")
  })

  it('revokes blob URL after download', () => {
    expect(content).toContain('URL.revokeObjectURL(url)')
  })

  it('shows success message after export', () => {
    expect(content).toContain("message.success('导出成功')")
  })

  it('guards against no exam selected', () => {
    expect(content).toContain('if (!selectedExamId.value) return')
  })
})

describe('MarkingProgressPage error handling', () => {
  it('wraps loadExams in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function loadProgress')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps loadProgress in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadProgress'),
      content.indexOf('async function manualRefresh')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps manualRefresh in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function manualRefresh'),
      content.indexOf('function startPolling')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps handleExport in try-catch with error message', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleExport'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(fnBlock).toContain('} catch {')
    expect(fnBlock).toContain("message.error('导出失败')")
  })

  it('wraps polling callback in try-catch', () => {
    const pollBlock = content.slice(
      content.indexOf('function startPolling'),
      content.indexOf('function stopPolling')
    )
    expect(pollBlock).toContain('try {')
    expect(pollBlock).toContain('} catch')
  })
})

describe('MarkingProgressPage subject card color logic', () => {
  it('uses green for 100% complete subjects', () => {
    expect(content).toContain("subjectPercentage(subj) >= 100 ? '#2a9d8f' : '#f4a261'")
  })
})

describe('MarkingProgressPage spin animation', () => {
  it('defines spin keyframe animation', () => {
    expect(content).toContain('@keyframes spin')
    expect(content).toContain('from { transform: rotate(0deg); }')
    expect(content).toContain('to { transform: rotate(360deg); }')
  })

  it('applies spin-icon class binding to refresh icon', () => {
    expect(content).toContain("'spin-icon': refreshing")
  })
})
