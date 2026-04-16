<template>
  <div class="analytics-report">
    <n-card title="分析报告">
      <n-space vertical :size="16">
        <n-space>
          <n-select
            v-model:value="selectedExamIds"
            :options="examOptions"
            multiple
            placeholder="选择考试（可多选）"
            style="min-width: 300px"
          />
          <n-select
            v-model:value="selectedMetrics"
            :options="metricOptions"
            multiple
            placeholder="选择指标"
            style="min-width: 200px"
          />
          <n-select
            v-model:value="exportSubjectId"
            :options="subjectOptions"
            placeholder="选择导出科目"
            style="min-width: 180px"
            clearable
          />
          <n-button type="primary" @click="runQuery" :loading="loading">
            生成分析
          </n-button>
          <n-button
            @click="() => handleDownload('pdf')"
            :loading="exporting"
            :disabled="!canExport"
          >
            导出 PDF
          </n-button>
          <n-button
            @click="() => handleDownload('xlsx')"
            :loading="exporting"
            :disabled="!canExport"
          >
            导出 Excel
          </n-button>
        </n-space>

        <template v-if="reportData">
          <n-tabs type="line">
            <n-tab-pane v-if="reportData.metrics.summary" name="summary" tab="总览">
              <n-descriptions bordered :column="3">
                <n-descriptions-item label="参考人数">
                  {{ reportData.metrics.summary.total_students }}
                </n-descriptions-item>
                <n-descriptions-item
                  v-for="subj in reportData.metrics.summary.subjects || []"
                  :key="subj.subject_id"
                  :label="subj.subject_name + ' 均分'"
                >
                  {{ subj.avg_score }}
                </n-descriptions-item>
              </n-descriptions>
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.segments" name="segments" tab="分数段分布">
              <v-chart :option="segmentChartOption" style="height: 400px" />
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.ranking" name="ranking" tab="班级排名">
              <n-data-table
                :columns="rankingColumns"
                :data="reportData.metrics.ranking.class_rankings || []"
                :pagination="false"
              />
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.top_bottom" name="top_bottom" tab="尖子生/临界生">
              <n-space vertical>
                <n-card title="前 10%">
                  <n-data-table
                    :columns="topColumns"
                    :data="reportData.metrics.top_bottom.top_10pct"
                    :pagination="false"
                    size="small"
                  />
                </n-card>
                <n-card title="后 10%">
                  <n-data-table
                    :columns="topColumns"
                    :data="reportData.metrics.top_bottom.bottom_10pct"
                    :pagination="false"
                    size="small"
                  />
                </n-card>
              </n-space>
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { queryReport, exportGradeReport, downloadBlob, getExamSummary } from '../api/analytics'
import client from '../api/client'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const message = useMessage()
const loading = ref(false)
const exporting = ref(false)
const reportData = ref(null)
const selectedExamIds = ref([])
const selectedMetrics = ref(['summary', 'segments', 'ranking'])
const examOptions = ref([])
const subjectOptions = ref([])
const exportSubjectId = ref(null)

const canExport = computed(
  () => selectedExamIds.value.length === 1 && !!exportSubjectId.value && !exporting.value,
)

const metricOptions = [
  { label: '考试总览', value: 'summary' },
  { label: '分数段分布', value: 'segments' },
  { label: '班级排名', value: 'ranking' },
  { label: '题目分析', value: 'questions' },
  { label: '尖子生/临界生', value: 'top_bottom' },
]

const rankingColumns = [
  { title: '排名', key: 'rank' },
  { title: '班级', key: 'class_name' },
  { title: '均分', key: 'avg_score' },
  { title: '人数', key: 'student_count' },
]

const topColumns = [
  { title: '学生', key: 'student_id' },
  { title: '总分', key: 'score' },
]

const segmentChartOption = computed(() => {
  const segments = reportData.value?.metrics?.segments?.intervals || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: segments.map(s => s.label) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: segments.map(s => s.count),
      itemStyle: { color: '#63e2b7' },
    }],
  }
})

onMounted(async () => {
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch { /* ignore */ }
})

async function runQuery() {
  if (!selectedExamIds.value.length) {
    message.warning('请至少选择一次考试')
    return
  }
  loading.value = true
  try {
    const resp = await queryReport({
      exam_ids: selectedExamIds.value,
      metrics: selectedMetrics.value,
    })
    reportData.value = resp.data
  } catch (e) {
    message.error(e.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

async function loadSubjects(examId) {
  if (!examId) { subjectOptions.value = []; return }
  try {
    const { data } = await getExamSummary(examId)
    subjectOptions.value = (data.subjects || []).map(s => ({
      label: s.subject_name, value: s.subject_id,
    }))
  } catch { subjectOptions.value = [] }
}

watch(selectedExamIds, async (ids) => {
  exportSubjectId.value = null
  if (ids.length === 1) await loadSubjects(ids[0])
  else subjectOptions.value = []
})

async function handleDownload(format) {
  if (!canExport.value) {
    message.warning('请选择 1 次考试 + 1 个科目后再导出')
    return
  }
  exporting.value = true
  try {
    const resp = await exportGradeReport(
      selectedExamIds.value[0], exportSubjectId.value, format,
    )
    downloadBlob(resp, `年级报告.${format}`)
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}
</script>
