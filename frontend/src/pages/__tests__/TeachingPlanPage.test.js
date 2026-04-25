import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import TeachingPlanPage from '../TeachingPlanPage.vue'

const mockListPlans = vi.fn().mockResolvedValue({ data: [] })
const mockCreatePlan = vi.fn().mockResolvedValue({ data: { id: '1' } })
const mockGetPlan = vi.fn().mockResolvedValue({ data: { id: '1', weeks_json: [] } })
const mockUpdatePlan = vi.fn().mockResolvedValue({ data: {} })
const mockDeletePlan = vi.fn().mockResolvedValue({})
const mockListSemesters = vi.fn().mockResolvedValue({ data: [] })

vi.mock('../../api/academic', () => ({
  createTeachingPlan: (...args) => mockCreatePlan(...args),
  listTeachingPlans: (...args) => mockListPlans(...args),
  getTeachingPlan: (...args) => mockGetPlan(...args),
  updateTeachingPlan: (...args) => mockUpdatePlan(...args),
  deleteTeachingPlan: (...args) => mockDeletePlan(...args),
  listSemesters: (...args) => mockListSemesters(...args),
}))

vi.mock('../../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
}))

const mockWarning = vi.fn()
const mockError = vi.fn()
const mockSuccess = vi.fn()
vi.mock('naive-ui', () => ({
  useMessage: () => ({ warning: mockWarning, error: mockError, success: mockSuccess }),
  NButton: { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
  NTag: { template: '<span><slot /></span>' },
  NInput: { template: '<input />', props: ['value'] },
  NSpace: { template: '<div><slot /></div>' },
}))

function createWrapper() {
  return mount(TeachingPlanPage, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'n-card': { template: '<div><slot /></div>' },
        'n-space': { template: '<div><slot /></div>' },
        'n-select': { template: '<div />', props: ['modelValue', 'options', 'placeholder'], emits: ['update:modelValue'] },
        'n-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'n-spin': { template: '<div><slot /></div>' },
        'n-data-table': { template: '<div />', props: ['columns', 'data'] },
        'n-modal': { template: '<div v-if="show"><slot /></div>', props: ['show'] },
        'n-drawer': { template: '<div v-if="show"><slot /></div>', props: ['show'] },
        'n-drawer-content': { template: '<div><slot /><slot name="footer" /></div>' },
        'n-form': { template: '<div><slot /></div>' },
        'n-form-item': { template: '<div><slot /></div>' },
        'n-input': { template: '<input />', props: ['value'] },
        'n-tag': { template: '<span><slot /></span>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TeachingPlanPage', () => {
  it('renders page title', async () => {
    const wrapper = createWrapper()
    await flushPromises()
    expect(wrapper.text()).toContain('教学计划')
  })

  it('calls listTeachingPlans on mount', async () => {
    createWrapper()
    await flushPromises()
    expect(mockListPlans).toHaveBeenCalled()
  })

  it('calls listSemesters on mount for filter options', async () => {
    createWrapper()
    await flushPromises()
    expect(mockListSemesters).toHaveBeenCalled()
  })

  it('renders create button', async () => {
    const wrapper = createWrapper()
    await flushPromises()
    expect(wrapper.text()).toContain('新建计划')
  })
})
