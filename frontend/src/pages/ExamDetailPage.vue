<template>
  <div>
    <div v-if="loading" style="text-align: center; padding: 80px 0;">
      <n-spin size="large" />
      <p style="margin-top: 16px; color: var(--color-text-secondary);">加载中...</p>
    </div>
    <template v-else>
      <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <n-button text style="margin-bottom: 8px;" @click="$router.push('/exams')">
            <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
            返回考试列表
          </n-button>
          <h1 class="page-title">{{ exam?.name || '' }}</h1>
          <p class="page-subtitle">
            <n-tag v-if="exam" :type="statusType(exam.status)" round size="small">{{ statusLabel(exam.status) }}</n-tag>
          </p>
        </div>
      </div>

      <n-tabs v-model:value="activeTab" type="line">
        <!-- 科目管理 -->
        <n-tab-pane name="subjects" tab="科目管理">
          <SubjectsTab
            :subjects="subjects"
            @open-subject-modal="openSubjectModal"
          />
        </n-tab-pane>

        <!-- 答题卡制作 -->
        <n-tab-pane name="card" tab="答题卡制作">
          <CardMakerTab
            :exam-id="examId"
            :exam="exam"
            :subjects="subjects"
            :subject-options="subjectOptions"
            @update:exam="exam = $event"
            @go-to-editor="handleGoToEditor"
            @confirm-answers="handleConfirmAnswers"
          />
        </n-tab-pane>

        <!-- 可视化答题卡编辑器 -->
        <n-tab-pane name="visual-editor" tab="可视化编辑">
          <VisualEditorTab
            ref="visualEditorTabRef"
            :exam-id="examId"
            :exam="exam"
            :subjects="subjects"
            :subject-options="subjectOptions"
            v-model:visual-editor-subject-id="visualEditorSubjectId"
            :pending-questions="pendingQuestionsForEditor"
            @reload-exam="loadExam"
          />
        </n-tab-pane>

        <!-- 标准答案 -->
        <n-tab-pane name="answers" tab="标准答案">
          <AnswersTab :subject-options="subjectOptions" />
        </n-tab-pane>

        <!-- 题目管理 -->
        <n-tab-pane name="questions" tab="题目管理">
          <QuestionsTab :subject-options="subjectOptions" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { NIcon } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { getExam } from '../api/exams'
import { listSubjects, createSubject } from '../api/subjects'
import { getRubric, upsertRubric } from '../api/rubrics'

import SubjectsTab from './exam-detail/SubjectsTab.vue'
import CardMakerTab from './exam-detail/CardMakerTab.vue'
import VisualEditorTab from './exam-detail/VisualEditorTab.vue'
import AnswersTab from './exam-detail/AnswersTab.vue'
import QuestionsTab from './exam-detail/QuestionsTab.vue'

const route = useRoute()
const message = useMessage()
const examId = route.params.id

const loading = ref(true)
const activeTab = ref('subjects')
const exam = ref(null)
const subjects = ref([])
const visualEditorSubjectId = ref(null)
const pendingQuestionsForEditor = ref(null)
const visualEditorTabRef = ref(null)

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
const rubricForm = reactive({ criteria: '', reference_answer: '', questionId: '' })

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

async function loadExam() {
  loading.value = true
  try {
    const [examRes, subjRes] = await Promise.all([getExam(examId), listSubjects(examId)])
    exam.value = examRes.data
    subjects.value = subjRes.data
  } catch { /* interceptor */ } finally {
    loading.value = false
  }
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

// Cross-tab navigation handlers
function handleGoToEditor(subjectId) {
  pendingQuestionsForEditor.value = null
  visualEditorSubjectId.value = subjectId
  activeTab.value = 'visual-editor'
}

function handleConfirmAnswers({ subjectId, questions }) {
  pendingQuestionsForEditor.value = questions
  visualEditorSubjectId.value = subjectId
  activeTab.value = 'visual-editor'
  message.success('题型数据已填充到编辑器，请检查后导出 PDF')
}

// Expose for test compatibility (tests access vm.visualEditorSubjectId and vm.handlePublishCard)
function handlePublishCard() {
  visualEditorTabRef.value?.handlePublishCard()
}

onMounted(loadExam)
</script>
