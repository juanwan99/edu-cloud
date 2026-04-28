<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">题库</h1>
      <p class="page-subtitle">按知识点/难度/题型/来源搜索题目</p>
    </div>

    <!-- 统计概览 -->
    <div class="stats-grid" v-if="statsData">
      <div class="stat-card">
        <div class="stat-value">{{ statsData.total_count }}</div>
        <div class="stat-label">题目总数</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-coral-light, #fff0f0);">
        <div class="stat-value" style="color: var(--color-danger, #e63946);">
          {{ Object.keys(statsData.by_question_type).length }}
        </div>
        <div class="stat-label">题型分类</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-yellow-light, #fff8e1);">
        <div class="stat-value" style="color: var(--color-warning, #f4a261);">
          {{ Object.keys(statsData.by_difficulty_level).length }}
        </div>
        <div class="stat-label">难度等级</div>
      </div>
      <div class="stat-card" style="background: var(--macaron-mint-light, #e8f5e9);">
        <div class="stat-value" style="color: var(--color-success, #2a9d8f);">
          {{ Object.keys(statsData.by_source).length }}
        </div>
        <div class="stat-label">题目来源</div>
      </div>
    </div>

    <!-- 搜索栏 + 筛选面板 -->
    <div class="filter-bar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索题目内容..."
        clearable
        style="width: 320px;"
        @keyup.enter="doSearch"
      >
        <template #prefix>
          <span style="font-size: 14px; color: var(--color-text-muted);">Q</span>
        </template>
      </n-input>
      <n-select
        v-model:value="questionType"
        :options="questionTypeOptions"
        placeholder="题型"
        clearable
        style="width: 140px;"
      />
      <n-select
        v-model:value="difficultyLevel"
        :options="difficultyOptions"
        placeholder="难度"
        clearable
        style="width: 140px;"
      />
      <n-select
        v-model:value="source"
        :options="sourceOptions"
        placeholder="来源"
        clearable
        style="width: 160px;"
      />
      <n-button type="primary" @click="doSearch">搜索</n-button>
      <n-button quaternary @click="resetFilters">重置</n-button>
    </div>

    <!-- 题目列表 -->
    <n-spin :show="loading">
      <div v-if="questions.length" class="question-list">
        <n-card
          v-for="q in questions"
          :key="q.id"
          class="question-card"
          :bordered="true"
          size="small"
          hoverable
        >
          <div class="question-content">
            <div class="question-text">{{ q.content_text || '(无题干文本)' }}</div>
            <div class="question-meta">
              <n-tag size="small" :type="typeTagType(q.question_type)">
                {{ QUESTION_TYPE_LABELS[q.question_type] || q.question_type }}
              </n-tag>
              <n-tag v-if="q.difficulty_level" size="small" :type="difficultyTagType(q.difficulty_level)">
                {{ DIFFICULTY_LABELS[q.difficulty_level] || q.difficulty_level }}
              </n-tag>
              <n-tag v-if="q.source" size="small" type="info">
                {{ q.source }}
              </n-tag>
              <span v-if="q.max_score" class="meta-score">{{ q.max_score }}分</span>
            </div>
            <div v-if="q.tags && q.tags.length" class="question-tags">
              <n-tag v-for="tag in q.tags" :key="tag" size="tiny" round>{{ tag }}</n-tag>
            </div>
            <div v-if="q.knowledge_point_ids && q.knowledge_point_ids.length" class="question-kps">
              <span class="kp-label">知识点:</span>
              <n-tag v-for="kp in q.knowledge_point_ids" :key="kp" size="tiny" type="success" round>
                {{ kp }}
              </n-tag>
            </div>
          </div>
        </n-card>
      </div>
      <n-empty v-else-if="!loading && searched" description="未找到匹配的题目" style="margin-top: 40px;">
        <template #extra>
          <n-button size="small" @click="resetFilters">清除筛选</n-button>
        </template>
      </n-empty>
      <n-empty v-else-if="!loading && !searched" description="请设置筛选条件后搜索" style="margin-top: 40px;" />
    </n-spin>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination-bar">
      <n-pagination
        v-model:page="page"
        :page-size="pageSize"
        :item-count="total"
        show-size-picker
        :page-sizes="[10, 20, 50]"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { searchQuestions, getQuestionBankStats } from '../api/bank.js'

const keyword = ref('')
const questionType = ref(null)
const difficultyLevel = ref(null)
const source = ref(null)
const loading = ref(false)
const searched = ref(false)
const questions = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statsData = ref(null)

const QUESTION_TYPE_LABELS = {
  choice: '选择题',
  fill_blank: '填空题',
  essay: '主观题',
  true_false: '判断题',
}

const DIFFICULTY_LABELS = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

const questionTypeOptions = [
  { label: '选择题', value: 'choice' },
  { label: '填空题', value: 'fill_blank' },
  { label: '主观题', value: 'essay' },
  { label: '判断题', value: 'true_false' },
]

const difficultyOptions = [
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' },
]

const sourceOptions = ref([])

function typeTagType(type) {
  const map = { choice: 'info', fill_blank: 'warning', essay: 'success', true_false: 'default' }
  return map[type] || 'default'
}

function difficultyTagType(level) {
  const map = { easy: 'success', medium: 'warning', hard: 'error' }
  return map[level] || 'default'
}

async function loadStats() {
  try {
    const { data } = await getQuestionBankStats()
    statsData.value = data
    // 从统计数据中生成来源选项
    if (data.by_source) {
      sourceOptions.value = Object.keys(data.by_source).map(s => ({
        label: `${s} (${data.by_source[s]})`,
        value: s,
      }))
    }
  } catch {
    statsData.value = null
  }
}

async function doSearch() {
  loading.value = true
  searched.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    if (questionType.value) params.question_type = questionType.value
    if (difficultyLevel.value) params.difficulty_level = difficultyLevel.value
    if (source.value) params.source = source.value

    const { data } = await searchQuestions(params)
    questions.value = data.items
    total.value = data.total
  } catch {
    questions.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  keyword.value = ''
  questionType.value = null
  difficultyLevel.value = null
  source.value = null
  page.value = 1
  doSearch()
}

function onPageChange(newPage) {
  page.value = newPage
  doSearch()
}

function onPageSizeChange(newSize) {
  pageSize.value = newSize
  page.value = 1
  doSearch()
}

onMounted(() => {
  loadStats()
  doSearch()
})
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-subtitle { font-size: 14px; color: var(--color-text-muted); margin: 4px 0 0; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--color-bg-alt);
  padding: 16px;
  border-radius: var(--radius-lg);
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 6px;
}

.filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-card {
  transition: box-shadow 0.2s ease;
}

.question-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text);
  word-break: break-word;
}

.question-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-score {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-left: auto;
}

.question-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.question-kps {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.kp-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 24px;
  padding-bottom: 20px;
}
</style>
