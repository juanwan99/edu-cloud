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
      <n-radio-group v-model:value="statusFilter" style="margin-left: var(--space-4);" @update:value="loadErrorBook">
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
        style="margin-top: var(--space-4);"
        :row-props="(row) => ({ style: 'cursor: pointer;', onClick: () => showDetail(row) })"
      />
      <n-empty v-else-if="selectedStudentId && !loading" description="暂无错题记录" style="margin-top: 40px;" />
      <n-empty v-else-if="!selectedStudentId" description="请先选择学生" style="margin-top: 40px;" />
    </n-spin>

    <!-- 详情弹窗 -->
    <n-modal v-model:show="detailVisible" preset="card" style="width: 600px;" title="错题详情">
      <template v-if="detailRow">
        <div class="detail-section">
          <div class="detail-row"><span class="detail-label">考试</span><span>{{ examNames[detailRow.exam_id] || detailRow.exam_id }}</span></div>
          <div class="detail-row"><span class="detail-label">题目 ID</span><span style="font-family: monospace; font-size: var(--fs-base);">{{ detailRow.question_id }}</span></div>
          <div class="detail-row"><span class="detail-label">得分</span><span>{{ detailRow.student_score }} / {{ detailRow.max_score }}</span></div>
          <div class="detail-row">
            <span class="detail-label">掌握状态</span>
            <n-tag size="small" :type="(STATUS_MAP[detailRow.mastery_status] || {}).type || 'default'">
              {{ (STATUS_MAP[detailRow.mastery_status] || {}).label || detailRow.mastery_status }}
            </n-tag>
          </div>
          <div class="detail-row"><span class="detail-label">错误类型</span><span>{{ detailRow.error_type || '-' }}</span></div>
          <div class="detail-row"><span class="detail-label">重做次数</span><span>{{ detailRow.retry_count }} 次</span></div>
          <div class="detail-row"><span class="detail-label">收藏</span><span>{{ detailRow.is_starred ? '★ 已收藏' : '未收藏' }}</span></div>
        </div>
        <div class="detail-section" v-if="detailRow.ai_feedback" style="margin-top: var(--space-4);">
          <h4 style="margin: 0 0 8px; font-size: var(--fs-base);">AI 反馈</h4>
          <div class="detail-feedback">{{ detailRow.ai_feedback }}</div>
        </div>
        <div class="detail-section" v-if="detailRow.knowledge_point_ids?.length" style="margin-top: var(--space-4);">
          <h4 style="margin: 0 0 8px; font-size: var(--fs-base);">关联知识点</h4>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <n-tag v-for="kp in detailRow.knowledge_point_ids" :key="kp" size="small">{{ kp }}</n-tag>
          </div>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NTag, NProgress } from 'naive-ui'
import { getStudentErrorBook, getErrorBookStats } from '../api/bank.js'
import { listStudents } from '../api/students.js'
import client from '../api/client.js'

const route = useRoute()

const selectedStudentId = ref(null)
const statusFilter = ref('')
const loading = ref(false)
const studentsLoading = ref(false)
const stats = ref(null)
const detailVisible = ref(false)
const detailRow = ref(null)
const errors = ref([])
const studentOptions = ref([])
const examNames = ref({})

const STATUS_MAP = {
  unmastered: { label: '未掌握', type: 'error' },
  practicing: { label: '练习中', type: 'warning' },
  mastered: { label: '已掌握', type: 'success' },
}

const columns = computed(() => [
  {
    title: '考试',
    key: 'exam_id',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => examNames.value[row.exam_id] || row.exam_id?.slice(0, 8) + '...',
  },
  {
    title: '得分',
    key: 'score',
    width: 130,
    render: (row) => {
      const pct = row.max_score > 0 ? Math.round(row.student_score / row.max_score * 100) : 0
      const status = pct >= 60 ? 'success' : pct >= 40 ? 'warning' : 'error'
      return h('div', { style: 'display: flex; align-items: center; gap: var(--space-2);' }, [
        h('span', { style: 'font-size: var(--fs-base); min-width: 45px;' }, `${row.student_score}/${row.max_score}`),
        h(NProgress, { percentage: pct, showIndicator: false, status, style: 'width: 50px;' }),
      ])
    },
  },
  { title: '错误类型', key: 'error_type', width: 110, render: (row) => row.error_type || '-' },
  {
    title: '状态',
    key: 'mastery_status',
    width: 90,
    render: (row) => {
      const info = STATUS_MAP[row.mastery_status] || { label: row.mastery_status, type: 'default' }
      return h(NTag, { size: 'small', type: info.type }, () => info.label)
    },
  },
  {
    title: 'AI 反馈',
    key: 'ai_feedback',
    ellipsis: { tooltip: true },
    render: (row) => row.ai_feedback || '-',
  },
  {
    title: '重做',
    key: 'retry_count',
    width: 60,
    render: (row) => `${row.retry_count}次`,
  },
  {
    title: '收藏',
    key: 'is_starred',
    width: 50,
    render: (row) => row.is_starred ? '★' : '-',
  },
])

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

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

    const examIds = [...new Set(errors.value.map(e => e.exam_id).filter(Boolean))]
    const missing = examIds.filter(id => !examNames.value[id])
    if (missing.length) {
      try {
        const { data } = await client.get('/exams', { params: { limit: 50 } })
        const list = Array.isArray(data) ? data : (data.items || [])
        for (const ex of list) { examNames.value[ex.id] = ex.name }
      } catch { /* exam names unavailable */ }
    }
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
.page-header { margin-bottom: var(--space-6); }

.filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
  gap: var(--space-3);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.stat-card {
  background: var(--color-bg-alt);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  text-align: center;
}

.stat-value {
  color: var(--color-primary);
}

.stat-label {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-top: 6px;
}

.detail-section {
  background: var(--color-bg-alt, #f9f9f9);
  border-radius: var(--radius-lg, 8px);
  padding: var(--space-4);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: var(--fs-base);
  border-bottom: 1px solid var(--color-border-light);
}
.detail-row:last-child { border-bottom: none; }

.detail-label {
  color: var(--color-text-muted);
  min-width: 80px;
}

.detail-feedback {
  padding: var(--space-3);
  border-radius: var(--r-xs);
  font-size: var(--fs-base);
  line-height: 1.8;
  white-space: pre-line;
  border: 1px solid var(--color-border-light);
}
</style>
