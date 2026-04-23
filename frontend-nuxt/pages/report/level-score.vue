<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <el-card class="config-card">
      <template #header>等级配置</template>
      <div class="preset-buttons">
        <el-button size="small" @click="applyPreset('guangdong')">广东新高考</el-button>
        <el-button size="small" @click="applyPreset('zhejiang')">浙江</el-button>
      </div>
      <el-table :data="levels" border size="small">
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column label="百分位区间" width="160">
          <template #default="{ row }">{{ row.start_pct }}% - {{ row.end_pct }}%</template>
        </el-table-column>
        <el-table-column label="赋分区间" width="160">
          <template #default="{ row }">{{ row.score_min }} - {{ row.score_max }}</template>
        </el-table-column>
      </el-table>
      <el-button type="primary" :disabled="!canConvert" @click="convert" style="margin-top: 12px">
        开始赋分
      </el-button>
    </el-card>

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="result">
      <div class="dist-row">
        <el-card class="dist-card">
          <template #header>赋分前分布</template>
          <v-chart :option="beforeOption" style="height: 250px" autoresize />
        </el-card>
        <el-card class="dist-card">
          <template #header>赋分后分布</template>
          <v-chart :option="afterOption" style="height: 250px" autoresize />
        </el-card>
      </div>

      <el-card class="table-card">
        <template #header>
          <div class="table-header">
            <span>学生明细（共 {{ result.total_students }} 人）</span>
            <el-button size="small" @click="exportStudents">导出 Excel</el-button>
          </div>
        </template>
        <el-table :data="result.students" stripe max-height="500">
          <el-table-column prop="rank" label="排名" width="80" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="raw_score" label="原始分" width="100" />
          <el-table-column prop="level" label="等级" width="80" />
          <el-table-column prop="assigned_score" label="赋分" width="100" />
        </el-table>
      </el-card>
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
const api = useApi()

const loading = ref(false)
const result = ref<any>(null)

const PRESETS = {
  guangdong: [
    { level: 'A', start_pct: 0, end_pct: 17, score_min: 83, score_max: 100 },
    { level: 'B', start_pct: 17, end_pct: 50, score_min: 71, score_max: 82 },
    { level: 'C', start_pct: 50, end_pct: 83, score_min: 59, score_max: 70 },
    { level: 'D', start_pct: 83, end_pct: 98, score_min: 41, score_max: 58 },
    { level: 'E', start_pct: 98, end_pct: 100, score_min: 30, score_max: 40 },
  ],
  zhejiang: [
    { level: 'A', start_pct: 0, end_pct: 15, score_min: 91, score_max: 100 },
    { level: 'B', start_pct: 15, end_pct: 40, score_min: 76, score_max: 90 },
    { level: 'C', start_pct: 40, end_pct: 70, score_min: 61, score_max: 75 },
    { level: 'D', start_pct: 70, end_pct: 95, score_min: 46, score_max: 60 },
    { level: 'E', start_pct: 95, end_pct: 100, score_min: 40, score_max: 45 },
  ],
}

const levels = ref([...PRESETS.guangdong])

function applyPreset(name: 'guangdong' | 'zhejiang') {
  levels.value = [...PRESETS[name]]
}

const canConvert = computed(() => po.value?.hasSelection?.value)

function buildDistOption(dist: any, color: string) {
  if (!dist?.segments) return {}
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dist.segments },
    yAxis: { type: 'value', name: '人数' },
    series: [{ type: 'bar', data: dist.counts, itemStyle: { color } }],
  }
}

const beforeOption = computed(() => buildDistOption(result.value?.distribution_before, '#409eff'))
const afterOption = computed(() => buildDistOption(result.value?.distribution_after, '#67c23a'))

async function convert() {
  const params = po.value?.analysisParams?.value
  if (!params?.exam_id) return
  loading.value = true
  try {
    result.value = await api.convertLevelScore({
      exam_id: params.exam_id,
      subject_id: params.subject_id,
      class_id: params.class_id,
      levels: levels.value,
    })
  } finally {
    loading.value = false
  }
}

function exportStudents() {
  if (!result.value?.students?.length) return
  const headers = ['排名', '姓名', '原始分', '等级', '赋分']
  const rows = result.value.students.map((s: any) =>
    [s.rank, s.name, s.raw_score, s.level, s.assigned_score]
  )
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '等级赋分.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.config-card, .table-card { margin-bottom: 16px; }
.preset-buttons { margin-bottom: 12px; }
.dist-row { display: flex; gap: 16px; margin-bottom: 16px; }
.dist-card { flex: 1; }
.table-header { display: flex; justify-content: space-between; align-items: center; }
</style>
