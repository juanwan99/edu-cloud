<template>
  <div class="subject-analysis-panel">
    <div class="panel-grid">
      <div class="report-panel">
        <h3>各科平均得分率</h3>
        <v-chart class="chart-height-xl" :option="subjectRateChartOption" />
      </div>
      <div class="report-panel">
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
