/**
 * ParentOverview.vue — action-oriented dashboard tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Source text contains key design elements (focus card, trend, behavior, updates)
 *  3. API calls use Promise.allSettled for resilience
 *  4. Empty state with ParentEmpty for unbound child
 *  5. Focus items logic (negative behavior + rank drop)
 *  6. Mount-based tests for data loading and card rendering
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentOverview.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentOverview smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentOverview.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentOverview template — focus card', () => {
  it('contains focus card with calm variant', () => {
    expect(content).toContain('class="focus-card"')
    expect(content).toContain("'focus-card--calm': !focusItems.length")
  })

  it('shows actionable count when focus items exist', () => {
    expect(content).toContain('focusItems.length')
  })

  it('shows calm message when nothing needs attention', () => {
    expect(content).toContain('focus-card__header--calm')
  })
})

describe('ParentOverview template — academic trend card', () => {
  it('contains trend card with sparkline and percentile', () => {
    expect(content).toContain('sparklineOption')
    expect(content).toContain('classPercentile')
  })

  it('shows rank change with directional icon', () => {
    expect(content).toContain('rankChangeClass')
    expect(content).toContain('TrendingDown')
    expect(content).toContain('TrendingUp')
  })

  it('shows latest score inline', () => {
    expect(content).toContain('v-if="latestScore"')
    expect(content).toContain('trend-latest__score')
    expect(content).toContain('latestScore.total_score')
  })
})

describe('ParentOverview template — behavior card', () => {
  it('uses positive-first behavior display', () => {
    expect(content).toContain('behaviorSummary.positive_count || 0')
    expect(content).toContain('behaviorSummary.negative_count || 0')
    expect(content).toContain('behavior-tag--good')
    expect(content).toContain('behavior-tag--warn')
  })

  it('shows recent records with positive framing', () => {
    expect(content).toContain('recentRecords.slice(0, 3)')
    expect(content).toContain("r.rule_name || r.note || '")
    expect(content).toContain("r.points >= 0 ? '+' : ''")
  })

  it('shows semester total', () => {
    expect(content).toContain(':value="totalPoints"')
  })
})

describe('ParentOverview template — data source attribution', () => {
  it('shows data source on cards', () => {
    expect(content).toContain('p-card__source')
    expect(content).toContain('dataSource')
  })
})

describe('ParentOverview template — empty state and shared components', () => {
  it('uses ParentEmpty for unbound child', () => {
    expect(content).toContain('v-if="!currentChild"')
    expect(content).toContain("'/parent/bind'")
  })

  it('uses shared PullRefresh wrapper', () => {
    expect(content).toContain('PullRefresh')
    expect(content).toContain(':loading="refreshing"')
    expect(content).toContain('@refresh="loadData"')
  })

  it('uses ParentSkeleton for loading state', () => {
    expect(content).toContain('ParentSkeleton')
    expect(content).toContain('v-if="loading && !hasLoaded"')
  })

  it('receives currentChild via props', () => {
    expect(content).toContain('currentChild: { type: Object, default: null }')
  })
})

describe('ParentOverview script — API and data flow', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain('getChildRecords')
    expect(content).toContain('getChildExams')
    expect(content).toContain('getChildRankings')
    expect(content).toContain('getChildBehaviorSummary')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('uses Promise.allSettled for resilient data fetching', () => {
    expect(content).toContain('Promise.allSettled')
  })

  it('computes focus items from behavior and rank data', () => {
    expect(content).toContain('const focusItems = computed')
    expect(content).toContain('negative_count > 0')
    expect(content).toContain('rankChange.value < -3')
  })

  it('watches currentChild with immediate flag and resets state', () => {
    expect(content).toContain('watch(() => props.currentChild')
    expect(content).toContain('}, { immediate: true })')
    expect(content).toContain('hasLoaded.value = false')
  })

  it('formats relative time', () => {
    expect(content).toContain('function formatRelative')
  })
})

describe('ParentOverview style — design tokens', () => {
  it('uses --p-* design tokens for all colors', () => {
    expect(content).toContain('var(--p-card-bg)')
    expect(content).toContain('var(--p-card-radius)')
    expect(content).toContain('var(--p-text-1)')
    expect(content).toContain('var(--p-text-2)')
    expect(content).toContain('var(--p-text-3)')
    expect(content).toContain('var(--p-color-accent)')
    expect(content).toContain('var(--p-color-success)')
    expect(content).toContain('var(--p-color-warning)')
  })
})

// ============================================================
// F-009: Mount-based tests — notification feature
// ============================================================

vi.mock('../../../api/conduct', () => ({
  getChildRecords: vi.fn().mockResolvedValue({ data: { items: [] } }),
  getChildScores: vi.fn().mockResolvedValue({ data: [] }),
  getChildExams: vi.fn().mockResolvedValue({ data: [] }),
  getChildRankings: vi.fn().mockResolvedValue({ data: [] }),
  getChildBehaviorSummary: vi.fn().mockResolvedValue({ data: null }),
}))

import { mount, flushPromises } from '@vue/test-utils'
import {
  getChildRecords, getChildExams, getChildRankings, getChildBehaviorSummary,
} from '../../../api/conduct'

const componentStubs = {
  PullRefresh: { template: '<div class="pull-refresh"><slot /></div>', props: ['loading', 'lastUpdate'] },
  ParentSkeleton: { template: '<div class="skeleton" />', props: ['rows'] },
  ParentEmpty: { template: '<div class="empty"><slot name="action" /></div>', props: ['message'] },
  NumberRoll: { template: '<span class="number-roll">{{ value }}</span>', props: ['value', 'size'] },
  VChart: { template: '<div class="chart" />', props: ['option', 'autoresize'] },
  Zap: { template: '<span class="icon-zap" />', props: ['size'] },
  CircleCheck: { template: '<span class="icon-check" />', props: ['size'] },
  ChevronRight: { template: '<span class="icon-chevron" />', props: ['size'] },
  TrendingUp: { template: '<span class="icon-up" />', props: ['size'] },
  TrendingDown: { template: '<span class="icon-down" />', props: ['size'] },
  'n-button': { template: '<button class="n-button"><slot /></button>' },
  'n-tag': { template: '<span class="n-tag"><slot /></span>', props: ['type', 'size', 'round'] },
}

describe('ParentOverview mount — empty state', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows ParentEmpty when no child is bound', async () => {
    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: null },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(wrapper.find('.empty').exists()).toBe(true)
    expect(wrapper.find('.focus-card').exists()).toBe(false)
  })
})

// ============================================================
// Mount-based tests — data loading and card rendering
// ============================================================

describe('ParentOverview mount — data loading', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getChildRecords.mockResolvedValue({ data: { items: [] } })
    getChildExams.mockResolvedValue({ data: [] })
    getChildRankings.mockResolvedValue({ data: [] })
    getChildBehaviorSummary.mockResolvedValue({ data: null })
  })

  it('calls all 4 API endpoints on child load', async () => {
    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: { student_id: 's1', student_name: 'Test', class_name: 'Class A' } },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(getChildRecords).toHaveBeenCalledWith('s1', { page: 1, size: 10 })
    expect(getChildExams).toHaveBeenCalledWith('s1')
    expect(getChildRankings).toHaveBeenCalledWith('s1')
    expect(getChildBehaviorSummary).toHaveBeenCalledWith('s1')
  })

  it('shows calm focus card when no issues', async () => {
    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: { student_id: 's1', student_name: 'Test', class_name: 'Class A' } },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(wrapper.find('.focus-card--calm').exists()).toBe(true)
  })

  it('shows behavior card with positive-first when data exists', async () => {
    getChildBehaviorSummary.mockResolvedValue({
      data: { positive_count: 4, negative_count: 1 },
    })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: { student_id: 's1', student_name: 'Test', class_name: 'Class A' } },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(wrapper.html()).toContain('加分')
    expect(wrapper.html()).toContain('待改善')
  })

  it('shows focus item when negative behavior exists', async () => {
    getChildBehaviorSummary.mockResolvedValue({
      data: { positive_count: 2, negative_count: 3 },
    })

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: { student_id: 's1', student_name: 'Test', class_name: 'Class A' } },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(wrapper.find('.focus-card--calm').exists()).toBe(false)
  })

  it('handles API errors gracefully without crashing', async () => {
    getChildRecords.mockRejectedValue(new Error('fail'))
    getChildExams.mockRejectedValue(new Error('fail'))
    getChildRankings.mockRejectedValue(new Error('fail'))
    getChildBehaviorSummary.mockRejectedValue(new Error('fail'))

    const wrapper = mount((await import('../ParentOverview.vue')).default, {
      props: { currentChild: { student_id: 's1', student_name: 'Test', class_name: 'Class A' } },
      global: { stubs: componentStubs },
    })
    await flushPromises()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.focus-card').exists()).toBe(true)
  })
})
