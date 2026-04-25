<template>
  <div>
    <n-page-header title="德育概览" style="margin-bottom: 16px;">
      <template #extra>
        <n-radio-group v-model:value="timeRange" size="small" @update:value="loadDashboard">
          <n-radio-button value="week">本周</n-radio-button>
          <n-radio-button value="month">本月</n-radio-button>
          <n-radio-button value="semester">本学期</n-radio-button>
        </n-radio-group>
      </template>
    </n-page-header>

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Stats cards -->
      <n-grid :cols="4" :x-gap="16" :y-gap="16" style="margin-bottom: 16px;">
        <n-gi>
          <n-card size="small">
            <n-statistic label="总学生数" :value="stats.totalStudents" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="加分总额" :value="stats.weeklyPlus">
              <template #suffix>分</template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="扣分总额" :value="stats.weeklyMinus">
              <template #suffix>分</template>
            </n-statistic>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="记录数" :value="stats.weeklyCount" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Charts row: trend + pie -->
      <n-grid :cols="2" :x-gap="16" style="margin-bottom: 16px;">
        <n-gi>
          <n-card title="积分走势（最近 4 周）" size="small">
            <v-chart v-if="trendOption" :option="trendOption" autoresize style="height: 260px;" />
            <n-empty v-else description="暂无数据" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card title="加分/扣分比例" size="small">
            <v-chart v-if="pieOption" :option="pieOption" autoresize style="height: 260px;" />
            <n-empty v-else description="暂无数据" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Top / Bottom students -->
      <n-grid :cols="2" :x-gap="16" style="margin-bottom: 16px;">
        <n-gi>
          <n-card title="积分最高" size="small">
            <n-spin :show="loadingRankings">
              <n-list v-if="topStudents.length > 0" bordered size="small">
                <n-list-item v-for="s in topStudents" :key="s.student_id">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>{{ s.student_name }}</span>
                    <div style="display: flex; align-items: center; gap: 8px; min-width: 140px;">
                      <n-progress
                        type="line"
                        :percentage="maxPoints > 0 ? Math.min(100, Math.round((s.total_points / maxPoints) * 100)) : 0"
                        :show-indicator="false"
                        status="success"
                        style="flex: 1;"
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
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>{{ s.student_name }}</span>
                    <div style="display: flex; align-items: center; gap: 8px; min-width: 140px;">
                      <n-progress
                        type="line"
                        :percentage="minPoints < 0 ? Math.min(100, Math.round((Math.abs(s.total_points) / Math.abs(minPoints)) * 100)) : 0"
                        :show-indicator="false"
                        status="error"
                        style="flex: 1;"
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
      <n-card title="最近记录" style="margin-bottom: 16px;">
        <n-spin :show="loadingRecords">
          <n-list v-if="recentRecords.length > 0" bordered size="small">
            <n-list-item v-for="r in recentRecords" :key="r.id">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                  <span style="font-weight: 500;">{{ r.student_name }}</span>
                  <span style="margin-left: 8px; color: rgba(255,255,255,0.5);">{{ r.note || r.rule_name || '' }}</span>
                </div>
                <n-space :size="8" align="center">
                  <n-tag :type="r.points >= 0 ? 'success' : 'error'" size="small">
                    {{ r.points >= 0 ? '+' : '' }}{{ r.points }}
                  </n-tag>
                  <span style="font-size: 12px; color: rgba(255,255,255,0.4);">
                    {{ r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '' }}
                  </span>
                </n-space>
              </div>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无记录" />
        </n-spin>
      </n-card>

      <!-- Quick actions -->
      <n-card size="small">
        <n-space justify="center" :size="16">
          <n-button type="primary" @click="$router.push({ name: 'ConductPoints' })">记积分</n-button>
          <n-button type="info" @click="$router.push({ name: 'ConductRankings' })">查排行</n-button>
          <n-button type="default" @click="$router.push({ name: 'ConductExport' })">导出</n-button>
        </n-space>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NStatistic, NList, NListItem,
  NTag, NSpace, NSpin, NEmpty, NAlert, NRadioGroup, NRadioButton,
  NProgress, NButton,
} from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useAuthStore } from '../../stores/auth'
import { getRecords, getStudentRankings } from '../../api/conduct'

use([LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

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
    tooltip: { trigger: 'axis' },
    legend: { data: ['加分', '扣分'], textStyle: { color: 'rgba(255,255,255,0.65)' } },
    grid: { left: 40, right: 16, top: 36, bottom: 24 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: 'rgba(255,255,255,0.45)' }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } } },
    yAxis: { type: 'value', axisLabel: { color: 'rgba(255,255,255,0.45)' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } },
    series: [
      { name: '加分', type: 'line', data: weeks.map(w => w.plus), smooth: true, itemStyle: { color: '#63e2b7' }, areaStyle: { color: 'rgba(99,226,183,0.15)' } },
      { name: '扣分', type: 'line', data: weeks.map(w => w.minus), smooth: true, itemStyle: { color: '#e88080' }, areaStyle: { color: 'rgba(232,128,128,0.15)' } },
    ],
  }
}

function buildPieOption(plusTotal, minusTotal) {
  if (plusTotal === 0 && minusTotal === 0) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: 'rgba(255,255,255,0.65)' } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: { show: true, color: 'rgba(255,255,255,0.65)' },
      data: [
        { value: plusTotal, name: '加分', itemStyle: { color: '#63e2b7' } },
        { value: minusTotal, name: '扣分', itemStyle: { color: '#e88080' } },
      ],
    }],
  }
}

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
      page_size: 200,
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

onMounted(() => {
  if (classId.value) loadDashboard()
})
</script>
