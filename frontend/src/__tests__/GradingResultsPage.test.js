/**
 * GradingResultsPage 增强测试
 *
 * 验证：
 *   1. 组件可正常导入（无语法/import 错误）
 *   2. 挂载后展示统计摘要卡片
 *   3. 分数分布和置信度分布 computed 正确聚合
 *   4. 筛选和排序逻辑正确
 *   5. 详情弹窗中显示题目序号（而非 UUID）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockResults = [
  { question_id: 'aaaaaaaa-1111-2222-3333-444444444444', question_name: '第1题', question_index: 0, student_id: 's1', score: 8, max_score: 10, confidence: 0.92, review_status: 'approved', feedback: '回答完整' },
  { question_id: 'bbbbbbbb-1111-2222-3333-444444444444', question_name: '第2题', question_index: 1, student_id: 's2', score: 3, max_score: 10, confidence: 0.45, review_status: 'pending', feedback: null },
  { question_id: 'cccccccc-1111-2222-3333-444444444444', question_name: null, question_index: 2, student_id: 's3', score: 6, max_score: 10, confidence: 0.65, review_status: 'pending', feedback: '部分正确' },
  { question_id: 'dddddddd-1111-2222-3333-444444444444', question_name: null, question_index: null, student_id: 's4', score: 10, max_score: 10, confidence: 0.88, review_status: 'overridden', feedback: null },
]

const mockTask = { id: 'task-1', status: 'completed', completed: 3, total: 4, exam_id: 'e1', subject_id: 'sub1' }

vi.mock('../api/grading', () => ({
  getTask: vi.fn().mockResolvedValue({ data: mockTask }),
  listResults: vi.fn().mockResolvedValue({ data: mockResults }),
}))

vi.mock('../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="vchart-stub" />', props: ['option'] },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'task-1' } }),
}))

async function createWrapper() {
  return mount((await import('../pages/GradingResultsPage.vue')).default, {
    global: {
      stubs: {
        'n-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'n-tag': { template: '<span class="n-tag"><slot /></span>' },
        'n-card': { template: '<div class="n-card"><slot /><slot name="header" /></div>' },
        'n-space': { template: '<div class="n-space"><slot /></div>' },
        'n-select': { template: '<div />', props: ['modelValue', 'options', 'placeholder', 'clearable'], emits: ['update:modelValue'] },
        'n-spin': { template: '<div><slot /></div>', props: ['show'] },
        'n-data-table': { template: '<div class="n-data-table" />', props: ['columns', 'data', 'rowProps'] },
        'n-empty': { template: '<div />' },
        'n-modal': { template: '<div v-if="show"><slot /></div>', props: ['show'] },
        'n-descriptions': { template: '<div><slot /></div>' },
        'n-descriptions-item': { template: '<div class="desc-item"><slot /></div>', props: ['label'] },
        'n-progress': { template: '<div class="n-progress" />', props: ['percentage', 'showIndicator', 'color', 'railColor', 'type'] },
        'n-blockquote': { template: '<blockquote><slot /></blockquote>' },
      },
    },
  })
}

describe('GradingResultsPage smoke', () => {
  it('can be imported without errors', async () => {
    const mod = await import('../pages/GradingResultsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('GradingResultsPage computed aggregations', () => {
  it('computes correct statistics from mock results', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    // Check that statistic cards are rendered (4 cards)
    const stats = wrapper.findAll('.stat-card')
    expect(stats.length).toBe(4)

    const vm = wrapper.vm
    // avgScore: (8+3+6+10)/4 = 6.75 -> "6.8"
    expect(vm.avgScore).toBe('6.8')
    // avgConfidence: ((0.92+0.45+0.65+0.88)/4)*100 = 72.5 -> "73"
    expect(vm.avgConfidence).toBe('73')
    // pendingReviewCount: 2 (s2 and s3)
    expect(vm.pendingReviewCount).toBe(2)
    // gradedCount: 4 (total results)
    expect(vm.gradedCount).toBe(4)
    // progressPercent: 3/4 = 75
    expect(vm.progressPercent).toBe(75)
  })
})

describe('GradingResultsPage question label', () => {
  it('displays question_name when available instead of UUID', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    // The data-table stub doesn't render rows, but we can verify the columns
    // include our questionLabel function via the component instance
    const vm = wrapper.vm

    // Test questionLabel with different data shapes
    expect(vm.questionLabel({ question_name: '第1题', question_id: 'some-uuid' }))
      .toBe('第1题')

    expect(vm.questionLabel({ question_index: 2, question_id: 'some-uuid' }))
      .toBe('第 3 题')

    expect(vm.questionLabel({ question_id: 'aaaaaaaa-1111-2222' }))
      .toBe('aaaaaaaa...')

    expect(vm.questionLabel({ question_id: 'short' }))
      .toBe('short')
  })
})

describe('GradingResultsPage score helpers', () => {
  it('scorePercent computes correctly', async () => {
    const wrapper = await createWrapper()
    await flushPromises()
    const vm = wrapper.vm

    expect(vm.scorePercent({ score: 8, max_score: 10 })).toBe(80)
    expect(vm.scorePercent({ score: 0, max_score: 10 })).toBe(0)
    expect(vm.scorePercent({ score: 5, max_score: 0 })).toBe(0) // edge: zero max
  })

  it('scoreColor returns correct color based on percentage', async () => {
    const wrapper = await createWrapper()
    await flushPromises()
    const vm = wrapper.vm

    expect(vm.scoreColor({ score: 9, max_score: 10 })).toBe('#22C55E') // >=80%
    expect(vm.scoreColor({ score: 7, max_score: 10 })).toBe('#ED9A51') // 60-80%
    expect(vm.scoreColor({ score: 3, max_score: 10 })).toBe('#dc2626') // <60%
  })

  it('confidenceType returns correct tag type', async () => {
    const wrapper = await createWrapper()
    await flushPromises()
    const vm = wrapper.vm

    expect(vm.confidenceType(0.92)).toBe('success')
    expect(vm.confidenceType(0.65)).toBe('warning')
    expect(vm.confidenceType(0.3)).toBe('error')
  })
})

describe('GradingResultsPage filtering', () => {
  it('filteredResults filters by review_status', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    // Default: all
    expect(wrapper.vm.filteredResults.length).toBe(4)

    // Set filter to pending
    wrapper.vm.filter = 'pending'
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.filteredResults.length).toBe(2)
    expect(wrapper.vm.filteredResults.every((r) => r.review_status === 'pending')).toBe(true)
  })
})

describe('GradingResultsPage sorting', () => {
  it('sortedResults sorts by confidence ascending', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    wrapper.vm.sortBy = 'confidence_asc'
    await wrapper.vm.$nextTick()

    const sorted = wrapper.vm.sortedResults
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i].confidence).toBeGreaterThanOrEqual(sorted[i - 1].confidence)
    }
  })

  it('sortedResults sorts by score descending', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    wrapper.vm.sortBy = 'score_desc'
    await wrapper.vm.$nextTick()

    const sorted = wrapper.vm.sortedResults
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i].score).toBeLessThanOrEqual(sorted[i - 1].score)
    }
  })
})

describe('GradingResultsPage chart options', () => {
  it('scoreDistOption has 5 buckets', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    const opt = wrapper.vm.scoreDistOption
    expect(opt.xAxis.data).toEqual(['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'])
    expect(opt.series[0].data.length).toBe(5)
    // Sum of all buckets should equal total results
    const sum = opt.series[0].data.reduce((a, b) => a + b, 0)
    expect(sum).toBe(4)
  })

  it('confidenceDistOption partitions into high/mid/low', async () => {
    const wrapper = await createWrapper()
    await flushPromises()

    const opt = wrapper.vm.confidenceDistOption
    const data = opt.series[0].data
    // Should have entries for high, mid, and low (filtering zero values)
    const total = data.reduce((s, d) => s + d.value, 0)
    expect(total).toBe(4)
  })
})
