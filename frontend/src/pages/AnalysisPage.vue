<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">分析中心</h1>
      <p class="page-subtitle">选择考试或功能模块进行数据分析</p>
    </div>

    <div class="stats-grid" style="margin-bottom: 24px;">
      <div class="stat-card" style="background: var(--macaron-mint-light);">
        <div class="stat-value">{{ exams.length }}</div>
        <div class="stat-label">考试总数</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-purple-light);">
        <div class="stat-value">{{ recentExams.length }}</div>
        <div class="stat-label">近期考试</div>
      </div>
    </div>

    <n-card title="快速进入" size="small" style="margin-bottom: 24px;">
      <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 16px;">
        <n-select
          v-model:value="selectedExamId"
          :options="examOptions"
          placeholder="选择考试查看分析"
          style="flex: 1; max-width: 400px;"
          filterable
          clearable
        />
        <n-button type="primary" :disabled="!selectedExamId" @click="goExamAnalytics">
          查看分析
        </n-button>
      </div>
    </n-card>

    <div class="feature-grid">
      <n-card hoverable class="feature-card" @click="goExamAnalytics" :class="{ disabled: !selectedExamId }">
        <div class="feature-icon" style="background: var(--macaron-mint-light); color: var(--color-primary-light);">
          <span style="font-size: 24px;">📊</span>
        </div>
        <div class="feature-title">考试分析</div>
        <div class="feature-desc">查看单次考试的成绩分布、题目分析、学生排名</div>
      </n-card>

      <n-card hoverable class="feature-card" @click="$router.push('/analytics/trend')">
        <div class="feature-icon" style="background: var(--macaron-purple-light); color: #5b3d8f;">
          <span style="font-size: 24px;">📈</span>
        </div>
        <div class="feature-title">成绩趋势</div>
        <div class="feature-desc">年级、班级、学生多维度成绩趋势对比</div>
      </n-card>

      <n-card hoverable class="feature-card" @click="$router.push('/analytics/report')">
        <div class="feature-icon" style="background: var(--macaron-yellow-light); color: #8f6d3d;">
          <span style="font-size: 24px;">📋</span>
        </div>
        <div class="feature-title">分析报告</div>
        <div class="feature-desc">自定义指标查询，生成多维分析报告</div>
      </n-card>

      <n-card hoverable class="feature-card" :class="{ disabled: !selectedExamId }" @click="goStudentProfile">
        <div class="feature-icon" style="background: var(--macaron-coral-light); color: #8f3d3d;">
          <span style="font-size: 24px;">&#128100;</span>
        </div>
        <div class="feature-title">学生画像</div>
        <div class="feature-desc">个体学情画像，知识掌握度与薄弱环节分析</div>
      </n-card>
    </div>

    <n-card v-if="recentExams.length" title="近期考试" size="small" style="margin-top: 24px;">
      <n-data-table
        :columns="recentColumns"
        :data="recentExams"
        size="small"
        :pagination="false"
      />
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { listExams } from '../api/exams'
// WorkbenchLayout preserved as backup for future three-panel mode
// import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'

const router = useRouter()
const exams = ref([])
const selectedExamId = ref(null)

const examOptions = computed(() =>
  exams.value.map(e => ({ label: e.name, value: e.id }))
)

const recentExams = computed(() => exams.value.slice(0, 5))

const recentColumns = [
  { title: '考试名称', key: 'name', ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 80 },
  {
    title: '操作', key: 'actions', width: 100,
    render: (row) => h(NButton, {
      size: 'tiny', type: 'primary', quaternary: true,
      onClick: () => router.push(`/analytics/${row.id}`),
    }, () => '查看分析'),
  },
]

function goExamAnalytics() {
  if (selectedExamId.value) {
    router.push(`/analytics/${selectedExamId.value}`)
  }
}

function goStudentProfile() {
  if (selectedExamId.value) {
    router.push(`/profile/student/${selectedExamId.value}`)
  }
}

onMounted(async () => {
  try {
    const { data } = await listExams()
    exams.value = data.exams || data || []
  } catch { /* interceptor */ }
})
</script>

<style scoped>
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.feature-card {
  cursor: pointer;
  transition: transform 0.2s;
  text-align: center;
  padding: 8px;
}
.feature-card:hover {
  transform: translateY(-2px);
}
.feature-card.disabled {
  opacity: 0.5;
  pointer-events: none;
}
.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.feature-title {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  margin-bottom: 8px;
}
.feature-desc {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
</style>
