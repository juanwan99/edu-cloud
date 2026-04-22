<template>
  <div class="dispatch-page">
    <div class="top-bar">
      <div>
        <h2 class="page-title">阅卷调度</h2>
        <p class="page-subtitle">扫描切割 → 选择题判分 → AI 阅卷 → 教师校对</p>
      </div>
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 300px"
        @update:value="onExamChange"
      />
    </div>

    <template v-if="selectedExamId">
      <!-- 汇总条 -->
      <div class="summary-bar" v-if="subjects.length > 0">
        <div class="summary-item">
          <span class="summary-num">{{ subjects.length }}</span>
          <span class="summary-label">科目</span>
        </div>
        <div class="summary-item" v-for="g in stageGroups" :key="g.key">
          <span class="summary-num" :class="g.key">{{ g.count }}</span>
          <span class="summary-label">{{ g.label }}</span>
        </div>
      </div>

      <!-- 扫描区（可折叠） -->
      <div class="scan-section">
        <div class="scan-header" @click="scanExpanded = !scanExpanded">
          <span class="scan-toggle">{{ scanExpanded ? '▾' : '▸' }}</span>
          <span class="scan-title">扫描目录</span>
          <span class="scan-hint" v-if="scanResults.length > 0">已识别 {{ scanResults.length }} 个科目</span>
        </div>
        <div class="scan-body" v-if="scanExpanded">
          <div class="scan-row">
            <n-button size="small" type="primary" @click="pickFolder" :loading="uploadLoading">
              {{ uploadLoading ? `上传中 ${uploadProgress}` : '选择扫描文件夹' }}
            </n-button>
            <span class="scan-status" v-if="scanRootDir">{{ scanRootDir }}</span>
            <n-button v-if="scanRootDir" size="small" @click="handleScanDir" :loading="scanLoading">识别科目</n-button>
          </div>
          <input ref="folderInput" type="file" webkitdirectory multiple style="display:none" @change="handleFolderSelected" />
          <div class="upload-hint" v-if="!scanRootDir">选择包含扫描图片的文件夹，按科目子文件夹组织（如 语文/、数学/）</div>
        </div>
      </div>

      <!-- 一键全科检测（仅教务主任+） -->
      <div class="batch-bar" v-if="canManageAll && detectableSubjects.length > 0 && scanResults.length > 0">
        <n-button size="small" @click="handleBatchDetect" :loading="batchDetectLoading">
          一键全科检测（{{ detectableSubjects.length }} 科）
        </n-button>
      </div>

      <!-- 批量操作 -->
      <div class="batch-bar" v-if="selectedSubjects.length > 0">
        <span>已选 <b>{{ selectedSubjects.length }}</b> 科</span>
        <n-button size="tiny" type="primary" @click="handleBatchCut" :disabled="!canBatchCut">批量切割</n-button>
        <n-button size="tiny" type="warning" @click="handleBatchGrade" :disabled="!canBatchGrade">批量 AI 阅卷</n-button>
      </div>

      <!-- 科目卡片 -->
      <div class="subject-list">
        <div
          v-for="s in subjects" :key="s.subject_id"
          class="subject-card"
          :class="{ selected: selectedSubjects.includes(s.subject_id) }"
        >
          <div class="card-left">
            <n-checkbox
              :checked="selectedSubjects.includes(s.subject_id)"
              @update:checked="(v) => toggleSubject(s.subject_id, v)"
            />
            <span class="card-name">{{ s.subject_name }}</span>
            <span class="stage-tag" :class="stageClass(s.stage)">{{ stageLabel(s.stage) }}</span>
          </div>

          <div class="card-mid">
            <template v-if="s.stage === 'cutting'">
              <div class="prog-row">
                <div class="prog-bar"><div class="prog-fill" :style="{ width: progressPct + '%' }"></div></div>
                <span class="prog-text">{{ progressPct }}%</span>
              </div>
            </template>
            <template v-else-if="s.stage === 'idle'">
              <span class="card-detail" v-if="scanMatchedDir(s)">{{ scanMatchedDir(s) }}</span>
              <span class="card-detail muted" v-else>等待扫描目录</span>
            </template>
            <template v-else-if="s.stage === 'ready'">
              <span class="card-detail">主观题 <b>{{ s.subjective_total }}</b> 份就绪</span>
            </template>
            <template v-else-if="s.stage === 'ai_grading'">
              <div class="prog-row">
                <div class="prog-bar"><div class="prog-fill warn" :style="{ width: s.subjective_total ? (s.ai_graded/s.subjective_total*100)+'%' : '0%' }"></div></div>
                <span class="prog-text">{{ s.ai_graded }}/{{ s.subjective_total }}</span>
              </div>
            </template>
            <template v-else-if="s.stage === 'reviewing'">
              <div class="prog-row">
                <div class="prog-bar"><div class="prog-fill purple" :style="{ width: s.ai_graded ? (s.reviewed/s.ai_graded*100)+'%' : '0%' }"></div></div>
                <span class="prog-text">校对 {{ s.reviewed }}/{{ s.ai_graded }}</span>
              </div>
            </template>
            <template v-else-if="s.stage === 'failed'">
              <span class="card-detail err">{{ s.ai_failed }} 份失败</span>
            </template>
            <template v-else-if="s.stage === 'done'">
              <span class="card-detail ok">全部完成</span>
            </template>
          </div>

          <div class="card-stats">
            <span title="扫描">{{ s.scan_images }} 扫</span>
            <span title="客观题">{{ s.objective_graded }} 客</span>
            <span title="主观题">{{ s.subjective_total }} 主</span>
          </div>

          <div class="card-actions">
            <n-button v-if="canDetect(s)" size="small" @click="handleDetectTemplate(s)" :loading="detectLoading === s.subject_id">模板检测</n-button>
            <n-button v-if="canCut(s)" size="small" type="primary" @click="handleStartCut(s)">切割</n-button>
            <n-button v-if="s.stage === 'cutting'" size="small" type="error" @click="handleStopCut">停止</n-button>
            <n-button v-if="s.stage === 'ready'" size="small" type="warning" @click="handleStartGrade(s)" :loading="gradingLoading === s.subject_id">AI 阅卷</n-button>
            <n-button v-if="s.stage === 'failed'" size="small" type="error" @click="handleStartGrade(s)">重试</n-button>
            <n-button v-if="s.stage === 'reviewing'" size="small" @click="$router.push({ name: 'MarkingSelect' })">去校对</n-button>
          </div>
        </div>

        <div v-if="subjects.length === 0" class="empty-state">
          {{ loading ? '加载中...' : '暂无科目数据' }}
        </div>
      </div>
    </template>

    <div v-else class="empty-state">请先选择一个考试</div>

    <TemplatePreviewEditor
      v-model:show="editorShow"
      :blob-url="editorBlobUrl"
      :blob-url-b="editorBlobUrlB"
      :regions="editorRegions"
      :regions-b="editorRegionsB"
      :image-width="editorWidth"
      :image-height="editorHeight"
      :image-width-b="editorWidthB"
      :image-height-b="editorHeightB"
      @confirm="onEditorConfirm"
      @cancel="editorShow = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NSelect, NButton, NCheckbox } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { listExams } from '../api/exams'
import { getDispatchStatus, createTask } from '../api/grading'
import { uploadScanFolder, scanDirectory, startPipeline, getPipelineProgress, stopPipeline, autoDetectCV, saveCVTemplate, fetchScanImageBlob } from '../api/scan'
import TemplatePreviewEditor from '../components/TemplatePreviewEditor.vue'

const message = useMessage()
const auth = useAuthStore()

const canManageAll = computed(() => SCHOOL_ADMIN_ROLES.includes(auth.roleName))
const mySubjectCodes = computed(() => auth.currentRole?.subject_codes || null)

const selectedExamId = ref(null)
const examOptions = ref([])
const allSubjects = ref([])
const subjects = computed(() => {
  if (canManageAll.value || !mySubjectCodes.value) return allSubjects.value
  return allSubjects.value.filter(s => mySubjectCodes.value.includes(s.subject_code))
})
const selectedSubjects = ref([])
const loading = ref(false)

const scanRootDir = ref('')
const scanLoading = ref(false)
const scanResults = ref([])
const scanExpanded = ref(true)

const folderInput = ref(null)
const uploadLoading = ref(false)
const uploadProgress = ref('')

const progressPct = ref(0)
let pollTimer = null
const detectLoading = ref(null)
const gradingLoading = ref(null)

function countByStage(stage) {
  return subjects.value.filter(s => s.stage === stage).length
}

const stageGroups = computed(() => {
  const defs = [
    { key: 'done', label: '已完成' },
    { key: 'active', label: '阅卷中', stages: ['ai_grading', 'reviewing'] },
    { key: 'ready', label: '待阅卷' },
    { key: 'idle', label: '待扫描' },
    { key: 'failed', label: '失败' },
  ]
  return defs.map(d => ({
    ...d,
    count: d.stages ? d.stages.reduce((n, st) => n + countByStage(st), 0) : countByStage(d.key),
  })).filter(g => g.count > 0)
})
onMounted(async () => {
  try {
    const res = await listExams()
    examOptions.value = (res.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch (e) {
    message.error('加载考试列表失败')
  }
})

onUnmounted(() => {
  stopPolling()
})

async function onExamChange(examId) {
  selectedSubjects.value = []
  scanResults.value = []
  scanRootDir.value = ''
  if (!examId) {
    allSubjects.value = []
    return
  }
  await loadStatus(examId)
  await tryAutoDetectScanDir(examId)
}

async function tryAutoDetectScanDir(examId) {
  const path = `/home/ops/projects/edu-cloud/uploads/scan-input/${examId}`
  try {
    const res = await scanDirectory(path)
    const subs = res.data?.subjects || []
    if (subs.length > 0) {
      scanRootDir.value = path
      scanResults.value = subs
      scanExpanded.value = false
    }
  } catch (e) { /* 目录不存在 */ }
}

async function loadStatus(examId) {
  loading.value = true
  try {
    const res = await getDispatchStatus(examId)

    allSubjects.value = res.data || []
  } catch (e) {
    message.error('加载阅卷状态失败')
    allSubjects.value = []
  } finally {
    loading.value = false
  }
}

// 文件夹上传
function pickFolder() {
  folderInput.value?.click()
}

async function handleFolderSelected(e) {
  const files = Array.from(e.target.files || [])
  if (files.length === 0) return

  const imageFiles = files.filter(f =>
    /\.(png|jpg|jpeg|bmp)$/i.test(f.name)
  )
  if (imageFiles.length === 0) {
    message.warning('未找到图片文件（支持 png/jpg/bmp）')
    return
  }

  uploadLoading.value = true
  uploadProgress.value = `0/${imageFiles.length}`
  try {
    const res = await uploadScanFolder(selectedExamId.value, imageFiles, (done, total) => {
      uploadProgress.value = `${done}/${total}`
    })
    scanRootDir.value = res.data.dir_path
    message.success(`已上传 ${imageFiles.length} 张图片`)
    await handleScanDir()
  } catch (err) {
    message.error('上传失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    uploadLoading.value = false
    e.target.value = ''
  }
}

// 切割/检测可用性（idle 或 ready 阶段 + 有匹配的扫描目录）
const CUTTABLE_STAGES = ['idle', 'ready']
function canCut(s) {
  return CUTTABLE_STAGES.includes(s.stage) && scanMatchedDir(s)
}
function canDetect(s) {
  if (!CUTTABLE_STAGES.includes(s.stage) || !scanMatchedDir(s)) return false
  if (canManageAll.value) return true
  if (!mySubjectCodes.value) return false
  return mySubjectCodes.value.includes(s.subject_code)
}

const detectableSubjects = computed(() => subjects.value.filter(s => canDetect(s)))

// 扫描目录
async function handleScanDir() {
  if (!scanRootDir.value) return
  scanLoading.value = true
  try {
    const res = await scanDirectory(scanRootDir.value)
    scanResults.value = res.data?.subjects || []
    if (scanResults.value.length > 0) scanExpanded.value = false
  } catch (e) {
    message.error('扫描失败: ' + (e.response?.data?.detail || e.message))
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

// 模板编辑器状态
const editorShow = ref(false)
const editorBlobUrl = ref(null)
const editorBlobUrlB = ref(null)
const editorRegions = ref([])
const editorRegionsB = ref(null)
const editorWidth = ref(0)
const editorHeight = ref(0)
const editorWidthB = ref(0)
const editorHeightB = ref(0)
const editorSubjectId = ref(null)

function findFirstFile(dir, side) {
  const files = scanResults.value.find(r => r.name === dir || r.folder === dir)
  if (!files || !files.first_file) return null
  return files.first_file.replace(/[AB]\.png$/, side + '.png')
}

// 模板检测 → 打开编辑器（A 面 + 可选 B 面）
async function handleDetectTemplate(s) {
  const dir = getScanDir(s)
  if (!dir) return
  detectLoading.value = s.subject_id
  try {
    const fileA = `${dir}/${scanFirstFile(s)}`
    const fileB = fileA.replace(/A\.png$/, 'B.png')

    // A 面：检测 + 加载图
    const [detectA, blobA] = await Promise.all([
      autoDetectCV(fileA),
      fetchScanImageBlob(fileA),
    ])
    const dataA = detectA.data

    // B 面：带 A 面上下文检测（题号延续）
    let dataB = null, blobB = null
    try {
      const [detectB, blobBRes] = await Promise.all([
        autoDetectCV(fileB, { priorRegions: dataA.regions }),
        fetchScanImageBlob(fileB),
      ])
      dataB = detectB.data
      blobB = blobBRes
    } catch (_) { /* 无 B 面 */ }

    if ((!dataA.regions || dataA.regions.length === 0) && (!dataB?.regions || dataB.regions.length === 0)) {
      message.warning(`${s.subject_name}: 未检测到区域，可手动框选`)
    }

    editorBlobUrl.value = blobA
    editorRegions.value = dataA.regions || []
    editorWidth.value = dataA.width
    editorHeight.value = dataA.height

    editorBlobUrlB.value = blobB
    editorRegionsB.value = dataB?.regions || null
    editorWidthB.value = dataB?.width || 0
    editorHeightB.value = dataB?.height || 0

    editorSubjectId.value = s.subject_id
    editorShow.value = true
  } catch (e) {
    message.error(`模板检测失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    detectLoading.value = null
  }
}

async function onEditorConfirm({ A, B }) {
  editorShow.value = false
  try {
    const saves = [saveCVTemplate(editorSubjectId.value, 'A', A, editorWidth.value, editorHeight.value)]
    if (B) saves.push(saveCVTemplate(editorSubjectId.value, 'B', B, editorWidthB.value, editorHeightB.value))
    await Promise.all(saves)
    const total = A.length + (B ? B.length : 0)
    message.success(`模板已保存（A 面 ${A.length} 区${B ? `，B 面 ${B.length} 区` : ''}）`)
    if (editorBlobUrl.value) { URL.revokeObjectURL(editorBlobUrl.value); editorBlobUrl.value = null }
    if (editorBlobUrlB.value) { URL.revokeObjectURL(editorBlobUrlB.value); editorBlobUrlB.value = null }
  } catch (e) {
    message.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 一键全科检测（串行，直接保存不逐科打开编辑器）
const batchDetectLoading = ref(false)
async function handleBatchDetect() {
  const list = detectableSubjects.value
  if (!list.length) return
  batchDetectLoading.value = true
  let ok = 0, fail = 0
  for (const s of list) {
    try {
      const dir = getScanDir(s)
      if (!dir) continue
      const fileA = `${dir}/${scanFirstFile(s)}`
      const fileB = fileA.replace(/A\.png$/, 'B.png')

      const detectA = (await autoDetectCV(fileA)).data
      if (detectA.regions?.length) {
        await saveCVTemplate(s.subject_id, 'A', detectA.regions, detectA.width, detectA.height)
      }

      try {
        const detectB = (await autoDetectCV(fileB, { priorRegions: detectA.regions })).data
        if (detectB.regions?.length) {
          await saveCVTemplate(s.subject_id, 'B', detectB.regions, detectB.width, detectB.height)
        }
      } catch (_) { /* 无 B 面 */ }

      ok++
    } catch (_) {
      fail++
    }
  }
  batchDetectLoading.value = false
  message.success(`全科检测完成：${ok} 科成功${fail ? `，${fail} 科失败` : ''}`)
}

function scanFirstFile(subjectStatus) {
  const match = scanResults.value.find(
    r => r.name === subjectStatus.subject_name || r.folder === subjectStatus.subject_name
  )
  return match?.first_file || ''
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
    message.error('启动切割失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function handleStopCut() {
  try {
    await stopPipeline()
  } catch (e) {
    message.error('停止��败')
  }
  stopPolling()
  await loadStatus(selectedExamId.value)
}

// 批量切割
const canBatchCut = computed(() =>
  selectedSubjects.value.some(id => {
    const s = subjects.value.find(x => x.subject_id === id)
    return s && canCut(s)
  })
)

async function handleBatchCut() {
  for (const id of selectedSubjects.value) {
    const s = subjects.value.find(x => x.subject_id === id)
    if (s && canCut(s) && getScanDir(s)) {
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
    message.error('创建阅卷任务失败: ' + (e.response?.data?.detail || e.message))
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
        message.error(`阅卷任务创建失���: ${s.subject_name}`)
      }
    }
  }
  await loadStatus(selectedExamId.value)
}

function toggleSubject(id, checked) {
  if (checked) {
    selectedSubjects.value.push(id)
  } else {
    selectedSubjects.value = selectedSubjects.value.filter(x => x !== id)
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

const STAGE_LABELS = {
  idle: '待扫描', cutting: '切割中', ready: '待阅卷',
  ai_grading: 'AI 阅卷', reviewing: '校对中', failed: '失败', done: '已完成',
}
function stageLabel(stage) { return STAGE_LABELS[stage] || stage }
function stageClass(stage) { return `tag-${stage}` }
</script>

<style scoped>
.dispatch-page { padding: 4px 0; }
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }
.page-subtitle { font-size: 13px; color: #8a9a8e; margin-top: 2px; }

.summary-bar { display: flex; gap: 24px; padding: 12px 20px; background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: 12px; margin-bottom: 12px; }
.summary-item { display: flex; align-items: baseline; gap: 4px; }
.summary-num { font-size: 20px; font-weight: 800; color: #333; }
.summary-num.done { color: #16a34a; }
.summary-num.active { color: #d97706; }
.summary-num.ready { color: #7c3aed; }
.summary-num.idle { color: #9ca3af; }
.summary-num.failed { color: #dc2626; }
.summary-label { font-size: 12px; color: #8a9a8e; }

.scan-section { background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: 12px; margin-bottom: 12px; overflow: hidden; }
.scan-header { display: flex; align-items: center; gap: 8px; padding: 10px 16px; cursor: pointer; user-select: none; }
.scan-header:hover { background: var(--body-color, #f9fafb); }
.scan-toggle { font-size: 12px; color: #8a9a8e; width: 14px; }
.scan-title { font-weight: 600; font-size: 13px; }
.scan-hint { font-size: 12px; color: #16a34a; margin-left: auto; }
.scan-body { padding: 0 16px 12px; }
.scan-row { display: flex; gap: 8px; }

.batch-bar { display: flex; align-items: center; gap: 10px; padding: 8px 16px; background: #f0faf3; border: 1px solid #b8e6c8; border-radius: 12px; margin-bottom: 12px; font-size: 13px; }

.subject-list { display: flex; flex-direction: column; gap: 6px; }
.subject-card { display: grid; grid-template-columns: 200px 1fr 140px 180px; align-items: center; gap: 12px; padding: 12px 16px; background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: 12px; transition: all 0.15s; }
.subject-card:hover { border-color: #c0d0c4; }
.subject-card.selected { background: #f8fdf9; border-color: #a0d0a8; }

.card-left { display: flex; align-items: center; gap: 10px; }
.card-name { font-weight: 700; font-size: 14px; }
.stage-tag { display: inline-block; padding: 1px 10px; border-radius: 50px; font-size: 11px; font-weight: 500; white-space: nowrap; }
.tag-idle { background: #f3f4f6; color: #6b7280; }
.tag-cutting { background: #dbeafe; color: #1e40af; }
.tag-ready { background: #ede9fe; color: #5b21b6; }
.tag-ai_grading { background: #fef3c7; color: #92400e; }
.tag-reviewing { background: #fee2e2; color: #991b1b; }
.tag-failed { background: #fee2e2; color: #dc2626; }
.tag-done { background: #dcfce7; color: #166534; }

.card-mid { min-width: 0; }
.card-detail { font-size: 13px; color: #555; }
.card-detail b { font-weight: 600; }
.card-detail.muted { color: #aaa; }
.card-detail.err { color: #dc2626; font-weight: 600; }
.card-detail.ok { color: #16a34a; font-weight: 600; }

.prog-row { display: flex; align-items: center; gap: 10px; }
.prog-bar { flex: 1; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.prog-fill { height: 100%; background: #3b82f6; border-radius: 3px; transition: width 0.3s; }
.prog-fill.warn { background: #f59e0b; }
.prog-fill.purple { background: #8b5cf6; }
.prog-text { font-size: 12px; color: #666; white-space: nowrap; }

.card-stats { display: flex; gap: 6px; font-size: 11px; color: #999; }
.card-stats span { padding: 2px 6px; background: #f5f5f5; border-radius: 4px; }

.card-actions { display: flex; gap: 6px; justify-content: flex-end; }

.empty-state { padding: 60px 0; text-align: center; color: #8a9a8e; font-size: 14px; }

.scan-status { font-size: 12px; color: #16a34a; font-family: monospace; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-hint { font-size: 12px; color: #aaa; margin-top: 6px; }
</style>
