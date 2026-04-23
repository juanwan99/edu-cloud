import { beforeEach, vi } from 'vitest'
import { defineStore, setActivePinia, createPinia } from 'pinia'
import { ref, computed, reactive, watch } from 'vue'

// 注入 Nuxt auto-import globals（仅测试环境）
const g = globalThis as any
g.defineStore = defineStore
g.ref = ref
g.computed = computed
g.reactive = reactive
g.watch = watch

// cookie store（内存模拟）
const cookieStore = new Map<string, any>()
g.useCookie = (name: string) => {
  if (!cookieStore.has(name)) cookieStore.set(name, ref(null))
  return cookieStore.get(name)
}

// API mock（逐测试 override）
g.useApi = () => ({
  login: vi.fn(),
  switchRole: vi.fn(),
  getMenus: vi.fn().mockResolvedValue({ menus: [] }),
  token: ref(null),
})

// useRuntimeConfig mock（useApi 依赖）
g.useRuntimeConfig = () => ({
  public: { apiBase: 'http://localhost:9000' },
})

// $fetch mock（useApi 内部调用）
g.$fetch = vi.fn()

// navigateTo mock
g.navigateTo = vi.fn()

// useMenus mock
g.useMenus = () => ({
  loadMenus: vi.fn().mockResolvedValue(undefined),
  activeModule: computed(() => null),
  currentSubMenus: computed(() => []),
  navigateToModule: vi.fn(),
})

// usePowerOptions mock（PowerFilter 组件依赖）
g.usePowerOptions = () => ({
  load: vi.fn().mockResolvedValue(undefined),
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

// onMounted mock (Nuxt auto-import)
g.onMounted = (cb: () => void) => cb()

beforeEach(() => {
  setActivePinia(createPinia())
  cookieStore.clear()
  localStorage.clear()
})
