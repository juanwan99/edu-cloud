<template>
  <div>
    <div v-if="loading" style="text-align: center; padding: 80px 0;">
      <n-spin size="large" />
      <p style="margin-top: 16px; color: var(--color-text-secondary);">加载中...</p>
    </div>
    <template v-else>
      <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <n-button text style="margin-bottom: 8px;" @click="$router.push('/exams')">← 返回考试列表</n-button>
          <h1 class="page-title">{{ exam?.name || '' }}</h1>
          <p class="page-subtitle">
            <n-tag v-if="exam" :type="statusType(exam.status)" round size="small">{{ statusLabel(exam.status) }}</n-tag>
          </p>
        </div>
      </div>

      <n-tabs v-model:value="activeTab" type="line">
        <!-- 科目管理 -->
        <n-tab-pane name="subjects" tab="科目管理">
          <div style="display: flex; justify-content: flex-end; margin-bottom: 16px;">
            <n-button type="primary" class="btn-pill" size="small" @click="openSubjectModal">添加科目</n-button>
          </div>
          <n-data-table :columns="subjectColumns" :data="subjects" size="small" />
        </n-tab-pane>

        <!-- 答题卡制作 -->
        <n-tab-pane name="card" tab="答题卡制作">
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

              <!-- Step 3: 已移除（权重调整+PDF预览），统一使用可视化编辑器 -->

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
              <div v-if="isFullscreen" style="position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.85); display: flex; flex-direction: column;">
                <div style="display: flex; justify-content: flex-end; padding: 12px 20px;">
                  <n-button type="primary" size="small" @click="toggleFullscreen">关闭全屏 (ESC)</n-button>
                </div>
                <iframe :src="cardPreviewUrl" style="flex: 1; border: none; margin: 0 20px 20px; border-radius: 8px; background: white;" />
              </div>
            </teleport>
          </div>
        </n-tab-pane>

        <!-- 可视化答题卡编辑器 -->
        <n-tab-pane name="visual-editor" tab="可视化编辑">
          <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <n-form-item label="科目" label-placement="left" label-width="auto" style="margin-bottom: 0;">
              <n-select
                v-model:value="visualEditorSubjectId"
                :options="subjectOptions"
                placeholder="选择科目"
                style="width: 200px;"
              />
            </n-form-item>
            <n-divider vertical />
            <n-button
              size="small"
              class="btn-pill toolbar-btn"
              :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
              @click="cardEditorRef?.save()"
            >
              保存
            </n-button>
            <n-button
              size="small"
              class="btn-pill toolbar-btn"
              :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
              @click="handleResetLayout"
            >
              恢复默认
            </n-button>
            <n-button
              size="small"
              class="btn-pill toolbar-btn"
              :loading="autoLayouting"
              :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
              @click="handleAutoLayout"
            >
              小微排版
            </n-button>
            <n-divider vertical />
            <n-button
              size="small"
              class="btn-pill toolbar-btn"
              :disabled="!visualEditorSubjectId"
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
              :disabled="!visualEditorSubjectId || exam?.status !== 'draft'"
              @click="handlePublishCard"
            >
              发布答题卡
            </n-button>
          </div>
          <div v-if="visualEditorSubjectId" style="min-height: 600px;">
            <CardEditor
              ref="cardEditorRef"
              :key="visualEditorSubjectId + (pendingQuestionsForEditor ? '-pq' : '')"
              :exam-id="examId"
              :subject-id="visualEditorSubjectId"
              :subject-name="visualEditorSubjectName"
              :card-title="exam?.card_title || ''"
              :readonly="exam?.status !== 'draft'"
              :pending-questions="pendingQuestionsForEditor"
              @publish="handlePublishCard"
            />
          </div>
          <n-empty v-else description="请先选择科目" />
        </n-tab-pane>

        <!-- 扫描功能已迁移到阅卷调度页面 GradingDispatchPage -->
      </n-tabs>
    </template>

    <!-- Modals 放在根级别，避免嵌套在 n-tabs 内部导致遮罩异常 -->
    <n-modal v-model:show="showSubjectModal" preset="card" title="添加科目" style="width: 480px;" :mask-closable="true">
      <n-checkbox-group v-model:value="selectedSubjectCodes">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
          <n-checkbox
            v-for="s in availablePresetSubjects"
            :key="s.code"
            :value="s.code"
            :label="`${s.name}（${s.code}）`"
          />
        </div>
      </n-checkbox-group>
      <n-text v-if="availablePresetSubjects.length === 0" depth="3">所有常用科目已添加</n-text>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px;">
        <n-button class="btn-pill" @click="showSubjectModal = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="subjectCreating" :disabled="selectedSubjectCodes.length === 0" @click="handleBatchCreateSubjects">
          添加 ({{ selectedSubjectCodes.length }})
        </n-button>
      </div>
    </n-modal>

    <n-modal v-model:show="showRubricModal" preset="card" title="评分标准" style="width: 600px;" :mask-closable="true">
      <n-spin :show="rubricLoading">
        <n-form :model="rubricForm" label-placement="top">
          <n-form-item label="评分细则 (JSON)">
            <n-input v-model:value="rubricForm.criteria" type="textarea" :rows="6"
              placeholder='[{"point": "要点1", "score": 3}, ...]' />
          </n-form-item>
          <n-form-item label="参考答案">
            <n-input v-model:value="rubricForm.reference_answer" type="textarea" :rows="4"
              placeholder="参考答案文本" />
          </n-form-item>
        </n-form>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button class="btn-pill" @click="showRubricModal = false">取消</n-button>
          <n-button type="primary" class="btn-pill" @click="handleSaveRubric">保存</n-button>
        </div>
      </n-spin>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, h } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, useDialog, NSelect, NInputNumber, NTag, NInput, NCheckbox, NCheckboxGroup } from 'naive-ui'
import { getExam, updateExam } from '../api/exams'
import { listSubjects, createSubject } from '../api/subjects'
import { getRubric, upsertRubric } from '../api/rubrics'
import { generateBarcode, parseAnswers, previewByWeights, generateCardV2 } from '../api/cards'
// scan 功能已迁移到 GradingDispatchPage
import CardEditor from '../components/CardEditor.vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/** 可靠的 blob 下载：用 File 构造器强制文件名（绕过 Chrome blob UUID 问题） */
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

const route = useRoute()
const message = useMessage()
const dialog = useDialog()
const examId = route.params.id

const loading = ref(true)
const activeTab = ref('subjects')
const pendingQuestionsForEditor = ref(null)
const exam = ref(null)
const subjects = ref([])
// Modals
const showSubjectModal = ref(false)
const showRubricModal = ref(false)
const rubricLoading = ref(false)
const subjectCreating = ref(false)

const PRESET_SUBJECTS = [
  { name: '语文', code: 'YW' }, { name: '数学', code: 'SX' }, { name: '英语', code: 'YY' },
  { name: '物理', code: 'WL' }, { name: '化学', code: 'HX' }, { name: '生物', code: 'SW' },
  { name: '政治', code: 'ZZ' }, { name: '历史', code: 'LS' }, { name: '地理', code: 'DL' },
  { name: '技术', code: 'JS' },
]
const selectedSubjectCodes = ref([])
const availablePresetSubjects = computed(() => {
  const existing = new Set(subjects.value.map(s => s.code))
  return PRESET_SUBJECTS.filter(s => !existing.has(s.code))
})
const subjectForm = reactive({ name: '', code: '' })
const rubricForm = reactive({ criteria: '', reference_answer: '', questionId: '' })

// Scan pipeline 已迁移到 GradingDispatchPage

const statusMap = {
  draft: { label: '草稿', type: 'default' },
  scanning: { label: '扫描中', type: 'info' },
  grading: { label: '批改中', type: 'warning' },
  reviewing: { label: '复核中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
}
const statusLabel = (s) => statusMap[s]?.label || s
const statusType = (s) => statusMap[s]?.type || 'default'

const subjectOptions = computed(() =>
  subjects.value.map((s) => ({ label: `${s.name} (${s.code})`, value: s.id })),
)

const subjectColumns = [
  { title: '科目名称', key: 'name' },
  { title: '代码', key: 'code', width: 120 },
]

async function loadExam() {
  loading.value = true
  try {
    const [examRes, subjRes] = await Promise.all([getExam(examId), listSubjects(examId)])
    exam.value = examRes.data
    cardForm.cardTitle = examRes.data.card_title || ''
    subjects.value = subjRes.data
  } catch { /* interceptor */ } finally {
    loading.value = false
  }
}

async function handleSaveCardTitle() {
  if (!cardForm.cardTitle.trim()) {
    message.warning('请输入答题卡标题')
    return
  }
  cardTitleSaving.value = true
  try {
    const { data } = await updateExam(examId, { card_title: cardForm.cardTitle })
    exam.value = data
    message.success('答题卡标题已保存')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
  cardTitleSaving.value = false
}

function openSubjectModal() {
  selectedSubjectCodes.value = availablePresetSubjects.value.map(s => s.code)
  showSubjectModal.value = true
}

async function handleBatchCreateSubjects() {
  if (selectedSubjectCodes.value.length === 0) return
  subjectCreating.value = true
  const toAdd = PRESET_SUBJECTS.filter(s => selectedSubjectCodes.value.includes(s.code))
  let ok = 0
  for (const s of toAdd) {
    try {
      await createSubject(examId, { name: s.name, code: s.code })
      ok++
    } catch (e) {
      message.error(`${s.name} 添加失败: ${e.response?.data?.detail || '未知错误'}`)
    }
  }
  if (ok > 0) {
    message.success(`成功添加 ${ok} 个科目`)
    showSubjectModal.value = false
    await loadExam()
  }
  subjectCreating.value = false
}

async function openRubric(questionId) {
  rubricForm.questionId = questionId
  rubricForm.criteria = ''
  rubricForm.reference_answer = ''
  showRubricModal.value = true
  rubricLoading.value = true
  try {
    const { data } = await getRubric(questionId)
    rubricForm.criteria = typeof data.criteria === 'string' ? data.criteria : JSON.stringify(data.criteria, null, 2)
    rubricForm.reference_answer = data.reference_answer || ''
  } catch (e) {
    if (e.response?.status !== 404) message.error('加载评分标准失败')
  }
  rubricLoading.value = false
}

async function handleSaveRubric() {
  let criteria
  try {
    criteria = JSON.parse(rubricForm.criteria)
  } catch {
    message.error('评分细则必须是合法 JSON')
    return
  }
  try {
    await upsertRubric({
      question_id: rubricForm.questionId,
      criteria,
      reference_answer: rubricForm.reference_answer,
    })
    message.success('评分标准保存成功')
    showRubricModal.value = false
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  }
}

// --- 批量导出 PDF ---
const batchExporting = ref(false)
const batchExportProgress = ref('')

async function handleBatchExportPdf() {
  if (subjects.value.length === 0) { message.warning('无科目可导出'); return }
  batchExporting.value = true
  batchExportProgress.value = '准备中...'
  try {
    const { batchExportPdf } = await import('@/card-editor/export.js')
    const results = await batchExportPdf(
      subjects.value,
      exam.value?.card_title || exam.value?.name || '',
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

// --- 可视化编辑器 ---
const cardEditorRef = ref(null)
const visualEditorSubjectId = ref(null)
const visualEditorSubjectName = computed(() => {
  const s = subjects.value.find(s => s.id === visualEditorSubjectId.value)
  return s ? s.name : ''
})

const autoLayouting = ref(false)

async function handleAutoLayout() {
  if (!visualEditorSubjectId.value || !cardEditorRef.value) return
  // 让用户选择答案文件
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.docx'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    autoLayouting.value = true
    try {
      // 上传文件到临时路径，后端解析
      const formData = new FormData()
      formData.append('file', file)
      const token = localStorage.getItem('token')
      const uploadHeaders = {}
      if (token) uploadHeaders['Authorization'] = `Bearer ${token}`
      const uploadResp = await fetch('/api/v1/card/upload-answer', {
        method: 'POST', headers: uploadHeaders, body: formData,
      })
      if (!uploadResp.ok) {
        message.warning('文件上传失败')
        return
      }
      const { file_path } = await uploadResp.json()

      // 调用排版接口
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const resp = await fetch(`/api/v1/card/auto-layout/${visualEditorSubjectId.value}`, {
        method: 'POST', headers,
        body: JSON.stringify({ answer_file: file_path }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        message.warning(err.detail || `排版失败: HTTP ${resp.status}`)
        return
      }
      const result = await resp.json()
      // 刷新编辑器加载新布局
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

async function handleResetLayout() {
  if (!cardEditorRef.value) return
  const d = dialog.warning({
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

async function handlePublishCard() {
  if (!visualEditorSubjectId.value) {
    message.warning('请先选择科目')
    return
  }
  const subjectId = visualEditorSubjectId.value
  const subj = subjects.value.find(s => s.id === subjectId)
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
        // F003: 单次调用后端 /api/v1/card/publish (PDF + Question + Template + status)
        const exportModule = await import('@/card-editor/export.js')
        await exportModule.publishCard(subjectId, examId, filename)

        // Refresh exam data (updates readonly state)
        await loadExam()
        message.success('答题卡已发布，扫描端可拉取模板')
      } catch (e) {
        message.error('发布失败: ' + (e.message || '未知错误'))
      }
    },
  })
}

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
const skeletonLoaded = ref(false)
const currentSkeleton = ref({})
const currentLayout = ref(null)
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
const previewLoading = ref(false)
const generateLoading = ref(false)
const isFullscreen = ref(false)
const previewIframe = ref(null)

function renderMath(text) {
  if (!text) return ''
  // 先渲染 LaTeX（在原始文本上操作，保留 < > 等符号给 KaTeX）
  // 用占位符保护已渲染的 HTML
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
  // 转义剩余文本的 HTML
  processed = processed
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  // 还原 KaTeX 渲染结果
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

async function onSubjectSelect(subjectId) {
  cardForm.subjectId = subjectId
  currentLayout.value = null
  answerFileList.value = []
  uploadKey.value++
  parseStep.value = 'upload'
  pendingQuestionsForEditor.value = null
  if (cardPreviewUrl.value) {
    URL.revokeObjectURL(cardPreviewUrl.value)
    cardPreviewUrl.value = null
  }
}

function goToEditor() {
  // 直接进可视化编辑器（无答案数据，使用学科默认模板）
  pendingQuestionsForEditor.value = null
  visualEditorSubjectId.value = cardForm.subjectId
  activeTab.value = 'visual-editor'
}


async function handleAnswerUpload({ file, onFinish, onError }) {
  const subj = subjects.value.find(s => s.id === cardForm.subjectId)
  if (!subj) { onError(); return }
  cardLoading.value = true
  try {
    const resp = await parseAnswers(file.file, cardForm.subjectId, examId, {
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

    // 保存 standardized 数据供后续 confirmAnswers 使用
    parsedStandardized.value = data.standardized || []
    // 始终进入答案预览步骤，让用户确认题型、小问数、分值
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

const objectiveQuestions = computed(() =>
  parsedQuestions.value.filter(q => q.question_type === 'objective')
)
const subjectiveParsed = computed(() =>
  parsedQuestions.value.filter(q => q.question_type === 'subjective')
)

const typeOptions = [
  { label: '单选', value: 'single_choice' },
  { label: '多选', value: 'multi_choice' },
  { label: '填空', value: 'fill_in_blank' },
  { label: '解答', value: 'short_answer' },
]

const scoreSum = computed(() =>
  (parsedStandardized.value || []).reduce((s, q) => s + (q.score || 0), 0)
)

const answerRowClass = (row) => {
  if (row.confidence < 0.5) return 'row-danger'
  if (row.confidence < 0.8) return 'row-warning'
  return ''
}

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
const subjectiveQuestions = computed(() =>
  parsedQuestions.value.filter(q => q.question_type === 'subjective')
)

async function confirmAnswers() {
  // 确认答案后带着解析数据跳到可视化编辑器
  pendingQuestionsForEditor.value = (parsedStandardized.value || []).map(q => ({
    number: q.number,
    type: q.type,
    answer: q.answer,
    score: q.score,
    options_count: q.options_count || 4,
    sub_count: q.sub_count || 0,
  }))
  visualEditorSubjectId.value = cardForm.subjectId
  activeTab.value = 'visual-editor'
  message.success('题型数据已填充到编辑器，请检查后导出 PDF')
}

function onWeightChange() {
  // 权重变化后归一化（只处理主观题，客观题无 weight 属性）
  const subjective = parsedQuestions.value.filter(q => q.weight !== undefined)
  const total = subjective.reduce((s, q) => s + q.weight, 0)
  if (total > 0) {
    parsedWeights.value = subjective.map(q => ({
      number: q.number,
      weight: q.weight / total,
      parsed_structure: [{ sub: 1, score: 1, space_type: 'essay' }],
    }))
  }
}

async function handlePreview() {
  previewLoading.value = true
  try {
    const payload = {
      subject_code: parsedMeta.value.subject_code,
      exam_id: examId,
      subject_id: cardForm.subjectId,
      weights: parsedWeights.value,
      skeleton: parsedSkeleton.value,
    }
    const resp = await previewByWeights(payload)
    if (cardPreviewUrl.value) URL.revokeObjectURL(cardPreviewUrl.value)
    cardPreviewUrl.value = URL.createObjectURL(resp.data)
    message.success('预览已生成')
  } catch (e) {
    const detail = e.response?.data instanceof Blob
      ? await e.response.data.text().then(t => { try { return JSON.parse(t).detail } catch { return t } })
      : e.response?.data?.detail
    message.error(detail || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function handleGenerate() {
  generateLoading.value = true
  try {
    const layout = hasTplSlots.value ? parsedLayout.value : null
    const payload = {
      subject_code: parsedMeta.value.subject_code,
      exam_id: examId,
      subject_id: cardForm.subjectId,
      layout: layout || parsedLayout.value,
    }
    const resp = await generateCardV2(payload)
    const subj = subjects.value.find(s => s.id === cardForm.subjectId)
    saveBlob(resp.data, `答题卡_${subj?.name || '未知'}.pdf`)
    message.success('答题卡已生成并下载')
    parseStep.value = 'done'
  } catch (e) {
    const detail = e.response?.data instanceof Blob
      ? await e.response.data.text().then(t => { try { return JSON.parse(t).detail } catch { return t } })
      : e.response?.data?.detail
    message.error(detail || '生成失败')
  } finally {
    generateLoading.value = false
  }
}

function resetToUpload() {
  answerFileList.value = []
  uploadKey.value++
  parseStep.value = 'upload'
  currentLayout.value = null
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

onMounted(loadExam)
</script>

<style scoped>
.row-warning td { background-color: #fffbe6 !important; }
.row-danger td { background-color: #fff1f0 !important; }
.toolbar-btn {
  border: 1px solid rgba(0, 0, 0, 0.2) !important;
  color: rgba(0, 0, 0, 0.75) !important;
  background: transparent !important;
}
.toolbar-btn:hover {
  border-color: rgba(0, 0, 0, 0.4) !important;
  color: #000 !important;
  background: rgba(0, 0, 0, 0.04) !important;
}
.toolbar-btn:disabled {
  border-color: rgba(0, 0, 0, 0.08) !important;
  color: rgba(0, 0, 0, 0.25) !important;
}
</style>
