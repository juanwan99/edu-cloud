<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="rankings">
      <el-tabs v-model="activeTab" class="report-tabs">
        <el-tab-pane label="基础分析" name="basic">
          <StudentRankTable :students="rankings.students" @expand="onStudentExpand">
            <template #expand="{ student }">
              <div class="expand-content" v-if="studentTrend[student.student_id]">
                <TrendLine
                  :labels="studentTrend[student.student_id].labels"
                  :series="studentTrend[student.student_id].series"
                  :height="200"
                  y-axis-name="分数"
                />
              </div>
              <div v-else v-loading="true" class="expand-loading" />
            </template>
          </StudentRankTable>
        </el-tab-pane>

        <el-tab-pane label="AI 深度诊断" name="advanced">
          <div v-if="advancedLoading" v-loading="true" class="loading-area" />
          <template v-else>
            <CriticalStudents
              :near-pass="criticalData?.near_pass ?? []"
              :near-excellent="criticalData?.near_excellent ?? []"
              :threshold="3"
            />
          </template>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const api = useApi()

const loading = ref(false)
const advancedLoading = ref(false)
const activeTab = ref('basic')
const rankings = ref<any>(null)
const criticalData = ref<any>(null)
const studentTrend = ref<Record<string, any>>({})

async function onStudentExpand(student: any) {
  if (studentTrend.value[student.student_id]) return
  try {
    const trend = await api.getStudentTrend(student.student_id)
    const snapshots = trend?.snapshots ?? []
    if (snapshots.length) {
      studentTrend.value[student.student_id] = {
        labels: snapshots.map((s: any) => s.exam_name ?? s.exam_date ?? ''),
        series: [
          { name: '得分', data: snapshots.map((s: any) => s.total_score ?? 0), color: '#409eff' },
        ],
      }
    }
  } catch {
    studentTrend.value[student.student_id] = { labels: [], series: [] }
  }
}

watch(activeTab, async (tab) => {
  if (tab === 'advanced' && !criticalData.value) {
    const params = po.value?.analysisParams?.value
    if (!params?.exam_id) return
    advancedLoading.value = true
    try {
      criticalData.value = await api.getCriticalStudents(
        params.exam_id, params.subject_id, params.class_id
      )
    } finally {
      advancedLoading.value = false
    }
  }
})

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  loading.value = true
  activeTab.value = 'basic'
  criticalData.value = null
  studentTrend.value = {}
  try {
    rankings.value = await api.getStudentRankings(
      params.exam_id, params.subject_id, params.class_id
    )
  } finally {
    loading.value = false
  }
}, { deep: true })
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.report-tabs { margin-top: 8px; }
.expand-content { padding: 12px 24px; }
.expand-loading { height: 100px; }
</style>
