import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { usePowerOptions } from '~/composables/usePowerOptions'

const MOCK_TREE = {
  grades: [
    {
      id: '高一', name: '高一',
      classes: [
        {
          id: 'all', name: '全部班级',
          subjects: [
            { id: 's1', code: 'math', name: '数学',
              exams: [{ id: 'e1', exam_id: 'e1', subject_id: 's1', name: '期中', exam_date: '2026-04-10', student_count: 90 }] },
          ],
        },
        {
          id: 'c1', name: '高一(1)班',
          subjects: [
            { id: 's2', code: 'chinese', name: '语文',
              exams: [{ id: 'e2', exam_id: 'e2', subject_id: 's2', name: '月考', exam_date: '2026-03-10', student_count: 45 }] },
          ],
        },
      ],
    },
  ],
}

describe('usePowerOptions', () => {
  beforeEach(() => {
    ;(globalThis as any).useApi = () => ({
      getPowerOptions: vi.fn().mockResolvedValue(MOCK_TREE),
    })
  })

  it('load 后自动选中首项', async () => {
    const po = usePowerOptions()
    await po.load()
    await nextTick()

    expect(po.gradeOptions.value).toEqual(['高一'])
    expect(po.selectedGrade.value).toBe('高一')
    expect(po.selectedClassId.value).toBe('all')
  })

  it('级联重置：切换班级重置科目和考试', async () => {
    const po = usePowerOptions()
    await po.load()
    await flushPromises()

    // Manually select c1 first to trigger cascade
    po.selectedClassId.value = 'c1'
    await flushPromises()
    // c1 has s2/e2
    expect(po.selectedSubjectId.value).toBe('s2')
    expect(po.selectedExamId.value).toBe('e2')

    // Switch back to 'all' -> should reset to s1/e1 (different from c1!)
    po.selectedClassId.value = 'all'
    await flushPromises()
    expect(po.selectedSubjectId.value).toBe('s1')
    expect(po.selectedExamId.value).toBe('e1')
  })

  it('analysisParams: all → class_id null (ORC-003)', async () => {
    const po = usePowerOptions()
    await po.load()
    await nextTick()

    expect(po.analysisParams.value.class_id).toBeNull()

    po.selectedClassId.value = 'c1'
    await nextTick()
    expect(po.analysisParams.value.class_id).toBe('c1')
  })

  it('空数据: gradeOptions 为空数组', async () => {
    ;(globalThis as any).useApi = () => ({
      getPowerOptions: vi.fn().mockResolvedValue({ grades: [] }),
    })
    const po = usePowerOptions()
    await po.load()
    expect(po.gradeOptions.value).toEqual([])
    expect(po.hasSelection.value).toBe(false)
  })
})
