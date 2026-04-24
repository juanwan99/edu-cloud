<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="aggregates">
      <el-tabs v-model="activeTab" class="report-tabs">
        <el-tab-pane label="基础分析" name="basic">
          <el-card class="section-card">
            <template #header>班级均分对比</template>
            <v-chart :option="contrastOption" style="height: 350px" autoresize />
          </el-card>

          <ClassRankTable
            :rankings="aggregates.class_rankings ?? []"
            :grade-avg="gradeAvg"
          />

          <el-card v-if="boxplotData" class="section-card">
            <template #header>分数箱线图</template>
            <v-chart :option="boxplotOption" style="height: 300px" autoresize />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="AI 深度诊断" name="advanced">
          <div v-if="advancedLoading" v-loading="true" class="loading-area" />
          <template v-else>
            <KnowledgeHeatmap
              v-if="knowledgeData"
              :knowledge-points="knowledgeData.knowledge_points"
              :classes="knowledgeData.classes"
              class="section-card"
            />

            <el-card v-if="errorPatterns" class="section-card">
              <template #header>班级错误模式对比</template>
              <el-table :data="errorPatterns.classes" stripe size="small">
                <el-table-column prop="name" label="班级" width="120" />
                <el-table-column v-for="et in errorPatterns.error_types" :key="et" :label="et" min-width="100" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.distribution[et] > 0.4 ? 'var(--el-color-danger)' : '' }">
                      {{ row.distribution[et] != null ? (row.distribution[et] * 100).toFixed(1) + '%' : '-' }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <AiDiagnosisCard
              :text="diagnosis?.summary_text"
              :suggestions="diagnosis?.suggestions"
              :weak-questions="diagnosis?.weak_questions"
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
import { BarChart, BoxplotChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DatasetComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, BoxplotChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent])

const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const api = useApi()

const loading = ref(false)
const advancedLoading = ref(false)
const activeTab = ref('basic')
const aggregates = ref<any>(null)
const boxplotData = ref<any>(null)
const knowledgeData = ref<any>(null)
const errorPatterns = ref<any>(null)
const diagnosis = ref<any>(null)

const gradeAvg = computed(() => {
  const ranks = aggregates.value?.class_rankings ?? []
  if (!ranks.length) return 0
  return ranks.reduce((s: number, c: any) => s + (c.avg_score ?? 0), 0) / ranks.length
})

const contrastOption = computed(() => {
  const data = aggregates.value?.class_rankings ?? []
  if (!data.length) return {}
  const names = data.map((c: any) => c.class_name)
  const avg = gradeAvg.value
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['均分', '年级均分'] },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value' },
    series: [
      { name: '均分', type: 'bar', data: data.map((c: any) => c.avg_score) },
      { name: '年级均分', type: 'line', data: names.map(() => avg), lineStyle: { type: 'dashed' }, symbol: 'none' },
    ],
  }
})

const boxplotOption = computed(() => {
  if (!boxplotData.value?.classes?.length) return {}
  const classes = boxplotData.value.classes
  return {
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: classes.map((c: any) => c.name) },
    yAxis: { type: 'value', name: '分数' },
    series: [{
      type: 'boxplot',
      data: classes.map((c: any) => [c.min, c.p25, c.median, c.p75, c.max]),
    }],
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'advanced' && !knowledgeData.value) {
    const params = po.value?.analysisParams?.value
    if (!params?.exam_id) return
    advancedLoading.value = true
    try {
      const [kd, ep, diag] = await Promise.all([
        api.getClassKnowledge(params.exam_id, params.subject_id),
        api.getClassErrorPatterns(params.exam_id, params.subject_id),
        api.getExamDiagnosis(params.exam_id, params.subject_id, params.class_id),
      ])
      knowledgeData.value = kd
      errorPatterns.value = ep
      diagnosis.value = diag
    } finally {
      advancedLoading.value = false
    }
  }
})

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  loading.value = true
  activeTab.value = 'basic'
  knowledgeData.value = null
  errorPatterns.value = null
  diagnosis.value = null
  try {
    const [agg, bp] = await Promise.all([
      api.getExamGradeAggregates(params.exam_id, { subject_id: params.subject_id }),
      api.getClassBoxplot(params.exam_id, params.subject_id),
    ])
    aggregates.value = agg
    boxplotData.value = bp
  } finally {
    loading.value = false
  }
}, { deep: true })
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.section-card { margin-bottom: 16px; }
.report-tabs { margin-top: 8px; }
</style>
