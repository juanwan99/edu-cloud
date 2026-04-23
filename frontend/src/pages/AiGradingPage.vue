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
    <div v-if="!hasRouteParams" class="selector-bar">
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 280px"
        :loading="loadingExams"
        @update:value="onExamSelected"
      />
      <n-select
        v-if="selectedExamId"
        v-model:value="selectedSubjectId"
        :options="subjectOptions"
        placeholder="选择科目"
        style="width: 200px"
        :loading="loadingSubjects"
        @update:value="onSubjectSelected"
      />
    </div>

    <div class="main-layout" v-if="examId && subjectId">
      <!-- 左侧：题目列表 -->
      <div class="left-panel">
        <div class="panel-title">主观题列表</div>
        <div v-if="loadingQuestions" class="loading-tip">加载中...</div>
        <div v-else-if="questions.length === 0" class="empty-tip">暂无主观题</div>
        <div
          v-for="q in questions"
          :key="q.question_id"
          class="question-item"
          :class="{ active: selectedQuestion?.question_id === q.question_id }"
          @click="selectQuestion(q)"
        >
          <div class="q-row">
            <span class="q-num">{{ q.name || q.question_name }}</span>
            <div class="q-info">
              <div class="q-title">
                {{ q.question_type === 'essay' ? '主观题' : '填空题' }}
                <span class="q-score">{{ q.max_score }}分</span>
              </div>
              <div class="q-tags">
                <span class="t" :class="q.has_content ? 'ok' : 'warn'">
                  {{ q.has_content ? '题干' : '无题干' }}{{ q.content_image_count ? ` ${q.content_image_count}图` : '' }}
                </span>
                <span class="t" :class="q.has_answer ? 'ok' : 'warn'">
                  {{ q.has_answer ? '答案' : '无答案' }}{{ q.answer_image_count ? ` ${q.answer_image_count}图` : '' }}
                </span>
                <span class="t" :class="q.has_rubric ? 'ok' : 'warn'">{{ q.has_rubric ? '细则' : '无细则' }}</span>
              </div>
              <div v-if="q.answer_count" class="q-progress">
                {{ q.graded_count }}/{{ q.answer_count }} 已阅
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：详情面板 -->
      <div class="right-panel">
        <div v-if="!selectedQuestion" class="empty-tip center">请从左侧选择一道题</div>
        <template v-else>

          <!-- 原题卡片 -->
          <n-card class="detail-card" title="原题">
            <template #header-extra>
              <n-button size="small" @click="openContentModal('content')">编辑</n-button>
            </template>
            <div v-if="selectedQuestion.content" class="content-text">{{ selectedQuestion.content }}</div>
            <div v-else class="empty-tip">暂无题干</div>
            <div v-if="selectedQuestion.content_images?.length" class="image-row">
              <div v-for="(img, i) in selectedQuestion.content_images" :key="i" class="img-wrapper">
                <img :src="img" class="content-img" alt="题目图片" />
                <span class="img-seq">{{ i + 1 }}</span>
                <n-button class="img-delete" size="tiny" circle type="error"
                          @click="removeImage('content', i)">✕</n-button>
              </div>
            </div>
          </n-card>

          <!-- 参考答案卡片 -->
          <n-card class="detail-card" title="参考答案">
            <template #header-extra>
              <n-button size="small" @click="openContentModal('answer')">编辑</n-button>
            </template>
            <div v-if="selectedQuestion.reference_answer" class="content-text">{{ selectedQuestion.reference_answer }}</div>
            <div v-else class="empty-tip">暂无参考答案</div>
            <div v-if="selectedQuestion.reference_answer_images?.length" class="image-row">
              <div v-for="(img, i) in selectedQuestion.reference_answer_images" :key="i" class="img-wrapper">
                <img :src="img" class="content-img" alt="答案图片" />
                <span class="img-seq">{{ i + 1 }}</span>
                <n-button class="img-delete" size="tiny" circle type="error"
                          @click="removeImage('answer', i)">✕</n-button>
              </div>
            </div>
          </n-card>

          <!-- 评分细则 -->
          <n-card class="detail-card" title="评分细则">
            <template #header-extra>
              <n-space>
                <n-button
                  size="small"
                  type="primary"
                  :loading="rubricGenerating"
                  @click="handleGenerateRubric"
                >AI 生成</n-button>
                <n-button
                  size="small"
                  :loading="rubricSaving"
                  @click="handleSaveRubric"
                >保存</n-button>
              </n-space>
            </template>
            <RubricEditor
              v-model="rubricItems"
              :max-score="selectedQuestion.max_score || 0"
              :loading="rubricLoading"
            />
          </n-card>

          <!-- 阅卷操作 -->
          <n-card class="detail-card" title="阅卷操作">
            <div v-if="taskProgress !== null" class="progress-area">
              <div class="progress-label">进度: {{ taskProgress.graded }}/{{ taskProgress.total }}</div>
              <n-progress
                type="line"
                :percentage="taskProgressPct"
                :show-indicator="false"
                style="margin-top: 6px"
              />
              <div v-if="taskProgress.status === 'completed'" class="done-text">阅卷完成</div>
              <div v-else-if="taskProgress.status === 'failed'" class="fail-text">阅卷失败</div>
            </div>
            <n-button
              type="primary"
              :loading="gradingStarting"
              :disabled="taskProgress?.status === 'processing'"
              @click="handleStartGrading"
            >开始阅卷</n-button>
          </n-card>

        </template>
      </div>
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
      @save="handleDocCropSave"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NCard, NButton, NSpace, NProgress, NSelect } from 'naive-ui'
import { getDispatchStatus, generateRubric, getRubric, saveRubric, createTask, getTask, getQuestion, updateQuestionContent, uploadQuestionImage } from '../api/grading'
import { listExams } from '../api/exams'
import { listSubjects } from '../api/subjects'
import RubricEditor from '../components/RubricEditor.vue'
import QuestionContentModal from '../components/QuestionContentModal.vue'
import DocCropPanel from '../components/DocCropPanel.vue'

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
const taskProgressPct = computed(() => {
  if (!taskProgress.value || !taskProgress.value.total) return 0
  return Math.round((taskProgress.value.graded / taskProgress.value.total) * 100)
})
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
