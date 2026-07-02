import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../MarkingProgressTab.vue')
const content = readFileSync(filePath, 'utf-8')

const mocks = vi.hoisted(() => ({
  getProgress: vi.fn(),
  exportCsv: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageInfo: vi.fn(),
}))

vi.mock('../../../api/marking', () => ({
  getProgress: (...args) => mocks.getProgress(...args),
  exportCsv: (...args) => mocks.exportCsv(...args),
}))

vi.mock('naive-ui', () => {
  const passthrough = (name) => ({
    name,
    template: '<div><slot /><slot name="icon" /></div>',
  })

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
      props: ['loading', 'disabled', 'secondary', 'size'],
      emits: ['click'],
      template: '<button :disabled="disabled" :data-loading="loading" @click="$emit(\'click\')"><slot name="icon" /><slot /></button>',
    },
    NCard: passthrough('NCard'),
    NDataTable: passthrough('NDataTable'),
    NEmpty: {
      name: 'NEmpty',
      props: ['description'],
      template: '<div class="n-empty-stub">{{ description }}</div>',
    },
    NIcon: passthrough('NIcon'),
    NProgress: passthrough('NProgress'),
    NSpin: {
      name: 'NSpin',
      props: ['show'],
      template: '<div class="n-spin-stub" :data-show="show"><slot /></div>',
    },
    NSwitch: passthrough('NSwitch'),
    NTag: passthrough('NTag'),
  }
})

function progressPayload(overrides = {}) {
  return {
    overall: {
      graded: 1,
      total: 2,
      percentage: 50,
      ...overrides.overall,
    },
    subjects: overrides.subjects || [],
  }
}

function resetBehaviorMocks() {
  for (const mock of Object.values(mocks)) {
    mock.mockReset()
  }
  mocks.getProgress.mockResolvedValue({ data: progressPayload() })
  mocks.exportCsv.mockResolvedValue({ data: 'csv' })
}

async function mountTab(props = { examId: 'exam-1' }) {
  const mod = await import('../MarkingProgressTab.vue')
  return mount(mod.default, {
    props,
    global: {
      stubs: { RefreshCw: true },
    },
  })
}

describe('MarkingProgressTab load failure behavior', () => {
  beforeEach(() => {
    resetBehaviorMocks()
  })

  it('shows an alert and releases loading when initial progress load rejects', async () => {
    mocks.getProgress.mockRejectedValueOnce(new Error('progress boom'))

    const wrapper = await mountTab()
    await flushPromises()
    await wrapper.vm.$nextTick()

    const alert = wrapper.find('[role="alert"]')
    expect(mocks.getProgress).toHaveBeenCalledWith('exam-1')
    expect(wrapper.vm.loading).toBe(false)
    expect(wrapper.vm.progress).toBe(null)
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('progress boom')
    expect(wrapper.find('.n-empty-stub').exists()).toBe(false)
    expect(mocks.messageError).toHaveBeenCalledWith(expect.stringContaining('progress boom'))
  })

  it('keeps old data visible, shows an alert, and releases refreshing when manual refresh rejects', async () => {
    const existingProgress = progressPayload({
      overall: { graded: 7, total: 10, percentage: 70 },
    })
    mocks.getProgress.mockResolvedValueOnce({ data: existingProgress })
    const wrapper = await mountTab()
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
    expect(wrapper.vm.progress.overall.graded).toBe(7)
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('当前数据未更新')
    expect(alert.text()).toContain('refresh boom')
    expect(mocks.messageError).toHaveBeenCalledWith(expect.stringContaining('当前数据未更新'))
  })
})

describe('MarkingProgressTab source error handling', () => {
  it('does not silently swallow progress load, refresh, or polling failures', () => {
    expect(content).not.toContain('catch {}')

    const loadBlock = content.slice(
      content.indexOf('async function loadProgress'),
      content.indexOf('async function manualRefresh')
    )
    expect(loadBlock).toContain('} catch (err) {')
    expect(loadBlock).toContain('showProgressError(formatProgressError(PROGRESS_LOAD_ERROR, err))')
    expect(loadBlock).toContain('} finally {')
    expect(loadBlock).toContain('loading.value = false')

    const refreshBlock = content.slice(
      content.indexOf('async function manualRefresh'),
      content.indexOf('function startPolling')
    )
    expect(refreshBlock).toContain('} catch (err) {')
    expect(refreshBlock).toContain('showProgressError(formatProgressError(PROGRESS_REFRESH_ERROR, err))')
    expect(refreshBlock).toContain('} finally {')
    expect(refreshBlock).toContain('refreshing.value = false')

    const pollBlock = content.slice(
      content.indexOf('function startPolling'),
      content.indexOf('function stopPolling')
    )
    expect(pollBlock).toContain('} catch (err) {')
    expect(pollBlock).toContain('loadError.value = formatProgressError(PROGRESS_REFRESH_ERROR, err)')
  })
})
