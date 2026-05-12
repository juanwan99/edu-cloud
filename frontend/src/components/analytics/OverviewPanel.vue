<template>
  <div class="overview-panel">
    <div class="overview-card-grid">
      <div v-for="item in overviewCards" :key="item.label" class="stat-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
    <div class="panel-grid">
      <div class="report-panel">
        <h3>分数分布</h3>
        <v-chart class="chart-height-xl" :option="segmentChartOption" />
      </div>
      <div class="report-panel">
        <h3>年级排名趋势</h3>
        <v-chart class="chart-height-xl" :option="rankTrendChartOption" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildSegmentChart, buildRankTrendChart } from '../../composables/useChartOptions'
import { fmt, pct } from '../../composables/useTableColumns'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  report: { type: Object, default: null },
})

const overviewCards = computed(() => {
  const overview = props.report?.overview || {}
  const students = props.report?.students || []
  const fullScore = Number(overview.total_full_score)
  const fullScoreCount = overview.full_score_count ?? (
    Number.isFinite(fullScore)
      ? students.filter(row => Math.abs(Number(row.total_score) - fullScore) < 0.01).length
      : 0
  )
  return [
    { label: '平均分', value: fmt(overview.avg_score) },
    { label: '及格率', value: pct(overview.pass_rate) },
    { label: '优秀率', value: pct(overview.excellent_rate) },
    { label: '满分人数', value: fullScoreCount },
  ]
})

const segmentChartOption = computed(() => buildSegmentChart(props.report?.distribution))
const rankTrendChartOption = computed(() => buildRankTrendChart(props.report?.overview, props.report?.exam?.name))
</script>

<style scoped>
.overview-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-3, 12px);
  margin-bottom: var(--space-4, 16px);
}

.stat-card {
  padding: var(--space-3, 12px);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  background: var(--surface-color, #fff);
}

.stat-card span {
  display: block;
  color: var(--text-secondary, #6b7280);
  font-size: var(--fs-sm, 14px);
}

.stat-card strong {
  display: block;
  margin-top: var(--space-1, 4px);
  font-size: var(--fs-xl, 24px);
  font-weight: var(--fw-semibold, 600);
}

.panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: var(--space-4, 16px);
}

.report-panel {
  padding-top: var(--space-3, 12px);
}

.report-panel h3 {
  margin: 0 0 var(--space-3, 12px);
  font-size: var(--fs-md, 16px);
  font-weight: var(--fw-semibold, 600);
}

.chart-height-xl {
  height: 320px;
}

@media (max-width: 760px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
