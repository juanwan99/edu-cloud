<template>
  <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
    <n-select
      v-model:value="ansSubjectId"
      :options="subjectOptions"
      placeholder="选择科目"
      style="width: 200px"
      @update:value="loadAnswerQuestions"
    />
    <n-tag v-if="ansChoiceQuestions.length" size="small" round>
      {{ ansFilledCount }}/{{ ansChoiceQuestions.length }} 已填
    </n-tag>
    <div style="flex:1" />
    <n-button type="primary" size="small" :loading="ansSaving" :disabled="!ansSubjectId" @click="handleSaveAnswers">
      保存全部
    </n-button>
  </div>

  <!-- 快速添加选择题 -->
  <div v-if="ansSubjectId && !ansLoading" class="add-choices-bar">
    <n-input-number v-model:value="ansAddFrom" size="small" :min="1" placeholder="起始题号" style="width:90px" />
    <span>~</span>
    <n-input-number v-model:value="ansAddTo" size="small" :min="ansAddFrom || 1" placeholder="结束题号" style="width:90px" />
    <n-select v-model:value="ansAddType" size="small" :options="[{label:'单选',value:'choice'},{label:'多选',value:'multi_choice'}]" style="width:90px" />
    <n-input-number v-model:value="ansAddScore" size="small" :min="0" :max="50" placeholder="分值" style="width:80px" />
    <n-input-number v-model:value="ansAddOptions" size="small" :min="2" :max="8" placeholder="选项数" style="width:80px" />
    <n-button size="small" type="primary" :loading="ansAdding" @click="handleBatchAddChoices">
      添加 {{ (ansAddTo || 0) - (ansAddFrom || 0) + 1 > 0 ? `${(ansAddTo || 0) - (ansAddFrom || 0) + 1} 题` : '' }}
    </n-button>
  </div>

  <div v-if="ansLoading" style="text-align:center; padding:40px;"><n-spin /></div>
  <div v-else-if="!ansSubjectId" class="empty-tip center">请选择科目</div>
  <div v-else-if="ansChoiceQuestions.length === 0" class="empty-tip center">暂无选择题，请用上方工具栏添加</div>
  <div v-else class="answer-grid">
    <div v-for="q in ansChoiceQuestions" :key="q.id" class="answer-item" :class="{ filled: ansAnswers[q.id] }">
      <div class="answer-num">{{ q.name }}</div>
      <div class="answer-options">
        <template v-if="q.question_type === 'choice'">
          <button v-for="opt in ansOptionList(q)" :key="opt"
            class="opt-btn" :class="{ selected: ansAnswers[q.id] === opt }"
            @click="ansAnswers[q.id] = ansAnswers[q.id] === opt ? '' : opt"
          >{{ opt }}</button>
        </template>
        <template v-else>
          <button v-for="opt in ansOptionList(q)" :key="opt"
            class="opt-btn multi" :class="{ selected: (ansAnswers[q.id] || '').includes(opt) }"
            @click="toggleMulti(q.id, opt)"
          >{{ opt }}</button>
        </template>
      </div>
      <n-button v-if="ansAnswers[q.id]" text size="tiny" class="skip-btn" @click="ansAnswers[q.id] = ''">清除</n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { listQuestions, createQuestion, updateQuestion } from '../../api/questions'

const props = defineProps({
  subjectOptions: { type: Array, required: true },
})

const message = useMessage()

// ── 标准答案 tab ──
const ansSubjectId = ref(null)
const ansAllQuestions = ref([])
const ansAnswers = reactive({})
const ansLoading = ref(false)
const ansSaving = ref(false)

const ansChoiceQuestions = computed(() =>
  ansAllQuestions.value.filter(q => q.question_type === 'choice' || q.question_type === 'multi_choice')
)
const ansFilledCount = computed(() =>
  ansChoiceQuestions.value.filter(q => ansAnswers[q.id]).length
)

function ansOptionList(q) {
  const count = q.options_count || 4
  return 'ABCDEFGH'.slice(0, count).split('')
}

function toggleMulti(qid, opt) {
  const cur = (ansAnswers[qid] || '').split('').filter(c => c)
  const idx = cur.indexOf(opt)
  if (idx >= 0) cur.splice(idx, 1)
  else cur.push(opt)
  cur.sort()
  ansAnswers[qid] = cur.join('')
}

async function loadAnswerQuestions(subjectId) {
  if (!subjectId) { ansAllQuestions.value = []; return }
  ansLoading.value = true
  try {
    const { data } = await listQuestions(subjectId)
    ansAllQuestions.value = data.sort((a, b) => {
      const na = parseInt(a.name), nb = parseInt(b.name)
      return (isNaN(na) ? 999 : na) - (isNaN(nb) ? 999 : nb)
    })
    for (const q of ansAllQuestions.value) {
      ansAnswers[q.id] = q.correct_answer || ''
    }
  } catch {
    ansAllQuestions.value = []
  }
  ansLoading.value = false
}

// 批量添加选择题
const ansAddFrom = ref(1)
const ansAddTo = ref(10)
const ansAddType = ref('choice')
const ansAddScore = ref(3)
const ansAddOptions = ref(4)
const ansAdding = ref(false)

async function handleBatchAddChoices() {
  const from = ansAddFrom.value, to = ansAddTo.value
  if (!ansSubjectId.value || !from || !to || to < from) {
    message.warning('请正确填写起止题号'); return
  }
  ansAdding.value = true
  let ok = 0
  const existingNames = new Set(ansAllQuestions.value.map(q => q.name))
  for (let i = from; i <= to; i++) {
    const name = String(i)
    if (existingNames.has(name)) continue
    try {
      await createQuestion({
        subject_id: ansSubjectId.value,
        name,
        question_type: ansAddType.value,
        max_score: ansAddScore.value,
      })
      ok++
    } catch { /* skip duplicates */ }
  }
  ansAdding.value = false
  if (ok > 0) {
    message.success(`已添加 ${ok} 道选择题`)
    await loadAnswerQuestions(ansSubjectId.value)
  } else {
    message.info('所有题号已存在')
  }
}

async function handleSaveAnswers() {
  const toSave = ansChoiceQuestions.value.filter(q => ansAnswers[q.id])
  if (toSave.length === 0) { message.warning('没有需要保存的答案'); return }
  ansSaving.value = true
  let ok = 0
  for (const q of toSave) {
    if (ansAnswers[q.id] === (q.correct_answer || '')) continue
    try {
      await updateQuestion(q.id, { correct_answer: ansAnswers[q.id] })
      q.correct_answer = ansAnswers[q.id]
      ok++
    } catch (e) {
      message.error(`第 ${q.name} 题保存失败`)
    }
  }
  ansSaving.value = false
  if (ok > 0) message.success(`已保存 ${ok} 题标准答案`)
  else message.info('无变更')
}
</script>

<style scoped>
.answer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.answer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--color-bg-alt, #f7f8fa);
  border: 1px solid transparent;
  transition: border-color 0.2s;
}
.answer-item.filled {
  border-color: #18a058;
  background: rgba(24, 160, 88, 0.06);
}
.answer-num {
  font-weight: 700;
  font-size: 15px;
  min-width: 28px;
  text-align: center;
  color: var(--color-text-secondary);
}
.answer-options {
  display: flex;
  gap: 6px;
  flex: 1;
}
.opt-btn {
  width: 36px;
  height: 32px;
  border: 1px solid var(--color-border-light, #ddd);
  border-radius: 6px;
  background: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.opt-btn:hover {
  border-color: #18a058;
  color: #18a058;
}
.opt-btn.selected {
  background: #18a058;
  color: white;
  border-color: #18a058;
}
.opt-btn.multi.selected {
  background: #2080f0;
  border-color: #2080f0;
}
.skip-btn {
  opacity: 0.5;
}
.add-choices-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--color-bg-alt, #f7f8fa);
  border-radius: 8px;
  font-size: 13px;
}
</style>
