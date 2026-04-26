<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/joint-exams')">← 返回联考列表</n-button>
      <h1 class="page-title">{{ exam?.name || '加载中...' }}</h1>
      <p class="page-subtitle">
        <n-tag v-if="exam" size="small" :type="statusType">{{ statusLabel }}</n-tag>
      </p>
    </div>

    <n-spin :show="loading">
      <n-tabs type="line" v-if="exam">
        <!-- 基本信息 + 参与学校 -->
        <n-tab-pane name="info" tab="考试信息">
          <div style="display: flex; gap: 24px; flex-wrap: wrap;">
            <div class="info-card" style="flex: 1; min-width: 300px;">
              <h3 style="margin: 0 0 12px;">基本信息</h3>
              <div class="info-row"><span>联考名称</span><span>{{ exam.name }}</span></div>
              <div class="info-row"><span>状态</span><span>{{ statusLabel }}</span></div>
              <div class="info-row"><span>科目</span><span>{{ subjectNames }}</span></div>
              <div class="info-row" v-if="exam.description"><span>描述</span><span>{{ exam.description }}</span></div>
            </div>

            <div class="info-card" style="flex: 1; min-width: 300px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0;">参与学校</h3>
                <n-button v-if="canManage" size="small" @click="showAddSchool = true">添加学校</n-button>
              </div>
              <n-data-table
                :columns="participantColumns"
                :data="exam.participants || []"
                :bordered="false"
                size="small"
                :pagination="false"
              />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div style="margin-top: 24px; display: flex; gap: 12px;" v-if="canManage">
            <n-button v-if="exam.status === 'active'" type="warning" @click="handleDistribute">下发考试</n-button>
            <n-button v-if="exam.status !== 'done' && exam.status !== 'archived'" type="error" @click="handleForceComplete">强制完成</n-button>
          </div>
        </n-tab-pane>

        <!-- 成绩排名 -->
        <n-tab-pane name="rankings" tab="成绩排名">
          <n-button size="small" style="margin-bottom: 12px;" @click="loadRankings">刷新排名</n-button>
          <n-data-table
            v-if="rankings.length"
            :columns="rankingColumns"
            :data="rankings"
            :pagination="{ pageSize: 20 }"
            :bordered="false"
            size="small"
          />
          <n-empty v-else description="暂无排名数据" />
        </n-tab-pane>

        <!-- 校际对比 -->
        <n-tab-pane name="comparison" tab="校际对比">
          <n-button size="small" style="margin-bottom: 12px;" @click="loadComparison">刷新对比</n-button>
          <n-data-table
            v-if="comparison.length"
            :columns="comparisonColumns"
            :data="comparison"
            :bordered="false"
            size="small"
          />
          <n-empty v-else description="暂无校际对比数据" />
        </n-tab-pane>
      </n-tabs>
    </n-spin>

    <!-- 添加学校弹窗 -->
    <n-modal v-model:show="showAddSchool" title="添加参与学校" preset="card" style="width: 400px;">
      <n-input v-model:value="newSchoolId" placeholder="输入学校 ID" />
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="showAddSchool = false">取消</n-button>
          <n-button type="primary" @click="handleAddSchool">添加</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { NButton, NTag } from 'naive-ui'
import {
  getJointExam, addParticipant, removeParticipant,
  distributeExam, forceCompleteExam,
  getExamRankings, getSchoolComparison,
} from '../api/jointExams.js'

const route = useRoute()
const auth = useAuthStore()

const loading = ref(false)
const exam = ref(null)
const rankings = ref([])
const comparison = ref([])
const showAddSchool = ref(false)
const newSchoolId = ref('')

const canManage = computed(() => auth.checkPermission('manage_joint_exam'))

const STATUS_MAP = {
  draft: { label: '草稿', type: 'default' },
  active: { label: '进行中', type: 'info' },
  distributing: { label: '下发中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  archived: { label: '已归档', type: 'default' },
}
const statusLabel = computed(() => STATUS_MAP[exam.value?.status]?.label || exam.value?.status)
const statusType = computed(() => STATUS_MAP[exam.value?.status]?.type || 'default')
const subjectNames = computed(() => {
  const subs = exam.value?.subjects
  if (!subs?.length) return '-'
  return subs.map(s => s.name || s.code).join('、')
})

const participantColumns = [
  { title: '学校ID', key: 'school_id', ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) => canManage.value
      ? h(NButton, { size: 'tiny', text: true, type: 'error', onClick: () => handleRemoveSchool(row.school_id) }, () => '移除')
      : null,
  },
]

const rankingColumns = [
  { title: '排名', key: 'rank', width: 70 },
  { title: '学生', key: 'student_number', width: 140 },
  { title: '学校', key: 'school_name', width: 160, ellipsis: { tooltip: true } },
  { title: '总分', key: 'total_score', width: 100 },
]

const comparisonColumns = [
  { title: '学校', key: 'school_name', ellipsis: { tooltip: true } },
  { title: '平均分', key: 'avg_score', width: 100 },
  { title: '最高分', key: 'max_score', width: 100 },
  { title: '最低分', key: 'min_score', width: 100 },
  { title: '参考人数', key: 'student_count', width: 100 },
]

async function loadExam() {
  loading.value = true
  try {
    const { data } = await getJointExam(route.params.id)
    exam.value = data
  } finally {
    loading.value = false
  }
}

async function loadRankings() {
  try {
    const { data } = await getExamRankings(route.params.id)
    rankings.value = Array.isArray(data) ? data : []
  } catch { rankings.value = [] }
}

async function loadComparison() {
  try {
    const { data } = await getSchoolComparison(route.params.id)
    comparison.value = Array.isArray(data) ? data : []
  } catch { comparison.value = [] }
}

async function handleAddSchool() {
  if (!newSchoolId.value) return
  await addParticipant(route.params.id, newSchoolId.value)
  showAddSchool.value = false
  newSchoolId.value = ''
  await loadExam()
}

async function handleRemoveSchool(schoolId) {
  await removeParticipant(route.params.id, schoolId)
  await loadExam()
}

async function handleDistribute() {
  await distributeExam(route.params.id)
  await loadExam()
}

async function handleForceComplete() {
  await forceCompleteExam(route.params.id)
  await loadExam()
}

onMounted(() => {
  loadExam()
  loadRankings()
  loadComparison()
})
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-subtitle { margin: 8px 0 0; }

.info-card {
  background: white;
  padding: 20px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 14px;
}
.info-row:last-child { border-bottom: none; }
.info-row span:first-child { color: var(--color-text-muted); }
</style>
