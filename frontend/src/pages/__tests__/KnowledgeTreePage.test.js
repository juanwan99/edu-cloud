/**
 * KnowledgeTreePage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key layout sections (ModuleCards, main-layout, nav-side, graph-side)
 *  3. Template contains child components (TreeNavPanel, ConceptMapPanel, etc.)
 *  4. Script imports correct composables and components
 *  5. Data flow and state management (colorMode, activeTab, canEdit)
 *  6. API/composable calls (loadGraph, loadMastery, loadQuality)
 *  7. Error handling in handleEdit
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../KnowledgeTreePage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('KnowledgeTreePage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../KnowledgeTreePage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('KnowledgeTreePage template layout', () => {
  it('contains knowledge-tree-page root class', () => {
    expect(content).toContain('class="knowledge-tree-page"')
  })

  it('contains ModuleCards with conditional rendering', () => {
    expect(content).toContain('<ModuleCards')
    expect(content).toContain('v-if="showCards"')
    expect(content).toContain(':modules="moduleMastery"')
  })

  it('contains main-layout with nav-side and graph-side', () => {
    expect(content).toContain('class="main-layout"')
    expect(content).toContain('class="nav-side"')
    expect(content).toContain('class="graph-side"')
  })

  it('supports nav collapse state', () => {
    expect(content).toContain('collapsed: navCollapsed')
  })

  it('contains NodeDetailDrawer', () => {
    expect(content).toContain('<NodeDetailDrawer')
    expect(content).toContain('v-model:show="drawerVisible"')
    expect(content).toContain(':node="selectedNode"')
  })
})

describe('KnowledgeTreePage child components', () => {
  it('imports TreeNavPanel', () => {
    expect(content).toContain("import TreeNavPanel from '../components/knowledge-tree/TreeNavPanel.vue'")
    expect(content).toContain('<TreeNavPanel')
  })

  it('imports ModuleOverviewPanel', () => {
    expect(content).toContain("import ModuleOverviewPanel from '../components/knowledge-tree/ModuleOverviewPanel.vue'")
    expect(content).toContain('<ModuleOverviewPanel')
  })

  it('imports ConceptMapPanel', () => {
    expect(content).toContain("import ConceptMapPanel from '../components/knowledge-tree/ConceptMapPanel.vue'")
    expect(content).toContain('<ConceptMapPanel')
  })

  it('imports ColorModeToggle', () => {
    expect(content).toContain("import ColorModeToggle from '../components/knowledge-tree/ColorModeToggle.vue'")
    expect(content).toContain('<ColorModeToggle')
  })

  it('imports RelationReviewPanel', () => {
    expect(content).toContain("import RelationReviewPanel from '../components/knowledge-tree/RelationReviewPanel.vue'")
    expect(content).toContain('<RelationReviewPanel')
  })
})

describe('KnowledgeTreePage composable and store usage', () => {
  it('uses useKnowledgeTree composable', () => {
    expect(content).toContain("import { useKnowledgeTree } from '../components/knowledge-tree/useKnowledgeTree'")
    expect(content).toContain('useKnowledgeTree()')
  })

  it('uses useAuthStore for permission check', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth'")
    expect(content).toContain("authStore.checkPermission('edit_knowledge_tree')")
  })

  it('destructures key refs from useKnowledgeTree', () => {
    expect(content).toContain('navigationData')
    expect(content).toContain('graphData')
    expect(content).toContain('moduleMastery')
    expect(content).toContain('nodesWithMastery')
    expect(content).toContain('qualityIssues')
  })
})

describe('KnowledgeTreePage state management', () => {
  it('initializes activeTab to graph', () => {
    expect(content).toContain("const activeTab = ref('graph')")
  })

  it('initializes colorMode to exam_frequency', () => {
    expect(content).toContain("const colorMode = ref('exam_frequency')")
  })

  it('watches selectedStudentId to toggle colorMode', () => {
    expect(content).toContain('watch(selectedStudentId')
    expect(content).toContain("colorMode.value = 'mastery'")
    expect(content).toContain("colorMode.value = 'exam_frequency'")
  })

  it('forces review tab back to graph when canEdit becomes false', () => {
    expect(content).toContain('watch(canEdit')
    expect(content).toContain("activeTab.value = 'graph'")
  })

  it('defines needsStudentSelector with correct role list', () => {
    expect(content).toContain("'subject_teacher'")
    expect(content).toContain("'homeroom_teacher'")
    expect(content).toContain("'principal'")
    expect(content).toContain("'academic_director'")
    expect(content).toContain("'grade_leader'")
  })
})

describe('KnowledgeTreePage data loading', () => {
  it('calls loadGraph in init', () => {
    const initBlock = content.slice(
      content.indexOf('async function init()'),
      content.indexOf('async function handleModuleSelect')
    )
    expect(initBlock).toContain('await loadGraph()')
  })

  it('calls loadStatsOverview in init', () => {
    const initBlock = content.slice(
      content.indexOf('async function init()'),
      content.indexOf('async function handleModuleSelect')
    )
    expect(initBlock).toContain('await loadStatsOverview()')
  })

  it('conditionally loads quality for editors', () => {
    const initBlock = content.slice(
      content.indexOf('async function init()'),
      content.indexOf('async function handleModuleSelect')
    )
    expect(initBlock).toContain('if (canEdit.value)')
    expect(initBlock).toContain('await loadQuality(')
  })

  it('conditionally loads mastery when student selected', () => {
    const initBlock = content.slice(
      content.indexOf('async function init()'),
      content.indexOf('async function handleModuleSelect')
    )
    expect(initBlock).toContain('if (studentId.value)')
    expect(initBlock).toContain('await loadMastery(')
  })

  it('calls init on mount', () => {
    expect(content).toContain('onMounted(init)')
  })
})

describe('KnowledgeTreePage module navigation', () => {
  it('handleModuleSelect loads graph and quality for module', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleModuleSelect'),
      content.indexOf('async function handleBackToOverview')
    )
    expect(fnBlock).toContain('showCards.value = false')
    expect(fnBlock).toContain('selectedModule.value = mod')
    expect(fnBlock).toContain('await loadGraph(mod)')
    expect(fnBlock).toContain('await loadQuality(mod)')
  })

  it('handleBackToOverview resets to all modules', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleBackToOverview'),
      content.indexOf('async function handleRefreshModule')
    )
    expect(fnBlock).toContain("selectedModule.value = 'all'")
    expect(fnBlock).toContain("await loadGraph('all')")
  })

  it('backToCards resets to card view', () => {
    const fnBlock = content.slice(
      content.indexOf('function backToCards'),
      content.indexOf('function handleNodeClick')
    )
    expect(fnBlock).toContain('showCards.value = true')
    expect(fnBlock).toContain("selectedModule.value = 'all'")
  })
})

describe('KnowledgeTreePage error handling', () => {
  it('wraps handleEdit in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleEdit'),
      content.indexOf('onMounted(init)')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('shows error message on edit failure', () => {
    expect(content).toContain("message.error('编辑失败: ' + e.message)")
  })

  it('shows success message on edit success', () => {
    expect(content).toContain("message.success('图谱已更新')")
  })
})

describe('KnowledgeTreePage review functionality', () => {
  it('handleMarkReviewed sets review status to teacher_reviewed', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleMarkReviewed'),
      content.indexOf('function backToCards')
    )
    expect(fnBlock).toContain("op: 'set_review_status'")
    expect(fnBlock).toContain("status: 'teacher_reviewed'")
  })

  it('tab switch between graph and review views', () => {
    expect(content).toContain('v-model:value="activeTab"')
    expect(content).toContain('name="graph"')
    expect(content).toContain('name="review"')
  })

  it('conditionally shows view tabs for editors', () => {
    expect(content).toContain('v-if="canEdit"')
  })
})
