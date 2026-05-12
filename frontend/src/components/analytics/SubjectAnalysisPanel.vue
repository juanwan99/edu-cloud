<template>
  <div class="subject-analysis-panel">
    <div class="panel-grid">
      <div class="panel-card">
        <h3>各科平均得分率</h3>
        <v-chart class="chart-area" :option="subjectRateChartOption" />
      </div>
      <div class="panel-card">
        <h3>科目详情</h3>
        <n-data-table
          :columns="subjectColumns"
          :data="report?.subjects || []"
          :pagination="false"
          :scroll-x="920"
          size="small"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildSubjectRateChart } from '../../composables/useChartOptions'
import { getSubjectColumns } from '../../composables/useTableColumns'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  report: { type: Object, default: null },
})

const subjectRateChartOption = computed(() => buildSubjectRateChart(props.report?.subjects))
const subjectColumns = getSubjectColumns()
</script>

<style scoped>
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

@media (max-width: 760px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
