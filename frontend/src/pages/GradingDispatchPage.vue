<template>
  <div class="dispatch-page">
    <div class="top-bar">
      <div>
        <h2 class="page-title">扫描调度</h2>
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
      <ScanSection
        :scan-root-dir="scanRootDir"
        :scan-loading="scanLoading"
        :scan-results="scanResults"
        :upload-loading="uploadLoading"
        :upload-progress="uploadProgress"
        :initial-expanded="scanExpanded"
        @pick-folder="pickFolder"
        @scan-dir="handleScanDir"
      />
      <input ref="folderInput" type="file" webkitdirectory multiple style="display:none" @change="handleFolderSelected" />

      <!-- 批量操作 -->
      <BatchOperationsBar
        :can-manage-all="canManageAll"
        :detectable-count="detectableSubjects.length"
        :batch-detect-loading="batchDetectLoading"
        :batch-progress-text="batchProgressText"
        :selected-count="selectedSubjects.length"
        :can-batch-cut="canBatchCut"
        :can-batch-grade="canBatchGrade"
        @batch-detect="handleBatchDetect"
        @batch-cut="handleBatchCut"
        @batch-grade="handleBatchGrade"
      />

      <!-- 科目卡片 -->
      <div class="subject-list">
        <SubjectStatusCard
          v-for="s in subjects" :key="s.subject_id"
          :subject="s"
          :is-selected="selectedSubjects.includes(s.subject_id)"
          :progress-pct="progressPct"
          :detect-status="detectStatus[s.subject_id]"
          :show-detect="canDetect(s)"
          :show-cut="canCut(s)"
          :is-detect-loading="detectLoading === s.subject_id"
          :is-grading-loading="gradingLoading === s.subject_id"
          @toggle="toggleSubject"
          @detect="handleDetectTemplate"
          @preview="handlePreviewTemplate"
          @cut="handleStartCut"
          @stop-cut="handleStopCut"
          @grade="handleStartGrade"
          @go-review="$router.push({ name: 'MarkingSelect' })"
          @go-ai-grading="goToAiGrading"
          @verify="handleVerify"
        />

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

    <n-modal v-model:show="verifyShow" preset="card" title="配置校对" style="width:700px;max-width:90vw">
      <div v-if="verifyLoading" style="text-align:center;padding:40px">加载中...</div>
      <template v-else-if="verifyResult">
        <div class="verify-summary">
          <span :class="verifyResult.mismatched ? 'verify-bad' : 'verify-ok'">
            {{ verifyResult.mismatched ? `${verifyResult.mismatched} 项不一致` : '全部匹配' }}
          </span>
          <span class="verify-total">共 {{ verifyResult.total }} 题，匹配 {{ verifyResult.matched }}</span>
        </div>
        <n-data-table size="small" :columns="verifyCols" :data="verifyResult.items" :row-class-name="verifyRowClass"
                      max-height="55vh" :bordered="false" />
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import { NSelect, NModal, NDataTable, NTag } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { listExams } from '../api/exams'
import { getDispatchStatus, createTask } from '../api/grading'
import { uploadScanFolder, pdfImport, scanDirectory, startPipeline, getPipelineProgress, stopPipeline, autoDetectCV, saveCVTemplate, getCVTemplate, fetchScanImageBlob, verifyTemplate } from '../api/scan'
import TemplatePreviewEditor from '../components/TemplatePreviewEditor.vue'
import SubjectStatusCard from './grading-dispatch/SubjectStatusCard.vue'
import ScanSection from './grading-dispatch/ScanSection.vue'
import BatchOperationsBar from './grading-dispatch/BatchOperationsBar.vue'

const message = useMessage()
const router = useRouter()
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
const pendingBSide = ref(null)

function countByStage(stage) {
  return subjects.value.filter(s => s.stage === stage).length
}

const stageGroups = computed(() => {
  const defs = [
    { key: 'done', label: '已完成' },
    { key: 'active', label: '阅卷中', stages: ['ai_grading', 'reviewing'] },
    { key: 'ready', label: '待阅卷' },
    { key: 'pending_cut', label: '待切割' },
    { key: 'pending_detect', label: '待检测' },
    { key: 'idle', label: '待上传' },
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
    if (examOptions.value.length > 0) {
      selectedExamId.value = examOptions.value[0].value
      await onExamChange(selectedExamId.value)
    }
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
    /\.(png|jpg|jpeg|bmp|pdf)$/i.test(f.name)
  )
  if (imageFiles.length === 0) {
    message.warning('未找到文件（支持 png/jpg/bmp/pdf）')
    return
  }

  uploadLoading.value = true
  uploadProgress.value = `0/${imageFiles.length}`
  try {
    const res = await uploadScanFolder(selectedExamId.value, imageFiles, (done, total) => {
      uploadProgress.value = `${done}/${total}`
    })
    scanRootDir.value = res.data.dir_path
    const pdfCount = imageFiles.filter(f => /\.pdf$/i.test(f.name)).length
    if (pdfCount > 0) {
      message.info(`正在转换 ${pdfCount} 个 PDF...`)
      try { await pdfImport(res.data.dir_path) } catch(e) { message.warning('PDF 转换失败: ' + e.message) }
      message.success(`已上传 ${imageFiles.length} 个文件，PDF 已转换为图片`)
    } else {
      message.success(`已上传 ${imageFiles.length} 张图片`)
    }
    await handleScanDir()
    await loadStatus(selectedExamId.value)
  } catch (err) {
    message.error('上传失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    uploadLoading.value = false
    e.target.value = ''
  }
}

// 模板检测：无模板 + 有扫描图
function canDetect(s) {
  if (s.stage !== 'pending_detect') return false
  if (canManageAll.value) return true
  if (!mySubjectCodes.value) return false
  return mySubjectCodes.value.includes(s.subject_code)
}

// 切割：有模板 + 待切割阶段
function canCut(s) {
  return s.stage === 'pending_cut'
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
  const dir = getScanDirFallback(s)
  if (!dir) { message.error('找不到扫描目录'); return }
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

    // B 面：分开请求避免一个失败全丢
    let dataB = null, blobB = null
    try {
      blobB = await fetchScanImageBlob(fileB)
    } catch (_) { /* B 面可能不存在 */ }
    if (blobB) {
      try {
        const detectB = await autoDetectCV(fileB, { priorRegions: dataA.regions })
        dataB = detectB.data
      } catch (_) { /* B 面检测失败，静默跳过 */ }
    }

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

// 预览已有模板（从 DB 加载 Template + 扫描图，打开编辑器）
async function handlePreviewTemplate(s) {
  detectLoading.value = s.subject_id
  try {
    const tplRes = await getCVTemplate(s.subject_id)
    const tpl = tplRes.data

    const dir = getScanDirFallback(s)
    const fileA = dir ? `${dir}/${scanFirstFile(s)}` : null

    const hasB = !!(tpl.B && tpl.B.regions?.length)
    const fileB = hasB && fileA ? fileA.replace(/A\.png$/, 'B.png') : null

    const [blobA, blobB] = await Promise.all([
      fileA ? fetchScanImageBlob(fileA) : null,
      fileB ? fetchScanImageBlob(fileB).catch(() => null) : null,
    ])

    editorRegions.value = tpl.A?.regions || []
    editorWidth.value = tpl.A?.width || 0
    editorHeight.value = tpl.A?.height || 0
    editorBlobUrl.value = blobA

    if (hasB) {
      editorRegionsB.value = tpl.B.regions
      editorWidthB.value = tpl.B.width || 0
      editorHeightB.value = tpl.B.height || 0
      editorBlobUrlB.value = blobB
    } else {
      editorRegionsB.value = null
      editorBlobUrlB.value = null
    }

    editorSubjectId.value = s.subject_id
    editorShow.value = true
  } catch (e) {
    message.error(`加载模板失败: ${e.response?.data?.detail || e.message}`)
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
    await loadStatus(selectedExamId.value)
  } catch (e) {
    message.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

// 一键全科检测（并发，限流 3，逐科进度反馈）
const batchDetectLoading = ref(false)
const batchProgressText = ref('')
const detectStatus = ref({})

async function detectOneSubject(s) {
  const dir = getScanDirFallback(s)
  if (!dir) throw new Error('无扫描目录')
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
}

async function handleBatchDetect() {
  const list = detectableSubjects.value
  if (!list.length) return

  batchDetectLoading.value = true
  let ok = 0, fail = 0
  const total = list.length
  const failedNames = []

  for (const s of list) {
    detectStatus.value[s.subject_id] = 'pending'
  }
  batchProgressText.value = `0/${total}`

  const CONCURRENCY = 3
  let cursor = 0

  async function worker() {
    while (cursor < list.length) {
      const idx = cursor++
      const s = list[idx]
      detectStatus.value[s.subject_id] = 'running'
      try {
        await detectOneSubject(s)
        ok++
        detectStatus.value[s.subject_id] = 'done'
        // 实时更新本地状态，让按钮立即切换
        const entry = allSubjects.value.find(x => x.subject_id === s.subject_id)
        if (entry) {
          entry.stage = 'pending_cut'
          entry.has_template = true
        }
      } catch (e) {
        fail++
        failedNames.push(s.subject_name)
        detectStatus.value[s.subject_id] = 'failed'
      }
      batchProgressText.value = `${ok + fail}/${total}`
    }
  }

  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, list.length) }, () => worker()))

  batchDetectLoading.value = false
  detectStatus.value = {}

  if (fail === 0) {
    message.success(`全科检测完成：${ok} 科成功`)
  } else {
    message.warning(`检测完成：${ok} 成功，${fail} 失败（${failedNames.join('、')}）`)
  }

  await loadStatus(selectedExamId.value)
}

function scanFirstFile(subjectStatus) {
  const match = scanResults.value.find(
    r => r.name === subjectStatus.subject_name || r.folder === subjectStatus.subject_name
  )
  return match?.first_file || ''
}

// 切割
function getScanDirFallback(s) {
  const dir = getScanDir(s)
  if (dir) return dir
  if (s.has_scan_dir && selectedExamId.value) {
    return `/home/ops/projects/edu-cloud/uploads/scan-input/${selectedExamId.value}/${s.subject_name}`
  }
  return null
}

async function handleStartCut(s) {
  const dir = getScanDirFallback(s)
  if (!dir) {
    message.error('找不到扫描目录，请先上传扫描图')
    return
  }
  try {
    let hasB = false
    try {
      const tpl = (await getCVTemplate(s.subject_id)).data
      hasB = !!(tpl && tpl.B && tpl.B.regions && tpl.B.regions.length)
    } catch {}
    await startPipeline(s.subject_id, 'A', dir)
    if (hasB) pendingBSide.value = { subjectId: s.subject_id, dir }
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
  const cutQueue = []
  for (const id of selectedSubjects.value) {
    const s = subjects.value.find(x => x.subject_id === id)
    const dir = s ? getScanDirFallback(s) : null
    if (s && canCut(s) && dir) {
      let hasB = false
      try {
        const tpl = (await getCVTemplate(s.subject_id)).data
        hasB = !!(tpl && tpl.B && tpl.B.regions && tpl.B.regions.length)
      } catch {}
      cutQueue.push({ subjectId: s.subject_id, dir, sides: hasB ? ['A', 'B'] : ['A'] })
    }
  }
  for (const item of cutQueue) {
    for (const side of item.sides) {
      try {
        await startPipeline(item.subjectId, side, item.dir)
        await new Promise(resolve => {
          const check = setInterval(async () => {
            try {
              const res = await getPipelineProgress()
              if (res.data.status !== 'running') { clearInterval(check); resolve() }
            } catch { clearInterval(check); resolve() }
          }, 2000)
        })
      } catch {}
    }
  }
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

function goToAiGrading(s) {
  router.push(`/exams/${selectedExamId.value}/ai-grading/${s.subject_id}`)
}

// --- 校对配置 ---
const verifyShow = ref(false)
const verifyLoading = ref(false)
const verifyResult = ref(null)

const STATUS_MAP = {
  match: { label: '匹配', type: 'success' },
  score_mismatch: { label: '分值不一致', type: 'warning' },
  missing_question: { label: '缺少题目', type: 'error' },
  missing_template: { label: '缺少区域', type: 'error' },
}

const verifyCols = [
  { title: '题号', key: 'qno', width: 70 },
  {
    title: '模板（裁剪）',
    key: 'template',
    render: (row) => row.template
      ? `${row.template.type === 'choice_group' ? '选择题' : '主观题'} / ${row.template.score}分`
      : '-',
  },
  {
    title: '题目（阅卷）',
    key: 'question',
    render: (row) => row.question
      ? `${row.question.type} / ${row.question.max_score}分`
      : '-',
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) => {
      const s = STATUS_MAP[row.status] || { label: row.status, type: 'default' }
      return h(NTag, { size: 'small', type: s.type, bordered: false }, () => s.label)
    },
  },
  {
    title: '问题',
    key: 'issues',
    render: (row) => (row.issues || []).join('；') || '-',
  },
]

function verifyRowClass(row) {
  return row.status !== 'match' ? 'verify-mismatch-row' : ''
}

async function handleVerify(s) {
  verifyShow.value = true
  verifyLoading.value = true
  verifyResult.value = null
  try {
    const res = await verifyTemplate(s.subject_id)
    verifyResult.value = res.data
  } catch (e) {
    message.error(`校对失败: ${e.response?.data?.detail || e.message}`)
    verifyShow.value = false
  } finally {
    verifyLoading.value = false
  }
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
        if (pendingBSide.value) {
          const { subjectId, dir } = pendingBSide.value
          pendingBSide.value = null
          try {
            await startPipeline(subjectId, 'B', dir)
            message.info('A 面切割完成，自动开始 B 面切割')
            startPolling()
          } catch (e) {
            message.warning('B 面切割启动失败: ' + (e.response?.data?.detail || e.message))
          }
        }
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
  idle: '待上传', pending_detect: '待检测', pending_cut: '待切割',
  cutting: '切割中', ready: '待阅卷',
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
.tag-pending_detect { background: #fef3c7; color: #92400e; }
.tag-pending_cut { background: #e0f2fe; color: #0369a1; }
.tag-cutting { background: #dbeafe; color: #1e40af; }
.tag-ready { background: #ede9fe; color: #5b21b6; }
.tag-ai_grading { background: #fef3c7; color: #92400e; }
.tag-reviewing { background: #fee2e2; color: #991b1b; }
.tag-failed { background: #fee2e2; color: #dc2626; }
.tag-done { background: #dcfce7; color: #166534; }

.detect-tag { display: inline-block; padding: 1px 8px; border-radius: 50px; font-size: 11px; font-weight: 500; }
.detect-tag.running { background: #fef3c7; color: #92400e; }
.detect-tag.done { background: #dcfce7; color: #166534; }
.detect-tag.failed { background: #fee2e2; color: #dc2626; }
.batch-progress { font-size: 13px; color: #555; margin-left: 8px; }

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

.verify-summary { display: flex; align-items: center; gap: 16px; padding: 12px 0; margin-bottom: 8px; }
.verify-ok { font-size: 16px; font-weight: 700; color: #16a34a; }
.verify-bad { font-size: 16px; font-weight: 700; color: #dc2626; }
.verify-total { font-size: 13px; color: #888; }
:deep(.verify-mismatch-row td) { background: rgba(220,38,38,0.04) !important; }
</style>
