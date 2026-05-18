import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const listTeachersSpy = vi.fn().mockResolvedValue({ data: [] })
const createTeacherSpy = vi.fn().mockResolvedValue({ data: { id: 'new', roles: [] } })
const listSchoolsSpy = vi.fn().mockResolvedValue({
  data: [
    { id: 'sch_jy', name: '景炎初级中学', code: 'JY001' },
    { id: 'sch_yc', name: '育才实验中学', code: 'YC001' },
  ],
})
const clientGetSpy = vi.fn().mockResolvedValue({ data: [] })

vi.mock('../../api/teachers', () => ({
  listTeachers: (...a) => listTeachersSpy(...a),
  createTeacher: (...a) => createTeacherSpy(...a),
  updateTeacher: vi.fn(),
  deleteTeacher: vi.fn(),
  importTeachers: vi.fn(),
  exportTeachers: vi.fn(),
  downloadTemplate: vi.fn(),
}))

vi.mock('../../api/schools', () => ({
  listSchools: (...a) => listSchoolsSpy(...a),
}))

vi.mock('../../api/client', () => ({
  default: { get: (...a) => clientGetSpy(...a) },
}))

const messageStub = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useMessage: () => messageStub, useDialog: () => ({ warning: vi.fn() }) }
})

import { useAuthStore } from '../../stores/auth'

function seedAuth(role, schoolContext = null) {
  const auth = useAuthStore()
  auth.$patch({
    roles: schoolContext
      ? [{ id: 'r1', role, context: { type: 'school', id: schoolContext.id, name: schoolContext.name } }]
      : [{ id: 'r1', role, context: null }],
    currentRoleId: 'r1',
  })
}

const STUBS = {
  NDataTable: true, NModal: true, NForm: true, NFormItem: true,
  NInput: true, NButton: true, NSelect: true, NTag: true, NUpload: true,
  NSwitch: true, NDivider: true,
}

describe('TeachersPage — 超管跨校创建契约锁（ORC-003/ORC-004）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listTeachersSpy.mockClear()
    createTeacherSpy.mockClear()
    listSchoolsSpy.mockClear()
    clientGetSpy.mockClear()
    Object.values(messageStub).forEach((fn) => fn.mockClear())
  })

  it('platform_admin 登录 → GET /schools 调用 + DOM 渲染学校下拉（ORC-003 DOM 级 / R1-F005）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    expect(wrapper.find('[data-testid="school-select"]').exists()).toBe(true)
    expect(listSchoolsSpy).toHaveBeenCalled()
    expect(wrapper.vm.isPlatformAdmin).toBe(true)
    expect(wrapper.vm.schoolOptions.length).toBe(2)
    expect(wrapper.vm.schoolOptions[0]).toEqual(
      expect.objectContaining({ label: '景炎初级中学', value: 'sch_jy' })
    )
  })

  it('subject_teacher 登录 → GET /schools 不调用 + DOM 无学校下拉（ORC-003 DOM 级 / R1-F005）', async () => {
    seedAuth('subject_teacher', { id: 'sch_jy', name: '景炎初级中学' })
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    expect(wrapper.find('[data-testid="school-select"]').exists()).toBe(false)
    expect(listSchoolsSpy).not.toHaveBeenCalled()
    expect(wrapper.vm.isPlatformAdmin).toBe(false)
  })

  it('超管选中学校后 → createRoleOptions 仅含 principal+academic_director，importRoleOptions 保持全集（ORC-004 / R1-F004）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.selectedSchool = 'sch_jy'
    await flushPromises()
    expect(wrapper.vm.createRoleOptions.length).toBe(3)
    const values = wrapper.vm.createRoleOptions.map((o) => o.value).sort()
    expect(values).toEqual(['academic_director', 'principal', 'school_admin'])
    expect(wrapper.vm.importRoleOptions.length).toBeGreaterThanOrEqual(8)
  })

  it('超管跨校 openCreate 后未手改角色 handleSave → payload.roles === ["principal"]（R1-F003 默认角色泄漏防护）', async () => {
    seedAuth('platform_admin', null)
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.selectedSchool = 'sch_jy'
    wrapper.vm.openCreate()
    wrapper.vm.form.display_name = '景炎新校长'
    wrapper.vm.form.username = 'new_pri'
    await flushPromises()
    await wrapper.vm.handleSave()
    await flushPromises()
    expect(createTeacherSpy).toHaveBeenCalledTimes(1)
    const payload = createTeacherSpy.mock.calls[0][0]
    expect(payload.roles).toEqual(['principal'])
    expect(payload.school_id).toBe('sch_jy')
  })

  it('非超管场景 handleSave → payload 不含 school_id（回归锁）', async () => {
    seedAuth('principal', { id: 'sch_jy', name: '景炎初级中学' })
    const TeachersPage = (await import('../TeachersPage.vue')).default
    const wrapper = mount(TeachersPage, { global: { stubs: STUBS } })
    await flushPromises()
    wrapper.vm.openCreate()
    wrapper.vm.form.display_name = '本校新科任'
    wrapper.vm.form.username = 't_new'
    wrapper.vm.form.roles = ['subject_teacher']
    await flushPromises()
    await wrapper.vm.handleSave()
    await flushPromises()
    expect(createTeacherSpy).toHaveBeenCalledTimes(1)
    const payload = createTeacherSpy.mock.calls[0][0]
    expect(payload).not.toHaveProperty('school_id')
  })
})
