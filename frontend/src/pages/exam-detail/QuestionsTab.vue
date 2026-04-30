<template>
  <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
    <n-select
      v-model:value="qmgSubjectId"
      :options="subjectOptions"
      placeholder="选择科目"
      style="width: 200px"
      @update:value="loadQmgQuestions"
    />
    <n-tag v-if="qmgQuestions.length" size="small" round>
      {{ qmgQuestions.length }} 题 / 总分 {{ qmgTotalScore }}
    </n-tag>
    <div style="flex:1" />
    <n-button size="small" type="primary" @click="handleAddQuestion" :disabled="!qmgSubjectId">添加题目</n-button>
  </div>

  <div v-if="qmgLoading" style="text-align:center; padding:40px;"><n-spin /></div>
  <div v-else-if="!qmgSubjectId" class="empty-tip center">请选择科目</div>
  <div v-else-if="qmgQuestions.length === 0" class="empty-tip center">暂无题目</div>
  <n-data-table v-else :columns="qmgColumns" :data="qmgQuestions" size="small" :row-key="r => r.id" />
</template>

<script setup>
import { ref, computed, h } from 'vue'
import { useMessage, useDialog, NSelect, NInputNumber, NInput } from 'naive-ui'
import { listQuestions, createQuestion, updateQuestion, deleteQuestion } from '../../api/questions'

const props = defineProps({
  subjectOptions: { type: Array, required: true },
})

const message = useMessage()
const dialog = useDialog()

const qmgSubjectId = ref(null)
const qmgQuestions = ref([])
const qmgLoading = ref(false)
const qmgTotalScore = computed(() => qmgQuestions.value.reduce((s, q) => s + (q.max_score || 0), 0))

const qTypeOptions = [
  { label: '单选', value: 'choice' },
  { label: '多选', value: 'multi_choice' },
  { label: '填空', value: 'fill_blank' },
  { label: '主观', value: 'essay' },
]

async function loadQmgQuestions(subjectId) {
  if (!subjectId) { qmgQuestions.value = []; return }
  qmgLoading.value = true
  try {
    const res = await listQuestions(subjectId)
    qmgQuestions.value = (res.data || []).sort((a, b) => (parseInt(a.name) || 0) - (parseInt(b.name) || 0))
  } catch { qmgQuestions.value = [] }
  finally { qmgLoading.value = false }
}

async function handleQmgSave(row, field, value) {
  try {
    await updateQuestion(row.id, { [field]: value })
    row[field] = value
    message.success('已保存')
    if (field === 'max_score') qmgQuestions.value = [...qmgQuestions.value]
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
}

async function handleDeleteQuestion(row) {
  try {
    await deleteQuestion(row.id)
    qmgQuestions.value = qmgQuestions.value.filter(q => q.id !== row.id)
    message.success('已删除')
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleAddQuestion() {
  if (!qmgSubjectId.value) return
  const maxName = qmgQuestions.value.reduce((m, q) => Math.max(m, parseInt(q.name) || 0), 0)
  try {
    await createQuestion({
      subject_id: qmgSubjectId.value,
      name: String(maxName + 1),
      question_type: 'essay',
      max_score: 5,
    })
    await loadQmgQuestions(qmgSubjectId.value)
    message.success('已添加')
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
  }
}

const qmgColumns = [
  {
    title: '题号', key: 'name', width: 80,
    render(row) {
      return h(NInput, {
        value: row.name, size: 'small', style: 'width:60px',
        onUpdateValue: v => { row.name = v },
        onBlur: () => handleQmgSave(row, 'name', row.name),
      })
    },
  },
  {
    title: '类型', key: 'question_type', width: 110,
    render(row) {
      return h(NSelect, {
        value: row.question_type, size: 'small', options: qTypeOptions, style: 'width:90px',
        onUpdateValue: v => handleQmgSave(row, 'question_type', v),
      })
    },
  },
  {
    title: '分值', key: 'max_score', width: 100,
    render(row) {
      return h(NInputNumber, {
        value: row.max_score, size: 'small', min: 0, max: 200, step: 1, style: 'width:80px',
        onUpdateValue: v => { row.max_score = v },
        onBlur: () => handleQmgSave(row, 'max_score', row.max_score),
      })
    },
  },
  {
    title: '正确答案', key: 'correct_answer', width: 100,
    render(row) {
      if (row.question_type !== 'choice' && row.question_type !== 'multi_choice') return ''
      return h(NInput, {
        value: row.correct_answer || '', size: 'small', style: 'width:80px',
        onUpdateValue: v => { row.correct_answer = v },
        onBlur: () => handleQmgSave(row, 'correct_answer', row.correct_answer),
      })
    },
  },
  { title: '题干', key: 'has_content', width: 60, render(row) { return (row.content || (row.content_images || []).length) ? '✓' : '—' } },
  { title: '答案', key: 'has_answer', width: 60, render(row) { return (row.reference_answer || (row.reference_answer_images || []).length) ? '✓' : '—' } },
  {
    title: '', key: 'actions', width: 60,
    render(row) {
      return h('a', {
        style: 'color: var(--color-danger); cursor: pointer; font-size: var(--fs-base)',
        onClick: () => dialog.warning({
          title: '删除确认',
          content: `确定删除第 ${row.name} 题？`,
          positiveText: '删除',
          negativeText: '取消',
          onPositiveClick: () => handleDeleteQuestion(row),
        }),
      }, '删除')
    },
  },
]
</script>
