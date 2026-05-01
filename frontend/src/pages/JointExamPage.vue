<template>
  <div>
    <div class="page-header">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h1 class="page-title">联考管理</h1>
          <p class="page-subtitle">跨校联合考试的创建、下发与成绩管理</p>
        </div>
        <n-button v-if="canCreate" type="primary" @click="showCreate = true">创建联考</n-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <n-card size="small" class="stat-card">
        <n-statistic label="总联考数" :value="stats.total" />
      </n-card>
      <n-card size="small" class="stat-card">
        <n-statistic label="进行中" :value="stats.active">
          <template #suffix>
            <n-tag size="tiny" type="info" round>活跃</n-tag>
          </template>
        </n-statistic>
      </n-card>
      <n-card size="small" class="stat-card">
        <n-statistic label="已完成" :value="stats.done">
          <template #suffix>
            <n-tag size="tiny" type="success" round>完成</n-tag>
          </template>
        </n-statistic>
      </n-card>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <n-radio-group v-model:value="statusFilter" @update:value="loadExams">
        <n-radio-button value="">全部</n-radio-button>
        <n-radio-button value="draft">草稿</n-radio-button>
        <n-radio-button value="active">进行中</n-radio-button>
        <n-radio-button value="done">已完成</n-radio-button>
      </n-radio-group>
    </div>

    <n-spin :show="loading">
      <n-data-table
        v-if="exams.length"
        :columns="columns"
        :data="exams"
        :pagination="{ pageSize: 15 }"
        :bordered="false"
        size="small"
      />
      <!-- 空状态引导 -->
      <div v-else-if="!loading" class="empty-state">
        <n-empty description="暂无联考数据" size="large">
          <template #extra>
            <n-button v-if="canCreate" type="primary" @click="showCreate = true">
              创建第一个联考
            </n-button>
            <p v-else style="color: var(--color-text-muted); font-size: var(--fs-base);">
              联考由具有创建权限的管理员发起
            </p>
          </template>
        </n-empty>
      </div>
    </n-spin>

    <!-- 创建联考弹窗 -->
    <n-modal v-model:show="showCreate" title="创建联考" preset="card" style="width: 520px;">
      <n-form ref="formRef" :model="form" label-placement="top">
        <n-form-item label="联考名称" path="name">
          <n-input v-model:value="form.name" placeholder="例：2026年春季期中联考" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" type="textarea" placeholder="可选" :rows="2" />
        </n-form-item>
        <n-form-item label="考试科目">
          <n-select
            v-model:value="form.selectedSubjects"
            :options="SUBJECT_OPTIONS"
            multiple
            placeholder="选择考试科目"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: var(--space-2);">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="creating" @click="handleCreate">创建</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { NButton, NTag, NProgress, NPopconfirm } from 'naive-ui'
import { listJointExams, createJointExam, distributeExam, forceCompleteExam } from '../api/jointExams.js'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const loading = ref(false)
const exams = ref([])
const statusFilter = ref('')
const showCreate = ref(false)
const creating = ref(false)
const form = ref({ name: '', description: '', selectedSubjects: [] })

const canCreate = computed(() => auth.checkPermission('create_joint_exam'))
const canManage = computed(() => auth.checkPermission('manage_joint_exam'))

const SUBJECT_OPTIONS = [
  { label: '语文', value: 'chinese' },
  { label: '数学', value: 'math' },
  { label: '英语', value: 'english' },
  { label: '物理', value: 'physics' },
  { label: '化学', value: 'chemistry' },
  { label: '生物', value: 'biology' },
  { label: '政治', value: 'politics' },
  { label: '历史', value: 'history' },
  { label: '地理', value: 'geography' },
]

const SUBJECT_NAME_MAP = Object.fromEntries(SUBJECT_OPTIONS.map(o => [o.value, o.label]))

// 统计卡片
const stats = computed(() => {
  const list = exams.value
  return {
    total: list.length,
    active: list.filter(e => e.status === 'active').length,
    done: list.filter(e => e.status === 'done').length,
  }
})

const STATUS_MAP = {
  draft: { label: '草稿', type: 'default' },
  active: { label: '进行中', type: 'info' },
  distributing: { label: '下发中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  archived: { label: '已归档', type: 'default' },
}

const columns = computed(() => [
  { title: '联考名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const info = STATUS_MAP[row.status] || { label: row.status, type: 'default' }
      return h(NTag, { size: 'small', type: info.type }, () => info.label)
    },
  },
  {
    title: '科目',
    key: 'subjects',
    width: 200,
    render: (row) => {
      if (!row.subjects?.length) return '-'
      return row.subjects.map(s => s.name || s.code).join('、')
    },
  },
  {
    title: '参与校数',
    key: 'participant_count',
    width: 100,
    render: (row) => {
      const count = row.participants?.length ?? row.participant_count ?? 0
      return count || '-'
    },
  },
  {
    title: '进度',
    key: 'progress',
    width: 160,
    render: (row) => {
      if (row.status !== 'active') return '-'
      const participants = row.participants || []
      const total = participants.length || 1
      const completed = participants.filter(p => p.status === 'completed' || p.status === 'done').length
      const pct = Math.round((completed / total) * 100)
      return h('div', { style: 'display: flex; align-items: center; gap: var(--space-2);' }, [
        h(NProgress, {
          type: 'line',
          percentage: pct,
          indicatorPlacement: 'inside',
          processing: pct < 100,
          style: 'flex: 1;',
        }),
        h('span', { style: 'font-size: var(--fs-base); color: var(--color-text-muted); white-space: nowrap;' },
          `${completed}/${total}`),
      ])
    },
  },
  { title: '创建时间', key: 'created_at', width: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (row) => {
      const buttons = [
        h(NButton, {
          size: 'small', text: true, type: 'primary',
          onClick: () => router.push(`/joint-exams/${row.id}`),
        }, () => '详情'),
      ]

      // 下发按钮（draft → active）
      if (canManage.value && row.status === 'draft') {
        buttons.push(
          h(NPopconfirm, {
            onPositiveClick: () => handleDistribute(row.id),
          }, {
            trigger: () => h(NButton, {
              size: 'small', text: true, type: 'info',
            }, () => '下发'),
            default: () => '确认下发此联考？下发后各参与校将收到通知。',
          })
        )
      }

      // 强制截止按钮（active → done）
      if (canManage.value && row.status === 'active') {
        buttons.push(
          h(NPopconfirm, {
            onPositiveClick: () => handleForceComplete(row.id),
          }, {
            trigger: () => h(NButton, {
              size: 'small', text: true, type: 'warning',
            }, () => '强制截止'),
            default: () => '确认强制截止？未提交数据的学校将无法继续提交。',
          })
        )
      }

      return h('div', {
        style: 'display: flex; gap: var(--space-2);',
        onClick: (e) => e.stopPropagation(),
      }, buttons)
    },
  },
])

async function loadExams() {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await listJointExams(params)
    exams.value = Array.isArray(data) ? data : []
  } catch {
    exams.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.value.selectedSubjects.length) {
    message.warning('请至少选择一个科目')
    return
  }
  const subjects = form.value.selectedSubjects.map(code => ({
    code,
    name: SUBJECT_NAME_MAP[code] || code,
  }))
  creating.value = true
  try {
    const schoolId = auth.currentRole?.school_id || ''
    await createJointExam({
      name: form.value.name,
      description: form.value.description,
      subjects,
      creator_school_id: schoolId,
    })
    showCreate.value = false
    form.value = { name: '', description: '', selectedSubjects: [] }
    message.success('联考创建成功')
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDistribute(examId) {
  try {
    await distributeExam(examId)
    message.success('联考已下发')
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '下发失败')
  }
}

async function handleForceComplete(examId) {
  try {
    await forceCompleteExam(examId)
    message.success('联考已强制截止')
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '截止失败')
  }
}

onMounted(loadExams)
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card { text-align: center; }
.filter-bar { display: flex; align-items: center; margin-bottom: 16px; gap: 12px; }
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 80px 0;
}
@media (max-width: 768px) {
  .stats-row { grid-template-columns: 1fr; }
}
</style>
