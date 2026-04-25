<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">错题本</h1>
      <p class="page-subtitle">查看学生错题记录与掌握情况</p>
    </div>

    <!-- 学生选择 + 筛选 -->
    <div class="filter-bar">
      <n-select
        v-model:value="selectedStudentId"
        filterable
        remote
        :options="studentOptions"
        :loading="studentsLoading"
        placeholder="搜索学生姓名或学号..."
        style="width: 280px;"
        @search="onStudentSearch"
        @update:value="onStudentSelect"
      />
      <n-radio-group v-model:value="statusFilter" style="margin-left: 16px;" @update:value="loadErrorBook">
        <n-radio-button value="">全部</n-radio-button>
        <n-radio-button value="unmastered">未掌握</n-radio-button>
        <n-radio-button value="practicing">练习中</n-radio-button>
        <n-radio-button value="mastered">已掌握</n-radio-button>
      </n-radio-group>
    </div>

    <n-spin :show="loading">
      <!-- 统计卡片 -->
      <div class="stats-grid" v-if="stats">
        <div class="stat-card" style="background: var(--macaron-coral-light, #fff0f0);">
          <div class="stat-value" style="color: var(--color-danger, #e63946);">{{ stats.unmastered }}</div>
          <div class="stat-label">未掌握</div>
        </div>
        <div class="stat-card" style="background: var(--macaron-yellow-light, #fff8e1);">
          <div class="stat-value" style="color: var(--color-warning, #f4a261);">{{ stats.practicing }}</div>
          <div class="stat-label">练习中</div>
        </div>
        <div class="stat-card" style="background: var(--macaron-mint-light, #e8f5e9);">
          <div class="stat-value" style="color: var(--color-success, #2a9d8f);">{{ stats.mastered }}</div>
          <div class="stat-label">已掌握</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总计</div>
        </div>
      </div>

      <!-- 错题列表 -->
      <n-data-table
        v-if="errors.length"
        :columns="columns"
        :data="errors"
        :pagination="{ pageSize: 20 }"
        :bordered="false"
        size="small"
        style="margin-top: 16px;"
      />
      <n-empty v-else-if="selectedStudentId && !loading" description="暂无错题记录" style="margin-top: 40px;" />
      <n-empty v-else-if="!selectedStudentId" description="请先选择学生" style="margin-top: 40px;" />
    </n-spin>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NTag } from 'naive-ui'
import { getStudentErrorBook, getErrorBookStats } from '../api/bank.js'
import { listStudents } from '../api/students.js'

const route = useRoute()

const selectedStudentId = ref(null)
const statusFilter = ref('')
const loading = ref(false)
const studentsLoading = ref(false)
const stats = ref(null)
const errors = ref([])
const studentOptions = ref([])

const STATUS_MAP = {
  unmastered: { label: '未掌握', type: 'error' },
  practicing: { label: '练习中', type: 'warning' },
  mastered: { label: '已掌握', type: 'success' },
}

const columns = computed(() => [
  { title: '题目ID', key: 'question_id', width: 120, ellipsis: { tooltip: true } },
  {
    title: '得分',
    key: 'score',
    width: 100,
    render: (row) => `${row.student_score}/${row.max_score}`,
  },
  { title: '错误类型', key: 'error_type', width: 120 },
  {
    title: 'AI 反馈',
    key: 'ai_feedback',
    ellipsis: { tooltip: true },
  },
  {
    title: '知识点',
    key: 'knowledge_point_ids',
    width: 160,
    render: (row) => {
      const kps = row.knowledge_point_ids
      if (!kps || !kps.length) return '-'
      return h('div', { style: 'display: flex; gap: 4px; flex-wrap: wrap;' },
        kps.slice(0, 3).map(kp => h(NTag, { size: 'small', bordered: false }, () => kp))
      )
    },
  },
  {
    title: '状态',
    key: 'mastery_status',
    width: 100,
    render: (row) => {
      const info = STATUS_MAP[row.mastery_status] || { label: row.mastery_status, type: 'default' }
      return h(NTag, { size: 'small', type: info.type }, () => info.label)
    },
  },
  {
    title: '重做',
    key: 'retry_count',
    width: 70,
    render: (row) => `${row.retry_count}次`,
  },
  {
    title: '收藏',
    key: 'is_starred',
    width: 60,
    render: (row) => row.is_starred ? '★' : '-',
  },
])

async function searchStudents(query) {
  studentsLoading.value = true
  try {
    const { data } = await listStudents({ search: query, limit: 20 })
    const list = Array.isArray(data) ? data : (data.items || [])
    studentOptions.value = list.map(s => ({
      label: `${s.name || s.student_number || s.id}${s.class_name ? ' (' + s.class_name + ')' : ''}`,
      value: s.id,
    }))
  } catch {
    studentOptions.value = []
  } finally {
    studentsLoading.value = false
  }
}

function onStudentSearch(query) {
  if (query.length >= 1) searchStudents(query)
}

function onStudentSelect(studentId) {
  if (studentId) loadErrorBook()
}

async function loadErrorBook() {
  if (!selectedStudentId.value) return
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value) params.mastery_status = statusFilter.value
    const [errorResp, statsResp] = await Promise.all([
      getStudentErrorBook(selectedStudentId.value, params),
      getErrorBookStats(selectedStudentId.value),
    ])
    errors.value = errorResp.data
    stats.value = statsResp.data
  } catch (e) {
    errors.value = []
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await searchStudents('')
  const qStudent = route.query.studentId
  if (qStudent) {
    if (!studentOptions.value.find(o => o.value === qStudent)) {
      studentOptions.value.unshift({ label: qStudent.slice(0, 8) + '...', value: qStudent })
    }
    selectedStudentId.value = qStudent
    loadErrorBook()
  }
})
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-subtitle { font-size: 14px; color: var(--color-text-muted); margin: 4px 0 0; }

.filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--color-bg-alt);
  padding: 16px;
  border-radius: var(--radius-lg);
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 6px;
}
</style>
