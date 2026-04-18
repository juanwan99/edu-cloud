import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick, ref } from 'vue'
import { usePowerOptions } from '~/composables/usePowerOptions'

describe('usePowerOptions', () => {
  let getPowerOptionsMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    getPowerOptionsMock = vi
      .fn()
      .mockResolvedValue({ powerOptions: [], examInfoMap: {} })
    ;(globalThis as any).useApi = () => ({
      getPowerOptions: getPowerOptionsMock,
      login: vi.fn(),
      switchRole: vi.fn(),
      token: ref(null),
    })
  })

  describe('load() 空数据容错（ORC-load-empty / plan Task 10 测试契约 1）', () => {
    it('load() 空 tree 时不崩溃，selectedGrade 保持空', async () => {
      const pw = usePowerOptions()
      await pw.load()
      expect(pw.tree.value).toEqual([])
      expect(pw.selectedGrade.value).toBe('')
      expect(pw.selectedExamIds.value).toEqual([])
    })

    it('load() API 抛错时 tree/examInfoMap 清空，不向上抛', async () => {
      getPowerOptionsMock.mockRejectedValue(new Error('network timeout'))

      const pw = usePowerOptions()
      await expect(pw.load()).resolves.toBeUndefined()
      expect(pw.tree.value).toEqual([])
      expect(pw.examInfoMap.value).toEqual({})
    })
  })

  describe('级联 watch 上级变化自动选下级第一项（plan Task 10 测试契约 2 / cascade_reset）', () => {
    it('切换 grade 时 class/subject/examIds 自动跟到第一项', async () => {
      const pw = usePowerOptions()
      pw.tree.value = [
        {
          grade: '高三',
          classes: [
            {
              class: '1班',
              subjects: [{ subject: '语文', examids: ['e1'] }],
            },
          ],
        },
      ]
      pw.selectedGrade.value = '高三'
      await nextTick()
      expect(pw.selectedClass.value).toBe('1班')
      await nextTick()
      expect(pw.selectedSubject.value).toBe('语文')
      await nextTick()
      expect(pw.selectedExamIds.value).toEqual(['e1'])
    })

    it('切换到无班级的 grade → selectedClass 重置为空', async () => {
      const pw = usePowerOptions()
      pw.tree.value = [
        { grade: '高三', classes: [] },
      ]
      pw.selectedGrade.value = '高三'
      await nextTick()
      expect(pw.selectedClass.value).toBe('')
    })
  })
})
