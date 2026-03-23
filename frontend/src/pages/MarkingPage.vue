<template>
  <div class="marking-container">
    <!-- 顶栏 -->
    <div class="marking-topbar">
      <n-button text @click="$router.push('/marking')">
        <span style="font-size: 18px; margin-right: 4px;">&#8592;</span> 返回选题
      </n-button>
      <div class="topbar-info">
        <span class="topbar-question">{{ questionName }}</span>
        <n-tag type="info" round size="small">满分 {{ maxScore }}</n-tag>
        <span class="topbar-progress">{{ position.current }} / {{ position.total }}</span>
      </div>
      <div style="width: 100px;" />
    </div>

    <n-spin :show="loading" class="marking-body">
      <div v-if="done" class="marking-done">
        <n-result status="success" title="全部批改完成" description="该题所有答卷已批改">
          <template #footer>
            <n-button type="primary" @click="$router.push('/marking')">返回选题</n-button>
          </template>
        </n-result>
      </div>

      <div v-else class="marking-main">
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
            <h3 class="score-title">评分</h3>

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
              提交并下一份 (Enter)
            </n-button>
          </div>

          <!-- 快捷键提示 -->
          <div class="hotkey-hint">
            <div><kbd>0</kbd>-<kbd>9</kbd> 输入分数</div>
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
import client from '../api/client'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const questionId = route.params.questionId
const loading = ref(true)
const submitting = ref(false)
const done = ref(false)

// 答卷数据
const currentAnswerId = ref(null)
const imageUrl = ref('')
const position = ref({ current: 0, total: 0 })
const questionName = ref('')
const maxScore = ref(10)

// 打分
const currentScore = ref(null)
const comment = ref('')
const scoreInputRef = ref(null)

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
  for (let i = 0; i <= max; i++) {
    buttons.push(i)
  }
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

async function loadNext() {
  loading.value = true
  try {
    const { data } = await getNext(questionId)
    if (data.done) {
      done.value = true
    } else {
      const ans = data.answer
      currentAnswerId.value = ans.answer_id
      await loadImage(ans.answer_id)
      position.value = ans.position
    }
  } catch {
    message.error('加载失败')
  }
  loading.value = false
  currentScore.value = null
  comment.value = ''
  resetZoom()
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
    if (data.next?.done) {
      done.value = true
    } else if (data.next?.answer) {
      const ans = data.next.answer
      currentAnswerId.value = ans.answer_id
      await loadImage(ans.answer_id)
      position.value = ans.position
      currentScore.value = null
      comment.value = ''
      resetZoom()
      await nextTick()
      scoreInputRef.value?.focus()
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '提交失败')
  }
  submitting.value = false
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

// 拖拽
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

// 键盘快捷键
function handleKeydown(e) {
  if (e.target.tagName === 'TEXTAREA') return

  if (e.key === 'Escape') {
    router.push('/marking')
    return
  }

  if (e.key === 'Enter' && !e.target.closest('.n-input-number')) {
    handleSubmit()
    return
  }

  if (e.key >= '0' && e.key <= '9' && !e.target.closest('.n-input-number')) {
    const num = parseInt(e.key)
    if (num <= maxScore.value) {
      currentScore.value = num
    }
  }
}

async function loadQuestionInfo() {
  try {
    const { data } = await client.get(`/questions/${questionId}`)
    questionName.value = data.name
    maxScore.value = data.max_score
  } catch {
    questionName.value = '题目'
    maxScore.value = 10
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
.marking-container {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  z-index: 100;
}

.marking-topbar {
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

.marking-body {
  flex: 1;
  overflow: hidden;
}

.marking-main {
  display: grid;
  grid-template-columns: 1fr 320px;
  height: 100%;
}

.marking-done {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* 图片区 */
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

/* 打分区 */
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
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
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
