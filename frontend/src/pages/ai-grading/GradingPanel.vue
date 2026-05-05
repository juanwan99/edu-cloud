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
          <div class="anchor-hint">配置 5 档真实样本（至少填 3 档：42/38/35 分），AI 评分时以此为参照校准尺度。高分≥39时自动触发二次确认</div>
          <div v-for="(a, i) in anchors" :key="i" class="anchor-row">
            <div class="anchor-head">
              <span class="anchor-tier">{{ a.tier }}</span>
              <span class="anchor-range">{{ a.range }}</span>
              <span class="anchor-score-label">校准分</span>
              <n-input-number size="tiny" :value="a.score" :min="0" :max="question.max_score || 50"
                :show-button="false" style="width:68px" @update:value="v => updateAnchor(i, 'score', v)" />
            </div>
            <div class="anchor-field">
              <span class="anchor-field-label">作文原文</span>
              <n-input size="small" type="textarea" :value="a.summary"
                :placeholder="a.summaryPlaceholder"
                :autosize="{ minRows: 2, maxRows: 3 }"
                @update:value="v => updateAnchor(i, 'summary', v)" />
            </div>
            <div class="anchor-field">
              <span class="anchor-field-label">评分理由</span>
              <n-input size="small" type="textarea" :value="a.reason"
                :placeholder="a.reasonPlaceholder"
                :autosize="{ minRows: 1, maxRows: 3 }"
                @update:value="v => updateAnchor(i, 'reason', v)" />
            </div>
          </div>
        </div>
      </n-card>

    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NCard, NButton, NSpace, NImage, NInputNumber } from 'naive-ui'
import RubricEditor from '../../components/RubricEditor.vue'

const props = defineProps({
  question: { type: Object, default: null },
  rubricItems: { type: Array, default: () => [] },
  rubricLoading: { type: Boolean, default: false },
  rubricGenerating: { type: Boolean, default: false },
  rubricSaving: { type: Boolean, default: false },
})

const emit = defineEmits([
  'edit-content',
  'remove-image',
  'generate-rubric',
  'save-rubric',
  'update:rubricItems',
])

const isEssay = computed(() => {
  const items = props.rubricItems || []
  return items.length === 1 && (items[0]?.score || 0) >= 40
})

const ANCHOR_TIERS = [
  { tier: '优秀档', range: '一类文 46分左右', summaryPlaceholder: '粘贴作文原文（二次确认用）', reasonPlaceholder: '多个生动场景，语言有持续表现力，结构精巧' },
  { tier: '良好档', range: '二类文 43分左右', summaryPlaceholder: '粘贴作文原文（二次确认用）', reasonPlaceholder: '完整变化链，情感真挚' },
  { tier: '中等档', range: '二类文 42分左右', summaryPlaceholder: '粘贴作文原文（主评基准线）', reasonPlaceholder: '有心理变化和具体场景' },
  { tier: '合格档', range: '三类文 38分左右', summaryPlaceholder: '粘贴作文原文（主评基准线）', reasonPlaceholder: '切题完整通顺，材料普通' },
  { tier: '偏弱档', range: '三类文 35分左右', summaryPlaceholder: '粘贴作文原文（主评基准线）', reasonPlaceholder: '叙事松散，细节缺乏' },
]

const anchors = computed(() => {
  const saved = (props.rubricItems?.[0]?.essayAnchors) || []
  return ANCHOR_TIERS.map((t, i) => ({
    ...t,
    score: saved[i]?.score ?? null,
    summary: saved[i]?.summary ?? '',
    reason: saved[i]?.reason ?? '',
  }))
})

function updateAnchor(idx, field, value) {
  const items = [...props.rubricItems]
  const item = { ...items[0] }
  const arr = [...(item.essayAnchors || [])]
  while (arr.length < ANCHOR_TIERS.length) arr.push(null)
  arr[idx] = { ...(arr[idx] || {}), tier: ANCHOR_TIERS[idx].tier, range: ANCHOR_TIERS[idx].range, [field]: value }
  item.essayAnchors = arr
  items[0] = item
  emit('update:rubricItems', items)
}


</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-card {
  border-radius: var(--radius-md);
  border: 1px solid rgba(255, 255, 255, 0.12);
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
  border: 1px solid rgba(255, 255, 255, 0.15);
  object-fit: contain;
  cursor: pointer;
}

.empty-tip {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  padding: var(--space-2) 0;
}

.empty-tip.center {
  text-align: center;
  padding: 60px 0;
}

.anchor-section {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed rgba(255, 255, 255, 0.15);
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
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

.anchor-range {
  font-size: var(--fs-xs);
  color: var(--color-text-muted);
}

.anchor-score-label {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-left: auto;
}

.anchor-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.anchor-field-label {
  font-size: var(--fs-xs);
  color: var(--color-text-muted);
}
</style>
