<template>
  <div class="dispatch-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">阅卷调度</h2>
        <p class="page-subtitle">分割 → 选择题判分 → AI 阅卷 → 教师校对</p>
      </div>
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 280px"
        @update:value="onExamChange"
      />
    </div>

    <!-- 扫描目录栏 -->
    <div class="scan-bar" v-if="selectedExamId">
      <span class="scan-bar-icon">📁</span>
      <span class="scan-bar-label">扫描目录</span>
      <n-input
        v-model:value="scanRootDir"
        placeholder="输入扫描图片根目录路径"
        size="small"
        style="flex: 1"
      />
      <n-button size="small" type="primary" @click="handleScanDir" :loading="scanLoading">
        扫描
      </n-button>
    </div>

    <!-- 批量操作栏 -->
    <div class="batch-bar" v-if="selectedSubjects.length > 0">
      <n-tag type="success" size="small" round>{{ selectedSubjects.length }}</n-tag>
      <span>个科目已选中</span>
      <n-button size="tiny" type="primary" @click="handleBatchCut" :disabled="!canBatchCut">
        批量切割
      </n-button>
      <n-button size="tiny" type="warning" @click="handleBatchGrade" :disabled="!canBatchGrade">
        批量 AI 阅卷
      </n-button>
    </div>

    <!-- 科目列表 -->
    <div class="subject-table" v-if="selectedExamId">
      <div class="subject-header">
        <span><n-checkbox v-model:checked="selectAll" @update:checked="toggleSelectAll" /></span>
        <span>科目</span>
        <span>阶段</span>
        <span>详情</span>
        <span>统计</span>
        <span>操作</span>
      </div>
      <div
        v-for="s in subjects"
        :key="s.subject_id"
        class="subject-row"
        :class="{ selected: selectedSubjects.includes(s.subject_id) }"
      >
        <span>
          <n-checkbox
            :checked="selectedSubjects.includes(s.subject_id)"
            @update:checked="(v) => toggleSubject(s.subject_id, v)"
          />
        </span>
        <span class="subject-name">{{ s.subject_name }}</span>
        <span>
          <span class="stage-tag" :class="stageClass(s.stage)">{{ stageLabel(s.stage) }}</span>
        </span>
        <span class="detail-text">
          <template v-if="s.stage === 'cutting'">
            切割中 {{ progressPct }}%
          </template>
          <template v-else-if="s.stage === 'idle'">
            {{ scanMatchedDir(s) ? `已识别: ${scanMatchedDir(s)}` : '等待扫描' }}
          </template>
          <template v-else-if="s.stage === 'ready'">
            主观题 <b>{{ s.subjective_total }}</b> 份就绪
          </template>
          <template v-else-if="s.stage === 'ai_grading'">
            AI 阅卷中 <b>{{ s.ai_graded }}</b> 完成
          </template>
          <template v-else-if="s.stage === 'reviewing'">
            校对 <b>{{ s.reviewed }}/{{ s.ai_graded }}</b>
          </template>
          <template v-else-if="s.stage === 'failed'">
            <span class="detail-highlight">失败 {{ s.ai_failed }} 份</span>
          </template>
          <template v-else-if="s.stage === 'done'">
            全部完成 ✓
          </template>
        </span>
        <span class="detail-text">
          扫 <b>{{ s.scan_images }}</b>
          · 客 <b>{{ s.objective_graded }}</b>
          · 主 <b>{{ s.subjective_total }}</b>
        </span>
        <span class="actions">
          <n-button
            v-if="s.stage === 'idle' && scanMatchedDir(s)"
            size="tiny" type="primary"
            @click="handleStartCut(s)"
          >切割</n-button>
          <n-button
            v-if="s.stage === 'ready'"
            size="tiny" type="warning"
            @click="handleStartGrade(s)"
            :loading="gradingLoading === s.subject_id"
          >AI 阅卷</n-button>
          <n-button
            v-if="s.stage === 'failed'"
            size="tiny" type="error"
            @click="handleStartGrade(s)"
          >重试</n-button>
          <n-button
            v-if="s.stage === 'reviewing'"
            size="tiny"
            @click="$router.push({ name: 'MarkingSelect' })"
          >去校对</n-button>
          <n-button
            v-if="s.stage === 'cutting'"
            size="tiny" type="error"
            @click="handleStopCut"
          >停止</n-button>
        </span>
      </div>
      <div v-if="subjects.length === 0" class="empty-state">
        {{ loading ? '加载中...' : '暂无科目数据' }}
      </div>
    </div>

    <div v-else class="empty-state" style="margin-top: 40px; text-align: center; color: #8a9a8e;">
      请先选择一个考试
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NSelect, NInput, NButton, NCheckbox, NTag } from 'naive-ui'
import { listExams } from '../api/exams'
import { getDispatchStatus, createTask } from '../api/grading'
import { scanDirectory, startPipeline, getPipelineProgress, stopPipeline } from '../api/scan'

const selectedExamId = ref(null)
const examOptions = ref([])
const subjects = ref([])
const selectedSubjects = ref([])
const selectAll = ref(false)
const loading = ref(false)

// 扫描
const scanRootDir = ref('')
const scanLoading = ref(false)
const scanResults = ref([]) // [{name, folder, image_count, ...}]

// 进度轮询
const progressPct = ref(0)
let pollTimer = null

// 阅卷
const gradingLoading = ref(null)

// 加载考试列表
onMounted(async () => {
  try {
    const res = await listExams()
    examOptions.value = (res.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch (e) {
    console.error('加载考试列表失败', e)
  }
})

onUnmounted(() => {
  stopPolling()
})

async function onExamChange(examId) {
  selectedSubjects.value = []
  selectAll.value = false
  if (!examId) {
    subjects.value = []
    return
  }
  await loadStatus(examId)
}

async function loadStatus(examId) {
  loading.value = true
  try {
    const res = await getDispatchStatus(examId)
    subjects.value = res.data || []
  } catch (e) {
    console.error('加载状态失败', e)
    subjects.value = []
  } finally {
    loading.value = false
  }
}

// 扫描目录
async function handleScanDir() {
  if (!scanRootDir.value) return
  scanLoading.value = true
  try {
    const res = await scanDirectory(scanRootDir.value)
    scanResults.value = res.data?.subjects || []
  } catch (e) {
    console.error('扫描失败', e)
  } finally {
    scanLoading.value = false
  }
}

function scanMatchedDir(subjectStatus) {
  // 按科目名称匹配扫描目录中的文件夹
  const match = scanResults.value.find(
    r => r.name === subjectStatus.subject_name || r.folder === subjectStatus.subject_name
  )
  return match ? `${match.folder} (${match.image_count} 张)` : null
}

function getScanDir(subjectStatus) {
  const match = scanResults.value.find(
    r => r.name === subjectStatus.subject_name || r.folder === subjectStatus.subject_name
  )
  if (!match) return null
  const base = scanRootDir.value.replace(/\/$/, '')
  return match.folder === '.' ? base : `${base}/${match.folder}`
}

// 切割
async function handleStartCut(s) {
  const dir = getScanDir(s)
  if (!dir) return
  try {
    await startPipeline(s.subject_id, 'A', dir)
    startPolling()
    await loadStatus(selectedExamId.value)
  } catch (e) {
    console.error('启动切割失败', e)
  }
}

async function handleStopCut() {
  try {
    await stopPipeline()
  } catch (e) {
    console.error('停止失败', e)
  }
  stopPolling()
  await loadStatus(selectedExamId.value)
}

// 批量切割
const canBatchCut = computed(() =>
  selectedSubjects.value.some(id => {
    const s = subjects.value.find(x => x.subject_id === id)
    return s && s.stage === 'idle' && scanMatchedDir(s)
  })
)

async function handleBatchCut() {
  for (const id of selectedSubjects.value) {
    const s = subjects.value.find(x => x.subject_id === id)
    if (s && s.stage === 'idle' && getScanDir(s)) {
      await startPipeline(s.subject_id, 'A', getScanDir(s))
    }
  }
  startPolling()
  await loadStatus(selectedExamId.value)
}

// AI 阅卷
async function handleStartGrade(s) {
  gradingLoading.value = s.subject_id
  try {
    await createTask({ subject_id: s.subject_id })
    await loadStatus(selectedExamId.value)
  } catch (e) {
    console.error('创建阅卷任务失败', e)
  } finally {
    gradingLoading.value = null
  }
}

const canBatchGrade = computed(() =>
  selectedSubjects.value.some(id => {
    const s = subjects.value.find(x => x.subject_id === id)
    return s && s.stage === 'ready'
  })
)

async function handleBatchGrade() {
  for (const id of selectedSubjects.value) {
    const s = subjects.value.find(x => x.subject_id === id)
    if (s && s.stage === 'ready') {
      try {
        await createTask({ subject_id: s.subject_id })
      } catch (e) {
        console.error(`阅卷任务创建失败: ${s.subject_name}`, e)
      }
    }
  }
  await loadStatus(selectedExamId.value)
}

// 选择
function toggleSubject(id, checked) {
  if (checked) {
    selectedSubjects.value.push(id)
  } else {
    selectedSubjects.value = selectedSubjects.value.filter(x => x !== id)
  }
  selectAll.value = selectedSubjects.value.length === subjects.value.length
}

function toggleSelectAll(checked) {
  if (checked) {
    selectedSubjects.value = subjects.value.map(s => s.subject_id)
  } else {
    selectedSubjects.value = []
  }
}

// 进度轮询
function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await getPipelineProgress()
      const p = res.data
      if (p.total > 0) {
        progressPct.value = Math.round((p.processed / p.total) * 100)
      }
      if (p.status !== 'running') {
        stopPolling()
        await loadStatus(selectedExamId.value)
      }
    } catch (e) {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 阶段标签
const STAGE_MAP = {
  idle: { label: '待扫描', cls: 'stage-idle' },
  cutting: { label: '切割中', cls: 'stage-cutting' },
  ready: { label: '待阅卷', cls: 'stage-ready' },
  ai_grading: { label: 'AI 阅卷', cls: 'stage-ai-grading' },
  reviewing: { label: '校对中', cls: 'stage-reviewing' },
  failed: { label: '失败', cls: 'stage-failed' },
  done: { label: '已完成', cls: 'stage-done' },
}

function stageLabel(stage) {
  return STAGE_MAP[stage]?.label || stage
}
function stageClass(stage) {
  return STAGE_MAP[stage]?.cls || 'stage-idle'
}
</script>

<style scoped>
.dispatch-page {
  padding: 4px 0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.page-subtitle {
  font-size: 13px;
  color: var(--text-color-3, #8a9a8e);
  margin-top: 2px;
}
.scan-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--card-color, #fff);
  border: 1px solid var(--border-color, #e2e8e4);
  border-radius: 12px;
  padding: 8px 14px;
  margin-bottom: 10px;
}
.scan-bar-icon { font-size: 14px; }
.scan-bar-label { font-weight: 600; font-size: 13px; }
.batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #e8f8ee;
  border: 1px solid #b8e6c8;
  border-radius: 12px;
  padding: 6px 14px;
  margin-bottom: 10px;
  font-size: 13px;
}
.subject-table {
  background: var(--card-color, #fff);
  border: 1px solid var(--border-color, #e2e8e4);
  border-radius: 16px;
  overflow: hidden;
}
.subject-header {
  display: grid;
  grid-template-columns: 36px 80px 80px 1fr 1fr 140px;
  padding: 8px 14px;
  background: var(--body-color, #f9fafb);
  border-bottom: 1px solid var(--border-color, #e2e8e4);
  gap: 4px;
  font-size: 12px;
  color: var(--text-color-3, #8a9a8e);
  font-weight: 500;
}
.subject-row {
  display: grid;
  grid-template-columns: 36px 80px 80px 1fr 1fr 140px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--divider-color, #f0f4f1);
  align-items: center;
  gap: 4px;
  transition: background 0.15s;
}
.subject-row:last-child { border-bottom: none; }
.subject-row:hover { background: var(--body-color, #f9fafb); }
.subject-row.selected { background: #f0faf3; }
.subject-name { font-weight: 700; font-size: 13px; }
.stage-tag {
  display: inline-block;
  padding: 1px 9px;
  border-radius: 50px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.stage-idle { background: #f3f4f6; color: #6b7280; }
.stage-cutting { background: #ecf6ff; color: #0c4a6e; }
.stage-ready { background: #f3f0ff; color: #5b21b6; }
.stage-ai-grading { background: #fdf6e3; color: #854d0e; }
.stage-reviewing { background: #fef0f0; color: #991b1b; }
.stage-failed { background: #fef0f0; color: #dc2626; }
.stage-done { background: #e8f8ee; color: #166534; }
.detail-text { font-size: 12px; color: var(--text-color-2, #5a6b5e); }
.detail-text b { font-weight: 600; }
.detail-highlight { color: #dc2626; font-weight: 600; }
.actions { display: flex; gap: 4px; }
.empty-state {
  padding: 40px;
  text-align: center;
  color: var(--text-color-3, #8a9a8e);
  font-size: 14px;
}
</style>
