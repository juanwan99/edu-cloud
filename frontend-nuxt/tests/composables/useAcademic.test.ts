import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useApi } from '../../composables/useApi'

const mockFetch = vi.fn()
;(globalThis as any).$fetch = mockFetch

describe('useAcademic', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    // Override the global useApi stub with real implementation so
    // useAcademic's internal api.getSemesters/getTimetable route through $fetch.
    ;(globalThis as any).useApi = useApi
  })

  it('loadSemesters calls API and stores result', async () => {
    const mockData = [{ id: '1', name: 'S1', is_current: true }]
    mockFetch.mockResolvedValueOnce(mockData)

    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    await academic.loadSemesters()

    expect(mockFetch).toHaveBeenCalledWith(
      '/academic/semesters',
      expect.objectContaining({ baseURL: expect.any(String) })
    )
    expect(academic.semesters.value).toEqual(mockData)
  })

  it('loadTimetable passes class_id as query param', async () => {
    mockFetch.mockResolvedValueOnce([])

    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    await academic.loadTimetable('sem-1', 'cls-1')

    expect(mockFetch).toHaveBeenCalledWith(
      '/academic/timetable',
      expect.objectContaining({
        query: { semester_id: 'sem-1', class_id: 'cls-1' },
      })
    )
  })

  it('semesterProgress returns 0 for null semester', async () => {
    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    const result = academic.semesterProgress(null)
    expect(result).toEqual({ percent: 0, week: 0 })
  })

  it('semesterProgress calculates correctly for past date range', async () => {
    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    const result = academic.semesterProgress({
      start_date: '2020-01-01',
      end_date: '2020-06-30',
    })
    expect(result.percent).toBe(100)
  })
})
