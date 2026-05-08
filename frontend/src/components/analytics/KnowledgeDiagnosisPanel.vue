<template>
  <n-spin :show="loading">
    <n-empty v-if="!loading && isEmpty" description="暂无知识点诊断数据" />
    <n-grid v-else :cols="3" :x-gap="16" :y-gap="16">
      <!-- 薄弱知识点 -->
      <n-gi>
        <n-card title="薄弱知识点" size="small">
          <n-space vertical :size="12">
            <div v-for="item in diagnosis.worstKnowledges" :key="item.concept_id" class="kd-item">
              <div class="kd-label">{{ item.name }}</div>
              <n-progress
                type="line"
                :percentage="Math.round(item.rate * 100)"
                :color="rateColor(item.rate)"
                :rail-color="railColor"
                :show-indicator="true"
              />
            </div>
          </n-space>
        </n-card>
      </n-gi>

      <!-- 影响面最广 -->
      <n-gi>
        <n-card title="影响面最广" size="small">
          <n-space vertical :size="12">
            <div v-for="item in diagnosis.unmasterMaxCntKnowledges" :key="item.concept_id" class="kd-item">
              <div class="kd-label">
                {{ item.name }}
                <n-tag size="small" :bordered="false" type="error">{{ item.count }}人</n-tag>
              </div>
            </div>
          </n-space>
        </n-card>
      </n-gi>

      <!-- 分化最严重 -->
      <n-gi>
        <n-card title="分化最严重" size="small">
          <n-space vertical :size="12">
            <div v-for="item in diagnosis.maxScoreDiffKnowledges" :key="item.concept_id" class="kd-item">
              <div class="kd-label">
                {{ item.name }}
                <n-tag size="small" :bordered="false" type="warning">差异 {{ item.diff.toFixed(2) }}</n-tag>
              </div>
            </div>
          </n-space>
        </n-card>
      </n-gi>
    </n-grid>
  </n-spin>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getClassDiagnosis, getClassErrorPatterns, getQuestionInsights } from '../../api/analytics'

const props = defineProps({
  examId: { type: String, required: true },
  subjectId: { type: String, default: undefined },
  classId: { type: String, default: undefined },
})

const loading = ref(false)
const diagnosis = ref({
  worstKnowledges: [],
  unmasterMaxCntKnowledges: [],
  maxScoreDiffKnowledges: [],
})

const isEmpty = computed(() =>
  diagnosis.value.worstKnowledges.length === 0
  && diagnosis.value.unmasterMaxCntKnowledges.length === 0
  && diagnosis.value.maxScoreDiffKnowledges.length === 0,
)

const railColor = 'rgba(255,255,255,0.08)'

function rateColor(rate) {
  if (rate < 0.4) return '#dc2626'
  if (rate < 0.7) return '#ED9A51'
  return '#22C55E'
}

async function loadData() {
  if (!props.examId) return
  loading.value = true
  try {
    const params = {}
    if (props.subjectId) params.subject_id = props.subjectId
    if (props.classId) params.class_id = props.classId

    const [diagResp] = await Promise.all([
      getClassDiagnosis(props.examId, params),
      getClassErrorPatterns(props.examId, params),
      getQuestionInsights(props.examId),
    ])

    diagnosis.value = {
      worstKnowledges: diagResp.data.worstKnowledges || [],
      unmasterMaxCntKnowledges: diagResp.data.unmasterMaxCntKnowledges || [],
      maxScoreDiffKnowledges: diagResp.data.maxScoreDiffKnowledges || [],
    }
  } catch {
    diagnosis.value = { worstKnowledges: [], unmasterMaxCntKnowledges: [], maxScoreDiffKnowledges: [] }
  } finally {
    loading.value = false
  }
}

watch(() => [props.examId, props.subjectId, props.classId], loadData)

onMounted(loadData)

defineExpose({ loading, diagnosis, isEmpty, rateColor })
</script>

<style scoped>
.kd-item {
  padding: 4px 0;
}
.kd-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--text-secondary, #A0A0A8);
}
</style>
