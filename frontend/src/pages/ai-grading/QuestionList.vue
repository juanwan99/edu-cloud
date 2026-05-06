<template>
  <div class="left-panel">
    <div class="panel-title">
      <span>主观题列表</span>
      <a v-if="questions.length > 1" class="select-all-link" @click.stop="toggleAll">
        {{ checkedIds.length === questions.length ? '取消' : '全选' }}
      </a>
    </div>
    <div v-if="loading" class="loading-tip">加载中...</div>
    <div v-else-if="questions.length === 0" class="empty-tip">暂无主观题</div>
    <n-button v-if="!loading" size="medium" block dashed style="margin-bottom:10px;font-size: var(--fs-base);font-weight:var(--fw-bold);color:var(--color-success, #4ade80);border-color:var(--color-success, #4ade80)" @click="$emit('add-question')">+ 添加题目</n-button>
    <div
      v-for="q in questions"
      :key="q.question_id"
      class="question-item"
      :class="{ active: selectedQuestionId === q.question_id }"
      @click="$emit('select', q)"
    >
      <div class="q-row">
        <n-checkbox :checked="checkedIds.includes(q.question_id)" @update:checked="toggleCheck(q.question_id)" @click.stop class="q-check" />
        <span v-if="editingNameId !== q.question_id" class="q-num editable" @click.stop="$emit('start-edit-name', q)">{{ q.name || q.question_name }}</span>
        <n-input v-else :value="q.name || q.question_name" size="small" style="width:48px;font-size:var(--fs-xl);font-weight:var(--fw-bold);text-align:center"
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
            <span class="t vision-tag" :class="visionMap[q.question_id] ? 'vision-on' : 'vision-off'" @click.stop="$emit('toggle-vision', q.question_id)">{{ visionMap[q.question_id] ? 'Vision' : 'OCR' }}</span>
          </div>
          <div v-if="q.answer_count" class="q-progress">
            <span class="q-prog-ai">AI已评 {{ q.ai_scored_count || 0 }}</span>
            <span class="q-prog-manual">待评 {{ q.answer_count - (q.ai_scored_count || 0) }}</span>
            <span class="q-prog-total">/ {{ q.answer_count }}</span>
          </div>
        </div>
        <span v-if="q.parent_id" class="q-parent-label" @click.stop="$emit('set-parent', q, null)" title="点击取消挂载">↳{{ parentName(q.parent_id) }}</span>
        <n-popselect v-else :options="mountOptions(q)" @update:value="pid => $emit('set-parent', q, pid)" trigger="click" :consistent-menu-width="false">
          <a class="q-mount-icon" @click.stop title="挂载到其他题目">↳</a>
        </n-popselect>
        <a class="q-del" @click.stop="$emit('delete-question', q)" title="删除题目">✕</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NInput, NInputNumber, NPopselect, NCheckbox } from 'naive-ui'

const props = defineProps({
  questions: { type: Array, default: () => [] },
  selectedQuestionId: { type: [String, Number], default: null },
  checkedIds: { type: Array, default: () => [] },
  visionMap: { type: Object, default: () => ({}) },
  editingScoreId: { type: [String, Number], default: null },
  editingNameId: { type: [String, Number], default: null },
  generatingSet: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'start-edit-score', 'save-score', 'update-score-value', 'add-question', 'start-edit-name', 'save-name', 'update-name-value', 'delete-question', 'set-parent', 'update:checkedIds', 'toggle-vision'])

function toggleCheck(qid) {
  const s = new Set(props.checkedIds)
  if (s.has(qid)) s.delete(qid)
  else s.add(qid)
  emit('update:checkedIds', [...s])
}

function toggleAll() {
  if (props.checkedIds.length === props.questions.length) emit('update:checkedIds', [])
  else emit('update:checkedIds', props.questions.map(q => q.question_id))
}

function parentName(parentId) {
  const p = props.questions.find(q => q.question_id === parentId)
  return p ? (p.name || p.question_name) : '?'
}

function mountOptions(q) {
  return props.questions
    .filter(o => o.question_id !== q.question_id && !o.parent_id)
    .map(o => ({ label: `第${o.name || o.question_name}题`, value: o.question_id }))
}
</script>

<style scoped>
.left-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  position: sticky;
  top: var(--space-4);
  max-height: calc(100dvh - 280px);
  overflow-y: auto;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--fs-base);
  font-weight: var(--fw-bold);
  color: var(--color-text-secondary);
  margin-bottom: 10px;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.question-item {
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  margin-bottom: var(--space-1);
  transition: background 0.15s;
  border: 1px solid transparent;
  position: relative;
}

.question-item:hover {
  background: var(--color-bg-alt);
  border-color: var(--color-border);
}

.question-item.active {
  background: var(--surface-primary-light);
  border-color: var(--color-primary);
}

.q-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-check {
  flex-shrink: 0;
}
.q-check :deep(.n-checkbox-box) {
  width: 18px;
  height: 18px;
  border: 2px solid #6b7280;
  border-radius: 4px;
}
.q-check :deep(.n-checkbox-box--checked) {
  border-color: var(--color-primary);
}

.q-num {
  font-size: var(--fs-lg);
  font-weight: var(--fw-bold);
  color: var(--color-text);
  min-width: 28px;
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
  border-color: var(--color-text-muted);
}

.question-item.active .q-num {
  color: var(--color-primary);
}

.q-info {
  flex: 1;
  min-width: 0;
}

.q-title {
  font-size: var(--fs-sm);
  color: var(--color-text-secondary);
  margin-bottom: 4px;
  font-weight: var(--fw-medium);
  display: flex;
  gap: 4px;
  align-items: baseline;
  white-space: nowrap;
}

.q-score {
  color: var(--color-primary);
  font-weight: var(--fw-semibold);
}
.q-score.editable {
  cursor: pointer; border-bottom: 1px dashed var(--color-primary);
  margin-left: 6px;
}

.q-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.t {
  font-size: var(--fs-xs);
  padding: 2px 6px;
  border-radius: var(--r-xs);
  font-weight: var(--fw-medium);
}

.t.ok {
  background: var(--surface-success);
  color: var(--color-success-pressed);
}

.t.warn {
  background: var(--surface-accent);
  color: var(--color-warning-pressed);
}
.t.gen {
  background: var(--surface-primary);
  color: var(--color-primary-dark);
  animation: pulse 1.5s infinite;
}
.vision-tag {
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  border: 1px solid currentColor;
  padding: 2px 8px;
}
.vision-off {
  background: var(--color-bg-alt);
  color: var(--color-text-muted);
}
.vision-on {
  background: var(--surface-primary);
  color: var(--color-primary);
}
.vision-tag:hover {
  opacity: 0.8;
}

.select-all-link {
  font-size: var(--fs-xs);
  font-weight: var(--fw-medium);
  color: var(--color-text-muted);
  cursor: pointer;
  text-decoration: none;
}
.select-all-link:hover {
  color: var(--color-primary);
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

.q-progress {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: var(--space-1);
  display: flex;
  gap: 6px;
  align-items: center;
}
.q-prog-ai { color: var(--color-primary); font-weight: var(--fw-semibold); }
.q-prog-manual { color: var(--color-warning); font-weight: var(--fw-semibold); }
.q-prog-total { color: var(--color-text-muted); }
.q-del {
  font-size: var(--fs-sm); color: var(--color-text-muted); cursor: pointer;
  opacity: 0; transition: opacity 0.15s; text-decoration: none;
  position: absolute; right: 8px; top: 8px; padding: var(--space-1) 6px; font-weight: var(--fw-bold);
}
.question-item:hover .q-del { opacity: 0.7; }
.q-del:hover { opacity: 1 !important; color: var(--color-danger); }

.q-parent-label {
  font-size: var(--fs-lg); color: var(--color-info); cursor: pointer; text-decoration: none; font-weight: var(--fw-bold);
}
.q-parent-label:hover { color: var(--color-danger); }
.q-mount-icon {
  font-size: var(--fs-xl); color: var(--color-text-muted); cursor: pointer; text-decoration: none;
  opacity: 0; transition: opacity 0.15s; padding: 0 var(--space-1); font-weight: var(--fw-bold);
}
.question-item:hover .q-mount-icon { opacity: 0.7; }
.q-mount-icon:hover { opacity: 1 !important; color: var(--color-info); }

.loading-tip {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  padding: var(--space-4) 0;
  text-align: center;
}

.empty-tip {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  padding: var(--space-2) 0;
}
</style>
