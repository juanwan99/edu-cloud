import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick, defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

/**
 * F-003 修复：KnowledgeTreePage 真实 mount 测试
 *
 * 通过 mock useKnowledgeTree composable + useAuthStore + NMessage，
 * 让真实的 KnowledgeTreePage.vue 被挂载并验证关键契约：
 * - INV-004: selectedModule='all' ↔ ModuleOverviewPanel, 'M1' ↔ ConceptMapPanel 互斥
 * - F-001: platform_admin / subject_teacher / district_admin 默认入口 showCards=false
 * - F-002: handleBackToOverview 同步刷新 qualityIssues (loadQuality('all'))
 * - handleMarkReviewed → applyEdit with set_review_status
 */

// 全局可变 refs，mock 在 module level，测试里可修改
const mockState = {
  navigationData: ref([]),
  graphData: ref({ nodes: [], edges: [] }),
  loading: ref(false),
  selectedModule: ref('all'),
  // R2 F001/F002：composable 暴露的 selectedStudentId，页面解构读取（单一真源）。
  // useKnowledgeTree.loadMastery() 内部 selectedStudentId.value = studentId，
  // 本 mock 保持相同语义：loadMastery 写 mockState.selectedStudentId，页面自动响应。
  selectedStudentId: ref(null),
  moduleMastery: ref([]),
  nodesWithMastery: ref([]),
  qualityIssues: ref([]),
  modulesQuality: ref({}),
  statsOverview: ref(null),
  courseMapOverview: ref(null),
  courseMapModule: ref(null),
  courseMapStudyUnit: ref(null),
  loadGraphCalls: [],
  loadQualityCalls: [],
  loadAllModulesQualityCalls: 0,
  loadStatsOverviewCalls: 0,
  loadCourseMapOverviewCalls: 0,
  loadCourseMapModuleCalls: [],
  loadCourseMapStudyUnitCalls: [],
  loadMasteryCalls: [],
  applyEditCalls: [],
}

function resetMockState() {
  mockState.navigationData.value = [
    { id: 'M1', name: '分子与细胞', big_concepts: [] },
    { id: 'M2', name: '遗传与进化', big_concepts: [] },
  ]
  mockState.graphData.value = { nodes: [], edges: [] }
  mockState.selectedModule.value = 'all'
  mockState.selectedStudentId.value = null
  mockState.moduleMastery.value = []
  mockState.nodesWithMastery.value = []
  mockState.qualityIssues.value = []
  mockState.modulesQuality.value = {}
  mockState.statsOverview.value = null
  mockState.courseMapOverview.value = null
  mockState.courseMapModule.value = null
  mockState.courseMapStudyUnit.value = null
  mockState.loadGraphCalls.length = 0
  mockState.loadQualityCalls.length = 0
  mockState.loadAllModulesQualityCalls = 0
  mockState.loadStatsOverviewCalls = 0
  mockState.loadCourseMapOverviewCalls = 0
  mockState.loadCourseMapModuleCalls.length = 0
  mockState.loadCourseMapStudyUnitCalls.length = 0
  mockState.loadMasteryCalls.length = 0
  mockState.applyEditCalls.length = 0
}

vi.mock('../../components/knowledge-tree/useKnowledgeTree', () => ({
  useKnowledgeTree: () => ({
    navigationData: mockState.navigationData,
    graphData: mockState.graphData,
    loading: mockState.loading,
    selectedModule: mockState.selectedModule,
    selectedStudentId: mockState.selectedStudentId,
    moduleMastery: mockState.moduleMastery,
    nodesWithMastery: mockState.nodesWithMastery,
    qualityIssues: mockState.qualityIssues,
    modulesQuality: mockState.modulesQuality,
    statsOverview: mockState.statsOverview,
    courseMapOverview: mockState.courseMapOverview,
    courseMapModule: mockState.courseMapModule,
    courseMapStudyUnit: mockState.courseMapStudyUnit,
    loadCourseMapOverview: vi.fn(async () => {
      mockState.loadCourseMapOverviewCalls++
    }),
    loadCourseMapModule: vi.fn(async (mod) => {
      mockState.loadCourseMapModuleCalls.push(mod)
    }),
    loadCourseMapStudyUnit: vi.fn(async (suId) => {
      mockState.loadCourseMapStudyUnitCalls.push(suId)
    }),
    loadGraph: vi.fn(async (mod = 'all') => {
      mockState.loadGraphCalls.push(mod)
      mockState.selectedModule.value = mod
    }),
    loadMastery: vi.fn(async (sid) => {
      mockState.loadMasteryCalls.push(sid)
      // 对齐 useKnowledgeTree.loadMastery 真实行为：写入 composable selectedStudentId
      mockState.selectedStudentId.value = sid
    }),
    loadQuality: vi.fn(async (mod) => {
      mockState.loadQualityCalls.push(mod)
    }),
    loadAllModulesQuality: vi.fn(async () => {
      mockState.loadAllModulesQualityCalls++
    }),
    loadStatsOverview: vi.fn(async () => {
      mockState.loadStatsOverviewCalls++
    }),
    applyEdit: vi.fn(async (ops) => {
      mockState.applyEditCalls.push(ops)
    }),
  }),
}))

// Mock auth store — 运行时切换角色（checkPermission 基于 roleName 反应式，
// 让页面的 `computed(() => authStore.checkPermission(...))` 能响应 roleName 变化）
const ROLE_PERMS = {
  platform_admin: ['edit_knowledge_tree', 'view_knowledge_tree'],
  district_admin: ['edit_knowledge_tree', 'view_knowledge_tree'],
  principal: ['edit_knowledge_tree', 'view_knowledge_tree'],
  academic_director: ['edit_knowledge_tree', 'view_knowledge_tree'],
  subject_teacher: ['edit_knowledge_tree', 'view_knowledge_tree'],
  homeroom_teacher: ['edit_knowledge_tree', 'view_knowledge_tree'],
  grade_leader: ['view_knowledge_tree'],
  parent: [],
  student: [],
}
const mockAuth = {
  roleName: ref('subject_teacher'),
  checkPermission(perm) {
    // 读取 roleName.value，使 computed 捕获依赖
    const role = mockAuth.roleName.value
    return (ROLE_PERMS[role] || []).includes(perm)
  },
}

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => mockAuth,
}))

// Naive UI useMessage mock
vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    }),
  }
})

// Mock G6 Graph（ConceptMapPanel 依赖）
vi.mock('@antv/g6', () => {
  class Graph {
    constructor() {
      this.handlers = {}
      this.render = vi.fn()
      this.destroy = vi.fn()
      this.on = vi.fn((e, cb) => { this.handlers[e] = cb })
    }
  }
  return { Graph }
})

// 因 KnowledgeTreePage 的 import 链很深，使用 global stubs 让子组件 mount 时不实际渲染其复杂内容
const stubs = {
  ModuleCards: defineComponent({
    name: 'ModuleCards',
    props: ['modules'],
    emits: ['select'],
    setup(_, { emit }) {
      return () => h('div', {
        class: 'module-cards-stub',
        onClick: () => emit('select', 'M1'),
      }, 'ModuleCards')
    },
  }),
  TreeNavPanel: defineComponent({
    props: ['navigation', 'moduleMastery', 'nodesWithMastery', 'selectedModule'],
    emits: ['select-module', 'select-node'],
    setup(_, { emit }) {
      return () => h('div', { class: 'tree-nav-stub' }, [
        // 测试用触发器：从 TreeNavPanel 发出 select-module('all')，
        // 驱动真实页面的 handleModuleSelect('all') 对称分支（F-005 修复）
        h('button', {
          class: 'tree-nav-select-all',
          onClick: () => emit('select-module', 'all'),
        }, 'tree-select-all'),
        h('button', {
          class: 'tree-nav-select-m2',
          onClick: () => emit('select-module', 'M2'),
        }, 'tree-select-m2'),
      ])
    },
  }),
  ModuleOverviewPanel: defineComponent({
    // R2 F002 pattern: stub props 必须包含所有 parent 传入的 prop（含 T13 新增 statsOverview），
    // 否则 Vue 静默吞掉未声明 prop，测试失去接线保护
    props: ['navigation', 'nodes', 'edges', 'modulesQuality', 'statsOverview'],
    emits: ['select-module', 'refresh-quality'],
    setup(_, { emit }) {
      return () => h('div', {
        class: 'module-overview-stub',
        'data-stats-overview': _.statsOverview == null ? 'null' : 'object',
        onClick: () => emit('select-module', 'M1'),
      }, 'ModuleOverviewPanel')
    },
  }),
  ConceptMapPanel: defineComponent({
    // R2 F002: stub props 列表必须包含 colorMode/nodesWithMastery，否则 Vue 静默吞掉新 prop
    props: ['moduleId', 'moduleName', 'nodes', 'edges', 'navigation', 'qualityIssues', 'canEdit', 'colorMode', 'nodesWithMastery'],
    emits: ['back-to-overview', 'refresh', 'node-click', 'view-detail', 'mark-reviewed'],
    setup(_, { emit }) {
      return () => h('div', {
        class: 'concept-map-stub',
        'data-module': _.moduleId,
        'data-color-mode': _.colorMode,
        'data-mastery-count': String(Array.isArray(_.nodesWithMastery) ? _.nodesWithMastery.length : 0),
      }, [
        h('button', {
          class: 'back-btn',
          onClick: () => emit('back-to-overview'),
        }, 'back'),
        h('button', {
          class: 'mark-reviewed-btn',
          onClick: () => emit('mark-reviewed', { id: 'concept-X', name: '测试概念' }),
        }, 'mark'),
      ])
    },
  }),
  // R2 F002: ColorModeToggle stub 捕获 modelValue/hasStudent，供集成断言 grep
  ColorModeToggle: defineComponent({
    name: 'ColorModeToggle',
    props: ['modelValue', 'hasStudent'],
    emits: ['update:modelValue'],
    setup(props) {
      return () => h('div', {
        class: 'color-mode-toggle-stub',
        'data-has-student': String(Boolean(props.hasStudent)),
        'data-mode': props.modelValue,
      }, 'ColorModeToggle')
    },
  }),
  NodeDetailDrawer: {
    props: ['show', 'node', 'canEdit'],
    template: '<div class="node-drawer-stub" />',
  },
  RelationReviewPanel: {
    props: ['nodes', 'edges', 'qualityIssues', 'canEdit'],
    emits: ['edit'],
    template: '<div class="relation-review-stub">RelationReviewPanel</div>',
  },
  CourseMapOverview: defineComponent({
    name: 'CourseMapOverview',
    props: ['data'],
    emits: ['select-module'],
    setup(_, { emit }) {
      return () => h('div', {
        class: 'course-map-overview-stub',
        onClick: () => emit('select-module', 'M1'),
      }, 'CourseMapOverview')
    },
  }),
  ModuleMapView: defineComponent({
    name: 'ModuleMapView',
    props: ['data'],
    emits: ['select-unit', 'back'],
    setup(_, { emit }) {
      return () => h('div', { class: 'module-map-view-stub' }, [
        h('button', { class: 'back-btn', onClick: () => emit('back') }, 'back'),
        h('button', { class: 'select-unit-btn', onClick: () => emit('select-unit', 'su:m1_001') }, 'unit'),
      ])
    },
  }),
  StudyUnitDetail: defineComponent({
    name: 'StudyUnitDetail',
    props: ['data'],
    emits: ['select-concept', 'back'],
    setup(_, { emit }) {
      return () => h('div', { class: 'study-unit-detail-stub' }, [
        h('button', { class: 'back-btn', onClick: () => emit('back') }, 'back'),
        h('button', { class: 'select-concept-btn', onClick: () => emit('select-concept', 'BIO_SR_CP_M1_A') }, 'concept'),
      ])
    },
  }),
}

import KnowledgeTreePage from '../../pages/KnowledgeTreePage.vue'

async function mountPage(viewMode = 'course-map') {
  setActivePinia(createPinia())
  const wrapper = mount(KnowledgeTreePage, {
    global: {
      stubs,
    },
    attachTo: document.body,
  })
  await nextTick()
  await nextTick()
  await nextTick()
  await nextTick()
  if (viewMode !== 'course-map') {
    wrapper.vm.viewMode = viewMode
    await nextTick()
    await nextTick()
  }
  return wrapper
}

describe('KnowledgeTreePage real mount (F-003 fix)', () => {
  beforeEach(() => {
    resetMockState()
    mockAuth.roleName.value = 'subject_teacher'
  })

  describe('入口状态机 (F-001 cover)', () => {
    it('subject_teacher → init() sets showCards=false → CourseMapOverview visible (default view)', async () => {
      mockAuth.roleName.value = 'subject_teacher'
      const wrapper = await mountPage()

      expect(wrapper.find('.module-cards-stub').exists()).toBe(false)
      expect(wrapper.find('.course-map-overview-stub').exists()).toBe(true)
    })

    it('platform_admin → F-001 fix: showCards=false → course map entry', async () => {
      mockAuth.roleName.value = 'platform_admin'
      const wrapper = await mountPage()

      expect(wrapper.find('.module-cards-stub').exists()).toBe(false)
      expect(wrapper.find('.course-map-overview-stub').exists()).toBe(true)
    })

    it('district_admin → F-001 fix: showCards=false → course map entry', async () => {
      mockAuth.roleName.value = 'district_admin'
      const wrapper = await mountPage()

      expect(wrapper.find('.module-cards-stub').exists()).toBe(false)
      expect(wrapper.find('.course-map-overview-stub').exists()).toBe(true)
    })

    it('parent → showCards=true → ModuleCards visible', async () => {
      mockAuth.roleName.value = 'parent'
      const wrapper = await mountPage()

      expect(wrapper.find('.module-cards-stub').exists()).toBe(true)
      expect(wrapper.find('.module-overview-stub').exists()).toBe(false)
    })

    it('subject_teacher init() triggers loadCourseMapOverview', async () => {
      await mountPage()
      expect(mockState.loadCourseMapOverviewCalls).toBe(1)
    })

    it('parent init() also loads courseMapOverview (but stays on ModuleCards)', async () => {
      mockAuth.roleName.value = 'parent'
      await mountPage()
      expect(mockState.loadCourseMapOverviewCalls).toBe(1)
    })
  })

  describe('INV-004 mutex routing (graph-review mode)', () => {
    it('selectedModule=all → only ModuleOverviewPanel rendered', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'all'
      await nextTick()

      expect(wrapper.find('.module-overview-stub').exists()).toBe(true)
      expect(wrapper.find('.concept-map-stub').exists()).toBe(false)
    })

    it('selectedModule=M1 → only ConceptMapPanel rendered', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()

      expect(wrapper.find('.module-overview-stub').exists()).toBe(false)
      expect(wrapper.find('.concept-map-stub').exists()).toBe(true)
      expect(wrapper.find('.concept-map-stub').attributes('data-module')).toBe('M1')
    })

    it('select-module event on ModuleOverviewPanel switches to ConceptMapPanel', async () => {
      const wrapper = await mountPage('graph-review')
      expect(wrapper.find('.module-overview-stub').exists()).toBe(true)

      await wrapper.find('.module-overview-stub').trigger('click')
      await nextTick()

      expect(mockState.selectedModule.value).toBe('M1')
      expect(mockState.loadGraphCalls).toContain('M1')
      expect(mockState.loadQualityCalls).toContain('M1')
    })
  })

  describe('F-002 fix: handleBackToOverview refreshes qualityIssues', () => {
    it('back-to-overview event → loadQuality(all) called alongside loadAllModulesQuality', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      mockState.loadGraphCalls.length = 0
      mockState.loadQualityCalls.length = 0
      mockState.loadAllModulesQualityCalls = 0
      await nextTick()

      await wrapper.find('.back-btn').trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.selectedModule.value).toBe('all')
      expect(mockState.loadGraphCalls).toContain('all')
      expect(mockState.loadQualityCalls).toContain('all')
      expect(mockState.loadAllModulesQualityCalls).toBeGreaterThan(0)
    })

    it('handleModuleSelect(all) via TreeNavPanel select-module → loadQuality(all) + loadAllModulesQuality', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()
      mockState.loadGraphCalls.length = 0
      mockState.loadQualityCalls.length = 0
      mockState.loadAllModulesQualityCalls = 0

      await wrapper.find('.tree-nav-select-all').trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.selectedModule.value).toBe('all')
      expect(mockState.loadGraphCalls).toContain('all')
      expect(mockState.loadQualityCalls).toContain('all')
      expect(mockState.loadAllModulesQualityCalls).toBeGreaterThan(0)
    })

    it('handleModuleSelect(Mx) via TreeNavPanel → only loadQuality(Mx), not loadAllModulesQuality', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.loadGraphCalls.length = 0
      mockState.loadQualityCalls.length = 0
      mockState.loadAllModulesQualityCalls = 0

      await wrapper.find('.tree-nav-select-m2').trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.selectedModule.value).toBe('M2')
      expect(mockState.loadGraphCalls).toContain('M2')
      expect(mockState.loadQualityCalls).toContain('M2')
      expect(mockState.loadAllModulesQualityCalls).toBe(0)
    })

    it('parent role → ModuleCards select M1 → handleModuleSelect M1 (loadGraph only, no quality)', async () => {
      mockAuth.roleName.value = 'parent'
      const wrapper = await mountPage()

      const moduleCardsStub = wrapper.find('.module-cards-stub')
      expect(moduleCardsStub.exists()).toBe(true)

      mockState.loadGraphCalls.length = 0
      mockState.loadQualityCalls.length = 0
      mockState.loadAllModulesQualityCalls = 0

      await moduleCardsStub.trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.loadGraphCalls).toContain('M1')
      expect(mockState.selectedModule.value).toBe('M1')
      expect(mockState.loadQualityCalls).toHaveLength(0)
      expect(mockState.loadAllModulesQualityCalls).toBe(0)
    })

    it('handleBackToOverview with canEdit=false → loadGraph(all) only, no quality refresh', async () => {
      mockAuth.roleName.value = 'subject_teacher'
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()

      mockAuth.roleName.value = 'grade_leader'
      await nextTick()
      mockState.loadGraphCalls.length = 0
      mockState.loadQualityCalls.length = 0
      mockState.loadAllModulesQualityCalls = 0

      await wrapper.find('.back-btn').trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.selectedModule.value).toBe('all')
      expect(mockState.loadGraphCalls).toContain('all')
      expect(mockState.loadQualityCalls).toHaveLength(0)
      expect(mockState.loadAllModulesQualityCalls).toBe(0)
    })
  })

  describe('handleMarkReviewed dispatches set_review_status', () => {
    it('mark-reviewed event → applyEdit called with set_review_status op', async () => {
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()

      await wrapper.find('.mark-reviewed-btn').trigger('click')
      await nextTick()
      await nextTick()

      expect(mockState.applyEditCalls.length).toBeGreaterThan(0)
      expect(mockState.applyEditCalls[0]).toEqual([
        { op: 'set_review_status', id: 'concept-X', status: 'teacher_reviewed' },
      ])
    })
  })

  describe('Phase 1 T10 — selectedStudentId 单一真源 & auto-switch (F001/F002)', () => {
    it('进入 Mx 模块：ColorModeToggle 挂载，初始 hasStudent=false，ConceptMapPanel 收到 colorMode=exam_frequency', async () => {
      mockAuth.roleName.value = 'subject_teacher'
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()
      await nextTick()

      const toggle = wrapper.find('.color-mode-toggle-stub')
      expect(toggle.exists()).toBe(true)
      expect(toggle.attributes('data-has-student')).toBe('false')
      expect(toggle.attributes('data-mode')).toBe('exam_frequency')

      const cmp = wrapper.find('.concept-map-stub')
      expect(cmp.exists()).toBe(true)
      expect(cmp.attributes('data-color-mode')).toBe('exam_frequency')
    })

    it('composable selectedStudentId 写入后 hasStudent=true', async () => {
      mockAuth.roleName.value = 'subject_teacher'
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()
      await nextTick()

      expect(wrapper.find('.color-mode-toggle-stub').attributes('data-has-student')).toBe('false')

      mockState.selectedStudentId.value = 'student_1'
      await nextTick()
      await nextTick()

      expect(wrapper.find('.color-mode-toggle-stub').attributes('data-has-student')).toBe('true')
    })

    it('selectedStudentId 写入触发 auto-switch：ConceptMapPanel colorMode exam_frequency → mastery', async () => {
      mockAuth.roleName.value = 'subject_teacher'
      const wrapper = await mountPage('graph-review')
      mockState.selectedModule.value = 'M1'
      await nextTick()
      await nextTick()

      expect(wrapper.find('.concept-map-stub').attributes('data-color-mode')).toBe('exam_frequency')

      mockState.selectedStudentId.value = 'student_1'
      await nextTick()
      await nextTick()

      expect(wrapper.find('.concept-map-stub').attributes('data-color-mode')).toBe('mastery')
      expect(wrapper.find('.color-mode-toggle-stub').attributes('data-mode')).toBe('mastery')
    })
  })
})
