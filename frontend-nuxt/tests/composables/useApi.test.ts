import { describe, it, expect, vi } from 'vitest'

// 用真实 useApi（不 mock 掉），让 setup.ts 的 useCookie/useRuntimeConfig/$fetch mock 生效
vi.unmock('~/composables/useApi')

// 从被测文件动态 import（避免 setup mock 覆盖）
import { useApi } from '~/composables/useApi'

describe('useApi', () => {
  describe('getPowerOptions', () => {
    it('getPowerOptions calls $fetch with correct path', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ grades: [] })
      ;(globalThis as any).$fetch = mockFetch

      const api = useApi()
      await api.getPowerOptions()

      expect(mockFetch).toHaveBeenCalledWith(
        '/analytics/power-options',
        expect.objectContaining({
          baseURL: expect.stringContaining('/api/v1'),
          method: 'GET',
        }),
      )
    })

    it('getPowerOptions passes query params', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ grades: [] })
      ;(globalThis as any).$fetch = mockFetch

      const api = useApi()
      await api.getPowerOptions({ exam_type: 'midterm' })

      expect(mockFetch).toHaveBeenCalledWith(
        '/analytics/power-options',
        expect.objectContaining({
          query: { exam_type: 'midterm' },
        }),
      )
    })

    it('getPowerOptions works without token', async () => {
      const mockFetch = vi.fn().mockResolvedValue({ grades: [] })
      ;(globalThis as any).$fetch = mockFetch

      const api = useApi()
      const res = await api.getPowerOptions()
      expect(res).toEqual({ grades: [] })
    })
  })

  describe('useApi 结构', () => {
    it('useApi 暴露预期方法', () => {
      const api = useApi()
      expect(typeof api.login).toBe('function')
      expect(typeof api.switchRole).toBe('function')
      expect(typeof api.getMenus).toBe('function')
      expect(typeof api.getExams).toBe('function')
      expect(typeof api.getPowerOptions).toBe('function')
      expect(typeof api.chatStream).toBe('function')
      expect(typeof api.raw).toBe('function')
      expect(api.token).toBeDefined()
    })
  })
})
