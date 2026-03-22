<template>
  <div style="padding: 12px">
    <n-h4>学期日历</n-h4>

    <!-- 创建事件 -->
    <n-button size="small" type="primary" @click="showCreate = true" style="margin-bottom: 12px">
      + 新增事件
    </n-button>

    <!-- 事件列表 -->
    <n-list v-if="events.length">
      <n-list-item v-for="event in events" :key="event.id">
        <n-thing :title="event.title">
          <template #description>
            <n-tag :type="typeMap[event.type] || 'default'" size="small">{{ event.type }}</n-tag>
            <n-text depth="3" style="margin-left: 8px">{{ event.event_date }}</n-text>
          </template>
        </n-thing>
      </n-list-item>
    </n-list>
    <n-empty v-else description="暂无事件" size="small" />

    <!-- 创建弹窗 -->
    <n-modal v-model:show="showCreate" preset="card" style="width: 500px" title="新增学期事件">
      <n-form>
        <n-form-item label="类型">
          <n-select v-model:value="form.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="如：五一放假" />
        </n-form-item>
        <n-form-item label="日期">
          <n-date-picker v-model:value="form.date" type="date" />
        </n-form-item>
        <n-form-item label="提前通知（天）">
          <n-input-number v-model:value="form.daysBefore" :min="0" :max="30" />
        </n-form-item>
        <n-button type="primary" @click="handleCreate">创建</n-button>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import client from '../../api/client.js'

const events = ref([])
const showCreate = ref(false)
const form = ref({ type: 'holiday', title: '', date: null, daysBefore: 7 })

const typeOptions = [
  { label: '放假', value: 'holiday' },
  { label: '考试', value: 'exam' },
  { label: '家长会', value: 'parent_meeting' },
  { label: '截止日期', value: 'deadline' },
]
const typeMap = { holiday: 'success', exam: 'warning', parent_meeting: 'info', deadline: 'error' }

async function loadEvents() {
  const { data } = await client.get('/calendar/events')
  events.value = data
}

async function handleCreate() {
  if (!form.value.title || !form.value.date) return
  const dateStr = new Date(form.value.date).toISOString().split('T')[0]
  await client.post('/calendar/events', {
    type: form.value.type,
    title: form.value.title,
    event_date: dateStr,
    notification_rules: form.value.daysBefore > 0 ? [{
      days_before: form.value.daysBefore,
      template_type: form.value.type === 'holiday' ? 'holiday_safety' : form.value.type === 'exam' ? 'exam_reminder' : 'meeting_invite',
      target_roles: ['parent'],
      auto_draft: true,
    }] : [],
  })
  showCreate.value = false
  form.value = { type: 'holiday', title: '', date: null, daysBefore: 7 }
  await loadEvents()
}

onMounted(loadEvents)
</script>
