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
        <div v-if="isEssay" class="anchor-section">
          <div class="anchor-title">评分锚定范文（作文校准用，可选）</div>
          <div class="anchor-hint">配置高/中/低三档真实样本，AI 评分时以此为参照校准尺度</div>
          <div v-for="(a, i) in anchors" :key="i" class="anchor-row">
            <div class="anchor-head">
              <span class="anchor-tier">{{ a.tier }}</span>
              <span class="anchor-score-label">人工分</span>
              <n-input-number size="tiny" :value="a.score" :min="0" :max="question.max_score || 50"
                style="width:68px" @update:value="v => updateAnchor(i, 'score', v)" />
            </div>
            <n-input size="small" type="textarea" :value="a.summary"
              :placeholder="a.placeholder"
              :autosize="{ minRows: 2, maxRows: 4 }"
              @update:value="v => updateAnchor(i, 'summary', v)" />
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
        <div class="grading-mode-row">
          <span class="limit-label">阅卷模式</span>
          <n-radio-group v-model:value="modeValue" size="small">
            <n-radio-button value="realtime">实时模式</n-radio-button>
            <n-radio-button value="batch">经济模式</n-radio-button>
          </n-radio-group>
        </div>
        <div class="mode-desc">
          {{ modeValue === 'realtime' ? '即时返回结果，适合少量或急用' : '异步处理，成本减半，适合大批量' }}
        </div>
        <div class="grading-mode-row">
          <n-checkbox v-model:checked="useVision" size="small">Vision 直评</n-checkbox>
          <span class="limit-hint">跳过 OCR，直接看图评分（含图/表/图形的题目）</span>
        </div>
        <div class="grading-limit-row">
          <span class="limit-label">阅卷数量</span>
          <n-input-number
            v-model:value="limitValue"
            :min="1"
            :max="9999"
            placeholder="全部"
            clearable
            size="small"
            style="width: 140px"
          />
          <span class="limit-hint">留空则批改全部</span>
        </div>
        <n-button
          type="primary"
          :loading="gradingStarting"
          :disabled="taskProgress?.status === 'processing'"
          @click="$emit('start-grading', limitValue, modeValue, useVision)"
          style="margin-top: 10px"
        >开始阅卷</n-button>
      </n-card>

    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { NCard, NButton, NSpace, NProgress, NImage, NInputNumber, NRadioGroup, NRadioButton, NCheckbox } from 'naive-ui'
import RubricEditor from '../../components/RubricEditor.vue'

const props = defineProps({
  question: { type: Object, default: null },
  rubricItems: { type: Array, default: () => [] },
  rubricLoading: { type: Boolean, default: false },
  rubricGenerating: { type: Boolean, default: false },
  rubricSaving: { type: Boolean, default: false },
  taskProgress: { type: Object, default: null },
  gradingStarting: { type: Boolean, default: false },
})

const emit = defineEmits([
  'edit-content',
  'remove-image',
  'generate-rubric',
  'save-rubric',
  'update:rubricItems',
  'start-grading',
])

const limitValue = ref(null)
const modeValue = ref('realtime')
const useVision = ref(false)

const isEssay = computed(() => {
  const items = props.rubricItems || []
  return items.length === 1 && (items[0]?.score || 0) >= 40
})

const ANCHOR_TIERS = [
  { tier: '高分档', placeholder: '二类文样本摘要：扣题+叙事完整+感情真挚，人工给了多少分、为什么' },
  { tier: '中分档', placeholder: '三类文样本摘要：扣题+有叙事但情感一般，人工给了多少分、为什么' },
  { tier: '低分档', placeholder: '五类文样本摘要：跑题/残篇/字数严重不足，人工给了多少分、为什么' },
]

const anchors = computed(() => {
  const saved = (props.rubricItems?.[0]?.essayAnchors) || []
  return ANCHOR_TIERS.map((t, i) => ({
    ...t,
    score: saved[i]?.score ?? null,
    summary: saved[i]?.summary ?? '',
  }))
})

function updateAnchor(idx, field, value) {
  const items = [...props.rubricItems]
  const item = { ...items[0] }
  const arr = [...(item.essayAnchors || [null, null, null])]
  while (arr.length < 3) arr.push(null)
  arr[idx] = { ...(arr[idx] || {}), tier: ANCHOR_TIERS[idx].tier, [field]: value }
  item.essayAnchors = arr
  items[0] = item
  emit('update:rubricItems', items)
}

const taskProgressPct = computed(() => {
  if (!props.taskProgress || !props.taskProgress.total) return 0
  return Math.round((props.taskProgress.graded / props.taskProgress.total) * 100)
})
</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-card {
  border-radius: var(--radius-md);
}

.content-text {
  font-size: var(--fs-base);
  line-height: 1.6;
  white-space: pre-wrap;
}

.image-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
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
  top: var(--space-1);
  left: var(--space-1);
  background: rgba(0,0,0,0.6);
  color: var(--color-bg, #fff);
  font-size: var(--fs-xs);
  padding: 1px 5px;
  border-radius: 3px;
}

.img-delete {
  position: absolute;
  top: var(--space-1);
  right: var(--space-1);
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
  margin-bottom: var(--space-3);
}

.progress-label {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-bottom: var(--space-1);
}

.done-text {
  font-size: var(--fs-base);
  color: var(--color-success);
  margin-top: 6px;
  font-weight: var(--fw-semibold);
}

.fail-text {
  font-size: var(--fs-base);
  color: var(--color-danger);
  margin-top: 6px;
  font-weight: var(--fw-semibold);
}

.empty-tip {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  padding: var(--space-2) 0;
}

.grading-limit-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.limit-label {
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.limit-hint {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  white-space: nowrap;
}

.grading-mode-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.mode-desc {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
}

.empty-tip.center {
  text-align: center;
  padding: 60px 0;
}

.anchor-section {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border-color, #2e3e34);
}

.anchor-title {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

.anchor-hint {
  font-size: var(--fs-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
}

.anchor-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-color, #2e3e34);
}

.anchor-row:last-child { border-bottom: none; }

.anchor-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.anchor-tier {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-success);
  min-width: 56px;
}

.anchor-score-label {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
}
</style>
