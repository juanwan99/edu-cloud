<template>
  <div style="margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
    <n-form-item label="科目" label-placement="left" label-width="auto" style="margin-bottom: 0;">
      <n-select
        v-model:value="localSubjectId"
        :options="subjectOptions"
        placeholder="选择科目"
        style="width: 200px;"
      />
    </n-form-item>
    <n-divider vertical />
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      :disabled="!localSubjectId || exam?.status !== 'draft'"
      @click="cardEditorRef?.save()"
    >
      保存
    </n-button>
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      :disabled="!localSubjectId || exam?.status !== 'draft'"
      @click="handleResetLayout"
    >
      恢复默认
    </n-button>
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      :loading="autoLayouting"
      :disabled="!localSubjectId || exam?.status !== 'draft'"
      @click="handleAutoLayout"
    >
      小微排版
    </n-button>
    <n-divider vertical />
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      :disabled="!localSubjectId"
      @click="cardEditorRef?.exportPdf()"
    >
      导出 PDF
    </n-button>
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      :loading="batchExporting"
      :disabled="subjects.length === 0"
      @click="handleBatchExportPdf"
    >
      {{ batchExporting ? batchExportProgress : '导出全部 PDF' }}
    </n-button>
    <n-button
      size="small"
      class="btn-pill toolbar-btn"
      data-testid="publish-card-btn"
      :disabled="!localSubjectId || exam?.status !== 'draft'"
      @click="handlePublishCard"
    >
      发布答题卡
    </n-button>
  </div>
  <div v-if="localSubjectId" style="min-height: 600px;">
    <CardEditor
      ref="cardEditorRef"
      :key="localSubjectId + (pendingQuestions ? '-pq' : '')"
      :exam-id="examId"
      :subject-id="localSubjectId"
      :subject-name="localSubjectName"
      :card-title="exam?.card_title || ''"
      :readonly="exam?.status !== 'draft'"
      :pending-questions="pendingQuestions"
      @publish="handlePublishCard"
    />
  </div>
  <n-empty v-else description="请先选择科目" />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import CardEditor from '../../components/CardEditor.vue'
import client from '../../api/client'

const props = defineProps({
  examId: { type: String, required: true },
  exam: { type: Object, default: null },
  subjects: { type: Array, required: true },
  subjectOptions: { type: Array, required: true },
  visualEditorSubjectId: { type: [String, null], default: null },
  pendingQuestions: { type: [Array, null], default: null },
})

const emit = defineEmits(['update:visualEditorSubjectId', 'reload-exam'])

const message = useMessage()
const dialog = useDialog()
const cardEditorRef = ref(null)

// Local subject ID synced with parent via v-model
const localSubjectId = computed({
  get: () => props.visualEditorSubjectId,
  set: (v) => emit('update:visualEditorSubjectId', v),
})

const localSubjectName = computed(() => {
  const s = props.subjects.find(s => s.id === localSubjectId.value)
  return s ? s.name : ''
})

const autoLayouting = ref(false)
const batchExporting = ref(false)
const batchExportProgress = ref('')

/** 可靠的 blob 下载 */
function saveBlob(blob, filename) {
  const file = new File([blob], filename, { type: blob.type })
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

async function handleAutoLayout() {
  if (!localSubjectId.value || !cardEditorRef.value) return
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.docx'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    autoLayouting.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      const uploadResp = await client.post('/card/upload-answer', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const { file_path } = uploadResp.data

      const resp = await client.post(`/card/auto-layout/${localSubjectId.value}`, {
        answer_file: file_path,
      })
      const result = resp.data
      cardEditorRef.value.applyAutoLayout(result)
      message.success(`小微已为 ${result.subject} ${result.questions?.length || 0} 道题完成排版`)
    } catch (e) {
      message.error('小微排版失败: ' + e.message)
    } finally {
      autoLayouting.value = false
    }
  }
  input.click()
}

function handleResetLayout() {
  if (!cardEditorRef.value) return
  dialog.warning({
    title: '恢复默认模板',
    content: '当前编辑内容将丢失，确定恢复为系统默认模板？',
    positiveText: '确定恢复',
    negativeText: '取消',
    onPositiveClick: async () => {
      await cardEditorRef.value.resetToDefault()
      message.success('已恢复默认模板')
    },
  })
}

function handlePublishCard() {
  if (!localSubjectId.value) {
    message.warning('请先选择科目')
    return
  }
  const subjectId = localSubjectId.value
  const subj = props.subjects.find(s => s.id === subjectId)
  const filename = `答题卡_${subj?.name || '未知'}.pdf`

  dialog.warning({
    title: '确认发布',
    content: '发布后答题卡将锁定为只读，扫描端可开始拉取模板。确定发布？',
    positiveText: '发布',
    negativeText: '取消',
    positiveButtonProps: { class: 'btn-pill' },
    negativeButtonProps: { class: 'btn-pill' },
    onPositiveClick: async () => {
      try {
        const exportModule = await import('@/card-editor/export.js')
        await exportModule.publishCard(subjectId, props.examId, filename)
        emit('reload-exam')
        message.success('答题卡已发布，扫描端可拉取模板')
      } catch (e) {
        message.error('发布失败: ' + (e.message || '未知错误'))
      }
    },
  })
}

async function handleBatchExportPdf() {
  if (props.subjects.length === 0) { message.warning('无科目可导出'); return }
  batchExporting.value = true
  batchExportProgress.value = '准备中...'
  try {
    const { batchExportPdf } = await import('@/card-editor/export.js')
    const results = await batchExportPdf(
      props.subjects,
      props.exam?.card_title || props.exam?.name || '',
      (cur, total, name) => { batchExportProgress.value = `${cur}/${total} ${name}` }
    )
    const ok = results.filter(r => r.ok).length
    const fail = results.filter(r => r.error)
    if (fail.length === 0) {
      message.success(`全部 ${ok} 科导出成功`)
    } else {
      message.warning(`${ok} 科成功，${fail.length} 科失败: ${fail.map(f => f.name).join('、')}`)
    }
  } catch (e) {
    message.error('批量导出失败: ' + e.message)
  } finally {
    batchExporting.value = false
    batchExportProgress.value = ''
  }
}

// Expose for parent component test compatibility
defineExpose({
  handlePublishCard,
  cardEditorRef,
})
</script>

<style scoped>
.toolbar-btn {
  border: 1px solid var(--color-border) !important;
  color: var(--color-text) !important;
  background: transparent !important;
}
.toolbar-btn:hover {
  border-color: var(--color-text-secondary) !important;
  color: var(--color-text) !important;
  background: var(--color-bg-alt) !important;
}
.toolbar-btn:disabled {
  border-color: var(--color-border-light) !important;
  color: var(--color-text-muted) !important;
}
</style>
