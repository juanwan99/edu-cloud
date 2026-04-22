<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">人工阅卷</h1>
      <p class="page-subtitle">选择科目和题目开始阅卷</p>
    </div>

    <!-- 考试选择 + 导入 -->
    <div class="toolbar">
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 300px;"
        @update:value="loadSubjects"
      />
      <n-button type="primary" class="btn-pill" @click="showImportModal = true">
        导入试卷数据
      </n-button>
    </div>

    <n-spin :show="loading">
      <!-- 科目列表 -->
      <div v-for="subj in subjects" :key="subj.id" class="subject-card">
        <div class="subject-header">
          <h3 class="subject-name">{{ subj.name }}</h3>
          <div class="subject-actions">
            <n-button
              size="small"
              :loading="aiLoading === subj.id"
              :disabled="!!aiLoading"
              @click="handleAiGrade(subj)"
            >
              AI 批量阅卷
            </n-button>
          </div>
        </div>
        <n-data-table
          :columns="questionColumns"
          :data="subj.questions"
          :bordered="false"
          size="small"
        />
      </div>
      <n-empty v-if="!loading && subjects.length === 0" description="请先选择考试或导入数据" />
    </n-spin>

    <!-- 导入弹窗 -->
    <n-modal v-model:show="showImportModal" preset="dialog" title="导入试卷数据">
      <n-form>
        <n-form-item label="考试">
          <n-select v-model:value="importExamId" :options="examOptions" placeholder="选择考试" />
        </n-form-item>
        <n-form-item label="文件夹路径">
          <n-input v-model:value="importFolderPath" placeholder="如 D:/试卷数据/切割结果/141984" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showImportModal = false">取消</n-button>
        <n-button type="primary" :loading="importing" @click="handleImport">导入</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NProgress, NTag, useMessage } from 'naive-ui'
import { listSubjects, importFolder } from '../api/marking'
import { createTask, getTask } from '../api/grading'
import client from '../api/client'

const router = useRouter()
const message = useMessage()

const loading = ref(false)
const subjects = ref([])
const selectedExamId = ref(null)
const examOptions = ref([])

// 导入相关
const showImportModal = ref(false)
const importExamId = ref(null)
const importFolderPath = ref('')
const importing = ref(false)

const questionColumns = [
  { title: '题号', key: 'name', width: 120 },
  { title: '满分', key: 'max_score', width: 80 },
  {
    title: '进度',
    key: 'progress',
    render(row) {
      const pct = row.total_answers > 0 ? Math.round(row.graded_count / row.total_answers * 100) : 0
      return h('div', { style: 'display: flex; align-items: center; gap: 8px;' }, [
        h(NProgress, {
          type: 'line',
          percentage: pct,
          indicatorPlacement: 'inside',
          style: 'flex: 1;',
        }),
        h('span', { style: 'font-size: 12px; color: var(--color-text-secondary); white-space: nowrap;' },
          `${row.graded_count}/${row.total_answers}`),
      ])
    },
  },
  {
    title: '操作',
    key: 'action',
    width: 120,
    render(row) {
      const done = row.graded_count >= row.total_answers && row.total_answers > 0
      return h(
        NButton,
        {
          size: 'small',
          type: done ? 'default' : 'primary',
          onClick: () => router.push(`/marking/grade/${row.id}`),
        },
        { default: () => done ? '查看' : '开始阅卷' },
      )
    },
  },
]

// AI 阅卷
const aiLoading = ref(null)
let aiPollTimer = null

async function handleAiGrade(subj) {
  aiLoading.value = subj.id
  try {
    const { data } = await createTask({ subject_id: subj.id })
    message.success(`AI 阅卷任务已创建（${subj.name}）`)
    pollAiTask(data.id, subj)
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    message.error(`AI 阅卷失败: ${detail}`)
    aiLoading.value = null
  }
}

function pollAiTask(taskId, subj) {
  aiPollTimer = setInterval(async () => {
    try {
      const { data } = await getTask(taskId)
      if (data.status === 'completed') {
        clearInterval(aiPollTimer)
        aiLoading.value = null
        message.success(`${subj.name} AI 阅卷完成：${data.completed} 份`)
        await loadSubjects(selectedExamId.value)
      } else if (data.status === 'failed') {
        clearInterval(aiPollTimer)
        aiLoading.value = null
        message.error(`${subj.name} AI 阅卷失败`)
      }
    } catch {
      clearInterval(aiPollTimer)
      aiLoading.value = null
    }
  }, 3000)
}

async function loadExams() {
  try {
    const { data } = await client.get('/exams')
    examOptions.value = data.map(e => ({ label: e.name, value: e.id }))
    if (data.length > 0) {
      selectedExamId.value = data[0].id
      await loadSubjects(data[0].id)
    }
  } catch {}
}

async function loadSubjects(examId) {
  if (!examId) return
  loading.value = true
  try {
    const { data } = await listSubjects(examId)
    subjects.value = data
  } catch {}
  loading.value = false
}

async function handleImport() {
  if (!importExamId.value || !importFolderPath.value) {
    message.warning('请填写完整')
    return
  }
  importing.value = true
  try {
    const { data } = await importFolder({
      exam_id: importExamId.value,
      folder_path: importFolderPath.value,
    })
    message.success(`导入完成：${data.subjects_created} 科目，${data.questions_created} 题，${data.answers_created} 份答卷`)
    showImportModal.value = false
    if (selectedExamId.value === importExamId.value) {
      await loadSubjects(selectedExamId.value)
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '导入失败')
  }
  importing.value = false
}

onMounted(loadExams)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
}

.subject-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 20px;
  margin-bottom: 16px;
}

.subject-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.subject-name {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.subject-actions {
  display: flex;
  gap: 8px;
}
</style>
