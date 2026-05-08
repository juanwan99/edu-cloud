<template>
  <n-spin :show="loading">
    <n-empty v-if="!loading && isEmpty" description="暂无分层学情数据" />
    <n-space v-else vertical :size="16">
      <!-- 顶部统计卡片 -->
      <n-grid :cols="3" :x-gap="16">
        <n-gi v-for="layer in layers" :key="layer.label">
          <n-card size="small" class="layer-stat-card">
            <div class="layer-stat-label" :style="{ color: layerColor(layer.label) }">{{ layer.label }}</div>
            <div class="layer-stat-value">{{ layer.count }}<span class="layer-stat-unit">人</span></div>
            <div class="layer-stat-rate">均分率 {{ (layer.avgScoreRate * 100).toFixed(1) }}%</div>
          </n-card>
        </n-gi>
      </n-grid>

      <!-- 差异柱图 -->
      <n-card v-if="maxDiffKnowledges.length" title="知识点掌握差异" size="small">
        <v-chart class="diff-chart" :option="diffChartOption" autoresize />
      </n-card>

      <!-- 各层知识点掌握 -->
      <n-card title="分层知识点掌握" size="small" v-if="layers.length">
        <n-collapse>
          <n-collapse-item v-for="layer in layers" :key="layer.label" :title="`${layer.label}（${layer.count}人）`">
            <n-space vertical :size="8">
              <div v-for="kp in (layer.knowledgeMastery || [])" :key="kp.knpId" class="kp-item">
                <span class="kp-id">{{ kp.knpId }}</span>
                <n-progress
                  type="line"
                  :percentage="Math.round(kp.avgRate * 100)"
                  :color="masteryColor(kp.avgRate)"
                  :rail-color="railColor"
                  :show-indicator="true"
                  style="flex: 1"
                />
              </div>
            </n-space>
          </n-collapse-item>
        </n-collapse>
      </n-card>
    </n-space>
  </n-spin>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { CHART_PALETTE, CHART_DEFAULTS } from '../../config/chartTheme'
import { getLayerAnalysis } from '../../api/analytics'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  examId: { type: String, required: true },
  subjectId: { type: String, default: undefined },
  classId: { type: String, default: undefined },
})

const loading = ref(false)
const layers = ref([])
const maxDiffKnowledges = ref([])

const isEmpty = computed(() => layers.value.length === 0)

const railColor = 'rgba(255,255,255,0.08)'

const LAYER_COLORS = {
  '优秀': '#22C55E',
  '良好': CHART_PALETTE[0],
  '待提升': '#ED9A51',
}

function layerColor(label) {
  return LAYER_COLORS[label] || CHART_PALETTE[0]
}

function masteryColor(rate) {
  if (rate < 0.4) return '#dc2626'
  if (rate < 0.7) return '#ED9A51'
  return '#22C55E'
}

const diffChartOption = computed(() => ({
  ...CHART_DEFAULTS,
  tooltip: {
    ...CHART_DEFAULTS.tooltip,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
  },
  legend: {
    ...CHART_DEFAULTS.legend,
    data: ['优秀层', '待提升层'],
  },
  grid: { ...CHART_DEFAULTS.grid, left: 120 },
  yAxis: {
    type: 'category',
    data: maxDiffKnowledges.value.map(k => k.knpId),
    axisLabel: { ...CHART_DEFAULTS.yAxis.axisLabel },
    axisLine: { show: false },
    axisTick: { show: false },
  },
  xAxis: {
    type: 'value',
    max: 1,
    axisLabel: {
      ...CHART_DEFAULTS.xAxis.axisLabel,
      formatter: v => `${Math.round(v * 100)}%`,
    },
    axisLine: { ...CHART_DEFAULTS.xAxis.axisLine },
    axisTick: { show: false },
    splitLine: { ...CHART_DEFAULTS.yAxis.splitLine },
  },
  series: [
    {
      name: '优秀层',
      type: 'bar',
      data: maxDiffKnowledges.value.map(k => k.topLayerRate),
      itemStyle: { color: '#22C55E' },
      barGap: '10%',
    },
    {
      name: '待提升层',
      type: 'bar',
      data: maxDiffKnowledges.value.map(k => k.bottomLayerRate),
      itemStyle: { color: '#ED9A51' },
    },
  ],
}))

async function loadData() {
  if (!props.examId) return
  loading.value = true
  try {
    const params = {}
    if (props.subjectId) params.subject_id = props.subjectId
    if (props.classId) params.class_id = props.classId

    const resp = await getLayerAnalysis(props.examId, params)
    layers.value = resp.data.layers || []
    maxDiffKnowledges.value = resp.data.maxDiffKnowledges || []
  } catch {
    layers.value = []
    maxDiffKnowledges.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.examId, props.subjectId, props.classId], loadData)

onMounted(loadData)

defineExpose({ loading, layers, maxDiffKnowledges, isEmpty, layerColor, masteryColor, diffChartOption })
</script>

<style scoped>
.layer-stat-card {
  text-align: center;
}
.layer-stat-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.layer-stat-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary, #09061B);
}
.layer-stat-unit {
  font-size: 14px;
  font-weight: 400;
  margin-left: 2px;
  color: var(--text-secondary, #A0A0A8);
}
.layer-stat-rate {
  font-size: 12px;
  color: var(--text-secondary, #A0A0A8);
  margin-top: 2px;
}
.diff-chart {
  height: 280px;
}
.kp-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.kp-id {
  font-size: 13px;
  color: var(--text-secondary, #A0A0A8);
  min-width: 60px;
}
</style>
