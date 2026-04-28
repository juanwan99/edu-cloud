<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div>
        <h1 class="page-title">学生画像</h1>
        <p class="page-subtitle" v-if="loading || studentName">{{ studentName || '加载中...' }}</p>
      </div>
      <n-button size="small" type="primary" @click="$router.push(`/error-book?studentId=${studentId}`)">查看错题本</n-button>
    </div>

    <n-spin :show="loading">
      <n-result v-if="loadError" status="error" :title="loadError" style="margin: 40px 0;" />

      <!-- 概览卡片 -->
      <div class="stats-grid" v-if="latestSnapshot">
        <div class="stat-card" style="background: var(--macaron-mint-light);">
          <div class="stat-value">{{ latestSnapshot.total_score ?? '-' }}</div>
          <div class="stat-label">最近总分</div>
        </div>
        <div class="stat-card" style="background: var(--macaron-purple-light);">
          <div class="stat-value">{{ latestSnapshot.grade_rank ?? '-' }}</div>
          <div class="stat-label">年级排名</div>
        </div>
        <div class="stat-card" style="background: var(--macaron-yellow-light);">
          <div class="stat-value">{{ latestSnapshot.class_rank ?? '-' }}</div>
          <div class="stat-label">班级排名</div>
        </div>
        <div class="stat-card" style="background: var(--macaron-coral-light);">
          <div class="stat-value">{{ knowledgeList.length }}</div>
          <div class="stat-label">知识点掌握</div>
        </div>
      </div>

      <n-tabs type="line" style="margin-top: 24px;">
        <!-- 成绩趋势 -->
        <n-tab-pane name="trend" tab="成绩趋势">
          <div style="background: white; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--color-border-light);">
            <v-chart v-if="trendChartOption" class="chart-height-lg" :option="trendChartOption" autoresize />
            <n-empty v-else description="暂无多次考试数据" />
          </div>
        </n-tab-pane>

        <!-- 排名变化 -->
        <n-tab-pane name="ranking" tab="排名变化">
          <div style="background: white; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--color-border-light);">
            <v-chart v-if="rankingChartOption" class="chart-height-lg" :option="rankingChartOption" autoresize />
            <n-empty v-else description="暂无排名数据" />
          </div>
        </n-tab-pane>

        <!-- 知识点掌握 -->
        <n-tab-pane name="knowledge" tab="知识点掌握">
          <div style="display: flex; gap: 24px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 300px; background: white; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--color-border-light);">
              <v-chart v-if="radarChartOption" class="chart-height-lg" :option="radarChartOption" autoresize />
              <n-empty v-else description="暂无知识点数据" />
            </div>
            <div style="flex: 1; min-width: 300px;">
              <n-data-table :columns="knowledgeColumns" :data="knowledgeList" :pagination="false"
                size="small" :bordered="false" />
            </div>
          </div>
        </n-tab-pane>

        <!-- 错误模式 -->
        <n-tab-pane name="errors" tab="错误分析">
          <div style="display: flex; gap: 24px; flex-wrap: wrap;">
            <div v-for="ep in errorPatterns" :key="ep.id"
              style="flex: 1; min-width: 280px; background: white; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--color-border-light);">
              <h3 style="margin: 0 0 12px; font-size: 15px; font-weight: 600;">{{ ep.subject_code }}</h3>
              <v-chart class="chart-height-sm" :option="makeErrorPieOption(ep)" autoresize />
              <div style="margin-top: 8px; font-size: 13px; color: var(--color-text-muted);">
                共 {{ ep.total_errors }} 道错题 · {{ ep.exam_count }} 次考试
              </div>
            </div>
          </div>
          <n-empty v-if="!errorPatterns.length" description="暂无错误分析数据" style="margin-top: 24px;" />
        </n-tab-pane>

        <!-- AI 诊断 -->
        <n-tab-pane name="diagnosis" tab="AI 诊断">
          <n-card v-if="diagnosis" size="small">
            <p style="white-space: pre-line; line-height: 1.8;">{{ diagnosis.summary_text || diagnosis.text || JSON.stringify(diagnosis) }}</p>
          </n-card>
          <n-empty v-else description="暂无 AI 诊断数据" />
        </n-tab-pane>
      </n-tabs>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NProgress, NTag } from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart, BarChart, RadarChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  RadarComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import {
  getStudentTrend, getStudentKnowledge,
  getStudentErrorPatterns, getStudentAiDiagnosis,
} from '../api/profile.js'

use([LineChart, BarChart, RadarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])

const route = useRoute()
const message = useMessage()
const studentId = computed(() => route.params.studentId)
const studentName = ref('')

const loading = ref(true)
const snapshots = ref([])
const knowledgeList = ref([])
const errorPatterns = ref([])
const diagnosis = ref(null)
const loadError = ref('')

const latestSnapshot = computed(() => snapshots.value[0] || null)

// --- 成绩趋势图 ---
const trendChartOption = computed(() => {
  if (snapshots.value.length < 2) return null
  const grouped = {}
  for (const s of snapshots.value) {
    const key = s.subject_code || '总分'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(s)
  }
  const examLabels = [...new Set(snapshots.value.map(s => s.exam_id?.slice(0, 8) || ''))].reverse()

  const series = Object.entries(grouped).map(([name, items]) => ({
    name,
    type: 'line',
    smooth: true,
    data: items.map(s => s.total_score ?? s.score_rate * 100).reverse(),
    symbolSize: 6,
  }))

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: Object.keys(grouped) },
    xAxis: { type: 'category', data: examLabels },
    yAxis: { type: 'value', name: '分数' },
    series,
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
  }
})

// --- 排名变化图 ---
const rankingChartOption = computed(() => {
  const data = snapshots.value.filter(s => s.grade_rank != null)
  if (data.length < 2) return null
  const reversed = [...data].reverse()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['年级排名', '班级排名'] },
    xAxis: { type: 'category', data: reversed.map((_, i) => `第${i + 1}次`) },
    yAxis: { type: 'value', name: '排名', inverse: true, min: 1 },
    series: [
      { name: '年级排名', type: 'line', smooth: true, data: reversed.map(s => s.grade_rank), symbolSize: 6, itemStyle: { color: '#6366f1' } },
      { name: '班级排名', type: 'line', smooth: true, data: reversed.map(s => s.class_rank), symbolSize: 6, itemStyle: { color: '#f59e0b' } },
    ],
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
  }
})

// --- 知识点雷达图 ---
const radarChartOption = computed(() => {
  if (!knowledgeList.value.length) return null
  const top = knowledgeList.value.slice(0, 12)
  return {
    tooltip: {},
    radar: {
      indicator: top.map(k => ({
        name: (k.knowledge_point_name || k.knowledge_point_id || '').slice(0, 8),
        max: 1,
      })),
      shape: 'polygon',
    },
    series: [{
      type: 'radar',
      data: [{
        value: top.map(k => k.mastery_level ?? 0),
        name: '掌握率',
        areaStyle: { opacity: 0.2 },
      }],
    }],
  }
})

// --- 知识点表格列 ---
const knowledgeColumns = [
  { title: '知识点', key: 'knowledge_point_name', ellipsis: { tooltip: true },
    render: (row) => row.knowledge_point_name || row.knowledge_point_id?.slice(0, 12) || '-' },
  { title: '掌握度', key: 'mastery_level', width: 160,
    render: (row) => {
      const pct = Math.round((row.mastery_level || 0) * 100)
      const color = pct < 60 ? '#dc3545' : pct < 80 ? '#d97706' : '#16a34a'
      return h(NProgress, { type: 'line', percentage: pct, indicatorPlacement: 'inside', color, style: 'width: 120px;' })
    },
  },
  { title: '趋势', key: 'trend', width: 80,
    render: (row) => {
      const t = row.trend
      if (t === 'improving') return h(NTag, { type: 'success', size: 'small' }, { default: () => '↑进步' })
      if (t === 'declining') return h(NTag, { type: 'error', size: 'small' }, { default: () => '↓退步' })
      return h(NTag, { size: 'small' }, { default: () => '→稳定' })
    },
  },
  { title: '练习', key: 'attempt_count', width: 60 },
]

// --- 错误分析饼图 ---
function makeErrorPieOption(ep) {
  const dist = ep.error_distribution || {}
  const data = Object.entries(dist).map(([name, value]) => ({
    name, value: Math.round(value * 100),
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data,
      label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.15)' } },
    }],
  }
}

// --- 数据加载 ---
async function loadAll() {
  if (!studentId.value) { loading.value = false; return }
  loading.value = true
  loadError.value = ''
  try {
    const [trendRes, knRes, errRes, diagRes] = await Promise.all([
      getStudentTrend(studentId.value).catch(e => { console.warn('trend failed', e); return { data: [] } }),
      getStudentKnowledge(studentId.value).catch(e => { console.warn('knowledge failed', e); return { data: [] } }),
      getStudentErrorPatterns(studentId.value).catch(e => { console.warn('errors failed', e); return { data: [] } }),
      getStudentAiDiagnosis(studentId.value).catch(e => { console.warn('diagnosis failed', e); return { data: null } }),
    ])

    const trendData = Array.isArray(trendRes.data) ? trendRes.data : (trendRes.data?.snapshots || trendRes.data?.items || [])
    snapshots.value = trendData
    if (trendData.length > 0 && trendData[0].student_name) {
      studentName.value = trendData[0].student_name
    }

    const knData = Array.isArray(knRes.data) ? knRes.data : (knRes.data?.items || knRes.data?.knowledge || [])
    knowledgeList.value = knData

    const errData = Array.isArray(errRes.data) ? errRes.data : (errRes.data?.patterns || [])
    errorPatterns.value = errData

    diagnosis.value = diagRes.data
  } catch (e) {
    console.error('loadAll failed', e)
    loadError.value = e.message || '加载失败'
    message.error('加载学生画像失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-subtitle { font-size: 14px; color: var(--color-text-muted); margin: 4px 0 0; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
.stat-card { border-radius: var(--radius-lg); padding: 20px; text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--color-text-primary); }
.stat-label { font-size: 13px; color: var(--color-text-muted); margin-top: 4px; }
</style>
