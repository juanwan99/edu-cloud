<template>
  <div style="display: flex; gap: 24px;">
    <!-- 左侧：表单 -->
    <div style="flex: 1; min-width: 400px;">
      <!-- 答题卡配置 -->
      <n-card title="答题卡配置" size="small">
        <n-form label-placement="left" label-width="70" :show-feedback="false" style="display: grid; grid-template-columns: 1fr auto; gap: 8px 12px; align-items: center;">
          <n-form-item label="标题" style="grid-column: 1;">
            <n-input v-model:value="cardForm.cardTitle" placeholder="答题卡标题" size="small" />
          </n-form-item>
          <n-button type="primary" size="small" class="btn-pill" :loading="cardTitleSaving" @click="handleSaveCardTitle" style="grid-column: 2;">保存</n-button>

          <n-form-item label="科目" style="grid-column: 1 / -1;">
            <n-select v-model:value="cardForm.subjectId" :options="subjectOptions" placeholder="选择科目" size="small" @update:value="onSubjectSelect" />
          </n-form-item>

          <div style="grid-column: 1 / -1; display: flex; gap: 12px;">
            <n-form-item label="满分" label-width="42" style="flex: 0 0 130px;">
              <n-input-number v-model:value="cardForm.totalScore" :min="10" :max="300" :step="10" size="small" placeholder="100" />
            </n-form-item>
            <n-form-item label="纸张" label-width="42" style="flex: 0 0 120px;">
              <n-select v-model:value="cardForm.paperSize" :options="paperSizeOptions" size="small" />
            </n-form-item>
            <n-form-item label="印刷" label-width="42" style="flex: 0 0 120px;">
              <n-select v-model:value="cardForm.sides" :options="sidesOptions" size="small" />
            </n-form-item>
          </div>
        </n-form>
      </n-card>

      <!-- Step 1: 选科目后显示两个入口 -->
      <template v-if="cardForm.subjectId && parseStep === 'upload'">
        <div style="margin-top: 16px; display: flex; gap: 16px;">
          <!-- 入口 A: 直接编辑答题卡 -->
          <n-card size="small" hoverable style="flex: 1; cursor: pointer;" @click="goToEditor">
            <div style="text-align: center; padding: 20px 0;">
              <div style="font-size: 24px; margin-bottom: 8px;">&#9998;</div>
              <n-text strong>直接编辑答题卡</n-text>
              <br />
              <n-text depth="3" style="font-size: 12px;">使用学科默认模板，手动调整题型结构</n-text>
            </div>
          </n-card>
          <!-- 入口 B: 上传答案自动识别 -->
          <n-card size="small" style="flex: 1;">
            <div style="text-align: center; padding: 8px 0;">
              <n-text strong>上传答案自动识别（可选）</n-text>
              <br />
              <n-text depth="3" style="font-size: 12px; display: block; margin: 8px 0;">上传答案文件，自动识别题型填充到编辑器</n-text>
            </div>
            <n-upload
              :key="uploadKey"
              v-model:file-list="answerFileList"
              accept=".docx,.pdf"
              :custom-request="handleAnswerUpload"
              :disabled="cardLoading"
            >
              <n-upload-dragger>
                <div style="padding: 12px; text-align: center;">
                  <n-text depth="3">点击或拖拽上传 .docx / .pdf</n-text>
                </div>
              </n-upload-dragger>
            </n-upload>
            <n-spin v-if="cardLoading" size="small" style="margin-top: 8px;">
              <template #description>正在解析答案并识别题型...</template>
            </n-spin>
          </n-card>
        </div>
      </template>

      <!-- Step 2: 答案预览编辑（可编辑表格） -->
      <template v-if="parseStep === 'answers'">
        <n-card size="small" style="margin-top: 16px;">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>答案预览</span>
              <div style="display: flex; gap: 8px; align-items: center;">
                <n-tag :type="parsedStandardized.length === totalQuestions ? 'success' : 'warning'" size="small" round>
                  已识别 {{ parsedStandardized.length }} / {{ totalQuestions }} 题
                </n-tag>
                <n-tag v-if="parsedMeta.parse_method" size="small" round>
                  {{ parsedMeta.parse_method === 'vision_llm' ? 'Vision AI' : '文本解析' }}
                  · {{ parsedMeta.parse_time_ms ? (parsedMeta.parse_time_ms / 1000).toFixed(1) + 's' : '' }}
                </n-tag>
              </div>
            </div>
          </template>

          <n-data-table
            :columns="answerColumns"
            :data="parsedStandardized"
            :row-class-name="answerRowClass"
            size="small"
            :bordered="false"
            :max-height="500"
          />

          <!-- 分值汇总 -->
          <div style="margin-top: 12px; display: flex; gap: 16px; align-items: center;">
            <n-text>
              总分: <b>{{ scoreSum }}</b> / {{ cardForm.totalScore || 100 }}
            </n-text>
            <n-tag v-if="scoreSum > 0 && scoreSum !== (cardForm.totalScore || 100)" type="warning" size="small">
              分值不一致
            </n-tag>
          </div>
        </n-card>

        <div style="margin-top: 12px; display: flex; gap: 12px;">
          <n-button @click="resetToUpload">重新上传</n-button>
          <n-button type="primary" @click="confirmAnswers">确认答案</n-button>
        </div>
      </template>

      <!-- 条码贴纸 -->
      <n-card title="条码贴纸生成" size="small" style="margin-top: 24px;">
        <n-upload
          :max="1"
          accept=".xlsx,.xls"
          :default-upload="false"
          @change="handleBarcodeFileChange"
        >
          <n-button>上传学生名单 Excel</n-button>
        </n-upload>
        <div v-if="barcodeFile" style="margin-top: 12px;">
          <n-button type="primary" @click="handleBarcodeGenerate" :loading="barcodeLoading">
            下载条码贴纸 PDF
          </n-button>
        </div>
      </n-card>
    </div>

    <!-- 右侧：PDF 预览 -->
    <div style="flex: 1; min-width: 400px;" v-if="cardPreviewUrl">
      <n-card size="small">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>预览</span>
            <n-button size="small" quaternary @click="toggleFullscreen">
              {{ isFullscreen ? '退出全屏' : '全屏查看' }}
            </n-button>
          </div>
        </template>
        <iframe ref="previewIframe" :src="cardPreviewUrl" style="width: 100%; height: 800px; border: none; border-radius: 10px;" />
      </n-card>
    </div>

    <!-- 全屏预览遮罩 -->
    <teleport to="body">
      <div v-if="isFullscreen" style="position: fixed; inset: 0; z-index: var(--z-modal); background: rgba(0,0,0,0.85); display: flex; flex-direction: column;">
        <div style="display: flex; justify-content: flex-end; padding: 12px 20px;">
          <n-button type="primary" size="small" @click="toggleFullscreen">关闭全屏 (ESC)</n-button>
        </div>
        <iframe :src="cardPreviewUrl" style="flex: 1; border: none; margin: 0 20px 20px; border-radius: 8px; background: white;" />
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { NSelect, NInputNumber, NTag, NInput } from 'naive-ui'
import { updateExam } from '../../api/exams'
import { generateBarcode, parseAnswers, previewByWeights, generateCardV2 } from '../../api/cards'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps({
  examId: { type: String, required: true },
  exam: { type: Object, default: null },
  subjects: { type: Array, required: true },
  subjectOptions: { type: Array, required: true },
})

const emit = defineEmits(['update:exam', 'go-to-editor', 'confirm-answers'])

const message = useMessage()

// --- 答题卡制作（v3 文件上传驱动）---
const cardForm = reactive({
  subjectId: null,
  cardTitle: '',
  totalScore: 100,
  paperSize: 'A3',
  sides: 'duplex',
})
const paperSizeOptions = [
  { label: 'A3', value: 'A3' },
  { label: 'A4', value: 'A4' },
]
const sidesOptions = [
  { label: '双面', value: 'duplex' },
  { label: '单面', value: 'simplex' },
]
const cardTitleSaving = ref(false)
const cardLoading = ref(false)
const cardPreviewUrl = ref(null)
const barcodeFile = ref(null)
const barcodeLoading = ref(false)

// 答题卡状态
const parseStep = ref('upload')  // 'upload' | 'answers' | 'preview' | 'done'
const totalQuestions = ref(0)
const answerFileList = ref([])
const uploadKey = ref(0)
const parsedQuestions = ref([])
const parsedWeights = ref([])
const parsedStandardized = ref([])
const parsedSkeleton = ref(null)
const parsedLayout = ref(null)
const parsedMeta = ref({})
const hasTplSlots = ref(false)
const isFullscreen = ref(false)
const previewIframe = ref(null)

// Sync cardTitle from parent exam
if (props.exam?.card_title) {
  cardForm.cardTitle = props.exam.card_title
}

function renderMath(text) {
  if (!text) return ''
  const placeholders = []
  let processed = text
    .replace(/\$\$([\s\S]*?)\$\$/g, (_, expr) => {
      try {
        const html = katex.renderToString(expr.trim(), { displayMode: true, throwOnError: false })
        placeholders.push(html)
        return `\x00MATH${placeholders.length - 1}\x00`
      } catch { return `$$${expr}$$` }
    })
    .replace(/\$([^\$\n]+?)\$/g, (_, expr) => {
      try {
        const html = katex.renderToString(expr.trim(), { displayMode: false, throwOnError: false })
        placeholders.push(html)
        return `\x00MATH${placeholders.length - 1}\x00`
      } catch { return `$${expr}$` }
    })
  processed = processed
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  processed = processed.replace(/\x00MATH(\d+)\x00/g, (_, i) => placeholders[parseInt(i)])
  return processed
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

// ESC 退出全屏
const _escHandler = (e) => {
  if (e.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
  }
}
onMounted(() => window.addEventListener('keydown', _escHandler))
onUnmounted(() => {
  window.removeEventListener('keydown', _escHandler)
  if (cardPreviewUrl.value) URL.revokeObjectURL(cardPreviewUrl.value)
})

async function handleSaveCardTitle() {
  if (!cardForm.cardTitle.trim()) {
    message.warning('请输入答题卡标题')
    return
  }
  cardTitleSaving.value = true
  try {
    const { data } = await updateExam(props.examId, { card_title: cardForm.cardTitle })
    emit('update:exam', data)
    message.success('答题卡标题已保存')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
  cardTitleSaving.value = false
}

function onSubjectSelect(subjectId) {
  cardForm.subjectId = subjectId
  answerFileList.value = []
  uploadKey.value++
  parseStep.value = 'upload'
  if (cardPreviewUrl.value) {
    URL.revokeObjectURL(cardPreviewUrl.value)
    cardPreviewUrl.value = null
  }
}

function goToEditor() {
  emit('go-to-editor', cardForm.subjectId)
}

async function handleAnswerUpload({ file, onFinish, onError }) {
  const subj = props.subjects.find(s => s.id === cardForm.subjectId)
  if (!subj) { onError(); return }
  cardLoading.value = true
  try {
    const resp = await parseAnswers(file.file, cardForm.subjectId, props.examId, {
      total_score: cardForm.totalScore,
      paper_size: cardForm.paperSize,
      sides: cardForm.sides,
    })
    const data = resp.data
    parsedQuestions.value = data.questions.map(q => ({ ...q }))
    parsedWeights.value = data.weights
    parsedSkeleton.value = data.skeleton
    parsedLayout.value = data.layout
    parsedMeta.value = {
      subject_code: data.subject_code,
      subject_name: data.subject_name,
      exam_name: data.exam_name,
      parse_method: data.parse_method,
      parse_time_ms: data.parse_time_ms,
    }
    hasTplSlots.value = data.has_tpl_slots
    totalQuestions.value = data.total_questions || data.questions.length
    parsedStandardized.value = data.standardized || []
    parseStep.value = 'answers'
    message.success(`已识别 ${data.questions.length} 题答案，请检查后确认`)
    onFinish()
  } catch (e) {
    const detail = e.response?.data?.detail
    message.error(detail || '解析失败: ' + e.message)
    answerFileList.value = []
    uploadKey.value++
    onError()
  } finally {
    cardLoading.value = false
  }
}

const scoreSum = computed(() =>
  (parsedStandardized.value || []).reduce((s, q) => s + (q.score || 0), 0)
)

const answerRowClass = (row) => {
  if (row.confidence < 0.5) return 'row-danger'
  if (row.confidence < 0.8) return 'row-warning'
  return ''
}

const typeOptions = [
  { label: '单选', value: 'single_choice' },
  { label: '多选', value: 'multi_choice' },
  { label: '填空', value: 'fill_in_blank' },
  { label: '解答', value: 'short_answer' },
]

const answerColumns = [
  { title: '#', key: 'number', width: 50 },
  { title: '大题', key: 'section', width: 100,
    render: (row) => row.section || '-' },
  { title: '题型', key: 'type', width: 100,
    render: (row) => h(NSelect, {
      value: row.type, size: 'small', options: typeOptions,
      onUpdateValue: (v) => { row.type = v },
      style: 'width: 90px',
    })
  },
  { title: '答案', key: 'answer', minWidth: 200,
    render: (row) => h('div', { style: 'display: flex; gap: 4px; align-items: center;' }, [
      h(NInput, {
        value: row.answer, size: 'small',
        onUpdateValue: (v) => { row.answer = v },
        style: 'flex: 1',
      }),
      row.answer && row.answer.includes('\\')
        ? h('span', {
            class: 'math-preview',
            innerHTML: renderMath(row.answer),
            style: 'font-size: 12px; color: #666;',
          })
        : null,
    ])
  },
  { title: '分值', key: 'score', width: 70,
    render: (row) => h(NInputNumber, {
      value: row.score, size: 'small', min: 0, max: 100,
      onUpdateValue: (v) => { row.score = v },
      style: 'width: 60px',
      placeholder: '-',
    })
  },
  { title: '选项', key: 'options_count', width: 60,
    render: (row) => row.type?.includes('choice')
      ? h(NInputNumber, {
          value: row.options_count, size: 'small', min: 2, max: 8,
          onUpdateValue: (v) => { row.options_count = v },
          style: 'width: 50px',
        })
      : '-'
  },
  { title: '小问', key: 'sub_count', width: 60,
    render: (row) => h(NInputNumber, {
      value: row.sub_count, size: 'small', min: 1, max: 10,
      onUpdateValue: (v) => { row.sub_count = v },
      style: 'width: 50px',
    })
  },
  { title: '置信度', key: 'confidence', width: 70,
    render: (row) => {
      const c = row.confidence || 0
      const type = c >= 0.8 ? 'success' : c >= 0.5 ? 'warning' : 'error'
      return h(NTag, { type, size: 'small', round: true }, () => (c * 100).toFixed(0) + '%')
    }
  },
]

function confirmAnswers() {
  const questions = (parsedStandardized.value || []).map(q => ({
    number: q.number,
    type: q.type,
    answer: q.answer,
    score: q.score,
    options_count: q.options_count || 4,
    sub_count: q.sub_count || 0,
  }))
  emit('confirm-answers', { subjectId: cardForm.subjectId, questions })
}

function resetToUpload() {
  answerFileList.value = []
  uploadKey.value++
  parseStep.value = 'upload'
  parsedQuestions.value = []
  parsedWeights.value = []
  parsedSkeleton.value = null
  parsedLayout.value = null
  parsedMeta.value = {}
  hasTplSlots.value = false
  totalQuestions.value = 0
  if (cardPreviewUrl.value) {
    URL.revokeObjectURL(cardPreviewUrl.value)
    cardPreviewUrl.value = null
  }
}

function handleBarcodeFileChange({ fileList }) {
  barcodeFile.value = fileList.length ? fileList[0].file : null
}

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

async function handleBarcodeGenerate() {
  if (!barcodeFile.value) return
  barcodeLoading.value = true
  try {
    const resp = await generateBarcode(barcodeFile.value)
    saveBlob(resp.data, '条码贴纸.pdf')
    message.success('条码贴纸已生成')
  } catch (e) {
    message.error(e.response?.data?.detail || '生成失败')
  } finally {
    barcodeLoading.value = false
  }
}
</script>

<style scoped>
.row-warning td { background-color: #fffbe6 !important; }
.row-danger td { background-color: #fff1f0 !important; }
</style>
