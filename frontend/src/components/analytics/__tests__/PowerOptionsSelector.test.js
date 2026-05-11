import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// --- Mock data ---

const MOCK_TREE = {
  grades: [
    {
      id: 'g1', name: '八年级',
      classes: [
        { id: 'all', name: '全部班级' },
        {
          id: 'c1', name: '八年级1班',
          subjects: [
            {
              code: 'math', name: '数学',
              exams: [
                { id: 'e1', name: '期中考试', exam_date: '2026-04-20', student_count: 45 },
                { id: 'e2', name: '月考', exam_date: '2026-03-10', student_count: 44 },
              ],
            },
            {
              code: 'chinese', name: '语文',
              exams: [
                { id: 'e3', name: '期中考试', exam_date: '2026-04-20', student_count: 45 },
              ],
            },
          ],
        },
        {
          id: 'c2', name: '八年级2班',
          subjects: [
            {
              code: 'math', name: '数学',
              exams: [
                { id: 'e1', name: '期中考试', exam_date: '2026-04-20', student_count: 43 },
              ],
            },
          ],
        },
      ],
    },
    {
      id: 'g2', name: '九年级',
      classes: [
        { id: 'all', name: '全部班级' },
        {
          id: 'c3', name: '九年级1班',
          subjects: [
            {
              code: 'english', name: '英语',
              exams: [
                { id: 'e4', name: '期末考试', exam_date: '2026-06-30', student_count: 40 },
              ],
            },
          ],
        },
      ],
    },
  ],
}

const MOCK_EMPTY = { grades: [] }

// --- Mocks ---

let mockResolveData = MOCK_TREE

vi.mock('../../../api/analytics', () => ({
  getPowerOptions: vi.fn(() => Promise.resolve({ data: mockResolveData })),
}))

// Stubs for Naive UI components
const stubs = {
  'n-spin': { template: '<div class="n-spin" :data-show="show"><slot /></div>', props: ['show'] },
  'n-space': { template: '<div class="n-space"><slot /></div>' },
  'n-select': {
    template: '<select :data-value="value" :data-placeholder="placeholder"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
    props: ['value', 'options', 'placeholder'],
    emits: ['update:value'],
  },
}

async function createWrapper() {
  const comp = (await import('../PowerOptionsSelector.vue')).default
  const wrapper = mount(comp, { global: { stubs } })
  await flushPromises()
  return wrapper
}

describe('PowerOptionsSelector', () => {
  beforeEach(() => {
    mockResolveData = MOCK_TREE
    vi.clearAllMocks()
  })

  it('renders with normal data and auto-selects first grade', async () => {
    const wrapper = await createWrapper()

    const vm = wrapper.vm
    expect(vm.selectedGradeId).toBe('g1')
    expect(vm.selectedClassId).toBe('all')
    expect(vm.gradeOptions.length).toBe(2)
  })

  it('renders empty state when API returns no grades', async () => {
    mockResolveData = MOCK_EMPTY
    const wrapper = await createWrapper()

    const vm = wrapper.vm
    expect(vm.selectedGradeId).toBeNull()
    expect(vm.gradeOptions.length).toBe(0)
  })

  it('cascade: class list only contains classes from selected grade', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    // Initially g1 selected — classes are g1's classes
    const g1ClassIds = vm.classOptions.map(o => o.value)
    expect(g1ClassIds).toContain('all')
    expect(g1ClassIds).toContain('c1')
    expect(g1ClassIds).toContain('c2')
    expect(g1ClassIds).not.toContain('c3') // c3 belongs to g2

    // Switch to g2
    vm.selectedGradeId = 'g2'
    vm.onGradeChange()
    await flushPromises()

    const g2ClassIds = vm.classOptions.map(o => o.value)
    expect(g2ClassIds).toContain('all')
    expect(g2ClassIds).toContain('c3')
    expect(g2ClassIds).not.toContain('c1')
  })

  it('emits scope="grade" when classId is "all"', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    // Auto-cascade selects "all" as first class
    expect(vm.selectedClassId).toBe('all')

    // Check emitted event
    const changes = wrapper.emitted('change')
    expect(changes.length).toBeGreaterThan(0)
    const lastEvent = changes[changes.length - 1][0]
    expect(lastEvent.scope).toBe('grade')
    expect(lastEvent.classId).toBeNull()
    expect(lastEvent.gradeId).toBe('g1')
  })

  it('emits scope="class" when a specific class is selected', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    // Select a specific class
    vm.selectedClassId = 'c1'
    vm.onClassChange()
    await flushPromises()

    const changes = wrapper.emitted('change')
    const lastEvent = changes[changes.length - 1][0]
    expect(lastEvent.scope).toBe('class')
    expect(lastEvent.classId).toBe('c1')
  })

  it('exam options are sorted by date descending (most recent first)', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    // Select c1 which has math with two exams
    vm.selectedClassId = 'c1'
    vm.onClassChange()
    await flushPromises()

    // First subject should be math, exams sorted desc
    expect(vm.selectedSubjectCode).toBe('math')
    expect(vm.examOptions[0].value).toBe('e1') // 2026-04-20
    expect(vm.examOptions[1].value).toBe('e2') // 2026-03-10
    // Auto-selects most recent
    expect(vm.selectedExamId).toBe('e1')
  })

  it('merges subjects across classes when "all" is selected', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    // "all" is auto-selected; both c1 and c2 have math, c1 also has chinese
    const subjectCodes = vm.subjectOptions.map(o => o.value)
    expect(subjectCodes).toContain('math')
    expect(subjectCodes).toContain('chinese')
    // No duplicates
    const unique = new Set(subjectCodes)
    expect(unique.size).toBe(subjectCodes.length)
  })
})
