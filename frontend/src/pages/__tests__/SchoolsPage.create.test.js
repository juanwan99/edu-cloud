import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const listSchoolsSpy = vi.fn().mockResolvedValue({ data: [] })
const createSchoolSpy = vi.fn().mockResolvedValue({ data: {} })

vi.mock('../../api/schools', () => ({
  listSchools: (...args) => listSchoolsSpy(...args),
  createSchool: (...args) => createSchoolSpy(...args),
}))

const messageStub = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useMessage: () => messageStub }
})

describe('SchoolsPage handleCreate — 后端 CreateSchoolRequest 契约锁', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listSchoolsSpy.mockClear()
    createSchoolSpy.mockClear()
    Object.values(messageStub).forEach((fn) => fn.mockClear())
  })

  it('提交时 payload 必须包含 name/code/district 三个字段（后端 Pydantic 必填契约）', async () => {
    const SchoolsPage = (await import('../SchoolsPage.vue')).default
    const wrapper = mount(SchoolsPage, {
      global: {
        stubs: { NDataTable: true, NModal: true, NForm: true, NFormItem: true, NInput: true, NButton: true },
      },
    })
    await flushPromises()

    wrapper.vm.form.name = '第一中学'
    wrapper.vm.form.code = 'SCHOOL01'
    wrapper.vm.form.district = '河源市源城区'
    await flushPromises()

    await wrapper.vm.handleCreate()
    await flushPromises()

    expect(createSchoolSpy).toHaveBeenCalledTimes(1)
    const payload = createSchoolSpy.mock.calls[0][0]
    expect(payload).toEqual({
      name: '第一中学',
      code: 'SCHOOL01',
      district: '河源市源城区',
    })
  })

  it('district 为空时必须阻断提交并 warn，不发请求', async () => {
    const SchoolsPage = (await import('../SchoolsPage.vue')).default
    const wrapper = mount(SchoolsPage, {
      global: {
        stubs: { NDataTable: true, NModal: true, NForm: true, NFormItem: true, NInput: true, NButton: true },
      },
    })
    await flushPromises()

    wrapper.vm.form.name = '第一中学'
    wrapper.vm.form.code = 'SCHOOL01'
    wrapper.vm.form.district = ''
    await flushPromises()

    const result = await wrapper.vm.handleCreate()
    await flushPromises()

    expect(createSchoolSpy).not.toHaveBeenCalled()
    expect(messageStub.warning).toHaveBeenCalled()
    expect(result).toBe(false)
  })
})
