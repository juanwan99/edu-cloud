<template>
  <div class="review-container">
    <!-- 顶栏 -->
    <div class="review-topbar">
      <n-button text @click="$router.back()">
        <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
        返回上一级
      </n-button>
      <div class="topbar-info">
        <span class="topbar-question">{{ questionName }}</span>
        <n-tag type="info" round size="small">满分 {{ maxScore }}</n-tag>
        <n-button-group size="small">
          <n-button :type="reviewMode === 'ungraded' ? 'primary' : 'default'" @click="switchMode('ungraded')">待阅</n-button>
          <n-button :type="reviewMode === 'ai_review' ? 'primary' : 'default'" @click="switchMode('ai_review')">AI 复核</n-button>
          <n-button :type="reviewMode === 'reviewed' ? 'primary' : 'default'" @click="switchMode('reviewed')">已批改</n-button>
        </n-button-group>
        <template v-if="reviewMode === 'reviewed'">
          <n-switch v-model:value="divergenceFilter" size="small" style="margin-left: 12px;" />
          <span style="font-size: 12px; color: var(--color-text-secondary); margin-left: 4px;">只看分歧 ≥</span>
          <n-input-number v-model:value="divergenceMin" size="tiny" :min="1" :max="50" style="width: 60px; margin-left: 4px;" :disabled="!divergenceFilter" @update:value="reloadReviewed" />
          <span style="font-size: 12px; color: var(--color-text-secondary); margin-left: 2px;">分</span>
        </template>
      </div>
    </div>

    <n-spin :show="loading" class="review-body">
      <div v-if="done" class="review-done">
        <n-result
          status="success"
          :title="reviewMode === 'reviewed' ? (divergenceFilter ? '无分歧答卷' : '已浏览全部') : '全部批改完成'"
          :description="reviewMode === 'reviewed' ? (divergenceFilter ? '当前阈值下无匹配答卷，可调低阈值或关闭筛选' : '该题所有已批改答卷已浏览完毕') : '该题所有答卷已确认'"
        >
          <template #footer>
            <n-space>
              <n-button v-if="reviewMode !== 'reviewed'" @click="switchMode('ai_review')">查看 AI 复核记录</n-button>
              <n-button v-if="reviewMode !== 'reviewed'" @click="switchMode('reviewed')">查看已批改</n-button>
              <n-button type="primary" @click="$router.back()">
                <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
                返回上一级
              </n-button>
            </n-space>
          </template>
        </n-result>
      </div>

      <div v-else class="review-main">
        <!-- 左栏：图片 + AI 阅卷结果 -->
        <div class="left-panel">
          <div class="image-panel">
            <n-button
              v-if="imageUrl"
              class="floating-open-btn"
              size="small"
              secondary
              @click.stop="openFloatingReview(true)"
            >
              悬浮阅卷
            </n-button>
            <div
              class="image-wrapper"
              :style="imageTransform"
              @wheel.prevent="handleWheel"
              @mousedown="startDrag"
            >
              <img
                v-if="imageUrl"
                :src="imageUrl"
                class="answer-image answer-image--clickable"
                @click.stop="openFloatingReview()"
                @dblclick.stop="resetZoom"
                draggable="false"
              />
              <img
                v-for="(url, i) in childImageUrls"
                :key="'child-' + i"
                :src="url"
                class="answer-image child-image answer-image--clickable"
                @click.stop="openFloatingReview()"
                draggable="false"
              />
            </div>
          </div>
          <div class="review-pager">
            <n-button-group size="small">
              <n-button :disabled="browseIndex <= 0 || loading" @click="goPrev">&#9664;</n-button>
              <n-button disabled class="review-pager-count">{{ position.current }} / {{ position.total }}</n-button>
              <n-button :disabled="browseIndex >= position.total - 1 || loading" @click="goNext">&#9654;</n-button>
            </n-button-group>
          </div>

          <div v-if="ai" class="ai-result-card">
            <div class="ai-header">
              <span class="ai-title">AI 阅卷结果</span>
              <div class="ai-header-right">
                <n-tag v-if="ai.deductions?.length" type="error" round size="small" class="ai-deduction-badge">扣 {{ ai.deductions.length }} 项</n-tag>
                <span class="ai-score-num">{{ ai.score }}</span>
                <span class="ai-score-max">/ {{ maxScore }}</span>
                <n-tag
                  v-if="ai.confidence != null"
                  :type="ai.confidence >= 0.8 ? 'success' : 'warning'"
                  round
                  size="small"
                  style="margin-left: 8px"
                >
                  置信度 {{ (ai.confidence * 100).toFixed(0) + '%' }}
                </n-tag>
              </div>
            </div>
            <div v-if="ai.feedback" class="ai-feedback-wrap">
              <div class="ai-feedback" :class="{ 'ai-feedback--collapsed': !feedbackExpanded }">{{ ai.feedback }}</div>
              <n-button v-if="ai.feedback.length > 80" text size="tiny" class="ai-feedback-toggle" @click="feedbackExpanded = !feedbackExpanded">{{ feedbackExpanded ? '收起' : '展开' }}</n-button>
            </div>
            <div v-if="mergedDetails.length" class="ai-details">
              <div class="ai-details-title">逐空评分</div>
              <div class="ai-details-grid">
                <div v-for="(item, i) in mergedDetails" :key="i" class="ai-sub" :class="item.correct ? 'ai-sub--pass' : item.score > 0 ? 'ai-sub--partial' : 'ai-sub--wrong'">
                  <div class="ai-sub-header">
                    <span class="ai-sub-label">{{ formatBlankNo(item.blankNo, i) }}</span>
                    <span class="ai-sub-score" :class="item.correct ? 'ai-sub-score--pass' : item.score > 0 ? 'ai-sub-score--partial' : 'ai-sub-score--fail'">
                      {{ item.score }}/{{ item.maxScore }} {{ item.correct ? '✓' : item.score > 0 ? '△' : '✗' }}
                    </span>
                    <n-button v-if="!getAnnotation(item.blankNo || String(i)) && annEditing !== (item.blankNo || String(i))" class="ann-hover-btn" size="tiny" text @click.stop="startAnnotation(item.blankNo || String(i))">+</n-button>
                  </div>
                  <div class="ai-sub-body">
                    <div v-if="item.answer != null" class="ai-sub-answer">
                      <span class="ai-sub-field-label">答：</span><span :class="item.answer ? '' : 'ai-sub-empty'">{{ item.answer || '未作答' }}</span>
                    </div>
                    <div v-if="item.reason" class="ai-sub-reason"><span class="ai-sub-field-label">理：</span>{{ item.reason }}</div>
                  </div>
                  <div v-if="getAnnotation(item.blankNo || String(i))" class="ann-existing">
                    <span class="ann-tag">{{ getAnnotation(item.blankNo || String(i)).target === 'ocr' ? 'OCR' : '评分' }}</span>
                    <span class="ann-text">{{ getAnnotation(item.blankNo || String(i)).comment }}</span>
                    <n-button size="tiny" text type="error" @click="removeAnnotation(item.blankNo || String(i))">删</n-button>
                  </div>
                  <div v-if="annEditing === (item.blankNo || String(i))" class="ann-input-row">
                    <n-radio-group v-model:value="annTarget" size="tiny">
                      <n-radio-button value="ocr">OCR</n-radio-button>
                      <n-radio-button value="score">评分</n-radio-button>
                    </n-radio-group>
                    <n-input v-model:value="annComment" size="small" placeholder="标注说明" @keyup.enter="submitAnnotation(item.blankNo || String(i))" style="flex:1" />
                    <n-input-number v-if="annTarget === 'score'" v-model:value="annSuggestedScore" size="small" :min="0" :max="item.maxScore" placeholder="建议分" style="width:80px" />
                    <n-button size="tiny" type="primary" @click="submitAnnotation(item.blankNo || String(i))">确认</n-button>
                    <n-button size="tiny" @click="annEditing = null">取消</n-button>
                  </div>
                </div>
              </div>
            </div>
            <!-- 整题标注 -->
            <div v-if="ai" class="ann-overall">
              <div v-if="getAnnotation(null)" class="ann-existing">
                <span class="ann-tag">整题</span>
                <span class="ann-text">{{ getAnnotation(null).comment }}</span>
                <n-button size="tiny" text type="error" @click="removeAnnotation(null)">删除</n-button>
              </div>
              <div v-else-if="annEditing === '_overall'" class="ann-input-row">
                <n-input v-model:value="annComment" size="small" placeholder="整题标注" @keyup.enter="submitAnnotation(null)" style="flex:1" />
                <n-button size="tiny" type="primary" @click="submitAnnotation(null)">确认</n-button>
                <n-button size="tiny" @click="annEditing = null">取消</n-button>
              </div>
              <n-button v-else size="tiny" text @click="annEditing = '_overall'; annComment = ''; annTarget = 'score'">+ 整题标注</n-button>
            </div>
            <div v-if="ai.deductions?.length" class="ai-deductions">
              <div class="ai-deductions-title">扣分项</div>
              <div v-for="(d, i) in ai.deductions" :key="i" class="ai-deduction-item">{{ d }}</div>
            </div>
          </div>
        </div>

        <!-- 打分区 -->
        <div class="score-panel">
          <div class="score-section">
            <h3 class="score-title">评分</h3>

            <!-- AI vs 人工分值对比 -->
            <div v-if="ai && isGraded && reviewMode === 'ai_review'" class="ai-manual-compare">
              <span class="compare-label">人工评分：</span>
              <span class="compare-score">{{ currentScore }}</span>
              <span class="compare-separator">vs</span>
              <span class="compare-label">AI 评分：</span>
              <span class="compare-score">{{ ai.score }}</span>
              <n-tag
                v-if="currentScore != null && ai.score != null"
                :type="Math.abs(currentScore - ai.score) <= 1 ? 'success' : Math.abs(currentScore - ai.score) <= 3 ? 'warning' : 'error'"
                round
                size="small"
                style="margin-left: 8px"
              >
                差值 {{ (currentScore - ai.score) >= 0 ? '+' : '' }}{{ (currentScore - ai.score).toFixed(1) }}
              </n-tag>
            </div>

            <!-- 分数输入 -->
            <n-input-number
              ref="scoreInputRef"
              v-model:value="currentScore"
              :min="0"
              :max="maxScore"
              :step="scoreStep"
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

            <!-- 异常标记 -->
            <div class="anomaly-section">
              <n-popselect
                v-model:value="selectedAnomalyType"
                :options="anomalyOptions"
                trigger="click"
                @update:value="handleFlag"
              >
                <n-button
                  size="small"
                  block
                  :type="currentAnomaly ? 'warning' : 'default'"
                  :ghost="!currentAnomaly"
                >
                  {{ currentAnomaly ? `已标记: ${anomalyLabel}` : '标记异常' }}
                </n-button>
              </n-popselect>
              <n-button
                v-if="currentAnomaly"
                size="tiny"
                text
                type="error"
                @click="handleClearFlag"
              >
                取消标记
              </n-button>
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
              {{ isGraded ? '修改评分 (Enter)' : ai ? '确认并下一份 (Enter)' : '提交并下一份 (Enter)' }}
            </n-button>
          </div>

          <!-- 快捷键提示 -->
          <div class="hotkey-hint">
            <div><kbd>0</kbd>-<kbd>9</kbd> 输入分数</div>
            <div><kbd>Enter</kbd> 提交</div>
            <div><kbd>←</kbd><kbd>→</kbd> 前后翻页</div>
            <div><kbd>Esc</kbd> 返回</div>
            <div>滚轮缩放 / 双击还原</div>
          </div>
        </div>
      </div>
    </n-spin>

    <teleport to="body">
      <div v-if="floatingReviewOpen && !done" class="floating-review-mask">
        <div class="floating-review-shell">
          <div class="floating-review-toolbar">
            <div class="floating-review-title">
              <span class="floating-question-name">{{ questionName }}</span>
              <n-tag type="info" round size="small">满分 {{ maxScore }}</n-tag>
              <span class="floating-position">{{ position.current }} / {{ position.total }}</span>
            </div>
            <n-button-group size="small">
              <n-button @click="zoomOut">-</n-button>
              <n-button @click="resetZoom">1:1</n-button>
              <n-button @click="zoomIn">+</n-button>
              <n-button type="primary" ghost @click="closeFloatingReview">关闭</n-button>
            </n-button-group>
          </div>

          <div class="floating-review-layout">
            <div class="floating-image-stage">
              <div
                class="floating-review-image-wrapper"
                :style="imageTransform"
                @wheel="handleFloatingWheel"
                @mousedown="startDrag"
              >
                <img
                  v-if="imageUrl"
                  :src="imageUrl"
                  class="floating-answer-image"
                  @dblclick.stop="resetZoom"
                  draggable="false"
                />
                <img
                  v-for="(url, i) in childImageUrls"
                  :key="'floating-child-' + i"
                  :src="url"
                  class="floating-answer-image floating-child-image"
                  draggable="false"
                />
              </div>
            </div>

            <aside class="floating-score-panel">
              <div class="floating-score-fixed">
                <div class="floating-score-heading">
                  <h3 class="score-title">评分</h3>
                  <n-tag v-if="ai" size="small" round :type="ai.score != null ? 'info' : 'default'">
                    AI {{ ai.score ?? '-' }} / {{ maxScore }}
                  </n-tag>
                </div>
                <n-input-number
                  ref="floatingScoreInputRef"
                  v-model:value="currentScore"
                  :min="0"
                  :max="maxScore"
                  :step="scoreStep"
                  size="large"
                  placeholder="输入分数"
                  class="score-input"
                  @keydown.enter="handleSubmit"
                />
              </div>

              <div class="floating-score-scroll">
                <div class="score-buttons">
                  <button
                    v-for="s in scoreButtons"
                    :key="'floating-score-' + s"
                    :class="['score-btn', { active: currentScore === s }]"
                    @click="setScore(s)"
                  >
                    {{ s }}
                  </button>
                </div>

                <div class="comment-section">
                  <n-collapse>
                    <n-collapse-item title="添加批注" name="floating-comment">
                      <n-input
                        v-model:value="comment"
                        type="textarea"
                        placeholder="可选批注"
                        :rows="4"
                      />
                    </n-collapse-item>
                  </n-collapse>
                </div>

                <div class="anomaly-section">
                  <n-popselect
                    v-model:value="selectedAnomalyType"
                    :options="anomalyOptions"
                    trigger="click"
                    @update:value="handleFlag"
                  >
                    <n-button
                      size="small"
                      block
                      :type="currentAnomaly ? 'warning' : 'default'"
                      :ghost="!currentAnomaly"
                    >
                      {{ currentAnomaly ? `已标记: ${anomalyLabel}` : '标记异常' }}
                    </n-button>
                  </n-popselect>
                  <n-button
                    v-if="currentAnomaly"
                    size="tiny"
                    text
                    type="error"
                    @click="handleClearFlag"
                  >
                    取消标记
                  </n-button>
                </div>
              </div>

              <div class="floating-score-footer">
                <n-button-group size="small" class="floating-review-nav">
                  <n-button :disabled="browseIndex <= 0 || loading" @click="goPrev">&#9664;</n-button>
                  <n-button disabled class="review-pager-count">{{ position.current }} / {{ position.total }}</n-button>
                  <n-button :disabled="browseIndex >= position.total - 1 || loading" @click="goNext">&#9654;</n-button>
                </n-button-group>
                <n-button
                  type="primary"
                  size="large"
                  block
                  class="btn-pill"
                  :loading="submitting"
                  :disabled="currentScore === null"
                  @click="handleSubmit"
                >
                  {{ isGraded ? '修改评分 (Enter)' : ai ? '确认并下一份 (Enter)' : '提交并下一份 (Enter)' }}
                </n-button>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, NIcon } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { getNext, submitScore, getAnswerAt } from '../api/marking'
import client from '../api/client'
import { useImageZoom } from './review/useImageZoom'
import { useAnnotations } from './review/useAnnotations'
import { useScoring } from './review/useScoring'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const questionId = route.params.questionId
const loading = ref(true)
const submitting = ref(false)
const done = ref(false)

const currentAnswerId = ref(null)
const imageUrl = ref('')
const childImageUrls = ref([])
const childAi = ref([])
const position = ref({ current: 0, total: 0 })
const questionName = ref('')
const questionType = ref('')
const maxScore = ref(10)
const ai = ref(null)
const feedbackExpanded = ref(false)
const scoreInputRef = ref(null)
const floatingScoreInputRef = ref(null)
const floatingReviewOpen = ref(false)

const mergedDetails = computed(() => {
  const main = ai.value?.details || []
  const childDetails = childAi.value.flatMap(cai =>
    (cai.details?.length ? cai.details : [{ blankNo: '作图', score: cai.score, maxScore: cai.score, correct: cai.score > 0, reason: cai.feedback }])
  )
  return [...main, ...childDetails]
})

const {
  dragMoved,
  imageTransform,
  resetZoom, zoomIn, zoomOut,
  handleWheel, handleFloatingWheel,
  startDrag, stopDrag, cleanup: cleanupZoom,
} = useImageZoom()

const {
  annotations, annEditing, annTarget, annComment, annSuggestedScore,
  getAnnotation, startAnnotation, removeAnnotation: _removeAnnotation, submitAnnotation: _submitAnnotation,
  resetAnnotations,
} = useAnnotations()

const removeAnnotation = (blankNo) => _removeAnnotation(blankNo, ai.value?.result_id)
const submitAnnotation = (blankNo) => _submitAnnotation(blankNo, ai.value?.result_id)

const {
  currentScore, comment, isGraded,
  currentAnomaly, selectedAnomalyType,
  anomalyOptions, anomalyLabel,
  setScore, applyScoring,
  handleFlag: _handleFlag, handleClearFlag: _handleClearFlag,
} = useScoring()

const handleFlag = (value) => _handleFlag(value, currentAnswerId.value)
const handleClearFlag = () => _handleClearFlag(currentAnswerId.value)

const reviewMode = ref(route.query.mode === 'reviewed' ? 'reviewed' : 'ungraded')
const browseIndex = ref(-1)
const savedOffsets = { ungraded: -1, ai_review: -1, reviewed: -1 }
const divergenceFilter = ref(false)
const divergenceMin = ref(3)
const browsing = ref(false)
const loadSeq = ref(0)

const isCompositionQuestion = computed(() =>
  maxScore.value >= 40 && (!questionType.value || questionType.value === 'essay')
)
const scoreStep = computed(() => isCompositionQuestion.value ? 2 : 0.5)
const scoreButtons = computed(() => {
  const max = Math.floor(maxScore.value)
  const buttons = []
  const step = isCompositionQuestion.value ? 2 : 1
  for (let i = 0; i <= max; i += step) buttons.push(i)
  if (buttons[buttons.length - 1] !== max) buttons.push(max)
  return buttons
})

async function openFloatingReview(force = false) {
  if (!imageUrl.value || (!force && dragMoved.value)) return
  resetZoom()
  floatingReviewOpen.value = true
  dragMoved.value = false
  await nextTick()
  floatingScoreInputRef.value?.focus()
}

async function closeFloatingReview() {
  floatingReviewOpen.value = false
  stopDrag()
  await nextTick()
  scoreInputRef.value?.focus()
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

async function applyAnswer(answerPayload) {
  currentAnswerId.value = answerPayload.answer_id
  position.value = answerPayload.position
  const isReview = reviewMode.value === 'ai_review'
  ai.value = isReview ? (answerPayload.ai || null) : null
  resetAnnotations(isReview ? answerPayload.annotations : [])
  feedbackExpanded.value = false
  if (answerPayload.max_score != null) maxScore.value = answerPayload.max_score
  applyScoring(answerPayload, ai.value)
  resetZoom()

  childImageUrls.value.forEach(u => URL.revokeObjectURL(u))
  childImageUrls.value = []
  childAi.value = isReview ? (answerPayload.child_ai || []) : []
  if (answerPayload.child_answer_ids?.length) {
    for (const cid of answerPayload.child_answer_ids) {
      try {
        const resp = await client.get(`/marking/answer/${cid}/image`, { responseType: 'blob' })
        childImageUrls.value.push(URL.createObjectURL(resp.data))
      } catch { /* skip */ }
    }
  }
}

async function loadNext() {
  const seq = ++loadSeq.value
  loading.value = true
  done.value = false
  try {
    const extra = reviewMode.value === 'reviewed' && divergenceFilter.value ? { divergence_min: divergenceMin.value } : {}
    const { data } = await getNext(questionId, reviewMode.value, extra)
    if (seq !== loadSeq.value) return
    if (data.done) {
      done.value = true
      closeFloatingReview()
    } else {
      await applyAnswer(data.answer)
      browseIndex.value = data.answer.position.current - 1
      savedOffsets[reviewMode.value] = browseIndex.value
      browsing.value = false
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
    if (reviewMode.value === 'ai_review' || reviewMode.value === 'reviewed') {
      if (browseIndex.value < position.value.total - 1) {
        await loadAnswerAt(browseIndex.value + 1)
      } else {
        done.value = true
        closeFloatingReview()
      }
    } else if (data.next?.done) {
      done.value = true
      closeFloatingReview()
    } else if (data.next?.answer) {
      await applyAnswer(data.next.answer)
      await loadImage(data.next.answer.answer_id)
      await nextTick()
      scoreInputRef.value?.focus()
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '提交失败')
  }
  submitting.value = false
}

async function loadAnswerAt(offset) {
  const seq = ++loadSeq.value
  loading.value = true
  done.value = false
  try {
    const extra = reviewMode.value === 'reviewed' && divergenceFilter.value ? { divergence_min: divergenceMin.value } : {}
    const { data } = await getAnswerAt(questionId, offset, reviewMode.value, extra)
    if (seq !== loadSeq.value) return
    browseIndex.value = offset
    savedOffsets[reviewMode.value] = offset
    browsing.value = true
    await applyAnswer(data)
    if (data.graded_score != null) {
      currentScore.value = data.graded_score
      comment.value = data.graded_comment || ''
      isGraded.value = true
    }
    await loadImage(data.answer_id)
  } catch (e) {
    if (seq !== loadSeq.value) return
    if (e?.response?.status === 404 && reviewMode.value === 'ai_review') {
      done.value = true
    } else {
      message.error('加载失败')
    }
  }
  loading.value = false
  await nextTick()
  scoreInputRef.value?.focus()
}

function goPrev() {
  if (browseIndex.value > 0) loadAnswerAt(browseIndex.value - 1)
}

function goNext() {
  if (browseIndex.value < position.value.total - 1) loadAnswerAt(browseIndex.value + 1)
}

function switchMode(mode) {
  if (reviewMode.value === mode) return
  savedOffsets[reviewMode.value] = browseIndex.value
  reviewMode.value = mode
  const saved = savedOffsets[mode]
  if (saved >= 0) {
    loadAnswerAt(saved)
  } else {
    loadNext()
  }
}

function reloadReviewed() {
  if (reviewMode.value !== 'reviewed') return
  savedOffsets.reviewed = -1
  loadNext()
}

function formatBlankNo(blankNo, index) {
  if (!blankNo) return `第${index + 1}空`
  const s = String(blankNo)
  if (s.startsWith('第')) return s
  return `第${s}空`
}

function handleKeydown(e) {
  if (e.key === 'Escape') {
    if (floatingReviewOpen.value) { closeFloatingReview(); return }
    router.back()
    return
  }
  if (e.target.tagName === 'TEXTAREA') return
  if (e.key === 'ArrowLeft' && !e.target.closest('.n-input-number')) { goPrev(); return }
  if (e.key === 'ArrowRight' && !e.target.closest('.n-input-number')) { goNext(); return }
  if (e.key === 'Enter' && !e.target.closest('.n-input-number')) { handleSubmit(); return }
  if (e.key >= '0' && e.key <= '9' && !e.target.closest('.n-input-number')) {
    const num = parseInt(e.key)
    if (num <= maxScore.value) currentScore.value = num
  }
}

async function loadQuestionInfo() {
  try {
    const { data } = await client.get(`/questions/${questionId}`)
    questionName.value = data.name
    questionType.value = data.question_type || ''
    if (maxScore.value === 10) maxScore.value = data.max_score
  } catch {
    questionName.value = '题目'
    questionType.value = ''
  }
}

onMounted(() => {
  loadQuestionInfo()
  loadNext()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  cleanupZoom()
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  childImageUrls.value.forEach(u => URL.revokeObjectURL(u))
})
</script>

<style scoped>
.review-container {
  display: flex;
  flex-direction: column;
  height: 100%;
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
  font-weight: var(--fw-bold);
  font-size: var(--fs-base);
}

.topbar-progress {
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
}

.review-body {
  flex: 1;
  overflow: hidden;
}

.review-body :deep(.n-spin-content) {
  height: 100%;
}

.review-main {
  display: grid;
  grid-template-columns: 1fr 340px;
  grid-template-rows: 1fr;
  height: 100%;
  overflow: hidden;
}

.review-done {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.left-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.image-panel {
  height: 55%;
  flex-shrink: 0;
  overflow: hidden;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.floating-open-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.12));
}

.review-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 8px 12px;
  background: #fff;
  border-top: 1px solid var(--color-border-light);
  border-bottom: 1px solid var(--color-border-light);
}

.review-pager-count {
  min-width: 72px;
}

.ai-result-card {
  background: var(--color-bg-card, #fff);
  border-top: 1px solid var(--color-border-light);
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.ai-header-right {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.image-wrapper {
  transform-origin: center center;
  transition: transform 0.05s ease-out;
}

.answer-image {
  max-width: 90%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  box-shadow: var(--shadow-md, 0 2px 12px rgba(0, 0, 0, 0.15));
  border-radius: 4px;
}

.answer-image--clickable {
  cursor: zoom-in;
}

.child-image {
  margin-top: 12px;
  border: 2px solid #60a5fa;
}

.score-panel {
  background: white;
  border-left: 1px solid var(--color-border-light);
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow-y: auto;
  min-height: 0;
}

.floating-review-mask {
  position: fixed;
  inset: 0;
  z-index: 5000;
  padding: 16px;
  background: rgba(16, 20, 24, 0.72);
  display: flex;
  min-width: 0;
  min-height: 0;
}

.floating-review-shell {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-card, #fff);
  border-radius: 8px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.32);
}

.floating-review-toolbar {
  height: 56px;
  flex-shrink: 0;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid var(--color-border-light);
}

.floating-review-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.floating-question-name {
  font-size: var(--fs-base);
  font-weight: var(--fw-bold);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.floating-position {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.floating-review-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 370px;
}

.floating-image-stage {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8eaed;
}

.floating-review-image-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  transform-origin: center center;
  transition: transform 0.05s ease-out;
}

.floating-answer-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.22);
}

.floating-child-image {
  border: 2px solid #60a5fa;
}

.floating-review-image-wrapper:has(.floating-child-image) .floating-answer-image {
  max-height: 48%;
}

.floating-score-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid var(--color-border-light);
}

.floating-score-fixed {
  flex-shrink: 0;
  padding: 18px 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.floating-score-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.floating-score-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.floating-score-footer {
  flex-shrink: 0;
  padding: 14px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--color-border-light);
}

.floating-review-nav {
  width: 100%;
  display: flex;
}

.floating-review-nav :deep(.n-button) {
  flex: 1;
}

.score-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 900px) {
  .floating-review-mask {
    padding: 8px;
  }

  .floating-review-toolbar {
    height: auto;
    min-height: 56px;
    flex-wrap: wrap;
    padding: 10px 12px;
  }

  .floating-review-layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) 42vh;
  }

  .floating-score-panel {
    border-left: 0;
    border-top: 1px solid var(--color-border-light);
  }
}


.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ai-title {
  font-size: var(--fs-base);
  font-weight: var(--fw-bold);
  color: var(--color-text);
}

.ai-score-num {
  font-size: 24px;
  font-weight: var(--fw-bold);
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.ai-score-max {
  color: var(--color-text-muted);
  font-size: var(--fs-sm);
}

.ai-deduction-badge {
  margin-right: 6px;
}

.ai-feedback-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-feedback {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
}

.ai-feedback--collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ai-feedback-toggle {
  align-self: flex-start;
  color: var(--color-primary);
}


.ai-details {
  border-top: 1px solid var(--color-border-light);
  padding-top: 6px;
}

.ai-details-title {
  font-size: 12px;
  font-weight: var(--fw-semibold);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.ai-details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.ai-sub {
  border-left: 3px solid var(--color-border);
  border-radius: 0 4px 4px 0;
  background: var(--color-bg-alt);
}

.ai-sub--pass {
  border-left-color: var(--color-primary);
}

.ai-sub--partial {
  border-left-color: var(--color-warning);
}

.ai-sub--wrong {
  border-left-color: var(--color-danger);
  background: var(--surface-danger-light);
}

.ai-sub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  padding: 3px 8px;
}

.ai-sub-label {
  font-weight: var(--fw-semibold);
  color: var(--color-text);
}

.ai-sub-score {
  font-weight: var(--fw-bold);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  min-width: 48px;
  text-align: right;
}
.ai-sub-score--pass { color: var(--color-primary); }
.ai-sub-score--partial { color: var(--color-warning); }
.ai-sub-score--fail { color: var(--color-danger); }

.ai-sub-body {
  padding: 0 8px 4px;
  font-size: 12px;
  line-height: 1.4;
}

.ai-sub-field-label {
  color: var(--color-text-muted);
  font-size: 12px;
  margin-right: 2px;
}

.ai-sub-answer {
  color: var(--color-text);
  margin-bottom: 1px;
}

.ai-sub-empty {
  color: var(--color-danger);
  font-style: italic;
}

.ai-sub-reason {
  color: var(--color-text-secondary);
}

.ai-deductions {
  border-top: 1px solid var(--color-border-light);
  padding-top: 6px;
  margin-top: 2px;
}
.ai-deductions-title {
  font-size: 12px;
  font-weight: var(--fw-semibold);
  color: var(--color-danger);
  margin-bottom: 4px;
}
.ai-deduction-item {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  padding: 2px 0 2px 10px;
  border-left: 2px solid var(--surface-danger);
  margin-bottom: 3px;
}

.score-title {
  font-size: var(--fs-lg);
  font-weight: var(--fw-bold);
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
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  transition: transform 0.15s ease-out, box-shadow 0.15s ease-out;
}

.score-btn:hover {
  background: var(--color-bg-alt);
  border-color: var(--color-primary);
}

.score-btn.active {
  background: var(--color-primary, #644CF0);
  color: var(--color-bg, #fff);
  border-color: var(--color-primary, #644CF0);
  box-shadow: 0 0 0 2px rgba(24, 160, 88, 0.3);
}

.anomaly-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comment-section {
  margin-top: 8px;
}

.hotkey-hint {
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
  font-size: var(--fs-base);
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
  font-size: var(--fs-base);
}

.ann-hover-btn {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s;
  margin-left: auto;
  font-size: 14px;
}

.ai-sub:hover .ann-hover-btn {
  opacity: 1;
  pointer-events: auto;
}

.ann-input-row {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  padding: 3px 8px;
  border-top: 1px dashed var(--color-border-light);
}

.ann-existing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
}

.ann-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--surface-accent-light);
  color: var(--color-warning);
  white-space: nowrap;
  font-weight: var(--fw-semibold);
}

.ann-text {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.ann-overall {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--color-border-light);
}

.ai-manual-compare {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 10px;
  margin-bottom: 6px;
  background: var(--surface-primary-light);
  border-radius: var(--radius-sm, 6px);
  font-size: var(--fs-sm);
}

.compare-label {
  color: var(--color-text-muted);
}

.compare-score {
  font-weight: var(--fw-bold);
  font-size: var(--fs-lg);
  font-variant-numeric: tabular-nums;
}

.compare-separator {
  color: var(--color-text-muted);
  margin: 0 2px;
}

</style>
