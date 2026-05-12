<template>
  <div class="class-compare-panel">
    <div class="stack-layout">
      <div class="report-panel">
        <h3>班级平均分对比</h3>
        <v-chart class="chart-height-xl" :option="classCompareChartOption" />
      </div>
      <div class="report-panel">
        <h3>班级详细数据</h3>
        <n-data-table
          :columns="classColumns"
          :data="report?.classes || []"
          :pagination="{ pageSize: 30 }"
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
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildClassCompareChart } from '../../composables/useChartOptions'
import { getClassColumns } from '../../composables/useTableColumns'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  report: { type: Object, default: null },
})

const classCompareChartOption = computed(() => buildClassCompareChart(props.report?.classes))
const classColumns = getClassColumns()
</script>

<style scoped>
.stack-layout {
  display: grid;
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
</style>
