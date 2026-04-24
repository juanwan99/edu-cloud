<template>
  <el-card>
    <template #header>题目错因聚合</template>
    <div v-if="hasData" class="panel-content">
      <div class="chart-col">
        <v-chart :option="pieOption" style="height: 280px" autoresize />
      </div>
      <div class="table-col">
        <el-table :data="tableData" stripe size="small" max-height="280">
          <el-table-column prop="name" label="题号" width="80" />
          <el-table-column label="得分率" width="90">
            <template #default="{ row }">
              <span :style="{ color: scoreColor(row.score_rate) }">
                {{ (row.score_rate * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="主要错因">
            <template #default="{ row }">
              {{ row.topCause ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column label="错误人次" width="90" align="center">
            <template #default="{ row }">{{ row.errorCount }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>
    <el-empty v-else description="暂无错因数据（需要 AI 阅卷数据支持）" />
  </el-card>
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const props = defineProps<{
  questions?: any[]
}>()

const hasData = computed(() => props.questions && props.questions.length > 0
  && props.questions.some((q: any) => q.error_causes?.length > 0))

const tableData = computed(() => {
  if (!props.questions) return []
  return props.questions.map((q: any) => ({
    name: q.name,
    score_rate: q.score_rate,
    topCause: q.error_causes?.[0]?.cause ?? null,
    errorCount: q.error_causes?.reduce((s: number, c: any) => s + c.count, 0) ?? 0,
  }))
})

const pieOption = computed(() => {
  if (!props.questions) return {}
  const causeTotals: Record<string, number> = {}
  for (const q of props.questions) {
    for (const ec of q.error_causes ?? []) {
      causeTotals[ec.cause] = (causeTotals[ec.cause] ?? 0) + ec.count
    }
  }
  const data = Object.entries(causeTotals).map(([name, value]) => ({ name, value }))
  if (!data.length) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data, label: { show: false },
      emphasis: { label: { show: true, fontSize: 14 } },
    }],
  }
})

function scoreColor(rate: number): string {
  if (rate < 0.5) return 'var(--el-color-danger)'
  if (rate < 0.8) return 'var(--el-color-warning)'
  return 'var(--el-color-success)'
}
</script>

<style scoped>
.panel-content { display: flex; gap: 16px; }
.chart-col { flex: 0 0 320px; }
.table-col { flex: 1; min-width: 0; }
@media (max-width: 900px) {
  .panel-content { flex-direction: column; }
  .chart-col { flex: none; }
}
</style>
