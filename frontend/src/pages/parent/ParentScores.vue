<template>
  <div>
    <n-h3>成绩查询</n-h3>

    <n-spin :show="loading">
      <!-- 最近成绩卡片 -->
      <div v-if="latestExam" class="score-summary">
        <div class="score-card score-card--primary">
          <div class="score-card__value">{{ latestExam.total_score ?? '-' }}</div>
          <div class="score-card__label">最近总分</div>
          <div class="score-card__sub">满分 {{ latestExam.max_score }}</div>
        </div>
        <div class="score-card">
          <div class="score-card__value">{{ latestRank?.class_rank ?? '-' }}</div>
          <div class="score-card__label">班级排名</div>
          <div class="score-card__sub">共 {{ latestRank?.class_size ?? '-' }} 人</div>
        </div>
        <div class="score-card">
          <div class="score-card__value">{{ latestRank?.grade_rank ?? '-' }}</div>
          <div class="score-card__label">年级排名</div>
          <div class="score-card__sub">共 {{ latestRank?.grade_size ?? '-' }} 人</div>
        </div>
      </div>

      <!-- 考试成绩列表 -->
      <n-h4 style="margin-top: 24px;">历次考试</n-h4>
      <div v-if="exams.length" class="exam-list">
        <div
          v-for="exam in exams"
          :key="exam.exam_id"
          class="exam-item"
          @click="toggleExam(exam.exam_id)"
        >
          <div class="exam-item__header">
            <span class="exam-item__name">{{ exam.exam_name }}</span>
            <span class="exam-item__score">{{ exam.total_score }}/{{ exam.max_score }}</span>
          </div>
          <div class="exam-item__meta">
            <span>{{ formatDate(exam.exam_date) }}</span>
            <n-tag size="tiny" :type="exam.exam_status === 'completed' ? 'success' : 'default'">
              {{ exam.exam_status === 'completed' ? '已完成' : exam.exam_status }}
            </n-tag>
          </div>

          <!-- 展开的科目成绩 -->
          <div v-if="expandedExam === exam.exam_id && examScores[exam.exam_id]" class="exam-subjects">
            <div
              v-for="s in examScores[exam.exam_id]"
              :key="s.subject_code"
              class="subject-row"
            >
              <span>{{ s.subject_code }}</span>
              <span>{{ s.total_score }}/{{ s.max_score }}</span>
              <span v-if="s.class_rank">班{{ s.class_rank }}</span>
              <span v-if="s.grade_rank">级{{ s.grade_rank }}</span>
            </div>
          </div>
        </div>
      </div>
      <n-empty v-else-if="!loading" description="暂无考试成绩" />

      <!-- 错题概览 -->
      <div v-if="errorStats" style="margin-top: 24px;">
        <n-h4>错题概况</n-h4>
        <div class="score-summary">
          <div class="score-card" style="background: rgba(230, 57, 70, 0.15);">
            <div class="score-card__value" style="color: #e63946;">{{ errorStats.unmastered }}</div>
            <div class="score-card__label">未掌握</div>
          </div>
          <div class="score-card" style="background: rgba(244, 162, 97, 0.15);">
            <div class="score-card__value" style="color: #f4a261;">{{ errorStats.practicing }}</div>
            <div class="score-card__label">练习中</div>
          </div>
          <div class="score-card" style="background: rgba(42, 157, 143, 0.15);">
            <div class="score-card__value" style="color: #2a9d8f;">{{ errorStats.mastered }}</div>
            <div class="score-card__label">已掌握</div>
          </div>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, inject, computed } from 'vue'
import { getChildExams, getChildScores, getChildErrorBook } from '../../api/conduct'

const currentChild = inject('currentChild')
const loading = ref(false)
const exams = ref([])
const scores = ref([])
const expandedExam = ref(null)
const examScores = ref({})
const errorStats = ref(null)

const latestExam = computed(() => exams.value[0] || null)
const latestRank = computed(() => {
  if (!latestExam.value) return null
  const totalRow = scores.value.find(
    s => s.exam_id === latestExam.value.exam_id && s.subject_code === '_total'
  )
  return totalRow || scores.value.find(s => s.exam_id === latestExam.value.exam_id)
})

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function toggleExam(examId) {
  if (expandedExam.value === examId) {
    expandedExam.value = null
    return
  }
  expandedExam.value = examId
  if (!examScores.value[examId]) {
    const subjects = scores.value.filter(s => s.exam_id === examId && s.subject_code !== '_total')
    examScores.value[examId] = subjects
  }
}

async function loadData() {
  const child = currentChild?.value
  if (!child) return
  loading.value = true
  try {
    const [examRes, scoreRes, errorRes] = await Promise.all([
      getChildExams(child.student_id),
      getChildScores(child.student_id, { limit: 50 }),
      getChildErrorBook(child.student_id, { limit: 1 }),
    ])
    exams.value = examRes.data || []
    scores.value = scoreRes.data || []
    errorStats.value = errorRes.data?.stats || null
  } catch {
    exams.value = []
    scores.value = []
    errorStats.value = null
  } finally {
    loading.value = false
  }
}

watch(currentChild, loadData, { deep: true })
onMounted(loadData)
</script>

<style scoped>
.score-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.score-card {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}

.score-card--primary {
  background: rgba(99, 226, 183, 0.10);
}

.score-card__value {
  font-size: 22px;
  font-weight: 700;
  color: #63e2b7;
}

.score-card__label {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.score-card__sub {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 2px;
}

.exam-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.exam-item {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.exam-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.exam-item__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exam-item__name {
  font-size: 16px;
  font-weight: 600;
}

.exam-item__score {
  font-size: 16px;
  font-weight: 700;
  color: #63e2b7;
}

.exam-item__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.45);
}

.exam-subjects {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.subject-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
}
</style>
