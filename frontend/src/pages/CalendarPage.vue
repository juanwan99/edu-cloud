<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">校历管理</h1>
      <p class="page-subtitle">学期事件与日程安排</p>
    </div>

    <div style="display: flex; gap: 24px; flex-wrap: wrap;">
      <!-- 左侧：事件列表 -->
      <div style="flex: 2; min-width: 400px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <n-radio-group v-model:value="typeFilter" @update:value="loadEvents">
            <n-radio-button value="">全部</n-radio-button>
            <n-radio-button value="holiday">放假</n-radio-button>
            <n-radio-button value="exam">考试</n-radio-button>
            <n-radio-button value="parent_meeting">家长会</n-radio-button>
            <n-radio-button value="deadline">截止日期</n-radio-button>
          </n-radio-group>
          <n-button v-if="canCreate" type="primary" size="small" @click="showCreate = true">新增事件</n-button>
        </div>

        <n-spin :show="loading">
          <n-data-table
            v-if="events.length"
            :columns="columns"
            :data="events"
            :pagination="{ pageSize: 15 }"
            :bordered="false"
            size="small"
          />
          <n-empty v-else-if="!loading" description="暂无校历事件" style="margin-top: 40px;" />
        </n-spin>
      </div>

      <!-- 右侧：统计 -->
      <div style="flex: 1; min-width: 200px;">
        <div class="stats-grid">
          <div v-for="t in typeSummary" :key="t.type" class="stat-card">
            <div class="stat-value">{{ t.count }}</div>
            <div class="stat-label">{{ t.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建弹窗 -->
    <n-modal v-model:show="showCreate" preset="card" style="width: 480px;" title="新增校历事件">
      <n-form label-placement="top">
        <n-form-item label="类型">
          <n-select v-model:value="form.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="例：五一劳动节放假" />
        </n-form-item>
        <n-form-item label="日期">
          <n-date-picker v-model:value="form.date" type="date" style="width: 100%;" />
        </n-form-item>
        <n-form-item label="提前通知（天）">
          <n-input-number v-model:value="form.daysBefore" :min="0" :max="30" style="width: 100%;" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" type="textarea" placeholder="可选" :rows="2" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="creating" @click="handleCreate">创建</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { NButton, NTag } from 'naive-ui'
import { listCalendarEvents, createCalendarEvent, deleteCalendarEvent } from '../api/calendar.js'

const auth = useAuthStore()

const loading = ref(false)
const creating = ref(false)
const events = ref([])
const typeFilter = ref('')
const showCreate = ref(false)
const form = ref({ type: 'holiday', title: '', date: null, daysBefore: 7, description: '' })

const canCreate = computed(() => auth.checkPermission('generate_notification'))

const typeOptions = [
  { label: '放假', value: 'holiday' },
  { label: '考试', value: 'exam' },
  { label: '家长会', value: 'parent_meeting' },
  { label: '截止日期', value: 'deadline' },
]

const TYPE_MAP = {
  holiday: { label: '放假', type: 'success' },
  exam: { label: '考试', type: 'warning' },
  parent_meeting: { label: '家长会', type: 'info' },
  deadline: { label: '截止日期', type: 'error' },
}

const typeSummary = computed(() => {
  const counts = {}
  events.value.forEach(e => { counts[e.type] = (counts[e.type] || 0) + 1 })
  return Object.entries(TYPE_MAP).map(([type, info]) => ({
    type, label: info.label, count: counts[type] || 0,
  }))
})

const columns = computed(() => [
  { title: '标题', key: 'title', ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'type',
    width: 100,
    render: (row) => {
      const info = TYPE_MAP[row.type] || { label: row.type, type: 'default' }
      return h(NTag, { size: 'small', type: info.type }, () => info.label)
    },
  },
  { title: '日期', key: 'event_date', width: 120 },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) => canCreate.value
      ? h(NButton, { size: 'tiny', text: true, type: 'error', onClick: () => handleDelete(row.id) }, () => '删除')
      : null,
  },
])

async function loadEvents() {
  loading.value = true
  try {
    const params = {}
    if (typeFilter.value) params.type = typeFilter.value
    const { data } = await listCalendarEvents(params)
    events.value = Array.isArray(data) ? data : []
  } catch {
    events.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.value.title || !form.value.date) return
  creating.value = true
  try {
    const dateStr = new Date(form.value.date).toISOString().split('T')[0]
    await createCalendarEvent({
      type: form.value.type,
      title: form.value.title,
      event_date: dateStr,
      description: form.value.description,
      notification_rules: form.value.daysBefore >= 0 ? [{
        days_before: form.value.daysBefore,
        template_type: form.value.type === 'holiday' ? 'holiday_safety' : form.value.type === 'exam' ? 'exam_reminder' : 'meeting_invite',
        target_roles: ['parent'],
        auto_draft: true,
      }] : [],
    })
    showCreate.value = false
    form.value = { type: 'holiday', title: '', date: null, daysBefore: 7, description: '' }
    await loadEvents()
  } finally {
    creating.value = false
  }
}

async function handleDelete(eventId) {
  await deleteCalendarEvent(eventId)
  await loadEvents()
}

onMounted(loadEvents)
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-subtitle { font-size: 14px; color: var(--color-text-muted); margin: 4px 0 0; }

.stats-grid {
  display: grid;
  gap: 12px;
}

.stat-card {
  background: var(--color-bg-alt);
  padding: 16px;
  border-radius: var(--radius-lg);
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 4px;
}
</style>
