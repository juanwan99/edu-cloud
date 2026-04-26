<template>
  <div class="ai-grading-page">
    <div class="page-header">
      <n-button text @click="$router.push(hasRouteParams ? '/grading/tasks' : '/')">← 返回</n-button>
      <h2 class="page-title">AI 阅卷配置</h2>
      <div style="flex:1" />
      <n-button v-if="examId && subjectId" size="small" @click="showDocCrop = true">上传文档裁剪</n-button>
      <n-button v-if="examId && subjectId && questions.length" size="small" type="primary"
                :loading="batchGenerating" @click="handleBatchGenerate">批量生成细则</n-button>
    </div>

    <!-- 选择器：无路由参数时显示 -->
    <ExamSubjectSelector
      v-if="!hasRouteParams"
      :examId="selectedExamId"
      :subjectId="selectedSubjectId"
      :examOptions="examOptions"
      :subjectOptions="subjectOptions"
      :loadingExams="loadingExams"
      :loadingSubjects="loadingSubjects"
      @update:examId="onExamSelected"
      @update:subjectId="onSubjectSelected"
    />

    <div class="main-layout" v-if="examId && subjectId">
      <!-- 左侧：题目列表 -->
      <QuestionList
        :questions="questions"
        :selectedQuestionId="selectedQuestion?.question_id"
        :editingScoreId="editingScoreId"
        :loading="loadingQuestions"
        @select="selectQuestion"
        @start-edit-score="startEditScore"
        @save-score="saveScore"
        @update-score-value="handleUpdateScoreValue"
      />

      <!-- 右侧：阅卷操作面板 -->
      <GradingPanel
        :question="selectedQuestion"
        :rubricItems="rubricItems"
        :rubricLoading="rubricLoading"
        :rubricGenerating="rubricGenerating"
        :rubricSaving="rubricSaving"
        :taskProgress="taskProgress"
        :gradingStarting="gradingStarting"
        @edit-content="openContentModal"
        @remove-image="removeImage"
        @generate-rubric="handleGenerateRubric"
        @save-rubric="handleSaveRubric"
        @update:rubricItems="rubricItems = $event"
        @start-grading="handleStartGrading"
      />
    </div>

    <div v-if="!hasRouteParams && (!examId || !subjectId)" class="empty-tip center">
      {{ !examId ? '请先选择考试' : '请选择科目' }}
    </div>

    <!-- 题干/答案编辑弹窗 -->
    <QuestionContentModal
      v-model:show="contentModalShow"
      :title="contentModalTitle"
      :content="contentModalValue"
      :images="contentModalImages"
      @save="handleContentSave"
    />

    <!-- 文档裁剪面板 -->
    <DocCropPanel
      v-model:show="showDocCrop"
      :questions="questions"
      :subject-id="subjectId"
      @save="handleDocCropSave"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NButton } from 'naive-ui'
import { getDispatchStatus, generateRubric, getRubric, saveRubric, createTask, getTask, getQuestion, updateQuestionContent, uploadQuestionImage } from '../api/grading'
import { listExams } from '../api/exams'
import { updateQuestion } from '../api/questions'
import { listSubjects } from '../api/subjects'
import QuestionContentModal from '../components/QuestionContentModal.vue'
import DocCropPanel from '../components/DocCropPanel.vue'
import ExamSubjectSelector from './ai-grading/ExamSubjectSelector.vue'
import QuestionList from './ai-grading/QuestionList.vue'
import GradingPanel from './ai-grading/GradingPanel.vue'

const route = useRoute()
const message = useMessage()

const hasRouteParams = computed(() => !!route.params.examId && !!route.params.subjectId)

const selectedExamId = ref(null)
const selectedSubjectId = ref(null)
const examOptions = ref([])
const subjectOptions = ref([])
const loadingExams = ref(false)
const loadingSubjects = ref(false)

const examId = computed(() => route.params.examId || selectedExamId.value)
const subjectId = computed(() => route.params.subjectId || selectedSubjectId.value)

const questions = ref([])
const loadingQuestions = ref(false)
const selectedQuestion = ref(null)

const rubricItems = ref([])
const rubricLoading = ref(false)
const rubricGenerating = ref(false)
const rubricSaving = ref(false)

const showDocCrop = ref(false)
const batchGenerating = ref(false)

const gradingStarting = ref(false)
const taskProgress = ref(null)
let pollTimer = null

const contentModalShow = ref(false)
const contentModalTitle = ref('')
const contentModalValue = ref('')
const contentModalImages = ref([])
const contentModalType = ref('content') // 'content' | 'answer'

onMounted(async () => {
  if (hasRouteParams.value) {
    await loadQuestions()
  } else {
    await loadExamList()
  }
})

async function loadExamList() {
  loadingExams.value = true
  try {
    const res = await listExams()
    examOptions.value = (res.data || []).map(e => ({ label: e.name, value: e.id }))
    if (examOptions.value.length > 0 && !selectedExamId.value) {
      await onExamSelected(examOptions.value[0].value)
    }
  } catch (e) {
    message.error('加载考试列表失败')
  } finally {
    loadingExams.value = false
  }
}

async function onExamSelected(val) {
  selectedExamId.value = val
  selectedSubjectId.value = null
  subjectOptions.value = []
  questions.value = []
  selectedQuestion.value = null
  loadingSubjects.value = true
  try {
    const res = await listSubjects(val)
    const opts = (res.data || []).map(s => ({ label: s.name, value: s.id }))
    subjectOptions.value = opts
    if (opts.length === 1) {
      selectedSubjectId.value = opts[0].value
      await loadQuestions()
    }
  } catch (e) {
    message.error('加载科目列表失败')
  } finally {
    loadingSubjects.value = false
  }
}

async function onSubjectSelected(val) {
  selectedSubjectId.value = val
  questions.value = []
  selectedQuestion.value = null
  taskProgress.value = null
  stopPolling()
  await loadQuestions()
}

onUnmounted(() => {
  stopPolling()
})

async function loadQuestions() {
  loadingQuestions.value = true
  try {
    const res = await getDispatchStatus(examId.value)
    const subjects = res.data || []
    const subj = subjects.find(s => String(s.subject_id) === String(subjectId.value))
    if (subj && subj.questions) {
      questions.value = [...subj.questions].sort((a, b) => {
        const na = parseInt(a.name, 10) || 0
        const nb = parseInt(b.name, 10) || 0
        return na - nb
      })
    } else {
      questions.value = []
    }
  } catch (e) {
    message.error('加载题目失败')
  } finally {
    loadingQuestions.value = false
  }
}

const editingScoreId = ref(null)
function startEditScore(q) { editingScoreId.value = q.question_id }
function handleUpdateScoreValue(q, v) { q.max_score = v }
async function saveScore(q) {
  editingScoreId.value = null
  try {
    await updateQuestion(q.question_id, { max_score: q.max_score })
    message.success(`第${q.name}题分值已更新为 ${q.max_score}`)
  } catch (e) {
    message.error('保存失败')
  }
}

async function selectQuestion(q) {
  selectedQuestion.value = { ...q }
  rubricItems.value = []
  taskProgress.value = null
  stopPolling()
  // Fetch full question details (content/reference_answer) from backend
  try {
    const res = await getQuestion(q.question_id)
    selectedQuestion.value = { ...selectedQuestion.value, ...res.data }
  } catch (e) {
    // Non-fatal: fall back to dispatch status fields
  }
  await loadRubric(q.question_id)
}

async function loadRubric(questionId) {
  rubricLoading.value = true
  try {
    const res = await getRubric(questionId)
    rubricItems.value = res.data?.criteria || []
  } catch (e) {
    if (e.response?.status !== 404) {
      message.error('加载评分细则失败')
    }
    rubricItems.value = []
  } finally {
    rubricLoading.value = false
  }
}

async function handleGenerateRubric() {
  if (!selectedQuestion.value) return
  rubricGenerating.value = true
  try {
    const res = await generateRubric(
      selectedQuestion.value.question_id,
      selectedQuestion.value.max_score || 0
    )
    rubricItems.value = res.data?.criteria || []
    message.success('AI 生成完成')
  } catch (e) {
    message.error('生成失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    rubricGenerating.value = false
  }
}

async function handleSaveRubric() {
  if (!selectedQuestion.value) return
  rubricSaving.value = true
  try {
    await saveRubric({
      question_id: selectedQuestion.value.question_id,
      criteria: rubricItems.value,
    })
    message.success('评分细则已保存')
    // refresh question list to update has_rubric flag
    await loadQuestions()
  } catch (e) {
    message.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    rubricSaving.value = false
  }
}

async function handleStartGrading() {
  if (!selectedQuestion.value) return
  gradingStarting.value = true
  try {
    const res = await createTask({
      subject_id: subjectId.value,
      question_id: selectedQuestion.value.question_id,
    })
    const taskId = res.data?.task_id || res.data?.id
    if (taskId) {
      startPolling(taskId)
    }
    message.success('阅卷任务已启动')
  } catch (e) {
    message.error('启动失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    gradingStarting.value = false
  }
}

function startPolling(taskId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await getTask(taskId)
      const task = res.data
      taskProgress.value = {
        status: task.status,
        graded: task.completed || 0,
        total: task.total || 0,
      }
      if (task.status === 'completed' || task.status === 'failed') {
        stopPolling()
        await loadQuestions()
      }
    } catch (e) {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function openContentModal(type) {
  contentModalType.value = type
  if (type === 'content') {
    contentModalTitle.value = '编辑题干'
    contentModalValue.value = selectedQuestion.value?.content || ''
    contentModalImages.value = selectedQuestion.value?.content_images || []
  } else {
    contentModalTitle.value = '编辑参考答案'
    contentModalValue.value = selectedQuestion.value?.reference_answer || ''
    contentModalImages.value = selectedQuestion.value?.reference_answer_images || []
  }
  contentModalShow.value = true
}

async function handleContentSave({ content, files }) {
  if (!selectedQuestion.value) return
  const qid = selectedQuestion.value.question_id
  try {
    // Upload images first if any
    const uploadedPaths = []
    for (const file of files) {
      const res = await uploadQuestionImage(qid, file)
      if (res.data?.path) uploadedPaths.push(res.data.path)
    }

    const payload = {}
    if (contentModalType.value === 'content') {
      payload.content = content
      if (uploadedPaths.length) {
        payload.content_images = [
          ...(selectedQuestion.value.content_images || []),
          ...uploadedPaths,
        ]
      }
    } else {
      payload.reference_answer = content
      if (uploadedPaths.length) {
        payload.reference_answer_images = [
          ...(selectedQuestion.value.reference_answer_images || []),
          ...uploadedPaths,
        ]
      }
    }

    await updateQuestionContent(qid, payload)
    message.success('保存成功')

    // Update local state
    if (contentModalType.value === 'content') {
      selectedQuestion.value.content = content
      if (payload.content_images) selectedQuestion.value.content_images = payload.content_images
    } else {
      selectedQuestion.value.reference_answer = content
      if (payload.reference_answer_images) {
        selectedQuestion.value.reference_answer_images = payload.reference_answer_images
      }
    }
  } catch (e) {
    message.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function removeImage(field, idx) {
  const q = selectedQuestion.value
  if (!q) return
  const key = field === 'content' ? 'content_images' : 'reference_answer_images'
  const imgs = [...(q[key] || [])]
  imgs.splice(idx, 1)
  try {
    await updateQuestionContent(q.question_id, { [key]: imgs })
    q[key] = imgs
    await loadQuestions()
    message.success('图片已删除')
  } catch (e) {
    message.error('删除失败')
  }
}

async function handleDocCropSave(results) {
  let ok = 0
  const grouped = {}
  for (const r of results) {
    const key = `${r.questionNum}::${r.field}`
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(r)
  }
  for (const [, items] of Object.entries(grouped)) {
    const { questionNum, field } = items[0]
    const q = questions.value.find(q =>
      q.name === questionNum || q.question_name === questionNum
    )
    if (!q) {
      message.warning(`题号 ${questionNum} 未找到对应题目（当前科目主观题：${questions.value.map(q => q.name || q.question_name).join(', ')}）`)
      continue
    }
    try {
      const paths = []
      // 先上传父题题干（如果有层级关系）
      const parentBlobs = items.filter(it => it.parentBlob).map(it => it.parentBlob)
      const seenParents = new Set()
      for (const pb of parentBlobs) {
        const pbKey = pb.size
        if (seenParents.has(pbKey)) continue
        seenParents.add(pbKey)
        const parentFile = new File([pb], `crop_${questionNum}_parent_stem.png`, { type: 'image/png' })
        const uploadRes = await uploadQuestionImage(q.question_id, parentFile)
        if (uploadRes.data?.path) paths.push(uploadRes.data.path)
      }
      // 再上传子题自身的裁剪
      for (const item of items) {
        const file = new File([item.blob], `crop_${questionNum}_${field}_${items.indexOf(item) + 1}.png`, { type: 'image/png' })
        const uploadRes = await uploadQuestionImage(q.question_id, file)
        if (uploadRes.data?.path) paths.push(uploadRes.data.path)
      }
      if (paths.length) {
        const fresh = (await getQuestion(q.question_id)).data
        const existing = field === 'content'
          ? (fresh.content_images || [])
          : (fresh.reference_answer_images || [])
        const payload = field === 'content'
          ? { content_images: [...existing, ...paths] }
          : { reference_answer_images: [...existing, ...paths] }
        await updateQuestionContent(q.question_id, payload)
        ok += paths.length
      }
      // 同步分值（如果裁剪时填了分值）
      const scoreItem = items.find(it => it.score != null)
      if (scoreItem && scoreItem.score > 0) {
        try { await updateQuestion(q.question_id, { max_score: scoreItem.score }) } catch {}
      }
    } catch (e) {
      message.error(`题号 ${questionNum} 保存失败`)
    }
  }
  if (ok) await loadQuestions()
}

async function handleBatchGenerate() {
  batchGenerating.value = true
  let ok = 0, fail = 0
  try {
    for (const q of questions.value) {
      try {
        await generateRubric(q.question_id, q.max_score || 0)
        ok++
      } catch (e) {
        if (e.response?.status !== 400) fail++
      }
    }
    message.success(`批量生成完成: ${ok} 成功${fail ? ', ' + fail + ' 失败' : ''}`)
    await loadQuestions()
  } finally {
    batchGenerating.value = false
  }
}
</script>

<style scoped>
.ai-grading-page {
  padding: 4px 0;
}

.selector-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 800;
  margin: 0;
}

.main-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  align-items: start;
}

.left-panel {
  background: var(--card-color, #1e2a22);
  border: 1px solid var(--border-color, #2e3e34);
  border-radius: 12px;
  padding: 12px;
  position: sticky;
  top: 16px;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #8a9a8e;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color, #2e3e34);
}

.question-item {
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
  border: 1px solid transparent;
}

.question-item:hover {
  background: #242e28;
  border-color: #3a4a3e;
}

.question-item.active {
  background: #1a3020;
  border-color: #4ade80;
}

.q-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-num {
  font-size: 22px;
  font-weight: 800;
  color: #e8f0ea;
  min-width: 32px;
  text-align: center;
  flex-shrink: 0;
  line-height: 1;
}

.question-item.active .q-num {
  color: #4ade80;
}

.q-info {
  flex: 1;
  min-width: 0;
}

.q-title {
  font-size: 13px;
  color: #d0dcd2;
  margin-bottom: 5px;
  font-weight: 500;
}

.q-score {
  color: #90c090;
  font-weight: 600;
}
.q-score.editable {
  cursor: pointer; border-bottom: 1px dashed #90c090;
  margin-left: 6px;
}

.q-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.t {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.t.ok {
  background: #1a4020;
  color: #6ee7a0;
}

.t.warn {
  background: #3a2a0a;
  color: #fcd34d;
}

.q-progress {
  font-size: 11px;
  color: #b0c0b4;
  margin-top: 4px;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-card {
  border-radius: 12px;
}

.content-text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.image-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.img-wrapper {
  position: relative;
  display: inline-block;
}

.img-wrapper:hover .img-delete {
  opacity: 1;
}

.img-seq {
  position: absolute;
  top: 4px;
  left: 4px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
}

.img-delete {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.content-img {
  max-width: 240px;
  max-height: 180px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #2e3e34);
  object-fit: contain;
  cursor: pointer;
}

.progress-area {
  margin-bottom: 12px;
}

.progress-label {
  font-size: 13px;
  color: #8a9a8e;
  margin-bottom: 4px;
}

.done-text {
  font-size: 13px;
  color: #4ade80;
  margin-top: 6px;
  font-weight: 600;
}

.fail-text {
  font-size: 13px;
  color: #f87171;
  margin-top: 6px;
  font-weight: 600;
}

.empty-tip {
  font-size: 13px;
  color: #8a9a8e;
  padding: 8px 0;
}

.empty-tip.center {
  text-align: center;
  padding: 60px 0;
}

.loading-tip {
  font-size: 13px;
  color: #8a9a8e;
  padding: 16px 0;
  text-align: center;
}
</style>
