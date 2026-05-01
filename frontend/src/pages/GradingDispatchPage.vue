<template>
  <div class="dispatch-page">
    <div class="top-bar">
      <div>
        <h2 class="page-title">扫描调度</h2>
        <p class="page-subtitle">扫描切割 → 选择题自动判分</p>
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
        @batch-detect="handleBatchDetect"
        @batch-cut="handleBatchCut"
      />

      <!-- 科目卡片 -->
      <div class="subject-list">
        <SubjectStatusCard
          v-for="s in subjects" :key="s.subject_id"
          :subject="s"
          :is-selected="selectedSubjects.includes(s.subject_id)"
          :progress-pct="activeCutSubjectId === s.subject_id ? progressPct : 0"
          :detect-status="detectStatus[s.subject_id]"
          :show-detect="canDetect(s)"
          :show-cut="canCut(s)"
          :is-detect-loading="detectLoading === s.subject_id"
          :is-cut-loading="cutLoading === s.subject_id"
          @toggle="toggleSubject"
          @detect="handleDetectTemplate"
          @preview="handlePreviewTemplate"
          @cut="handleStartCut"
          @stop-cut="handleStopCut"
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
          <n-button v-if="orphanQnos.length" size="small" type="error" @click="handleDeleteOrphans">
            删除 {{ orphanQnos.length }} 个多余题目
          </n-button>
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
import { useAuthStore } from '../stores/auth'
import { SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { listExams } from '../api/exams'
import { getDispatchStatus } from '../api/grading'
import { uploadScanFolder, pdfImport, scanDirectory, startPipeline, getPipelineProgress, stopPipeline, autoDetectCV, saveCVTemplate, getCVTemplate, fetchScanImageBlob, verifyTemplate, deleteOrphanQuestions } from '../api/scan'
import TemplatePreviewEditor from '../components/TemplatePreviewEditor.vue'
import SubjectStatusCard from './grading-dispatch/SubjectStatusCard.vue'
import ScanSection from './grading-dispatch/ScanSection.vue'
import BatchOperationsBar from './grading-dispatch/BatchOperationsBar.vue'

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
const activeCutSubjectId = ref(null)
const cutLoading = ref(null)
let pollTimer = null
let pollBound = false
let unboundPollCount = 0
const detectLoading = ref(null)
const pendingBSide = ref(null)

function countByStage(stage) {
  return subjects.value.filter(s => s.stage === stage).length
}

const stageGroups = computed(() => {
  const defs = [
    { key: 'done', label: '已切割', stages: ['ready', 'done', 'ai_grading', 'reviewing', 'failed'] },
    { key: 'pending_cut', label: '待切割' },
    { key: 'pending_detect', label: '待检测' },
    { key: 'idle', label: '待上传' },
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

    const cuttingSubject = (res.data || []).find(s => s.stage === 'cutting')
    if (cuttingSubject && !pollTimer) {
      activeCutSubjectId.value = cuttingSubject.subject_id
      pollBound = true
      startPolling()
    }
  } catch (e) {
    message.error('加载科目状态失败')
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
  cutLoading.value = s.subject_id
  try {
    let hasB = false
    try {
      const tpl = (await getCVTemplate(s.subject_id)).data
      hasB = !!(tpl && tpl.B && tpl.B.regions && tpl.B.regions.length)
    } catch {}
    const res = await startPipeline(s.subject_id, 'A', dir)
    if (hasB) pendingBSide.value = { subjectId: s.subject_id, dir }

    // F002: 乐观更新 — 立即将本地 stage 改为 cutting
    const entry = allSubjects.value.find(x => x.subject_id === s.subject_id)
    if (entry) entry.stage = 'cutting'
    activeCutSubjectId.value = s.subject_id
    progressPct.value = 0
    pollBound = false

    message.info(`切割已启动（${res.data?.total_files || '?'} 份）`)
    startPolling()
  } catch (e) {
    message.error('启动切割失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    cutLoading.value = null
  }
}

async function handleStopCut() {
  try {
    await stopPipeline()
    message.info('切割已停止')
  } catch (e) {
    message.error('停止失败')
  }
  stopPolling()
  activeCutSubjectId.value = null
  pollBound = false
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
    title: '题目配置',
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

const verifySubjectId = ref(null)
const orphanQnos = computed(() =>
  (verifyResult.value?.items || [])
    .filter(i => i.status === 'missing_template')
    .map(i => i.qno)
)

async function handleVerify(s) {
  verifyShow.value = true
  verifyLoading.value = true
  verifyResult.value = null
  verifySubjectId.value = s.subject_id
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

async function handleDeleteOrphans() {
  if (!orphanQnos.value.length || !verifySubjectId.value) return
  try {
    const res = await deleteOrphanQuestions(verifySubjectId.value, orphanQnos.value)
    message.success(`已删除 ${res.data.deleted} 个多余题目`)
    const fresh = await verifyTemplate(verifySubjectId.value)
    verifyResult.value = fresh.data
  } catch (e) {
    message.error(`删除失败: ${e.response?.data?.detail || e.message}`)
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
async function pollOnce() {
  try {
    const res = await getPipelineProgress()
    const p = res.data

    // F003: 绑定 activeCutSubjectId
    if (p.status === 'running' && p.current_subject_id) {
      activeCutSubjectId.value = p.current_subject_id
      pollBound = true
      unboundPollCount = 0
      // V004: 同步本地 stage
      const entry = allSubjects.value.find(x => x.subject_id === p.current_subject_id)
      if (entry && entry.stage !== 'cutting') entry.stage = 'cutting'
    }

    // V003: 只有绑定后才更新进度，避免显示上一次任务的陈旧进度
    if (pollBound && p.total > 0) {
      progressPct.value = Math.round((p.processed / p.total) * 100)
    }

    if (p.status !== 'running') {
      // V002: 宽限期最多 3 次（约 6 秒），超时后刷新状态
      if (!pollBound) {
        unboundPollCount++
        if (unboundPollCount < 3) return
        stopPolling()
        activeCutSubjectId.value = null
        await loadStatus(selectedExamId.value)
        return
      }

      stopPolling()

      // F007: 完成反馈（V005: processed 已是成功数）
      if (p.failed > 0) {
        message.warning(`切割完成：${p.processed} 成功，${p.failed} 失败`)
      } else if (p.processed > 0) {
        message.success(`切割完成：${p.processed} 份`)
      }

      activeCutSubjectId.value = null
      pollBound = false
      unboundPollCount = 0

      if (pendingBSide.value) {
        const { subjectId, dir } = pendingBSide.value
        pendingBSide.value = null
        try {
          await startPipeline(subjectId, 'B', dir)
          activeCutSubjectId.value = subjectId
          progressPct.value = 0
          pollBound = false
          unboundPollCount = 0
          // V004: B 面乐观更新 stage
          const entry = allSubjects.value.find(x => x.subject_id === subjectId)
          if (entry) entry.stage = 'cutting'
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
    message.warning('切割进度获取失败')
  }
}

function startPolling() {
  stopPolling()
  unboundPollCount = 0
  pollOnce()
  pollTimer = setInterval(pollOnce, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

</script>

<style scoped>
.dispatch-page { padding: var(--space-1) 0; }
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-5); }
.page-title { font-size: var(--fs-3xl); font-weight: var(--fw-heavy); letter-spacing: -0.035em; }
.page-subtitle { font-size: var(--fs-base); color: var(--color-text-muted); margin-top: 2px; }

.summary-bar { display: flex; gap: var(--space-6); padding: var(--space-3) var(--space-5); background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: var(--radius-md); margin-bottom: var(--space-3); }
.summary-item { display: flex; align-items: baseline; gap: var(--space-1); }
.summary-num { font-size: var(--fs-xl); font-weight: var(--fw-bold); color: var(--color-text); }
.summary-num.done { color: var(--color-success); }
.summary-num.idle { color: #9ca3af; }
.summary-label { font-size: var(--fs-base); color: var(--color-text-muted); }

.scan-section { background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: var(--radius-md); margin-bottom: var(--space-3); overflow: hidden; }
.scan-header { display: flex; align-items: center; gap: var(--space-2); padding: 10px var(--space-4); cursor: pointer; user-select: none; }
.scan-header:hover { background: var(--body-color, #f9fafb); }
.scan-toggle { font-size: var(--fs-base); color: var(--color-text-muted); width: var(--fs-md); }
.scan-title { font-weight: var(--fw-semibold); font-size: var(--fs-base); }
.scan-hint { font-size: var(--fs-base); color: var(--color-success); margin-left: auto; }
.scan-body { padding: 0 var(--space-4) var(--space-3); }
.scan-row { display: flex; gap: var(--space-2); }

.batch-bar { display: flex; align-items: center; gap: 10px; padding: var(--space-2) var(--space-4); background: var(--color-success-bg-subtle); border: 1px solid var(--color-success-border); border-radius: var(--radius-md); margin-bottom: var(--space-3); font-size: var(--fs-base); }

.subject-list { display: flex; flex-direction: column; gap: 6px; }
.subject-card { display: grid; grid-template-columns: 200px 1fr 140px 180px; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); background: var(--card-color, #fff); border: 1px solid var(--border-color, #e2e8e4); border-radius: var(--radius-md); transition: transform 0.15s ease-out, box-shadow 0.15s ease-out; }
.subject-card:hover { border-color: var(--color-border); }
.subject-card.selected { background: var(--color-success-bg-subtle); border-color: var(--color-success-border); }

.card-left { display: flex; align-items: center; gap: 10px; }
.card-name { font-weight: var(--fw-bold); font-size: var(--fs-base); }
.stage-tag { display: inline-block; padding: 1px 10px; border-radius: var(--radius-pill); font-size: var(--fs-base); font-weight: var(--fw-medium); white-space: nowrap; }
.tag-idle { background: #f3f4f6; color: #6b7280; }
.tag-pending_detect { background: #fef3c7; color: #92400e; }
.tag-pending_cut { background: #e0f2fe; color: #0369a1; }
.tag-cutting { background: #dbeafe; color: #1e40af; }
.tag-ready { background: #dcfce7; color: #166534; }

.detect-tag { display: inline-block; padding: 1px var(--space-2); border-radius: var(--radius-pill); font-size: var(--fs-base); font-weight: var(--fw-medium); }
.detect-tag.running { background: #fef3c7; color: #92400e; }
.detect-tag.done { background: #dcfce7; color: #166534; }
.detect-tag.failed { background: #fee2e2; color: var(--color-danger); }
.batch-progress { font-size: var(--fs-base); color: var(--color-text-secondary); margin-left: var(--space-2); }

.card-mid { min-width: 0; }
.card-detail { font-size: var(--fs-base); color: var(--color-text-secondary); }
.card-detail b { font-weight: var(--fw-semibold); }
.card-detail.muted { color: var(--color-text-muted); }
.card-detail.ok { color: var(--color-success); font-weight: var(--fw-semibold); }

.prog-row { display: flex; align-items: center; gap: 10px; }
.prog-bar { flex: 1; height: 6px; background: var(--color-border); border-radius: 3px; overflow: hidden; }
.prog-fill { height: 100%; background: var(--color-info); border-radius: 3px; transition: width 0.3s; }
.prog-text { font-size: var(--fs-base); color: var(--color-text-secondary); white-space: nowrap; }

.card-stats { display: flex; gap: 6px; font-size: var(--fs-base); color: var(--color-text-muted); }
.card-stats span { padding: 2px 6px; background: var(--color-bg-alt); border-radius: var(--r-xs); }

.card-actions { display: flex; gap: 6px; justify-content: flex-end; }

.empty-state { padding: 60px 0; text-align: center; color: var(--color-text-muted); font-size: var(--fs-base); }

.scan-status { font-size: var(--fs-base); color: var(--color-success); font-family: monospace; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-hint { font-size: var(--fs-base); color: var(--color-text-muted); margin-top: 6px; }

.verify-summary { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) 0; margin-bottom: var(--space-2); }
.verify-ok { font-size: var(--fs-base); font-weight: var(--fw-bold); color: var(--color-success); }
.verify-bad { font-size: var(--fs-base); font-weight: var(--fw-bold); color: var(--color-danger); }
.verify-total { font-size: var(--fs-base); color: var(--color-text-muted); }
:deep(.verify-mismatch-row td) { background: rgba(220,38,38,0.04) !important; }
</style>
