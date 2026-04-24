<template>
  <v-chart :option="chartOption" :style="{ height: height + 'px' }" autoresize />
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  labels: string[]
  series: { name: string; data: number[]; color?: string; dashed?: boolean }[]
  height?: number
  yAxisName?: string
  inverse?: boolean
}>()

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: props.series.map(s => s.name) },
  grid: { left: 50, right: 20, bottom: 30, top: 40 },
  xAxis: { type: 'category', data: props.labels, boundaryGap: false },
  yAxis: { type: 'value', name: props.yAxisName, inverse: props.inverse ?? false },
  series: props.series.map(s => ({
    name: s.name, type: 'line', data: s.data, smooth: true,
    lineStyle: s.dashed ? { type: 'dashed' } : {},
    itemStyle: s.color ? { color: s.color } : {},
  })),
}))
</script>
