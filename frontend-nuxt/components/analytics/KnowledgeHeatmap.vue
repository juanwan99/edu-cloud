<template>
  <el-card>
    <template #header>知识点掌握热力图</template>
    <v-chart v-if="hasData" :option="heatOption" style="height: 350px" autoresize />
    <el-empty v-else description="暂无知识点数据" />
  </el-card>
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

const props = defineProps<{
  knowledgePoints: string[]
  classes: { class_id: string; name: string; mastery: { kp_id: string; rate: number }[] }[]
}>()

const hasData = computed(() => props.knowledgePoints?.length > 0 && props.classes?.length > 0)

const heatOption = computed(() => {
  const classNames = props.classes.map(c => c.name)
  const kpNames = props.knowledgePoints
  const data: [number, number, number][] = []
  for (let ci = 0; ci < props.classes.length; ci++) {
    const cls = props.classes[ci]
    for (let ki = 0; ki < kpNames.length; ki++) {
      const m = cls.mastery?.find(m => m.kp_id === kpNames[ki])
      data.push([ki, ci, m ? +(m.rate * 100).toFixed(1) : 0])
    }
  }
  return {
    tooltip: {
      formatter: (p: any) => `${classNames[p.value[1]]} / ${kpNames[p.value[0]]}: ${p.value[2]}%`,
    },
    grid: { left: 100, right: 60, bottom: 80, top: 10 },
    xAxis: { type: 'category', data: kpNames, axisLabel: { rotate: 45, fontSize: 11 } },
    yAxis: { type: 'category', data: classNames },
    visualMap: {
      min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
      inRange: { color: ['#f56c6c', '#e6a23c', '#67c23a', '#0a7e07'] },
    },
    series: [{
      type: 'heatmap', data,
      label: { show: true, formatter: (p: any) => p.value[2] + '%', fontSize: 11 },
      itemStyle: { borderWidth: 1, borderColor: '#fff' },
    }],
  }
})
</script>
