<template>
  <div>
    <template v-if="contextStore.dashboard">
      <n-grid :cols="4" :x-gap="12" style="margin-bottom: 16px">
        <n-gi>
          <n-statistic label="参加人数" :value="stats.count" />
        </n-gi>
        <n-gi>
          <n-statistic label="平均分" :value="stats.avg" />
        </n-gi>
        <n-gi>
          <n-statistic label="最高分" :value="stats.max" />
        </n-gi>
        <n-gi>
          <n-statistic label="中位数" :value="stats.median" />
        </n-gi>
      </n-grid>
      <n-card title="成绩分布">
        <ExamScoreChart :distribution="contextStore.dashboard.score_distribution" />
      </n-card>
    </template>
    <n-empty v-else description="请在左栏选择一次考试" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useContextStore } from '../../stores/context.js'
import ExamScoreChart from './ExamScoreChart.vue'

const contextStore = useContextStore()
const stats = computed(() => contextStore.dashboard?.stats || {})
</script>
