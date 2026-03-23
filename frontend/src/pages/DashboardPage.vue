<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">仪表盘</h1>
      <p class="page-subtitle">欢迎回来，{{ auth.user?.display_name }}</p>
    </div>

    <div class="stats-grid">
      <div class="stat-card" style="background: var(--macaron-mint-light);">
        <div class="stat-value">{{ stats.totalExams }}</div>
        <div class="stat-label">考试总数</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-yellow-light);">
        <div class="stat-value">{{ stats.gradingInProgress }}</div>
        <div class="stat-label">进行中批改</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-coral-light);">
        <div class="stat-value">{{ stats.pendingReviews }}</div>
        <div class="stat-label">待复核</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-purple-light);">
        <div class="stat-value">{{ stats.completionRate }}</div>
        <div class="stat-label">完成率</div>
      </div>
    </div>

    <div style="margin-top: 40px;">
      <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 20px;">最近考试</h2>
      <n-spin :show="loading">
        <div class="exam-cards">
          <div v-for="exam in exams" :key="exam.id" class="exam-card" @click="$router.push(`/exams/${exam.id}`)">
            <div class="exam-card-header">
              <span class="exam-name">{{ exam.name }}</span>
              <n-tag :type="statusType(exam.status)" round size="small">{{ statusLabel(exam.status) }}</n-tag>
            </div>
            <div class="exam-card-meta">
              <span>创建于 {{ formatDate(exam.created_at) }}</span>
            </div>
            <div class="exam-card-actions">
              <n-button text type="primary" size="small" @click.stop="$router.push(`/analytics/${exam.id}`)">
                查看分析 →
              </n-button>
            </div>
          </div>
          <n-empty v-if="!loading && exams.length === 0" description="暂无考试" />
        </div>
      </n-spin>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { listExams } from '../api/exams'
import { getPending } from '../api/grading'

const auth = useAuthStore()
const loading = ref(true)
const exams = ref([])
const stats = reactive({
  totalExams: 0,
  gradingInProgress: 0,
  pendingReviews: 0,
  completionRate: '-',
})

const statusMap = {
  draft: { label: '草稿', type: 'default' },
  scanning: { label: '扫描中', type: 'info' },
  grading: { label: '批改中', type: 'warning' },
  reviewing: { label: '复核中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
}

const statusLabel = (s) => statusMap[s]?.label || s
const statusType = (s) => statusMap[s]?.type || 'default'

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  try {
    const [examRes, pendingRes] = await Promise.all([listExams(), getPending()])
    exams.value = examRes.data
    stats.totalExams = examRes.data.length
    stats.pendingReviews = Array.isArray(pendingRes.data) ? pendingRes.data.length : 0
    const completed = examRes.data.filter((e) => e.status === 'completed').length
    stats.completionRate = examRes.data.length > 0
      ? Math.round((completed / examRes.data.length) * 100) + '%'
      : '-'
    stats.gradingInProgress = examRes.data.filter((e) => e.status === 'grading').length
  } catch { /* axios 拦截器处理 */ }
  loading.value = false
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.exam-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.exam-card {
  background: white;
  padding: 24px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: var(--transition);
}

.exam-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-border);
}

.exam-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.exam-name {
  font-size: 16px;
  font-weight: 700;
}

.exam-card-meta {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 12px;
}

.exam-card-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .exam-cards { grid-template-columns: 1fr; }
}
</style>
