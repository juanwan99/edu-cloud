<template>
  <div class="overview-panel">
    <div class="card-grid">
      <div
        v-for="item in overviewCards"
        :key="item.label"
        class="stat-card"
        :style="{ '--accent': item.color }"
      >
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </div>
    </div>
    <div class="panel-grid">
      <div class="panel-card">
        <h3>分数分布</h3>
        <v-chart class="chart-area" :option="segmentChartOption" />
      </div>
      <div class="panel-card">
        <h3>年级排名趋势</h3>
        <v-chart class="chart-area" :option="rankTrendChartOption" />
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
  const ov = props.report?.overview || {}
  const students = props.report?.students || []
  const fullScore = Number(ov.total_full_score)
  const fullScoreCount = ov.full_score_count ?? (
    Number.isFinite(fullScore)
      ? students.filter(row => Math.abs(Number(row.total_score) - fullScore) < 0.01).length
      : 0
  )
  return [
    { label: '平均分', value: fmt(ov.avg_score), color: '#644CF0' },
    { label: '及格率', value: pct(ov.pass_rate), color: '#22C55E' },
    { label: '优秀率', value: pct(ov.excellent_rate), color: '#F4DA4C' },
    { label: '最高分', value: fmt(ov.max_score), color: '#22C55E' },
    { label: '最低分', value: fmt(ov.min_score), color: '#ED9A51' },
    { label: '满分人数', value: fullScoreCount, color: '#8B7AF5' },
  ]
})

const segmentChartOption = computed(() => buildSegmentChart(props.report?.distribution))
const rankTrendChartOption = computed(() => buildRankTrendChart(props.report?.overview, props.report?.exam?.name))
</script>

<style scoped>
.card-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface-color, #fff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  border-left: 3px solid var(--accent, #644CF0);
}

.stat-label {
  display: block;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: 16px;
}

.panel-card {
  padding: 20px;
  border-radius: 12px;
  background: var(--surface-color, #fff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.panel-card h3 {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.chart-area {
  height: 320px;
}

@media (max-width: 960px) {
  .card-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 760px) {
  .card-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
