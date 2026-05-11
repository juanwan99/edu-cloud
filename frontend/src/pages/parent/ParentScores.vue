<template>
  <PullRefresh :loading="refreshing" :last-update="lastUpdate" @refresh="loadData">
    <ParentSkeleton v-if="loading && !hasLoaded" :rows="3" />

    <template v-else-if="currentChild">
      <n-radio-group v-model:value="segment" :options="segments" size="small" class="segment-control" />

      <!-- Exam View -->
      <template v-if="segment === 'exam'">
        <div class="p-card" v-if="latestExam">
          <div class="p-card__header">
            <span class="p-card__title">{{ latestExam.exam_name || '最近考试' }}</span>
            <span class="p-card__source">{{ latestExam.exam_date || '' }}</span>
          </div>
          <div class="score-summary">
            <div class="score-block score-block--accent">
              <NumberRoll :value="latestExam.total_score" size="var(--p-fs-hero)" />
              <div class="score-block__label">总分</div>
            </div>
            <div class="score-block" v-if="latestExam.class_rank">
              <div class="score-block__value">{{ latestExam.class_rank }}<span class="score-block__total">/{{ latestExam.class_total || '?' }}</span></div>
              <div class="score-block__label">班名次</div>
            </div>
            <div class="score-block" v-if="latestExam.grade_rank">
              <div class="score-block__value">{{ latestExam.grade_rank }}<span class="score-block__total">/{{ latestExam.grade_total || '?' }}</span></div>
              <div class="score-block__label">年名次</div>
            </div>
          </div>
        </div>

        <!-- Subject scores for latest exam -->
        <div class="p-card" v-if="latestSubjects.length">
          <div class="p-card__header">
            <span class="p-card__title">各科成绩</span>
          </div>
          <div v-for="s in latestSubjects" :key="s.subject_code" class="subject-row">
            <div class="subject-row__name">{{ s.subject_name || s.subject_code }}</div>
            <div class="subject-row__bar-wrap">
              <div class="subject-row__bar" :style="{ width: barWidth(s.score, s.max_score) }">
                <span class="subject-row__score">{{ s.score }}</span>
              </div>
              <div v-if="s.class_avg" class="subject-row__avg" :style="{ left: barWidth(s.class_avg, s.max_score) }" />
            </div>
            <AlertTriangle v-if="s.class_avg && s.score < s.class_avg" :size="14" class="subject-row__warn" />
          </div>
        </div>

        <!-- Historical exams -->
        <div class="p-card" v-if="exams.length > 1">
          <div class="p-card__header">
            <span class="p-card__title">历次考试</span>
          </div>
          <n-collapse>
            <n-collapse-item v-for="exam in exams.slice(1)" :key="exam.id || exam.exam_name" :title="exam.exam_name" :name="exam.id || exam.exam_name">
              <template #header-extra>
                <span class="exam-total">{{ exam.total_score ?? '-' }}分</span>
              </template>
              <div v-if="exam.subjects?.length" class="exam-subjects">
                <div v-for="s in exam.subjects" :key="s.subject_code" class="exam-subject-item">
                  <span>{{ s.subject_name || s.subject_code }}</span>
                  <span class="exam-subject-score">{{ s.score }}</span>
                </div>
              </div>
              <div v-else class="exam-no-detail">暂无科目明细</div>
            </n-collapse-item>
          </n-collapse>
        </div>

        <ParentEmpty v-if="!exams.length && hasLoaded" message="还没有考试记录" />
      </template>

      <!-- Subject View -->
      <template v-if="segment === 'subject'">
        <div class="p-card" v-if="subjectCodes.length">
          <div class="p-card__header">
            <span class="p-card__title">学科趋势</span>
          </div>
          <n-radio-group v-model:value="selectedSubject" :options="subjectOptions" size="small" class="subject-selector" />
          <div v-if="subjectTrend.length >= 2" class="subject-chart">
            <v-chart :option="trendChartOption" autoresize style="height: 180px;" />
          </div>
          <div v-else class="subject-no-data">数据不足，至少需要 2 次考试</div>
        </div>

        <!-- Error book stats -->
        <div class="p-card" v-if="errorStats">
          <div class="p-card__header">
            <span class="p-card__title">错题概况</span>
          </div>
          <div class="error-stats">
            <div class="error-stat error-stat--red">
              <div class="error-stat__value">{{ errorStats.unmastered || 0 }}</div>
              <div class="error-stat__label">未掌握</div>
            </div>
            <div class="error-stat error-stat--yellow">
              <div class="error-stat__value">{{ errorStats.practicing || 0 }}</div>
              <div class="error-stat__label">练习中</div>
            </div>
            <div class="error-stat error-stat--green">
              <div class="error-stat__value">{{ errorStats.mastered || 0 }}</div>
              <div class="error-stat__label">已掌握</div>
            </div>
          </div>
        </div>

        <ParentEmpty v-if="!subjectCodes.length && hasLoaded" message="还没有考试记录" />
      </template>
    </template>
  </PullRefresh>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { NRadioGroup, NRadioButton, NCollapse, NCollapseItem } from 'naive-ui'
import { AlertTriangle } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import PullRefresh from '../../components/parent/PullRefresh.vue'
import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../components/parent/NumberRoll.vue'
import { getChildExams, getChildScores, getChildErrorBook } from '../../api/conduct'

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const segment = ref('exam')
const segments = [
  { label: '考试', value: 'exam' },
  { label: '学科', value: 'subject' },
]

const loading = ref(false)
const refreshing = ref(false)
const hasLoaded = ref(false)
const lastUpdate = ref('')

const exams = ref([])
const errorStats = ref(null)
const selectedSubject = ref('')

const latestExam = computed(() => exams.value[0] || null)
const latestSubjects = computed(() => latestExam.value?.subjects || [])

const subjectCodes = computed(() => {
  const codes = new Set()
  exams.value.forEach(e => {
    (e.subjects || []).forEach(s => codes.add(s.subject_code || s.subject_name))
  })
  return [...codes]
})

const subjectOptions = computed(() =>
  subjectCodes.value.map(c => {
    const s = exams.value.flatMap(e => e.subjects || []).find(s => (s.subject_code || s.subject_name) === c)
    return { label: s?.subject_name || c, value: c }
  })
)

const subjectTrend = computed(() => {
  if (!selectedSubject.value) return []
  return exams.value
    .map(e => {
      const s = (e.subjects || []).find(s => (s.subject_code || s.subject_name) === selectedSubject.value)
      return s ? { score: s.score, name: e.exam_name } : null
    })
    .filter(Boolean)
    .reverse()
})

const trendChartOption = computed(() => ({
  grid: { top: 20, right: 16, bottom: 24, left: 40 },
  xAxis: {
    type: 'category',
    data: subjectTrend.value.map(t => t.name),
    axisLabel: { fontSize: 11, color: '#9B93B5' },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 11, color: '#9B93B5' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
  },
  series: [{
    type: 'line',
    data: subjectTrend.value.map(t => t.score),
    smooth: true,
    symbol: 'circle',
    symbolSize: 8,
    lineStyle: { color: '#644CF0', width: 2 },
    itemStyle: { color: '#644CF0' },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
      { offset: 0, color: 'rgba(100,76,240,0.2)' },
      { offset: 1, color: 'rgba(100,76,240,0)' },
    ] } },
  }],
}))

function barWidth(score, max) {
  if (!max || !score) return '0%'
  return Math.min(100, (score / max) * 100) + '%'
}

async function loadData() {
  const child = props.currentChild
  if (!child) return

  if (hasLoaded.value) refreshing.value = true
  else loading.value = true

  try {
    const [examsRes, errorRes] = await Promise.allSettled([
      getChildExams(child.student_id),
      getChildErrorBook(child.student_id, {}),
    ])

    if (examsRes.status === 'fulfilled') {
      exams.value = examsRes.value.data || []
    }

    if (errorRes.status === 'fulfilled') {
      const data = errorRes.value.data
      if (data) {
        errorStats.value = {
          unmastered: data.unmastered ?? data.not_mastered ?? 0,
          practicing: data.practicing ?? 0,
          mastered: data.mastered ?? 0,
        }
      }
    }

    if (subjectCodes.value.length && !selectedSubject.value) {
      selectedSubject.value = subjectCodes.value[0]
    }

    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    hasLoaded.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

watch(() => props.currentChild, (child) => {
  exams.value = []
  errorStats.value = null
  selectedSubject.value = ''
  hasLoaded.value = false
  if (child) loadData()
}, { immediate: true })
</script>

<style scoped>
.segment-control { margin-bottom: var(--p-space-5); }

.p-card {
  background: var(--p-card-bg);
  border: var(--p-card-border);
  box-shadow: var(--p-card-shadow);
  border-radius: var(--p-card-radius);
  padding: var(--p-card-padding);
  margin-bottom: var(--p-space-5);
}
.p-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--p-space-3); }
.p-card__title { font-size: var(--p-fs-section); font-weight: 600; color: var(--p-text-1); }
.p-card__source { font-size: var(--p-fs-label); color: var(--p-text-3); }

.score-summary { display: flex; gap: var(--p-space-4); margin-top: var(--p-space-3); }
.score-block { flex: 1; text-align: center; padding: var(--p-space-3); border-radius: 8px; background: rgba(255,255,255,0.03); }
.score-block--accent { background: var(--p-color-accent-surface); }
.score-block__value { font-size: var(--p-fs-page-title); font-weight: 700; color: var(--p-text-1); font-variant-numeric: tabular-nums; }
.score-block__total { font-size: var(--p-fs-label); color: var(--p-text-3); font-weight: 400; }
.score-block__label { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: 4px; }

.subject-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--p-border); }
.subject-row:last-child { border-bottom: none; }
.subject-row__name { width: 48px; font-size: var(--p-fs-label); color: var(--p-text-2); flex-shrink: 0; }
.subject-row__bar-wrap { flex: 1; height: 20px; background: rgba(255,255,255,0.04); border-radius: 4px; position: relative; overflow: hidden; }
.subject-row__bar { height: 100%; background: var(--p-color-primary); border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; min-width: 30px; transition: width 0.3s ease; }
.subject-row__score { font-size: 11px; color: #fff; font-weight: 600; }
.subject-row__avg { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--p-color-accent); }
.subject-row__warn { color: var(--p-color-warning); flex-shrink: 0; }

.exam-total { font-size: var(--p-fs-body); color: var(--p-color-accent); font-weight: 600; font-variant-numeric: tabular-nums; }
.exam-subjects { display: flex; flex-direction: column; gap: 4px; }
.exam-subject-item { display: flex; justify-content: space-between; font-size: var(--p-fs-body); color: var(--p-text-2); padding: 4px 0; }
.exam-subject-score { font-weight: 600; color: var(--p-text-1); font-variant-numeric: tabular-nums; }
.exam-no-detail { font-size: var(--p-fs-label); color: var(--p-text-3); }

.subject-selector { margin-bottom: var(--p-space-4); }
.subject-chart { margin-top: var(--p-space-3); }
.subject-no-data { font-size: var(--p-fs-body); color: var(--p-text-3); text-align: center; padding: 24px 0; }

.error-stats { display: flex; gap: var(--p-space-3); }
.error-stat { flex: 1; text-align: center; padding: var(--p-space-3); border-radius: 8px; }
.error-stat--red { background: var(--p-color-error-surface); }
.error-stat--yellow { background: var(--p-color-warning-surface); }
.error-stat--green { background: var(--p-color-success-surface); }
.error-stat__value { font-size: var(--p-fs-page-title); font-weight: 700; color: var(--p-text-1); }
.error-stat__label { font-size: var(--p-fs-label); color: var(--p-text-3); margin-top: 4px; }
</style>
