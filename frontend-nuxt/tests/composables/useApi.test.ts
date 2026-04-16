import { describe, it, expect, vi } from 'vitest'

// 用真实 useApi（不 mock 掉），让 setup.ts 的 useCookie/useRuntimeConfig/$fetch mock 生效
vi.unmock('~/composables/useApi')

// 从被测文件动态 import（避免 setup mock 覆盖）
import { useApi } from '~/composables/useApi'

describe('useApi', () => {
  describe('getPowerOptions stub', () => {
    it('getPowerOptions 返回 {powerOptions: [], examInfoMap: {}}', async () => {
      const api = useApi()
      const res = await api.getPowerOptions()
      expect(res).toEqual({ powerOptions: [], examInfoMap: {} })
    })

    it('getPowerOptions 传 params 不影响返回结构', async () => {
      const api = useApi()
      const res = await api.getPowerOptions({ subject: 'math' })
      expect(res).toEqual({ powerOptions: [], examInfoMap: {} })
    })

    it('getPowerOptions 未登录（无 token）仍可调用', async () => {
      // setup.ts 的 useCookie 初始返回 null token —— 不应抛异常
      const api = useApi()
      const res = await api.getPowerOptions()
      expect(res.powerOptions).toEqual([])
      expect(res.examInfoMap).toEqual({})
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
