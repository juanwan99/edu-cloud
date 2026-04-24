import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAnalytics } from '../../composables/useAnalytics'
import { useApi } from '../../composables/useApi'

describe('useAnalytics', () => {
  beforeEach(() => {
    // Override the global useApi mock with the real implementation
    // so that $fetch mock flows through the analytics API chain.
    ;(globalThis as any).useApi = useApi
  })

  it('loadBasicData calls 4 APIs in parallel', async () => {
    const mockSummary = { exam_id: 'e1', total_students: 50, subjects: [] }
    const mockDist = { intervals: [] }
    const mockAgg = { class_rankings: [] }

    const mockFetch = vi.fn()
      .mockResolvedValueOnce(mockSummary)
      .mockResolvedValueOnce(mockDist)
      .mockResolvedValueOnce(mockAgg)
      .mockResolvedValueOnce(null)
    ;(globalThis as any).$fetch = mockFetch

    const analytics = useAnalytics()
    await analytics.loadBasicData({ exam_id: 'e1' })

    expect(analytics.summary.value).toEqual(mockSummary)
    expect(analytics.distribution.value).toEqual(mockDist)
    expect(analytics.loading.value).toBe(false)
  })

  it('loadAdvancedData is lazy — skips if already loaded', async () => {
    const mockFetch = vi.fn().mockResolvedValue({})
    ;(globalThis as any).$fetch = mockFetch

    const analytics = useAnalytics()
    analytics.questionInsights.value = { questions: [] }

    await analytics.loadAdvancedData({ exam_id: 'e1' })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('clearAll resets all state', () => {
    const analytics = useAnalytics()
    analytics.summary.value = { test: 1 }
    analytics.questionInsights.value = { test: 2 }

    analytics.clearAll()

    expect(analytics.summary.value).toBeNull()
    expect(analytics.questionInsights.value).toBeNull()
  })
})
