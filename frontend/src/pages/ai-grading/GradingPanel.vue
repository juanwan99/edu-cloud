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
          @click="$emit('start-grading', limitValue)"
          style="margin-top: 10px"
        >开始阅卷</n-button>
      </n-card>

    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { NCard, NButton, NSpace, NProgress, NImage, NInputNumber } from 'naive-ui'
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

defineEmits([
  'edit-content',
  'remove-image',
  'generate-rubric',
  'save-rubric',
  'update:rubricItems',
  'start-grading',
])

const limitValue = ref(null)

const taskProgressPct = computed(() => {
  if (!props.taskProgress || !props.taskProgress.total) return 0
  return Math.round((props.taskProgress.graded / props.taskProgress.total) * 100)
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

.grading-limit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.limit-label {
  font-size: 13px;
  color: #cfd8d3;
  white-space: nowrap;
}

.limit-hint {
  font-size: 12px;
  color: #6b7c72;
  white-space: nowrap;
}

.empty-tip.center {
  text-align: center;
  padding: 60px 0;
}
</style>
