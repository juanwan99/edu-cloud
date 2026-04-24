<template>
  <v-chart :option="chartOption" :style="{ height: height + 'px' }" autoresize />
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart as ERadarChart } from 'echarts/charts'
import { TooltipComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, ERadarChart, TooltipComponent, TitleComponent])

const props = defineProps<{
  indicators: { name: string; max?: number }[]
  series: { name: string; values: number[] }[]
  height?: number
}>()

const chartOption = computed(() => ({
  tooltip: {},
  radar: {
    indicator: props.indicators.map(i => ({ name: i.name, max: i.max ?? 1 })),
    shape: 'polygon',
  },
  series: [{
    type: 'radar',
    data: props.series.map(s => ({
      name: s.name,
      value: s.values,
      areaStyle: { opacity: 0.15 },
    })),
  }],
}))
</script>
