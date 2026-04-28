<template>
  <div class="right-panel">
    <div v-if="!question" class="empty-tip center">请从左侧选择一道题</div>
    <template v-else>

      <!-- 原题卡片 -->
      <n-card class="detail-card" title="原题">
        <template #header-extra>
          <n-button size="small" @click="$emit('edit-content', 'content')">编辑</n-button>
        </template>
        <div v-if="question.content" class="content-text">{{ question.content }}</div>
        <div v-else class="empty-tip">暂无题干</div>
        <div v-if="question.content_images?.length" class="image-row">
          <div v-for="(img, i) in question.content_images" :key="i" class="img-wrapper">
            <n-image :src="img" :width="240" object-fit="contain" class="content-img" />
            <span class="img-seq">{{ i + 1 }}</span>
            <n-button class="img-delete" size="tiny" circle type="error"
                      @click="$emit('remove-image', 'content', i)">&#x2715;</n-button>
          </div>
        </div>
      </n-card>

      <!-- 参考答案卡片 -->
      <n-card class="detail-card" title="参考答案">
        <template #header-extra>
          <n-button size="small" @click="$emit('edit-content', 'answer')">编辑</n-button>
        </template>
        <div v-if="question.reference_answer" class="content-text">{{ question.reference_answer }}</div>
        <div v-else class="empty-tip">暂无参考答案</div>
        <div v-if="question.reference_answer_images?.length" class="image-row">
          <div v-for="(img, i) in question.reference_answer_images" :key="i" class="img-wrapper">
            <n-image :src="img" :width="240" object-fit="contain" class="content-img" />
            <span class="img-seq">{{ i + 1 }}</span>
            <n-button class="img-delete" size="tiny" circle type="error"
                      @click="$emit('remove-image', 'answer', i)">&#x2715;</n-button>
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
              @click="$emit('generate-rubric')"
            >AI 生成</n-button>
            <n-button
              size="small"
              :loading="rubricSaving"
              @click="$emit('save-rubric')"
            >保存</n-button>
          </n-space>
        </template>
        <RubricEditor
          :modelValue="rubricItems"
          @update:modelValue="$emit('update:rubricItems', $event)"
          :max-score="question.max_score || 0"
          :loading="rubricLoading"
        />
      </n-card>

      <!-- 学生答案预览 -->
      <n-card class="detail-card" title="学生答案">
        <template #header-extra>
          <span v-if="studentAnswers.length" class="answer-count">
            {{ currentAnswerIndex + 1 }} / {{ studentAnswers.length }}
          </span>
        </template>
        <div v-if="answersLoading" class="empty-tip">加载中...</div>
        <div v-else-if="!studentAnswers.length" class="empty-tip">暂无学生答案</div>
        <template v-else>
          <div class="answer-nav">
            <n-button size="small" :disabled="currentAnswerIndex <= 0"
                      @click="currentAnswerIndex--">&lt;</n-button>
            <span class="student-label">学号: {{ currentAnswer.student_id }}</span>
            <n-button size="small" :disabled="currentAnswerIndex >= studentAnswers.length - 1"
                      @click="currentAnswerIndex++">></n-button>
          </div>
          <div v-if="currentAnswer.is_absent" class="status-tag absent">缺考</div>
          <div v-else-if="currentAnswer.is_anomaly" class="status-tag anomaly">异常</div>
          <div v-if="currentAnswer.image_url" class="answer-image-box">
            <n-image :src="currentAnswer.image_url" object-fit="contain" class="answer-img" />
          </div>
          <div v-else class="empty-tip">无答卷图片</div>
        </template>
      </n-card>

      <!-- 评分结果 -->
      <n-card v-if="currentGradingResult" class="detail-card result-card" title="评分结果">
        <template #header-extra>
          <span class="score-badge">
            {{ currentGradingResult.final_score ?? currentGradingResult.ai_score ?? '-' }}
            / {{ currentGradingResult.max_score }}
          </span>
        </template>

        <div class="result-meta">
          <div class="result-row">
            <span class="result-label">状态</span>
            <n-tag :type="statusTagType" size="small">{{ statusText }}</n-tag>
          </div>
          <div v-if="currentGradingResult.ai_confidence != null" class="result-row">
            <span class="result-label">置信度</span>
            <span>{{ (currentGradingResult.ai_confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>

        <div v-if="currentGradingResult.ai_feedback" class="feedback-section">
          <div class="section-title">评语</div>
          <div class="feedback-text">{{ currentGradingResult.ai_feedback }}</div>
        </div>

        <div v-if="currentGradingResult.details?.length" class="details-section">
          <div class="section-title">细化评分</div>
          <div v-for="(sub, si) in currentGradingResult.details" :key="si" class="sub-question-block">
            <div class="sub-header">
              <span class="sub-label">{{ sub.subQuestion || `第${si + 1}小题` }}</span>
              <span class="sub-score">{{ sub.score }}/{{ sub.fullScore }}分</span>
            </div>
            <div v-if="sub.blanks?.length" class="blanks-list">
              <div v-for="(blank, bi) in sub.blanks" :key="bi"
                   class="blank-item" :class="blank.correct ? 'correct' : 'wrong'">
                <span>第{{ blank.index }}空: {{ blank.score }}/{{ blank.fullScore }}分
                  {{ blank.correct ? '✓' : '✗' }}</span>
                <span v-if="blank.answer" class="blank-answer">{{ blank.answer }}</span>
                <span v-if="blank.reason" class="blank-reason">({{ blank.reason }})</span>
              </div>
            </div>
          </div>
        </div>
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
          @click="$emit('start-grading')"
        >开始阅卷</n-button>
      </n-card>

    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { NCard, NButton, NSpace, NProgress, NImage, NTag } from 'naive-ui'
import RubricEditor from '../../components/RubricEditor.vue'

const props = defineProps({
  question: { type: Object, default: null },
  rubricItems: { type: Array, default: () => [] },
  rubricLoading: { type: Boolean, default: false },
  rubricGenerating: { type: Boolean, default: false },
  rubricSaving: { type: Boolean, default: false },
  taskProgress: { type: Object, default: null },
  gradingStarting: { type: Boolean, default: false },
  studentAnswers: { type: Array, default: () => [] },
  answersLoading: { type: Boolean, default: false },
})

defineEmits([
  'edit-content',
  'remove-image',
  'generate-rubric',
  'save-rubric',
  'update:rubricItems',
  'start-grading',
])

const currentAnswerIndex = ref(0)

watch(() => props.studentAnswers, () => {
  currentAnswerIndex.value = 0
})

const currentAnswer = computed(() => props.studentAnswers[currentAnswerIndex.value] || null)
const currentGradingResult = computed(() => currentAnswer.value?.grading_result || null)

const taskProgressPct = computed(() => {
  if (!props.taskProgress || !props.taskProgress.total) return 0
  return Math.round((props.taskProgress.graded / props.taskProgress.total) * 100)
})

const statusText = computed(() => {
  const s = currentGradingResult.value?.status
  if (s === 'ai_done') return 'AI 已评'
  if (s === 'confirmed') return '已确认'
  if (s === 'ai_pending') return '评分中'
  return s || ''
})

const statusTagType = computed(() => {
  const s = currentGradingResult.value?.status
  if (s === 'confirmed') return 'success'
  if (s === 'ai_done') return 'info'
  if (s === 'ai_pending') return 'warning'
  return 'default'
})
</script>

<style scoped>
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

/* --- 学生答案预览 --- */
.answer-count {
  font-size: 12px;
  color: #8a9a8e;
}

.answer-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.student-label {
  font-size: 13px;
  color: #c0d0c4;
  flex: 1;
  text-align: center;
}

.status-tag {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.status-tag.absent {
  background: rgba(251, 146, 60, 0.15);
  color: #fb923c;
}

.status-tag.anomaly {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.answer-image-box {
  border: 1px solid #2e3e34;
  border-radius: 8px;
  overflow: hidden;
  background: #0d1a12;
}

.answer-img {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
}

/* --- 评分结果 --- */
.result-card {
  border-left: 3px solid #4ade80;
}

.score-badge {
  background: linear-gradient(135deg, #4ade80, #22c55e);
  color: #0d1a12;
  padding: 3px 12px;
  border-radius: 16px;
  font-weight: 700;
  font-size: 13px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
}

.result-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.result-label {
  color: #8a9a8e;
}

.feedback-section {
  margin-bottom: 12px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #8a9a8e;
  margin-bottom: 6px;
}

.feedback-text {
  font-size: 13px;
  line-height: 1.6;
  color: #c0d0c4;
  white-space: pre-wrap;
}

.details-section {
  border-top: 1px dashed #2e3e34;
  padding-top: 12px;
}

.sub-question-block {
  margin-bottom: 8px;
}

.sub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(74, 222, 128, 0.08);
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.sub-label {
  font-size: 13px;
  font-weight: 500;
  color: #4ade80;
}

.sub-score {
  font-size: 13px;
  font-weight: 600;
  color: #4ade80;
}

.blanks-list {
  padding-left: 12px;
}

.blank-item {
  font-size: 12px;
  padding: 3px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.blank-item.correct {
  color: #4ade80;
}

.blank-item.wrong {
  color: #f87171;
}

.blank-answer {
  color: #8a9a8e;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.blank-reason {
  color: #6b7b6f;
  font-size: 11px;
}
</style>
