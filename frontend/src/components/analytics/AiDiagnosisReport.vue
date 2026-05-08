<template>
  <div class="ai-diagnosis">
    <n-spin :show="loading">
      <template v-if="error">
        <n-alert type="error" :bordered="false">{{ error }}</n-alert>
        <n-button style="margin-top: 12px" @click="generate">重试</n-button>
      </template>

      <template v-else-if="report">
        <n-alert v-if="report.data_limits && report.data_limits.length" type="warning" :bordered="false" style="margin-bottom: 16px">
          <span v-for="(dl, i) in report.data_limits" :key="i">{{ dl.text }}<br v-if="i < report.data_limits.length - 1" /></span>
        </n-alert>

        <n-card title="诊断摘要" size="small" style="margin-bottom: 16px">
          <p>{{ report.summary?.text }}</p>
          <n-space v-if="report.summary?.evidence_fact_ids?.length" :size="4" style="margin-top: 8px">
            <n-tag v-for="fid in report.summary.evidence_fact_ids" :key="fid" size="tiny" :bordered="false">{{ fid }}</n-tag>
          </n-space>
        </n-card>

        <n-card v-if="report.findings && report.findings.length" title="关键发现" size="small" style="margin-bottom: 16px">
          <n-list :bordered="false">
            <n-list-item v-for="f in report.findings" :key="f.id">
              <n-thing>
                <template #header>
                  <n-tag size="small" :type="confidenceType(f.confidence)">{{ f.confidence }}</n-tag>
                  {{ f.text }}
                </template>
                <template #description>
                  <n-space :size="4">
                    <n-tag v-for="fid in f.evidence_fact_ids" :key="fid" size="tiny" :bordered="false">{{ fid }}</n-tag>
                  </n-space>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
        </n-card>

        <n-card v-if="report.risk_alerts && report.risk_alerts.length" title="风险预警" size="small" style="margin-bottom: 16px">
          <n-list :bordered="false">
            <n-list-item v-for="(ra, i) in report.risk_alerts" :key="i">
              {{ ra.text }}
            </n-list-item>
          </n-list>
        </n-card>

        <n-card v-if="report.teaching_actions && report.teaching_actions.length" title="教学建议" size="small" style="margin-bottom: 16px">
          <n-list :bordered="false">
            <n-list-item v-for="(a, i) in report.teaching_actions" :key="i">
              <n-thing>
                <template #header>
                  <n-tag size="small" :type="priorityType(a.priority)">{{ a.priority }}</n-tag>
                  {{ a.text }}
                </template>
                <template v-if="a.target" #description>
                  目标：{{ a.target }}
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
        </n-card>

        <n-card v-if="report.student_followups && report.student_followups.length" title="学生关注" size="small">
          <n-list :bordered="false">
            <n-list-item v-for="(sf, i) in report.student_followups" :key="i">
              <n-tag v-if="sf.layer" size="small" :bordered="false" style="margin-right: 8px">{{ sf.layer }}</n-tag>
              {{ sf.text }}
            </n-list-item>
          </n-list>
        </n-card>

        <div style="margin-top: 16px; text-align: right">
          <n-button size="small" :loading="loading" @click="generate(true)">重新生成</n-button>
        </div>
      </template>

      <template v-else-if="!loading">
        <n-empty description="选择考试后可生成 AI 分析报告">
          <template #extra>
            <n-button type="primary" :disabled="!examId" @click="generate">生成 AI 报告</n-button>
          </template>
        </n-empty>
      </template>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { generateAiDiagnosis, getAiDiagnosis } from '../../api/analytics'

const props = defineProps({
  examId: { type: String, default: '' },
  subjectId: { type: String, default: null },
  classId: { type: String, default: null },
})

const loading = ref(false)
const error = ref('')
const report = ref(null)

function confidenceType(c) {
  if (c === 'high') return 'success'
  if (c === 'low') return 'warning'
  return 'info'
}

function priorityType(p) {
  if (p === 'high') return 'error'
  if (p === 'medium') return 'warning'
  return 'info'
}

async function tryLoadCached() {
  if (!props.examId) return
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (props.subjectId) params.subject_id = props.subjectId
    if (props.classId) params.class_id = props.classId
    const res = await getAiDiagnosis(props.examId, params)
    if (res.data && res.data.status !== 'not_found') {
      report.value = res.data
    }
  } catch {
    // no cached report — normal
  } finally {
    loading.value = false
  }
}

async function generate(forceRefresh = false) {
  if (!props.examId) return
  loading.value = true
  error.value = ''
  report.value = null
  try {
    const params = { force_refresh: !!forceRefresh }
    if (props.subjectId) params.subject_id = props.subjectId
    if (props.classId) params.class_id = props.classId
    const res = await generateAiDiagnosis(props.examId, params)
    report.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.detail || '生成超时，请重试'
  } finally {
    loading.value = false
  }
}

watch(() => props.examId, () => {
  report.value = null
  error.value = ''
  tryLoadCached()
}, { immediate: true })
</script>
