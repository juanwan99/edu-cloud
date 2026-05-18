<template>
  <div class="knowledge-tree-page">
    <!-- 家长入口：模块卡片（未选择模块时显示） -->
    <ModuleCards
      v-if="showCards"
      :modules="moduleMastery"
      @select="handleModuleSelect"
    />

    <!-- 主视图 -->
    <div v-else class="main-layout">
      <!-- 课程地图模式：无左侧导航，全宽渲染 -->
      <template v-if="viewMode === 'course-map'">
        <div class="course-map-container">
          <div class="view-mode-bar">
            <n-tabs v-model:value="viewMode" type="segment" size="small">
              <n-tab-pane name="course-map" tab="课程地图" />
              <n-tab-pane name="graph-review" tab="图谱视图" />
              <n-tab-pane v-if="canEdit" name="review-workbench" tab="审查工作台" />
            </n-tabs>
          </div>
          <CourseMapOverview
            v-if="courseMapLayer === 'overview'"
            :data="courseMapOverview"
            @select-module="handleCourseMapModuleSelect"
          />
          <ModuleMapView
            v-else-if="courseMapLayer === 'module'"
            :data="courseMapModule"
            @select-unit="handleCourseMapUnitSelect"
            @back="courseMapLayer = 'overview'"
          />
          <StudyUnitDetail
            v-else-if="courseMapLayer === 'unit'"
            :data="courseMapStudyUnit"
            @select-concept="handleCourseMapConceptSelect"
            @back="courseMapLayer = 'module'"
          />
        </div>
      </template>

      <!-- 图谱视图模式：保留原有左侧导航 + G6 图谱 -->
      <template v-else>
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
                <template #icon><n-icon><ArrowLeft :size="14" /></n-icon></template>
                返回模块概览
              </n-button>
            </template>
          </TreeNavPanel>
        </div>
        <div class="graph-side">
          <div class="view-mode-bar">
            <n-tabs v-model:value="viewMode" type="segment" size="small">
              <n-tab-pane name="course-map" tab="课程地图" />
              <n-tab-pane name="graph-review" tab="图谱视图" />
              <n-tab-pane v-if="canEdit" name="review-workbench" tab="审查工作台" />
            </n-tabs>
          </div>
          <template v-if="viewMode === 'graph-review'">
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
            v-if="viewMode === 'review-workbench'"
            :nodes="nodesWithMastery"
            :edges="graphData.edges"
            :quality-issues="qualityIssues"
            :can-edit="canEdit"
            style="flex: 1; min-height: 0"
            @edit="handleEdit"
          />
        </div>
      </template>
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
import { NButton, NTabs, NTabPane, NIcon, useMessage } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useKnowledgeTree } from '../components/knowledge-tree/useKnowledgeTree'
import ModuleCards from '../components/knowledge-tree/ModuleCards.vue'
import TreeNavPanel from '../components/knowledge-tree/TreeNavPanel.vue'
import ModuleOverviewPanel from '../components/knowledge-tree/ModuleOverviewPanel.vue'
import ConceptMapPanel from '../components/knowledge-tree/ConceptMapPanel.vue'
import ColorModeToggle from '../components/knowledge-tree/ColorModeToggle.vue'
import NodeDetailDrawer from '../components/knowledge-tree/NodeDetailDrawer.vue'
import RelationReviewPanel from '../components/knowledge-tree/RelationReviewPanel.vue'
import CourseMapOverview from '../components/knowledge-tree/CourseMapOverview.vue'
import ModuleMapView from '../components/knowledge-tree/ModuleMapView.vue'
import StudyUnitDetail from '../components/knowledge-tree/StudyUnitDetail.vue'

const message = useMessage()
const {
  navigationData, graphData, loading, selectedModule, selectedStudentId, moduleMastery,
  nodesWithMastery, qualityIssues, modulesQuality, statsOverview,
  courseMapOverview, courseMapModule, courseMapStudyUnit,
  loadGraph, loadMastery, loadQuality, loadAllModulesQuality, loadStatsOverview, applyEdit,
  loadCourseMapOverview, loadCourseMapModule, loadCourseMapStudyUnit,
} = useKnowledgeTree()

const viewMode = ref('course-map')
const courseMapLayer = ref('overview')
const showCards = ref(true)
const navCollapsed = ref(false)
const drawerVisible = ref(false)
const selectedNode = ref(null)
const colorMode = ref('exam_frequency')
watch(selectedStudentId, (val) => {
  if (val) {
    colorMode.value = 'mastery'
  } else if (colorMode.value === 'mastery') {
    colorMode.value = 'exam_frequency'
  }
})

const authStore = useAuthStore()
const canEdit = computed(() => authStore.checkPermission('edit_knowledge_tree'))
watch(canEdit, (val) => {
  if (!val && viewMode.value === 'review-workbench') {
    viewMode.value = 'course-map'
  }
})
const needsStudentSelector = computed(() =>
  ['subject_teacher', 'homeroom_teacher', 'school_admin', 'principal', 'academic_director', 'grade_leader'].includes(authStore.roleName)
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
  await loadCourseMapOverview()
  if (canEdit.value && !studentId.value) {
    showCards.value = false
  }
}

async function lazyLoadGraphData() {
  if (graphData.value.nodes.length > 0) return
  await loadGraph()
  await loadStatsOverview()
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
    await loadAllModulesQuality()
  }
  if (studentId.value) {
    await loadMastery(studentId.value)
  }
}

watch(viewMode, async (val) => {
  if (val === 'graph-review' || val === 'review-workbench') {
    await lazyLoadGraphData()
  }
})

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

async function handleCourseMapModuleSelect(moduleId) {
  courseMapLayer.value = 'module'
  await loadCourseMapModule(moduleId)
}

async function handleCourseMapUnitSelect(suId) {
  courseMapLayer.value = 'unit'
  await loadCourseMapStudyUnit(suId)
}

function handleCourseMapConceptSelect(conceptId) {
  const node = nodesWithMastery.value.find(n => n.id === conceptId)
  selectedNode.value = node || { id: conceptId, name: conceptId }
  drawerVisible.value = true
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
  height: 100%;
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
.course-map-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.view-mode-bar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, rgba(255, 255, 255, 0.08));
  flex-shrink: 0;
}
</style>
