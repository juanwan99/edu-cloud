<template>
  <div class="knowledge-tree-page">
    <!-- 家长入口：模块卡片（未选择模块时显示） -->
    <ModuleCards
      v-if="showCards"
      :modules="moduleMastery"
      @select="handleModuleSelect"
    />

    <!-- 主视图：左侧导航 + 右侧图谱 -->
    <div v-else class="main-layout">
      <div class="nav-side" :class="{ collapsed: navCollapsed }">
        <TreeNavPanel
          :navigation="navigationData"
          :module-mastery="moduleMastery"
          :nodes-with-mastery="nodesWithMastery"
          :selected-module="selectedModule"
          @select-module="handleModuleSelect"
          @select-node="handleNodeClick"
        >
          <template #student-selector>
            <n-button size="small" quaternary @click="backToCards" style="margin-bottom: 8px">
              ← 返回模块概览
            </n-button>
          </template>
        </TreeNavPanel>
      </div>
      <div class="graph-side">
        <div class="view-tabs" v-if="canEdit">
          <n-tabs v-model:value="activeTab" type="segment" size="small">
            <n-tab-pane name="graph" tab="图谱视图" />
            <n-tab-pane name="review" tab="审查工作台" />
          </n-tabs>
        </div>
        <template v-if="activeTab === 'graph'">
          <ModuleOverviewPanel
            v-if="selectedModule === 'all'"
            :navigation="navigationData"
            :nodes="nodesWithMastery"
            :edges="graphData.edges"
            :modules-quality="modulesQuality"
            :stats-overview="statsOverview"
            style="flex: 1; min-height: 0"
            @select-module="handleModuleSelect"
            @refresh-quality="loadAllModulesQuality"
          />
          <template v-else>
            <div class="graph-tools">
              <ColorModeToggle
                v-model="colorMode"
                :has-student="!!selectedStudentId"
              />
            </div>
            <ConceptMapPanel
              :module-id="selectedModule"
              :module-name="currentModuleName"
              :nodes="nodesWithMastery"
              :edges="graphData.edges"
              :navigation="navigationData"
              :quality-issues="qualityIssues"
              :can-edit="canEdit"
              :color-mode="colorMode"
              :nodes-with-mastery="nodesWithMastery"
              style="flex: 1; min-height: 0"
              @back-to-overview="handleBackToOverview"
              @refresh="handleRefreshModule"
              @node-click="handleNodeClick"
              @view-detail="handleNodeClick"
              @mark-reviewed="handleMarkReviewed"
            />
          </template>
        </template>
        <RelationReviewPanel
          v-if="activeTab === 'review'"
          :nodes="nodesWithMastery"
          :edges="graphData.edges"
          :quality-issues="qualityIssues"
          :can-edit="canEdit"
          style="flex: 1; min-height: 0"
          @edit="handleEdit"
        />
      </div>
    </div>

    <!-- 节点详情抽屉 -->
    <NodeDetailDrawer
      v-model:show="drawerVisible"
      :node="selectedNode"
      :can-edit="canEdit"
      @edit="handleEdit"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NButton, NTabs, NTabPane, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useKnowledgeTree } from '../components/knowledge-tree/useKnowledgeTree'
import ModuleCards from '../components/knowledge-tree/ModuleCards.vue'
import TreeNavPanel from '../components/knowledge-tree/TreeNavPanel.vue'
import ModuleOverviewPanel from '../components/knowledge-tree/ModuleOverviewPanel.vue'
import ConceptMapPanel from '../components/knowledge-tree/ConceptMapPanel.vue'
import ColorModeToggle from '../components/knowledge-tree/ColorModeToggle.vue'
import NodeDetailDrawer from '../components/knowledge-tree/NodeDetailDrawer.vue'
import RelationReviewPanel from '../components/knowledge-tree/RelationReviewPanel.vue'

const message = useMessage()
const {
  navigationData, graphData, loading, selectedModule, selectedStudentId, moduleMastery,
  nodesWithMastery, qualityIssues, modulesQuality, statsOverview,
  loadGraph, loadMastery, loadQuality, loadAllModulesQuality, loadStatsOverview, applyEdit,
} = useKnowledgeTree()

const activeTab = ref('graph')
const showCards = ref(true)
const navCollapsed = ref(false)
const drawerVisible = ref(false)
const selectedNode = ref(null)
// Phase 1 T10: 节点着色模式
const colorMode = ref('exam_frequency')
// 学生选择变化时自动切换 colorMode：选中学生 → mastery；取消选中 → 退回 exam_frequency
watch(selectedStudentId, (val) => {
  if (val) {
    colorMode.value = 'mastery'
  } else if (colorMode.value === 'mastery') {
    colorMode.value = 'exam_frequency'
  }
})

const authStore = useAuthStore()
const canEdit = computed(() => authStore.checkPermission('edit_knowledge_tree'))
// 权限收窄时强制回退到图谱视图
watch(canEdit, (val) => {
  if (!val && activeTab.value === 'review') {
    activeTab.value = 'graph'
  }
})
const needsStudentSelector = computed(() =>
  ['subject_teacher', 'homeroom_teacher', 'principal', 'academic_director', 'grade_leader'].includes(authStore.roleName)
)
const studentId = computed(() => {
  if (!needsStudentSelector.value) return null
  return selectedStudentId.value
})

const currentModuleName = computed(() => {
  const mod = navigationData.value.find(m => m.id === selectedModule.value)
  return mod?.name ?? selectedModule.value
})

async function init() {
  await loadGraph()
  await loadStatsOverview()
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
    await loadAllModulesQuality()
  }
  // student_id 为空时跳过掌握度加载（教师未选学生 / 家长未绑定）
  if (studentId.value) {
    await loadMastery(studentId.value)
  }
  // 教师 / 管理员（canEdit=true）→ 默认直接进入 main-layout（Phase 2 教师工作台入口）
  // 覆盖 platform_admin / district_admin / principal / academic_director / subject_teacher / homeroom_teacher 等
  // 家长 / 学生（canEdit=false）保留 ModuleCards 掌握度欢迎页
  if (canEdit.value && !studentId.value) {
    showCards.value = false
  }
}

async function handleModuleSelect(mod) {
  showCards.value = false
  selectedModule.value = mod
  await loadGraph(mod)
  if (canEdit.value) {
    // F-002 修复：qualityIssues 是 RelationReviewPanel 的数据源，必须跟随当前作用域刷新
    await loadQuality(mod)
    if (mod === 'all') {
      await loadAllModulesQuality()
    }
  }
}

async function handleBackToOverview() {
  selectedModule.value = 'all'
  await loadGraph('all')
  if (canEdit.value) {
    // F-002 修复：同步刷新 qualityIssues，避免 RelationReviewPanel 停留在上一个模块的数据
    await loadQuality('all')
    await loadAllModulesQuality()
  }
}

async function handleRefreshModule() {
  await loadGraph(selectedModule.value)
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
  }
}

async function handleMarkReviewed(concept) {
  // 推进 review_status: ai_draft → teacher_reviewed
  await handleEdit([{
    op: 'set_review_status', id: concept.id, status: 'teacher_reviewed',
  }])
}

function backToCards() {
  showCards.value = true
  selectedModule.value = 'all'
  loadGraph('all')
}

function handleNodeClick(node) {
  selectedNode.value = node
  drawerVisible.value = true
}

async function handleEdit(operations) {
  try {
    await applyEdit(operations)
    message.success('图谱已更新')
    if (canEdit.value) {
      await loadQuality(selectedModule.value)
    }
    if (studentId.value) {
      await loadMastery(studentId.value, selectedModule.value)
    }
  } catch (e) {
    message.error('编辑失败: ' + e.message)
  }
}

onMounted(init)
</script>

<style scoped>
.knowledge-tree-page {
  height: calc(100dvh - 64px);
  overflow: hidden;
}
.main-layout {
  display: flex;
  height: 100%;
}
.nav-side {
  width: 280px;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  overflow-y: auto;
  flex-shrink: 0;
}
.nav-side.collapsed {
  width: 0;
  overflow: hidden;
}
.graph-side {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
}
.view-tabs {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}
.graph-tools {
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}
</style>
