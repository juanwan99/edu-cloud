<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">教师复核</h1>
      <p class="page-subtitle">审批 AI 批改结果，通过或改分</p>
    </div>

    <n-spin :show="loading">
      <div class="review-layout">
        <!-- 左侧列表 -->
        <div class="review-list">
          <div v-for="(item, idx) in pendingItems" :key="item.id"
            :class="['review-item', { active: currentIndex === idx }]"
            @click="selectItem(idx)">
            <div style="font-weight: 600; font-size: 14px;">{{ item.question_id?.slice(0, 8) }}...</div>
            <div style="font-size: 13px; color: var(--color-text-secondary);">
              AI: {{ item.score }} / {{ item.max_score }}
            </div>
            <n-tag size="tiny" round :type="item.confidence >= 0.8 ? 'success' : 'warning'">
              {{ (item.confidence * 100).toFixed(0) }}%
            </n-tag>
          </div>
          <n-empty v-if="!loading && pendingItems.length === 0" description="全部复核完成 🎉" />
        </div>

        <!-- 右侧详情 -->
        <div class="review-detail">
          <template v-if="current">
            <n-card>
              <n-descriptions bordered :column="2" size="small" style="margin-bottom: 20px;">
                <n-descriptions-item label="AI 评分" :span="1">
                  <span style="font-size: 24px; font-weight: 800;">{{ current.score }}</span>
                  <span style="color: var(--color-text-muted);"> / {{ current.max_score }}</span>
                </n-descriptions-item>
                <n-descriptions-item label="置信度" :span="1">
                  <n-tag :type="current.confidence >= 0.8 ? 'success' : 'warning'" round>
                    {{ (current.confidence * 100).toFixed(0) }}%
                  </n-tag>
                </n-descriptions-item>
              </n-descriptions>

              <h4 style="margin-bottom: 8px; font-weight: 700;">AI 反馈</h4>
              <div style="background: var(--color-bg-alt); padding: 16px; border-radius: var(--radius-sm); white-space: pre-wrap; margin-bottom: 24px; font-size: 14px; line-height: 1.8;">
                {{ current.feedback || '无反馈' }}
              </div>

              <n-divider />

              <div style="display: flex; gap: 12px; align-items: flex-end;">
                <n-button type="primary" class="btn-pill" size="large" :loading="submitting"
                  @click="handleApprove">
                  ✓ 通过
                </n-button>

                <div style="display: flex; gap: 8px; align-items: center;">
                  <n-input-number v-model:value="adjustedScore" :min="0" :max="current.max_score"
                    :step="0.5" style="width: 120px;" placeholder="改分" />
                  <n-button type="warning" class="btn-pill" size="large" :loading="submitting"
                    :disabled="adjustedScore === null" @click="handleOverride">
                    改分
                  </n-button>
                </div>
              </div>
            </n-card>
          </template>
          <n-empty v-else description="选择左侧条目开始复核" />
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { getPending, submitReview } from '../api/grading'

const message = useMessage()
const loading = ref(true)
const submitting = ref(false)
const pendingItems = ref([])
const currentIndex = ref(-1)
const adjustedScore = ref(null)

const current = computed(() => currentIndex.value >= 0 ? pendingItems.value[currentIndex.value] : null)

function selectItem(idx) {
  currentIndex.value = idx
  adjustedScore.value = null
}

async function handleApprove() {
  if (!current.value) return
  submitting.value = true
  try {
    await submitReview(current.value.id, { action: 'approve' })
    message.success('已通过')
    removeAndAdvance()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  }
  submitting.value = false
}

async function handleOverride() {
  if (!current.value || adjustedScore.value === null) return
  submitting.value = true
  try {
    await submitReview(current.value.id, { action: 'override', adjusted_score: adjustedScore.value })
    message.success('已改分')
    removeAndAdvance()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  }
  submitting.value = false
}

function removeAndAdvance() {
  pendingItems.value.splice(currentIndex.value, 1)
  if (currentIndex.value >= pendingItems.value.length) {
    currentIndex.value = pendingItems.value.length - 1
  }
  adjustedScore.value = null
}

onMounted(async () => {
  try {
    const { data } = await getPending()
    pendingItems.value = data
    if (data.length > 0) currentIndex.value = 0
  } catch { /* interceptor */ }
  loading.value = false
})
</script>

<style scoped>
.review-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
  min-height: 500px;
}

.review-list {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 8px;
  overflow-y: auto;
  max-height: 70vh;
}

.review-item {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.review-item:hover {
  background: var(--color-bg-alt);
}

.review-item.active {
  background: var(--macaron-mint-light);
  border: 1px solid var(--macaron-mint);
}

.review-detail {
  min-width: 0;
}

@media (max-width: 768px) {
  .review-layout {
    grid-template-columns: 1fr;
  }
  .review-list {
    max-height: 200px;
  }
}
</style>
