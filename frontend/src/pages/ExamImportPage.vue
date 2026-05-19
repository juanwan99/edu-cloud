<template>
  <div class="import-wrapper">
    <div class="page-header">
      <h1 class="page-title">外部考试成绩导入</h1>
      <p class="page-subtitle">上传 Excel / ZIP 文件，批量导入外部考试成绩</p>
    </div>

    <n-steps :current="currentStep" style="margin-bottom: var(--space-8);">
      <n-step title="上传文件" />
      <n-step title="预览确认" />
      <n-step title="导入中" />
      <n-step title="完成" />
    </n-steps>

    <!-- Step 1: Upload -->
    <n-card v-if="currentStep === 1" class="step-card">
      <n-form ref="formRef" :model="formData" label-placement="top">
        <n-form-item label="考试名称" required>
          <n-input v-model:value="formData.name" placeholder="如：2026年5月月考" />
        </n-form-item>

        <n-form-item label="考试类型">
          <n-select v-model:value="formData.exam_type" :options="examTypeOptions" placeholder="选择考试类型" />
        </n-form-item>

        <n-form-item label="年级">
          <n-select v-model:value="formData.grade" :options="gradeOptions" placeholder="选择年级" />
        </n-form-item>

        <n-form-item label="考试日期">
          <n-date-picker v-model:value="formData.exam_date" type="date" style="width: 100%;" />
        </n-form-item>

        <n-form-item label="导入模式">
          <n-radio-group v-model:value="formData.import_mode">
            <n-radio value="detail">小题分导入</n-radio>
            <n-radio value="total_only">仅总分导入</n-radio>
          </n-radio-group>
        </n-form-item>

        <n-form-item label="文件上传">
          <n-upload
            :max="1"
            accept=".xlsx,.zip"
            :default-upload="false"
            @change="handleFileChange"
          >
            <n-button>选择文件</n-button>
          </n-upload>
          <p class="help-text">
            支持 .xlsx 或 .zip 格式，单文件上传
          </p>
        </n-form-item>
      </n-form>

      <div class="form-actions">
        <n-button
          type="primary"
          class="btn-pill"
          :loading="uploading"
          :disabled="!formData.name || !uploadFile"
          @click="handleUpload"
        >
          上传并解析
        </n-button>
      </div>
    </n-card>

    <!-- Step 2: Preview -->
    <n-card v-if="currentStep === 2" class="step-card">
      <template v-if="preview">
        <!-- Subjects table -->
        <h3 class="section-title">科目列表</h3>
        <n-data-table
          :columns="subjectColumns"
          :data="preview.subjects || []"
          :bordered="false"
          size="small"
          style="margin-bottom: var(--space-6);"
        />

        <!-- Questions needing confirmation -->
        <template v-if="preview.questions_need_confirm && preview.questions_need_confirm.length > 0">
          <h3 class="section-title">需确认满分的题目</h3>
          <n-data-table
            :columns="confirmColumns"
            :data="preview.questions_need_confirm"
            :bordered="false"
            size="small"
            style="margin-bottom: var(--space-6);"
          />
        </template>

        <!-- Student matching stats -->
        <h3 class="section-title">学生匹配</h3>
        <div class="match-stats">
          <div class="match-stat-item match-stat-matched">
            <n-statistic label="已匹配" :value="preview.matched_count || 0" />
          </div>
          <div class="match-stat-item match-stat-unmatched">
            <n-statistic label="未匹配" :value="preview.unmatched_count || 0" />
          </div>
          <div class="match-stat-item match-stat-ambiguous">
            <n-statistic label="歧义" :value="preview.ambiguous_count || 0" />
          </div>
        </div>

        <!-- Unmatched students list -->
        <template v-if="preview.unmatched_students && preview.unmatched_students.length > 0">
          <n-collapse style="margin-top: var(--space-4); margin-bottom: var(--space-4);">
            <n-collapse-item title="查看未匹配学生" name="unmatched">
              <div class="unmatched-list">
                <n-tag v-for="name in preview.unmatched_students" :key="name" size="small" type="error" style="margin: 2px;">
                  {{ name }}
                </n-tag>
              </div>
            </n-collapse-item>
          </n-collapse>
        </template>

        <!-- Warnings -->
        <template v-if="preview.warnings && preview.warnings.length > 0">
          <n-alert
            v-for="(warn, idx) in preview.warnings"
            :key="idx"
            type="warning"
            :title="warn"
            style="margin-bottom: var(--space-2);"
          />
        </template>
      </template>

      <div class="form-actions">
        <n-button class="btn-pill" @click="handleCancel">取消导入</n-button>
        <n-button type="primary" class="btn-pill" @click="handleConfirm">确认导入</n-button>
      </div>
    </n-card>

    <!-- Step 3: Importing -->
    <n-card v-if="currentStep === 3" class="step-card step-center">
      <n-spin size="large" />
      <p class="importing-text">正在导入数据，请稍候...</p>
      <n-progress type="circle" :percentage="importProgress" :status="importProgress >= 100 ? 'success' : 'default'" />
    </n-card>

    <!-- Step 4: Result -->
    <n-card v-if="currentStep === 4" class="step-card">
      <n-result
        status="success"
        title="导入完成"
        :description="`考试「${formData.name}」成绩已成功导入`"
      >
        <template #footer>
          <div v-if="importResult" class="result-stats">
            <div class="result-stat-row">
              <n-statistic label="考试" :value="importResult.exams_created || 0" />
              <n-statistic label="科目" :value="importResult.subjects_created || 0" />
              <n-statistic label="题目" :value="importResult.questions_created || 0" />
            </div>
            <div class="result-stat-row">
              <n-statistic label="答题记录" :value="importResult.answers_created || 0" />
              <n-statistic label="评分记录" :value="importResult.scores_created || 0" />
            </div>
            <template v-if="importResult.pipeline">
              <n-divider />
              <div class="result-stat-row">
                <n-statistic label="分析快照" :value="importResult.pipeline.snapshots || 0" />
                <n-statistic label="错题记录" :value="importResult.pipeline.error_books || 0" />
              </div>
            </template>
          </div>

          <div class="form-actions" style="margin-top: var(--space-6);">
            <n-button class="btn-pill" @click="handleReset">继续导入</n-button>
            <n-button
              v-if="importResult?.exam_id"
              type="primary"
              class="btn-pill"
              @click="goToExam"
            >
              查看考试详情
            </n-button>
          </div>
        </template>
      </n-result>
    </n-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { createImport, commitImport, cancelImport } from '../api/examImport'

const router = useRouter()
const message = useMessage()

const currentStep = ref(1)
const uploading = ref(false)
const uploadFile = ref(null)
const importId = ref(null)
const preview = ref(null)
const importProgress = ref(0)
const importResult = ref(null)

const formData = reactive({
  name: '',
  exam_type: null,
  grade: null,
  exam_date: null,
  import_mode: 'detail',
})

const examTypeOptions = [
  { label: '月考', value: '月考' },
  { label: '期中', value: '期中' },
  { label: '期末', value: '期末' },
  { label: '联考', value: '联考' },
  { label: '统考', value: '统考' },
  { label: '模考', value: '模考' },
]

const gradeOptions = [
  { label: '高一', value: '高一' },
  { label: '高二', value: '高二' },
  { label: '高三', value: '高三' },
  { label: '初一', value: '初一' },
  { label: '初二', value: '初二' },
  { label: '初三', value: '初三' },
]

const subjectColumns = [
  { title: '科目', key: 'name' },
  { title: '学生数', key: 'student_count', width: 100 },
  { title: '题目数', key: 'question_count', width: 100 },
]

const confirmColumns = [
  { title: '科目', key: 'subject_name' },
  { title: '题号', key: 'question_label' },
  { title: '建议满分', key: 'suggested_max_score', width: 120 },
]

function handleFileChange({ fileList }) {
  uploadFile.value = fileList.length > 0 ? fileList[0].file : null
}

async function handleUpload() {
  if (!formData.name) {
    message.warning('请输入考试名称')
    return
  }
  if (!uploadFile.value) {
    message.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadFile.value)
    fd.append('name', formData.name)
    if (formData.exam_type) fd.append('exam_type', formData.exam_type)
    if (formData.grade) fd.append('grade', formData.grade)
    if (formData.exam_date) fd.append('exam_date', new Date(formData.exam_date).toISOString().split('T')[0])
    fd.append('import_mode', formData.import_mode)

    const { data } = await createImport(fd)
    importId.value = data.id
    preview.value = data.preview
    currentStep.value = 2
  } catch (e) {
    message.error(e.response?.data?.detail || '上传失败，请检查文件格式')
  } finally {
    uploading.value = false
  }
}

async function handleConfirm() {
  if (!importId.value) return
  currentStep.value = 3
  importProgress.value = 30

  try {
    importProgress.value = 60
    const { data } = await commitImport(importId.value)
    importProgress.value = 100
    importResult.value = data
    currentStep.value = 4
  } catch (e) {
    message.error(e.response?.data?.detail || '导入失败')
    currentStep.value = 2
    importProgress.value = 0
  }
}

async function handleCancel() {
  if (importId.value) {
    try {
      await cancelImport(importId.value)
    } catch {
      // ignore cancel errors
    }
  }
  handleReset()
}

function handleReset() {
  currentStep.value = 1
  uploadFile.value = null
  importId.value = null
  preview.value = null
  importProgress.value = 0
  importResult.value = null
  formData.name = ''
  formData.exam_type = null
  formData.grade = null
  formData.exam_date = null
  formData.import_mode = 'detail'
}

function goToExam() {
  if (importResult.value?.exam_id) {
    router.push({ name: 'ExamDetail', params: { examId: importResult.value.exam_id } })
  }
}
</script>

<style scoped>
.import-wrapper {
  max-width: 800px;
  margin: 0 auto;
}

.step-card {
  border-radius: var(--radius-md);
}

.step-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-12) var(--space-8);
}

.section-title {
  font-size: var(--fs-lg);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
  margin-bottom: var(--space-3);
}

.match-stats {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-4);
}

.match-stat-item {
  flex: 1;
  padding: var(--space-4);
  border-radius: var(--radius-sm);
  text-align: center;
}

.match-stat-matched {
  background: var(--surface-success);
  color: var(--color-success-text);
}

.match-stat-unmatched {
  background: var(--surface-danger);
  color: var(--color-danger-text);
}

.match-stat-ambiguous {
  background: var(--surface-accent);
  color: var(--color-warning-text);
}

.unmatched-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.importing-text {
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
}

.result-stats {
  margin-top: var(--space-4);
}

.result-stat-row {
  display: flex;
  justify-content: center;
  gap: var(--space-8);
  margin-bottom: var(--space-4);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-6);
}

.help-text {
  font-size: var(--fs-sm);
  color: var(--color-text-muted);
  margin-top: var(--space-1);
}
</style>
