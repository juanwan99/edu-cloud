<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <div v-if="analytics.loading.value" v-loading="true" class="loading-area" />

    <template v-else-if="analytics.summary.value">
      <el-tabs v-model="activeTab" class="report-tabs">
        <el-tab-pane label="基础分析" name="basic">
          <div class="stats-row">
            <StatCard
              v-for="stat in statsCards" :key="stat.label"
              :value="stat.value" :label="stat.label" :format="stat.format"
            />
          </div>

          <el-card class="section-card">
            <template #header>成绩分布</template>
            <v-chart :option="distributionOption" style="height: 300px" autoresize />
          </el-card>

          <ClassRankTable
            v-if="analytics.gradeAggregates.value?.class_rankings?.length"
            :rankings="analytics.gradeAggregates.value.class_rankings"
            :grade-avg="gradeAvg"
          />

          <el-card v-if="analytics.questions.value?.questions?.length" class="section-card">
            <template #header>题目分析</template>
            <el-table :data="analytics.questions.value.questions" stripe>
              <el-table-column prop="question_name" label="题号" width="100" />
              <el-table-column prop="question_type" label="题型" width="100" />
              <el-table-column prop="max_score" label="满分" width="80" align="center" />
              <el-table-column label="均分" width="80" align="center">
                <template #default="{ row }">{{ row.avg_score?.toFixed(1) ?? '-' }}</template>
              </el-table-column>
              <el-table-column label="得分率" width="120">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.score_rate != null ? +(row.score_rate * 100).toFixed(1) : 0"
                    :color="scoreColor(row.score_rate)"
                    :stroke-width="14"
                    :text-inside="true"
                  />
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="AI 深度诊断" name="advanced">
          <div v-if="analytics.advancedLoading.value" v-loading="true" class="loading-area" />
          <template v-else-if="analytics.questionInsights.value">
            <AiDiagnosisCard
              :text="analytics.diagnosis.value?.summary_text"
              :suggestions="analytics.diagnosis.value?.suggestions"
              :weak-questions="analytics.diagnosis.value?.weak_questions"
            />
            <ErrorCausePanel
              :questions="analytics.questionInsights.value?.questions"
              class="section-card"
            />
          </template>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, TitleComponent])

const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const analytics = useAnalytics()
const activeTab = ref('basic')

const statsCards = computed(() => {
  if (!analytics.summary.value?.subjects?.length) return []
  const subjectId = po.value?.analysisParams?.value?.subject_id
  const s = (subjectId && analytics.summary.value.subjects.find((x: any) => x.subject_id === subjectId))
    || analytics.summary.value.subjects[0]
  return [
    { label: '平均分', value: s.avg_score, format: 'score' as const },
    { label: '最高分', value: s.highest, format: 'number' as const },
    { label: '最低分', value: s.lowest, format: 'number' as const },
    { label: '得分率', value: s.score_rate, format: 'percent' as const },
  ]
})

const gradeAvg = computed(() => {
  if (!analytics.summary.value?.subjects?.length) return 0
  const all = analytics.summary.value.subjects
  return all.reduce((sum: number, s: any) => sum + (s.avg_score ?? 0), 0) / all.length
})

const distributionOption = computed(() => {
  const intervals = analytics.distribution.value?.intervals
  if (!intervals?.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: intervals.map((i: any) => i.label) },
    yAxis: { type: 'value', name: '人数' },
    series: [{ type: 'bar', data: intervals.map((i: any) => i.count), itemStyle: { color: '#409eff' } }],
  }
})

function scoreColor(rate: number | null): string {
  if (rate == null) return '#909399'
  if (rate < 0.5) return '#f56c6c'
  if (rate < 0.8) return '#e6a23c'
  return '#67c23a'
}

// ORC-006: 进阶 Tab 懒加载
watch(activeTab, (tab) => {
  if (tab === 'advanced') {
    const params = po.value?.analysisParams?.value
    if (params?.exam_id) {
      analytics.loadAdvancedData({
        exam_id: params.exam_id,
        subject_id: params.subject_id,
        class_id: params.class_id,
      })
    }
  }
})

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  activeTab.value = 'basic'
  await analytics.loadBasicData({ exam_id: params.exam_id, subject_id: params.subject_id })
}, { deep: true })
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.stats-row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.stats-row > * { flex: 1; min-width: 150px; }
.section-card { margin-bottom: 16px; }
.report-tabs { margin-top: 8px; }
</style>
