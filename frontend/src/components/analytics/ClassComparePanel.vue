<template>
  <div class="class-compare-panel">
    <div class="stack-layout">
      <div class="panel-card">
        <h3>班级平均分对比</h3>
        <v-chart class="chart-area" :option="classCompareChartOption" />
      </div>
      <div class="panel-card">
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
</style>
