<template>
  <div class="left-panel">
    <div class="panel-title">主观题列表</div>
    <div v-if="loading" class="loading-tip">加载中...</div>
    <div v-else-if="questions.length === 0" class="empty-tip">暂无主观题</div>
    <n-button v-if="!loading" size="small" block type="primary" ghost style="margin-bottom:8px;font-size:14px;font-weight:600" @click="$emit('add-question')">+ 添加题目</n-button>
    <div
      v-for="q in questions"
      :key="q.question_id"
      class="question-item"
      :class="{ active: selectedQuestionId === q.question_id }"
      @click="$emit('select', q)"
    >
      <div class="q-row">
        <span v-if="editingNameId !== q.question_id" class="q-num editable" @click.stop="$emit('start-edit-name', q)">{{ q.name || q.question_name }}</span>
        <n-input v-else :value="q.name || q.question_name" size="small" style="width:48px;font-size:20px;font-weight:800;text-align:center"
          @update:value="v => $emit('update-name-value', q, v)"
          @blur="$emit('save-name', q)" @keyup.enter="$emit('save-name', q)" @click.stop />
        <div class="q-info">
          <div class="q-title">
            {{ q.question_type === 'essay' ? '主观题' : '填空题' }}
            <span v-if="editingScoreId !== q.question_id" class="q-score editable" @click.stop="$emit('start-edit-score', q)">{{ q.max_score }}分</span>
            <n-input-number v-else :value="q.max_score" size="tiny" :min="0" :max="200" :step="1"
              style="width:70px" @update:value="v => $emit('update-score-value', q, v)"
              @blur="$emit('save-score', q)" @keyup.enter="$emit('save-score', q)" />
          </div>
          <div class="q-tags">
            <span class="t" :class="q.has_content ? 'ok' : 'warn'">
              {{ q.has_content ? '题干' : '无题干' }}{{ q.content_image_count ? ` ${q.content_image_count}图` : '' }}
            </span>
            <span class="t" :class="q.has_answer ? 'ok' : 'warn'">
              {{ q.has_answer ? '答案' : '无答案' }}{{ q.answer_image_count ? ` ${q.answer_image_count}图` : '' }}
            </span>
            <span v-if="generatingSet?.has?.(q.question_id)" class="t gen">生成中...</span>
            <span v-else class="t" :class="q.has_rubric ? 'ok' : 'warn'">{{ q.has_rubric ? '细则' : '无细则' }}</span>
          </div>
          <div v-if="q.answer_count" class="q-progress">
            {{ q.graded_count }}/{{ q.answer_count }} 已阅
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NInput, NInputNumber } from 'naive-ui'

defineProps({
  questions: { type: Array, default: () => [] },
  selectedQuestionId: { type: [String, Number], default: null },
  editingScoreId: { type: [String, Number], default: null },
  editingNameId: { type: [String, Number], default: null },
  generatingSet: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
})

defineEmits(['select', 'start-edit-score', 'save-score', 'update-score-value', 'add-question', 'start-edit-name', 'save-name', 'update-name-value'])
</script>

<style scoped>
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
.q-num.editable {
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: border-color 0.15s;
}
.q-num.editable:hover {
  border-color: #8a9a8e;
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
.t.gen {
  background: #0a2a3a;
  color: #60a5fa;
  animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

.q-progress {
  font-size: 11px;
  color: #b0c0b4;
  margin-top: 4px;
}

.loading-tip {
  font-size: 13px;
  color: #8a9a8e;
  padding: 16px 0;
  text-align: center;
}

.empty-tip {
  font-size: 13px;
  color: #8a9a8e;
  padding: 8px 0;
}
</style>
