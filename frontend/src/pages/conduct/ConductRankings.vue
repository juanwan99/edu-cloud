<template>
  <div>
    <div style="display: flex; justify-content: flex-end; margin-bottom: var(--space-4);">
      <n-space :size="12">
        <n-input
          v-model:value="searchName"
          placeholder="搜索学生姓名"
          clearable
          size="small"
          style="width: 160px;"
        />
        <n-select
          v-model:value="semesterId"
          :options="semesterOptions"
          placeholder="选择学期"
          clearable
          size="small"
          style="width: 180px;"
        />
        <n-button size="small" type="primary" :loading="exporting" @click="handleExport">导出排行</n-button>
      </n-space>
    </div>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: var(--space-4);">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Distribution chart -->
      <n-card title="排名分布" size="small" style="margin-bottom: var(--space-4);">
        <v-chart v-if="distOption" class="chart-height-sm" :option="distOption" autoresize />
        <n-empty v-else description="暂无数据" />
      </n-card>

      <n-tabs v-model:value="activeTab" type="line" @update:value="handleTabChange">
        <n-tab-pane name="students" tab="学生排行">
          <n-spin :show="loadingStudents">
            <n-data-table
              :columns="studentColumns"
              :data="filteredStudentRankings"
              :pagination="false"
              size="small"
              :row-class-name="(row) => row.rank <= 3 ? 'top-rank' : ''"
            />
          </n-spin>
        </n-tab-pane>
        <n-tab-pane name="groups" tab="小组排行">
          <n-spin :show="loadingGroups">
            <n-data-table
              :columns="groupColumns"
              :data="groupRankings"
              :pagination="false"
              size="small"
            />
          </n-spin>
        </n-tab-pane>
      </n-tabs>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h, watch } from 'vue'
import {
  NPageHeader, NTabs, NTabPane, NDataTable, NSelect, NSpace,
  NSpin, NTag, NAlert, NInput, NButton, useMessage,
} from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useAuthStore } from '../../stores/auth'
import {
  getStudentRankings, getGroupRankings, getSemesters, exportRankings,
} from '../../api/conduct'
import { CHART_DEFAULTS } from '../../config/chartTheme.js'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
const message = useMessage()
const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const activeTab = ref('students')
const semesterId = ref(null)
const semesterOptions = ref([])
const searchName = ref('')
const exporting = ref(false)

const studentRankings = ref([])
const loadingStudents = ref(false)
const groupRankings = ref([])
const loadingGroups = ref(false)
const distOption = ref(null)

const filteredStudentRankings = computed(() => {
  if (!searchName.value) return studentRankings.value
  const keyword = searchName.value.toLowerCase()
  return studentRankings.value.filter(s =>
    (s.student_name || '').toLowerCase().includes(keyword)
  )
})

const studentColumns = [
  {
    title: '排名',
    key: 'rank',
    width: 70,
    render: (row) => {
      if (row.rank <= 3) {
        const medals = { 1: '🥇', 2: '🥈', 3: '🥉' }
        return h('span', {}, medals[row.rank] || row.rank)
      }
      return row.rank
    },
  },
  { title: '姓名', key: 'student_name' },
  {
    title: '总积分',
    key: 'total_points',
    width: 100,
    render: (row) => h(NTag, {
      type: row.total_points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => row.total_points),
  },
]

const groupColumns = [
  { title: '排名', key: 'rank', width: 70 },
  { title: '小组', key: 'group_name' },
  {
    title: '人数',
    key: 'member_count',
    width: 80,
    render: (row) => row.member_count ?? '-',
  },
  {
    title: '总积分',
    key: 'total_points',
    width: 100,
    render: (row) => h(NTag, {
      type: row.total_points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => row.total_points),
  },
  {
    title: '平均分',
    key: 'avg_points',
    width: 100,
    render: (row) => {
      const avg = row.member_count > 0
        ? (row.total_points / row.member_count).toFixed(1)
        : '-'
      return avg
    },
  },
]

function buildDistOption(rankings) {
  const buckets = [
    { label: '<0', min: -Infinity, max: 0, count: 0 },
    { label: '0-10', min: 0, max: 10, count: 0 },
    { label: '10-30', min: 10, max: 30, count: 0 },
    { label: '30-50', min: 30, max: 50, count: 0 },
    { label: '50+', min: 50, max: Infinity, count: 0 },
  ]
  rankings.forEach(s => {
    const p = s.total_points ?? 0
    for (const b of buckets) {
      if (p >= b.min && p < b.max) { b.count++; break }
    }
  })
  if (rankings.length === 0) return null
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    grid: { ...CHART_DEFAULTS.grid, left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: {
      ...CHART_DEFAULTS.xAxis,
      type: 'category',
      data: buckets.map(b => b.label),
    },
    yAxis: {
      ...CHART_DEFAULTS.yAxis,
      type: 'value',
    },
    series: [{
      type: 'bar',
      data: buckets.map(b => b.count),
      itemStyle: { color: 'rgba(244,218,76,0.7)', borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 40,
    }],
  }
}

async function loadSemesters() {
  if (!classId.value) return
  try {
    const res = await getSemesters(classId.value)
    const list = res.data.semesters || res.data || []
    semesterOptions.value = list.map((s) => ({
      label: s.name + (s.is_active ? '（当前）' : ''),
      value: s.id,
    }))
  } catch {
    semesterOptions.value = []
  }
}

async function loadStudentRankings() {
  if (!classId.value) return
  loadingStudents.value = true
  try {
    const params = semesterId.value ? { semester_id: semesterId.value } : {}
    const res = await getStudentRankings(classId.value, params)
    studentRankings.value = res.data.rankings || res.data || []
    distOption.value = buildDistOption(studentRankings.value)
  } catch {
    studentRankings.value = []
    distOption.value = null
  } finally {
    loadingStudents.value = false
  }
}

async function loadGroupRankings() {
  if (!classId.value) return
  loadingGroups.value = true
  try {
    const params = semesterId.value ? { semester_id: semesterId.value } : {}
    const res = await getGroupRankings(classId.value, params)
    groupRankings.value = res.data.rankings || res.data || []
  } catch {
    groupRankings.value = []
  } finally {
    loadingGroups.value = false
  }
}

function handleTabChange(tab) {
  if (tab === 'students') loadStudentRankings()
  else loadGroupRankings()
}

async function handleExport() {
  if (!classId.value) return
  exporting.value = true
  try {
    const params = semesterId.value ? { semester_id: semesterId.value } : {}
    const res = await exportRankings(classId.value, params)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `积分排行_${new Date().toISOString().split('T')[0]}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

watch(semesterId, () => {
  if (activeTab.value === 'students') loadStudentRankings()
  else loadGroupRankings()
})

onMounted(() => {
  if (classId.value) {
    loadSemesters()
    loadStudentRankings()
  }
})
</script>

<style scoped>
:deep(.top-rank td) {
  font-weight: var(--fw-semibold);
}
</style>
