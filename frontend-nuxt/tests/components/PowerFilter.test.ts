import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import PowerFilter from '~/components/common/PowerFilter.vue'

describe('PowerFilter', () => {
  it('renders 4 ElSelect components', () => {
    const wrapper = mount(PowerFilter, {
      global: { plugins: [ElementPlus] },
    })
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBe(4)
  })

  it('calls load on mounted', () => {
    const loadFn = vi.fn().mockResolvedValue(undefined)
    ;(globalThis as any).usePowerOptions = () => ({
      load: loadFn,
      tree: ref([]),
      loading: ref(false),
      selectedGrade: ref(''),
      selectedClassId: ref('all'),
      selectedSubjectId: ref(''),
      selectedExamId: ref(''),
      gradeOptions: computed(() => []),
      classOptions: computed(() => []),
      subjectOptions: computed(() => []),
      examOptions: computed(() => []),
      analysisParams: computed(() => ({ exam_id: '', subject_id: '', class_id: null })),
      hasSelection: computed(() => false),
    })
    mount(PowerFilter, {
      global: { plugins: [ElementPlus] },
    })
    expect(loadFn).toHaveBeenCalled()
  })
})
