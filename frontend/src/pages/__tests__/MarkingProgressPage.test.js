/**
 * MarkingProgressPage source-text and behavior tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (toolbar, overall-card, subject-cards, table)
 *  3. API calls (getProgress, exportCsv, client.get /exams)
 *  4. State/data processing (remainingCount, subjectPercentage, questionColorBand, columns, autoRefresh)
 *  5. Error handling (visible load errors, finally cleanup, export message)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../MarkingProgressPage.vue')
const content = readFileSync(filePath, 'utf-8')

const mocks = vi.hoisted(() => ({
  getProgress: vi.fn(),
  exportCsv: vi.fn(),
  clientGet: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageInfo: vi.fn(),
}))

vi.mock('../../api/marking', () => ({
  getProgress: (...args) => mocks.getProgress(...args),
  exportCsv: (...args) => mocks.exportCsv(...args),
}))

vi.mock('../../api/client', () => ({
  default: { get: (...args) => mocks.clientGet(...args) },
}))

vi.mock('naive-ui', () => {
  const passthrough = (name) => ({ name, template: '<div><slot /><slot name="icon" /></div>' })
  return {
    useMessage: () => ({
      error: mocks.messageError,
      success: mocks.messageSuccess,
      warning: mocks.messageWarning,
      info: mocks.messageInfo,
    }),
    NAlert: {
      name: 'NAlert',
      props: ['type', 'bordered', 'closable'],
      emits: ['close'],
      template: '<div role="alert" class="n-alert-stub"><slot /></div>',
    },
    NButton: {
      name: 'NButton',
      props: ['loading', 'disabled', 'secondary', 'text'],
      emits: ['click'],
      template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot name="icon" /><slot /></button>',
    },
    NCard: passthrough('NCard'),
    NDataTable: passthrough('NDataTable'),
    NIcon: passthrough('NIcon'),
    NProgress: passthrough('NProgress'),
    NSelect: passthrough('NSelect'),
    NSpin: passthrough('NSpin'),
    NSwitch: passthrough('NSwitch'),
  }
})

function progressPayload() {
  return {
    overall: { graded: 1, total: 2, percentage: 50 },
    subjects: [],
  }
}

function resetBehaviorMocks() {
  for (const mock of Object.values(mocks)) {
    mock.mockReset()
  }
  mocks.clientGet.mockResolvedValue({ data: [{ id: 'exam-1', name: 'Midterm' }] })
  mocks.getProgress.mockResolvedValue({ data: progressPayload() })
  mocks.exportCsv.mockResolvedValue({ data: 'csv' })
}

async function createBehaviorWrapper() {
  const mod = await import('../MarkingProgressPage.vue')
  return mount(mod.default, {
    global: {
      mocks: { $router: { push: vi.fn() } },
      stubs: { ArrowLeft: true, RefreshCw: true },
    },
  })
}

describe('MarkingProgressPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../MarkingProgressPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 60000)
})

describe('MarkingProgressPage load failure behavior', () => {
  beforeEach(() => {
    resetBehaviorMocks()
  })

  it('shows an alert and releases loading when progress load rejects', async () => {
    mocks.getProgress.mockRejectedValueOnce(new Error('progress boom'))

    const wrapper = await createBehaviorWrapper()
    await flushPromises()
    await wrapper.vm.$nextTick()

    const alert = wrapper.find('[role="alert"]')
    expect(mocks.clientGet).toHaveBeenCalledWith('/exams')
    expect(mocks.getProgress).toHaveBeenCalledWith('exam-1')
    expect(wrapper.vm.loading).toBe(false)
    expect(wrapper.vm.progress).toBe(null)
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('progress boom')
    expect(mocks.messageError).toHaveBeenCalledWith(expect.stringContaining('progress boom'))
  })

  it('shows an alert and releases refreshing when manual refresh rejects', async () => {
    const wrapper = await createBehaviorWrapper()
    await flushPromises()
    await wrapper.vm.$nextTick()
    mocks.getProgress.mockClear()
    mocks.messageError.mockClear()
    mocks.getProgress.mockRejectedValueOnce({
      response: { data: { detail: 'refresh boom' } },
    })

    await wrapper.vm.manualRefresh()
    await flushPromises()
    await wrapper.vm.$nextTick()

    const alert = wrapper.find('[role="alert"]')
    expect(mocks.getProgress).toHaveBeenCalledWith('exam-1')
    expect(wrapper.vm.refreshing).toBe(false)
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('refresh boom')
    expect(mocks.messageError).toHaveBeenCalledWith(expect.stringContaining('refresh boom'))
  })
})

describe('MarkingProgressPage template sections', () => {
  it('contains page header with back button', () => {
    expect(content).toContain("$router.push('/marking')")
    expect(content).toContain('返回阅卷')
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

  it('contains page-level visible load error alert', () => {
    expect(content).toContain('<n-alert')
    expect(content).toContain('v-if="loadError"')
    expect(content).toContain('type="error"')
    expect(content).toContain('role="alert"')
    expect(content).toContain('{{ loadError }}')
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
    expect(content).toContain('selectedExamId.value = exams[0].id')
    expect(content).toContain('await loadProgress(exams[0].id)')
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
  it('defines columns with correct keys', () => {
    expect(content).toContain("title: '题号', key: 'name', width: 100")
    expect(content).toContain("title: '满分', key: 'max_score', width: 60")
    expect(content).toContain("title: '总数', key: 'total_answers', width: 60")
    expect(content).toContain("title: 'AI 进度'")
    expect(content).toContain("title: '人工进度'")
  })

  it('renders progress columns with render functions', () => {
    expect(content).toContain("key: 'ai_progress'")
    expect(content).toContain("key: 'manual_progress'")
    expect(content).toContain("render(row)")
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
  it('defines explicit load error messages', () => {
    expect(content).toContain("const EXAMS_LOAD_ERROR = '考试列表加载失败，请稍后重试'")
    expect(content).toContain("const PROGRESS_LOAD_ERROR = '阅卷进度加载失败，请稍后重试'")
    expect(content).toContain("const PROGRESS_REFRESH_ERROR = '阅卷进度刷新失败，当前数据未更新'")
    expect(content).toContain('const loadError = ref')
  })

  it('formats and displays load errors through page state and toast', () => {
    expect(content).toContain('function formatLoadError(fallback, err)')
    expect(content).toContain('err?.response?.data?.detail || err?.message')
    expect(content).toContain('function showLoadError(text)')
    expect(content).toContain('loadError.value = text')
    expect(content).toContain('message.error(text)')
    expect(content).toContain('function clearLoadError()')
    expect(content).toContain("loadError.value = ''")
  })

  it('makes loadExams failure visible', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function loadProgress')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch (err) {')
    expect(fnBlock).toContain('examOptions.value = []')
    expect(fnBlock).toContain('selectedExamId.value = null')
    expect(fnBlock).toContain('progress.value = null')
    expect(fnBlock).toContain('showLoadError(formatLoadError(EXAMS_LOAD_ERROR, err))')
    expect(fnBlock).not.toContain('catch {}')
  })

  it('makes loadProgress failure visible and clears stale data', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadProgress'),
      content.indexOf('async function manualRefresh')
    )
    expect(fnBlock).toContain('progress.value = null')
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('clearLoadError()')
    expect(fnBlock).toContain('} catch (err) {')
    expect(fnBlock).toContain('showLoadError(formatLoadError(PROGRESS_LOAD_ERROR, err))')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('loading.value = false')
    expect(fnBlock).not.toContain('catch {}')
  })

  it('makes manualRefresh failure visible and always resets refreshing', () => {
    const fnBlock = content.slice(
      content.indexOf('async function manualRefresh'),
      content.indexOf('function startPolling')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('clearLoadError()')
    expect(fnBlock).toContain('} catch (err) {')
    expect(fnBlock).toContain('showLoadError(formatLoadError(PROGRESS_REFRESH_ERROR, err))')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('refreshing.value = false')
    expect(fnBlock).not.toContain('catch {}')
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
    expect(pollBlock).toContain('clearLoadError()')
    expect(pollBlock).toContain('} catch (err) {')
    expect(pollBlock).toContain('loadError.value = formatLoadError(PROGRESS_REFRESH_ERROR, err)')
    expect(pollBlock).not.toContain('catch {}')
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
