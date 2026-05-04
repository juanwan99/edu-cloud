<template>
  <div>
    <div v-if="scopeType === 'class'" style="margin-bottom: var(--space-4); text-align: right;">
      <n-radio-group v-model:value="timeRange" size="small" @update:value="loadDashboard">
        <n-radio-button value="week">本周</n-radio-button>
        <n-radio-button value="month">本月</n-radio-button>
        <n-radio-button value="semester">本学期</n-radio-button>
      </n-radio-group>
    </div>

    <n-spin :show="loading">
      <!-- Summary cards (all scopes) -->
      <div v-if="overviewData?.summary" class="stats-row">
        <div v-for="(value, key) in summaryCards" :key="key" class="stat-card">
          <div class="stat-label">{{ value.label }}</div>
          <div class="stat-value">
            {{ value.value }}<span v-if="value.suffix" class="stat-suffix" :style="{ color: value.suffixColor }">{{ value.suffix }}</span>
          </div>
        </div>
      </div>

      <!-- CLASS scope: existing view -->
      <template v-if="scopeType === 'class'">
      <!-- Charts row: trend + pie -->
      <n-grid :cols="2" :x-gap="16" class="section-gap">
        <n-gi>
          <n-card title="积分走势（最近 4 周）" size="small">
            <v-chart v-if="trendOption" class="chart-height-sm" :option="trendOption" autoresize />
            <n-empty v-else description="暂无数据" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card title="加分/扣分比例" size="small">
            <v-chart v-if="pieOption" class="chart-height-sm" :option="pieOption" autoresize />
            <n-empty v-else description="暂无数据" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Top / Bottom students -->
      <n-grid :cols="2" :x-gap="16" class="section-gap">
        <n-gi>
          <n-card title="积分最高" size="small">
            <n-spin :show="loadingRankings">
              <n-list v-if="topStudents.length > 0" bordered size="small">
                <n-list-item v-for="s in topStudents" :key="s.student_id">
                  <div class="row-between">
                    <span>{{ s.student_name }}</span>
                    <div class="progress-cell">
                      <n-progress
                        type="line"
                        :percentage="maxPoints > 0 ? Math.min(100, Math.round((s.total_points / maxPoints) * 100)) : 0"
                        :show-indicator="false"
                        status="success"
                        class="progress-bar"
                        rail-color="rgba(255,255,255,0.08)"
                      />
                      <n-tag type="success" size="small">{{ s.total_points }}</n-tag>
                    </div>
                  </div>
                </n-list-item>
              </n-list>
              <n-empty v-else description="暂无数据" />
            </n-spin>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card title="积分最低" size="small">
            <n-spin :show="loadingRankings">
              <n-list v-if="bottomStudents.length > 0" bordered size="small">
                <n-list-item v-for="s in bottomStudents" :key="s.student_id">
                  <div class="row-between">
                    <span>{{ s.student_name }}</span>
                    <div class="progress-cell">
                      <n-progress
                        type="line"
                        :percentage="minPoints < 0 ? Math.min(100, Math.round((Math.abs(s.total_points) / Math.abs(minPoints)) * 100)) : 0"
                        :show-indicator="false"
                        status="error"
                        class="progress-bar"
                        rail-color="rgba(255,255,255,0.08)"
                      />
                      <n-tag type="error" size="small">{{ s.total_points }}</n-tag>
                    </div>
                  </div>
                </n-list-item>
              </n-list>
              <n-empty v-else description="暂无数据" />
            </n-spin>
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Recent records -->
      <n-card title="最近记录" class="section-gap">
        <n-spin :show="loadingRecords">
          <n-list v-if="recentRecords.length > 0" bordered size="small">
            <n-list-item v-for="r in recentRecords" :key="r.id">
              <div class="row-between">
                <div>
                  <span class="text-medium">{{ r.student_name }}</span>
                  <span class="record-note">{{ r.note || r.rule_name || '' }}</span>
                </div>
                <n-space :size="8" align="center">
                  <n-tag :type="r.points >= 0 ? 'success' : 'error'" size="small">
                    {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
                  </n-tag>
                  <span class="text-muted">
                    {{ r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '' }}
                  </span>
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无记录">
            <template #extra>
              <n-button type="primary" size="small" @click="$router.push({ path: '/conduct', query: { tab: 'points' } })">去记积分</n-button>
            </template>
          </n-empty>
        </n-spin>
      </n-card>

      <!-- Quick actions -->
      <n-card size="small">
        <n-space justify="center" :size="16">
          <n-button type="primary" @click="$router.push({ path: '/conduct', query: { tab: 'points' } })">记积分</n-button>
          <n-button type="info" @click="$router.push({ path: '/conduct', query: { tab: 'rankings' } })">查排行</n-button>
          <n-button type="default" @click="$router.push({ path: '/conduct', query: { tab: 'records' } })">查记录</n-button>
        </n-space>
      </n-card>
      </template>

      <!-- SCHOOL scope: class comparison table + trend -->
      <template v-else-if="scopeType === 'school'">
        <n-card title="班级德育对比" class="section-gap">
          <n-data-table
            :columns="classCompareColumns"
            :data="overviewData?.class_comparison || []"
            size="small"
          />
        </n-card>
        <n-card title="积分趋势（最近 4 周）" size="small" class="section-gap" v-if="overviewData?.trend?.length">
          <v-chart :option="overviewTrendOption" class="chart-height-sm" autoresize />
        </n-card>
      </template>

      <!-- DISTRICT scope: school comparison table + trend -->
      <template v-else-if="scopeType === 'district'">
        <n-card title="学校德育对比" class="section-gap">
          <n-data-table
            :columns="schoolCompareColumns"
            :data="overviewData?.school_comparison || []"
            size="small"
          />
        </n-card>
        <n-card title="积分趋势（最近 4 周）" size="small" class="section-gap" v-if="overviewData?.trend?.length">
          <v-chart :option="overviewTrendOption" class="chart-height-sm" autoresize />
        </n-card>
      </template>
    </n-spin>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import {
  NGrid, NGi, NCard, NList, NListItem,
  NTag, NSpace, NSpin, NEmpty, NRadioGroup, NRadioButton,
  NProgress, NButton, NDataTable,
} from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useAuthStore } from '../../stores/auth'
import { getConductOverview, getRecords, getStudentRankings } from '../../api/conduct'
import { CHART_DEFAULTS, CHART_PALETTE } from '../../config/chartTheme.js'

use([LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const overviewData = ref(null)
const scopeType = computed(() => overviewData.value?.scope_type || null)
const loading = ref(false)

const timeRange = ref('week')
const stats = ref({ totalStudents: 0, weeklyPlus: 0, weeklyMinus: 0, weeklyCount: 0 })
const topStudents = ref([])
const bottomStudents = ref([])
const recentRecords = ref([])
const loadingRankings = ref(false)
const loadingRecords = ref(false)
const trendOption = ref(null)
const pieOption = ref(null)

const maxPoints = computed(() => {
  if (topStudents.value.length === 0) return 1
  return Math.max(...topStudents.value.map(s => s.total_points), 1)
})

const minPoints = computed(() => {
  if (bottomStudents.value.length === 0) return -1
  return Math.min(...bottomStudents.value.map(s => s.total_points), -1)
})

// Summary cards adapt to scope
const summaryCards = computed(() => {
  const s = overviewData.value?.summary
  if (!s) return {}
  const st = scopeType.value
  if (st === 'class') {
    return {
      totalStudents: { label: '总学生数', value: s.total_students ?? stats.value.totalStudents },
      totalPositive: { label: '加分总额', value: s.total_positive ?? stats.value.weeklyPlus, suffix: '+', suffixColor: 'var(--color-success)' },
      totalNegative: { label: '扣分总额', value: s.total_negative ?? stats.value.weeklyMinus, suffix: '-', suffixColor: 'var(--color-danger)' },
      totalRecords: { label: '记录数', value: s.total_records ?? stats.value.weeklyCount },
    }
  }
  if (st === 'school') {
    return {
      totalStudents: { label: '总学生数', value: s.total_students ?? 0 },
      totalRecords: { label: '总记录数', value: s.total_records ?? 0 },
      classCount: { label: '班级数', value: s.class_count ?? 0 },
    }
  }
  if (st === 'district') {
    return {
      totalSchools: { label: '学校数', value: s.total_schools ?? 0 },
      totalStudents: { label: '总学生数', value: s.total_students ?? 0 },
    }
  }
  return {}
})

// Table columns for school/district scopes
const classCompareColumns = [
  { title: '班级', key: 'class_name' },
  { title: '记录数', key: 'record_count', sorter: 'default' },
  {
    title: '平均积分',
    key: 'avg_points',
    sorter: 'default',
    render: (row) => h(NTag, { type: row.avg_points >= 0 ? 'success' : 'error', size: 'small' }, () => row.avg_points.toFixed(1)),
  },
]

const schoolCompareColumns = [
  { title: '学校', key: 'school_name' },
  { title: '学生数', key: 'total_students' },
  { title: '记录数', key: 'record_count', sorter: 'default' },
  { title: '平均积分', key: 'avg_points', sorter: 'default' },
]

function getDateRange() {
  const now = new Date()
  if (timeRange.value === 'week') {
    return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  } else if (timeRange.value === 'month') {
    return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
  }
  // semester: ~6 months
  return new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000)
}

function buildTrendOption(items) {
  // Aggregate by week (last 4 weeks)
  const now = new Date()
  const weeks = []
  for (let i = 3; i >= 0; i--) {
    const weekEnd = new Date(now.getTime() - i * 7 * 24 * 60 * 60 * 1000)
    const weekStart = new Date(weekEnd.getTime() - 7 * 24 * 60 * 60 * 1000)
    weeks.push({ start: weekStart, end: weekEnd, plus: 0, minus: 0 })
  }
  items.forEach(r => {
    const d = new Date(r.created_at)
    for (const w of weeks) {
      if (d >= w.start && d < w.end) {
        if (r.points > 0) w.plus += r.points
        else w.minus += Math.abs(r.points)
        break
      }
    }
  })
  const labels = weeks.map((w, i) => `第${i + 1}周`)
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { ...CHART_DEFAULTS.legend, data: ['加分', '扣分'] },
    grid: { ...CHART_DEFAULTS.grid, left: 40, right: 16, top: 36, bottom: 24 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: labels },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [
      { name: '加分', type: 'line', data: weeks.map(w => w.plus), smooth: true, itemStyle: { color: CHART_PALETTE[1] }, areaStyle: { color: 'rgba(244,218,76,0.15)' } },
      { name: '扣分', type: 'line', data: weeks.map(w => w.minus), smooth: true, itemStyle: { color: '#e88080' }, areaStyle: { color: 'rgba(232,128,128,0.15)' } },
    ],
  }
}

function buildPieOption(plusTotal, minusTotal) {
  if (plusTotal === 0 && minusTotal === 0) return null
  return {
    ...CHART_DEFAULTS,
    grid: undefined,
    xAxis: undefined,
    yAxis: undefined,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { ...CHART_DEFAULTS.legend, bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: { show: true, color: CHART_DEFAULTS.textStyle.color },
      data: [
        { value: plusTotal, name: '加分', itemStyle: { color: CHART_PALETTE[1] } },
        { value: minusTotal, name: '扣分', itemStyle: { color: '#e88080' } },
      ],
    }],
  }
}

// Trend chart for school/district scopes (uses backend-aggregated trend data)
const overviewTrendOption = computed(() => {
  const trend = overviewData.value?.trend
  if (!trend?.length) return null
  const labels = trend.map(t => t.week_start?.slice(5) || '')
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { ...CHART_DEFAULTS.legend, data: ['加分', '扣分'] },
    grid: { ...CHART_DEFAULTS.grid, left: 40, right: 16, top: 36, bottom: 24 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: labels },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [
      { name: '加分', type: 'line', data: trend.map(t => t.positive), smooth: true, itemStyle: { color: CHART_PALETTE[1] }, areaStyle: { color: 'rgba(244,218,76,0.15)' } },
      { name: '扣分', type: 'line', data: trend.map(t => t.negative), smooth: true, itemStyle: { color: '#e88080' }, areaStyle: { color: 'rgba(232,128,128,0.15)' } },
    ],
  }
})

async function loadDashboard() {
  if (!classId.value) return
  loadingRankings.value = true
  loadingRecords.value = true

  // Load rankings for stats + top/bottom
  try {
    const res = await getStudentRankings(classId.value, {})
    const rankings = res.data.rankings || res.data || []
    stats.value.totalStudents = rankings.length
    topStudents.value = rankings.slice(0, 5)
    bottomStudents.value = rankings.length > 5 ? rankings.slice(-5).reverse() : []
  } catch {
    topStudents.value = []
    bottomStudents.value = []
  } finally {
    loadingRankings.value = false
  }

  // Load records for the selected time range + compute stats + charts
  try {
    const startDate = getDateRange()
    const res = await getRecords(classId.value, {
      page: 1,
      size: 200,
      start_date: startDate.toISOString().split('T')[0],
    })
    const items = res.data.items || res.data || []
    recentRecords.value = items.slice(0, 10)
    stats.value.weeklyCount = items.length
    const plusTotal = items.filter(r => r.points > 0).reduce((s, r) => s + r.points, 0)
    const minusTotal = Math.abs(items.filter(r => r.points < 0).reduce((s, r) => s + r.points, 0))
    stats.value.weeklyPlus = plusTotal
    stats.value.weeklyMinus = minusTotal
    trendOption.value = buildTrendOption(items)
    pieOption.value = buildPieOption(plusTotal, minusTotal)
  } catch {
    recentRecords.value = []
    trendOption.value = null
    pieOption.value = null
  } finally {
    loadingRecords.value = false
  }
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await getConductOverview()
    overviewData.value = res.data
    // If class scope, also load detailed data for charts
    if (res.data.scope_type === 'class' && classId.value) {
      await loadDashboard()
    }
  } catch (e) {
    console.error('Failed to load overview:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadOverview())
</script>

<style scoped>
.section-gap {
  margin-bottom: var(--space-4);
}

.row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 140px;
}

.progress-bar {
  flex: 1;
}

.text-medium {
  font-weight: var(--fw-medium);
}

.record-note {
  margin-left: var(--space-2);
  color: rgba(255, 255, 255, 0.5);
}

.text-muted {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.4);
}
</style>
