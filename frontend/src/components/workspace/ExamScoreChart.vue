<template>
  <v-chart class="chart-height-lg" :option="chartOption" autoresize />
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  distribution: { type: Array, default: () => [] },
})

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: props.distribution.map(d => d.range),
  },
  yAxis: { type: 'value', name: '人数' },
  series: [
    {
      type: 'bar',
      data: props.distribution.map(d => d.count),
      itemStyle: { color: '#63e2b7' },
    },
  ],
}))
</script>
