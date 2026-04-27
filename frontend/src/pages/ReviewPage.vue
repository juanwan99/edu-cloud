<template>
  <div class="review-container">
    <!-- 顶栏 -->
    <div class="review-topbar">
      <n-button text @click="$router.back()">
        <span style="font-size: 18px; margin-right: 4px;">&#8592;</span> 返回上一级
      </n-button>
      <div class="topbar-info">
        <span class="topbar-question">{{ questionName }}</span>
        <n-tag type="info" round size="small">满分 {{ maxScore }}</n-tag>
        <n-button-group v-if="canManageGrading" size="small">
          <n-button :type="reviewMode === 'ungraded' ? 'primary' : 'default'" @click="switchMode('ungraded')">待阅</n-button>
          <n-button :type="reviewMode === 'ai_review' ? 'primary' : 'default'" @click="switchMode('ai_review')">AI 复核</n-button>
        </n-button-group>
        <span class="topbar-progress">{{ position.current }} / {{ position.total }}</span>
      </div>
      <div v-if="canManageGrading" class="topbar-actions">
        <n-popconfirm @positive-click="handleBatchGrade">
          <template #trigger>
            <n-button size="small" :loading="batchStarting" :disabled="batchStarting">AI 批量阅卷</n-button>
          </template>
          确认对该题所有未阅答卷启动 AI 批量阅卷？
        </n-popconfirm>
      </div>
    </div>

    <n-spin :show="loading" class="review-body">
      <div v-if="done" class="review-done">
        <n-result
          :status="reviewMode === 'ai_review' ? 'info' : 'success'"
          :title="reviewMode === 'ai_review' ? '全部 AI 答卷已复核' : '全部批改完成'"
          :description="reviewMode === 'ai_review' ? '该题所有 AI 评分均已确认' : '该题所有答卷已确认'"
        >
          <template #footer>
            <n-space>
              <n-button v-if="reviewMode === 'ai_review'" @click="switchMode('ungraded')">切换到待阅模式</n-button>
              <n-button type="primary" @click="$router.back()">返回上一级</n-button>
            </n-space>
          </template>
        </n-result>
      </div>

      <div v-else class="review-main">
        <!-- 图片区 -->
        <div class="image-panel">
          <div
            class="image-wrapper"
            :style="imageTransform"
            @wheel.prevent="handleWheel"
            @mousedown="startDrag"
          >
            <img
              v-if="imageUrl"
              :src="imageUrl"
              class="answer-image"
              @dblclick="resetZoom"
              draggable="false"
            />
          </div>
        </div>

        <!-- 打分区 -->
        <div class="score-panel">
          <div class="score-section">
            <!-- AI 试阅按钮（需 manage_grading 权限） -->
            <n-button
              v-if="canManageGrading && !ai && !aiGrading"
              block
              @click="handleAiGradeSingle"
              :disabled="!currentAnswerId"
            >
              AI 试阅当前答卷
            </n-button>
            <div v-if="aiGrading" class="ai-grading-tip">
              <n-spin size="small" />
              <span>AI 评分中，请稍候...</span>
            </div>

            <!-- AI 预测 -->
            <div v-if="ai" class="ai-card">
              <div class="ai-header">
                <span class="ai-title">AI 预测</span>
                <n-tag
                  :type="ai.confidence >= 0.8 ? 'success' : 'warning'"
                  round
                  size="small"
                >
                  {{ ai.confidence != null ? (ai.confidence * 100).toFixed(0) + '%' : '—' }}
                </n-tag>
              </div>
              <div class="ai-score">
                <span class="ai-score-num">{{ ai.score }}</span>
                <span class="ai-score-max"> / {{ maxScore }}</span>
              </div>
              <div v-if="ai.feedback" class="ai-feedback">{{ ai.feedback }}</div>
              <n-button
                size="small"
                class="btn-pill"
                @click="currentScore = ai.score"
              >
                采纳 AI 分数 (A)
              </n-button>
            </div>

            <h3 class="score-title">{{ ai ? '校对' : '评分' }}</h3>

            <!-- 分数输入 -->
            <n-input-number
              ref="scoreInputRef"
              v-model:value="currentScore"
              :min="0"
              :max="maxScore"
              :step="0.5"
              size="large"
              placeholder="输入分数"
              class="score-input"
              @keydown.enter="handleSubmit"
            />

            <!-- 快捷分数按钮 -->
            <div class="score-buttons">
              <button
                v-for="s in scoreButtons"
                :key="s"
                :class="['score-btn', { active: currentScore === s }]"
                @click="setScore(s)"
              >
                {{ s }}
              </button>
            </div>

            <!-- 批注 -->
            <div class="comment-section">
              <n-collapse>
                <n-collapse-item title="添加批注" name="comment">
                  <n-input
                    v-model:value="comment"
                    type="textarea"
                    placeholder="可选批注"
                    :rows="3"
                  />
                </n-collapse-item>
              </n-collapse>
            </div>

            <!-- 提交按钮 -->
            <n-button
              type="primary"
              size="large"
              block
              class="btn-pill"
              :loading="submitting"
              :disabled="currentScore === null"
              @click="handleSubmit"
            >
              {{ ai ? '确认并下一份' : '提交并下一份' }} (Enter)
            </n-button>
          </div>

          <!-- 快捷键提示 -->
          <div class="hotkey-hint">
            <div><kbd>0</kbd>-<kbd>9</kbd> 输入分数</div>
            <div v-if="ai"><kbd>A</kbd> 采纳 AI 分数</div>
            <div><kbd>Enter</kbd> 提交</div>
            <div><kbd>Esc</kbd> 返回</div>
            <div>滚轮缩放 / 双击还原</div>
          </div>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { getNext, submitScore } from '../api/marking'
import { gradeSingle, createTask } from '../api/grading'
import { useAuthStore } from '../stores/auth'
import client from '../api/client'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const auth = useAuthStore()
const canManageGrading = computed(() => auth.checkPermission('manage_grading'))

const questionId = route.params.questionId
const loading = ref(true)
const submitting = ref(false)
const done = ref(false)

const currentAnswerId = ref(null)
const imageUrl = ref('')
const position = ref({ current: 0, total: 0 })
const questionName = ref('')
const maxScore = ref(10)
const ai = ref(null)  // {score, confidence, feedback, result_id} 或 null

const currentScore = ref(null)
const comment = ref('')
const scoreInputRef = ref(null)

const reviewMode = ref('ungraded')
const loadSeq = ref(0)
const aiGrading = ref(false)
const batchStarting = ref(false)
const subjectId = ref(null)

// 图片缩放/拖拽
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })

const imageTransform = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  cursor: dragging.value ? 'grabbing' : 'grab',
}))

const scoreButtons = computed(() => {
  const max = Math.floor(maxScore.value)
  const buttons = []
  for (let i = 0; i <= max; i++) buttons.push(i)
  return buttons
})

function setScore(s) {
  currentScore.value = s
}

async function loadImage(answerId) {
  try {
    const resp = await client.get(`/marking/answer/${answerId}/image`, { responseType: 'blob' })
    if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
    imageUrl.value = URL.createObjectURL(resp.data)
  } catch {
    imageUrl.value = ''
    message.error('图片加载失败')
  }
}

function applyAnswer(answerPayload) {
  currentAnswerId.value = answerPayload.answer_id
  position.value = answerPayload.position
  ai.value = answerPayload.ai || null
  if (answerPayload.max_score != null) maxScore.value = answerPayload.max_score
  // AI 预测时自动预填分数供教师校对
  currentScore.value = ai.value ? ai.value.score : null
  comment.value = ''
  resetZoom()
}

async function loadNext() {
  const seq = ++loadSeq.value
  loading.value = true
  done.value = false
  try {
    const { data } = await getNext(questionId, reviewMode.value)
    if (seq !== loadSeq.value) return
    if (data.done) {
      done.value = true
    } else {
      applyAnswer(data.answer)
      await loadImage(data.answer.answer_id)
    }
  } catch {
    if (seq !== loadSeq.value) return
    message.error('加载失败')
  }
  loading.value = false
  await nextTick()
  scoreInputRef.value?.focus()
}

async function handleSubmit() {
  if (currentScore.value === null || submitting.value) return
  submitting.value = true
  try {
    const { data } = await submitScore({
      answer_id: currentAnswerId.value,
      score: currentScore.value,
      comment: comment.value || undefined,
    })
    if (reviewMode.value === 'ai_review') {
      await loadNext()
    } else if (data.next?.done) {
      done.value = true
    } else if (data.next?.answer) {
      applyAnswer(data.next.answer)
      await loadImage(data.next.answer.answer_id)
      await nextTick()
      scoreInputRef.value?.focus()
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '提交失败')
  }
  submitting.value = false
}

async function handleAiGradeSingle() {
  if (!currentAnswerId.value || aiGrading.value) return
  aiGrading.value = true
  try {
    const { data } = await gradeSingle(currentAnswerId.value)
    ai.value = {
      score: data.score,
      confidence: data.confidence,
      feedback: data.feedback,
    }
    currentScore.value = data.score
    if (data.already_confirmed) {
      message.info('该答卷已有人工评分，AI 结果仅供参考')
    } else {
      message.success('AI 评分完成')
    }
  } catch (e) {
    message.error(e.response?.data?.detail || 'AI 评分失败')
  }
  aiGrading.value = false
}

async function handleBatchGrade() {
  if (!subjectId.value) {
    message.error('无法确定科目信息')
    return
  }
  batchStarting.value = true
  try {
    await createTask({ subject_id: subjectId.value, question_id: questionId })
    message.success('AI 批量阅卷任务已启动，稍后可切换到「AI 复核」模式查看结果')
  } catch (e) {
    message.error(e.response?.data?.detail || '启动批量阅卷失败')
  }
  batchStarting.value = false
}

function switchMode(mode) {
  if (reviewMode.value === mode) return
  reviewMode.value = mode
  loadNext()
}

// 图片缩放
function handleWheel(e) {
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  scale.value = Math.max(0.3, Math.min(5, scale.value + delta))
}

function resetZoom() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

function startDrag(e) {
  dragging.value = true
  dragStart.value = { x: e.clientX - translateX.value, y: e.clientY - translateY.value }
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  if (!dragging.value) return
  translateX.value = e.clientX - dragStart.value.x
  translateY.value = e.clientY - dragStart.value.y
}

function stopDrag() {
  dragging.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

function handleKeydown(e) {
  if (e.target.tagName === 'TEXTAREA') return

  if (e.key === 'Escape') {
    router.back()
    return
  }

  if (e.key === 'Enter' && !e.target.closest('.n-input-number')) {
    handleSubmit()
    return
  }

  if ((e.key === 'a' || e.key === 'A') && ai.value && !e.target.closest('.n-input-number')) {
    currentScore.value = ai.value.score
    return
  }

  if (e.key >= '0' && e.key <= '9' && !e.target.closest('.n-input-number')) {
    const num = parseInt(e.key)
    if (num <= maxScore.value) currentScore.value = num
  }
}

async function loadQuestionInfo() {
  try {
    const { data } = await client.get(`/questions/${questionId}`)
    questionName.value = data.name
    subjectId.value = data.subject_id
    if (maxScore.value === 10) maxScore.value = data.max_score
  } catch {
    questionName.value = '题目'
  }
}

onMounted(() => {
  loadQuestionInfo()
  loadNext()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
})
</script>

<style scoped>
.review-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 68px);
  background: var(--color-bg);
}

.review-topbar {
  height: 52px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.topbar-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-question {
  font-weight: 700;
  font-size: 16px;
}

.topbar-progress {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-body {
  flex: 1;
  overflow: hidden;
}

.review-main {
  display: grid;
  grid-template-columns: 1fr 340px;
  height: 100%;
}

.review-done {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.image-panel {
  overflow: hidden;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-wrapper {
  transform-origin: center center;
  transition: transform 0.05s ease-out;
}

.answer-image {
  max-width: 90%;
  max-height: 85vh;
  object-fit: contain;
  user-select: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.score-panel {
  background: white;
  border-left: 1px solid var(--color-border-light);
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow-y: auto;
}

.score-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-grading-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f0f7ff;
  border-radius: 8px;
  font-size: 13px;
  color: #3b82f6;
}

.ai-card {
  background: var(--color-bg-alt, #f7f8fa);
  border-radius: var(--radius-sm, 8px);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid var(--color-border-light, #e5e7eb);
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ai-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-secondary, #667085);
  letter-spacing: 0.5px;
}

.ai-score {
  display: flex;
  align-items: baseline;
}

.ai-score-num {
  font-size: 24px;
  font-weight: 800;
}

.ai-score-max {
  color: var(--color-text-muted);
  font-size: 14px;
}

.ai-feedback {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.score-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}

.score-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.score-btn {
  width: 48px;
  height: 40px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.score-btn:hover {
  background: var(--color-bg-alt);
  border-color: var(--color-primary);
}

.score-btn.active {
  background: #18a058;
  color: #fff;
  border-color: #18a058;
  box-shadow: 0 0 0 2px rgba(24, 160, 88, 0.3);
}

.comment-section {
  margin-top: 8px;
}

.hotkey-hint {
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
  font-size: 12px;
  color: var(--color-text-muted);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hotkey-hint kbd {
  display: inline-block;
  padding: 1px 6px;
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border-light);
  border-radius: 3px;
  font-family: inherit;
  font-size: 11px;
}
</style>
