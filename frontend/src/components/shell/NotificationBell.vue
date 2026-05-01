<template>
  <n-popover trigger="click" placement="bottom-end" :width="320" @update:show="onPopoverToggle">
    <template #trigger>
      <div class="bell-btn" title="通知">
        <n-badge :value="unreadCount" :max="99" :show="unreadCount > 0">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2a5 5 0 00-5 5v3l-1.3 2.6a.5.5 0 00.45.7h11.7a.5.5 0 00.45-.7L15 10V7a5 5 0 00-5-5z"
                  stroke="currentColor" stroke-width="1.4" fill="none"/>
            <path d="M8 14a2 2 0 004 0" stroke="currentColor" stroke-width="1.4" fill="none"/>
          </svg>
        </n-badge>
      </div>
    </template>
    <div class="notification-panel">
      <div class="notification-panel__header">
        <span class="notification-panel__title">通知</span>
        <span class="notification-panel__count" v-if="unreadCount">{{ unreadCount }} 条未读</span>
      </div>
      <div class="notification-panel__body">
        <div v-if="loading" style="padding: var(--space-6); text-align: center;">
          <n-spin size="small" />
        </div>
        <template v-else-if="notifications.length">
          <div
            v-for="n in notifications"
            :key="n.id"
            :class="['notification-item', { 'notification-item--unread': n.unread }]"
          >
            <div class="notification-item__title">{{ n.title || n.kind || '通知' }}</div>
            <div class="notification-item__summary">{{ n.summary || '-' }}</div>
            <div class="notification-item__time">{{ formatTime(n.created_at) }}</div>
          </div>
        </template>
        <div v-else class="notification-empty">暂无通知</div>
      </div>
    </div>
  </n-popover>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getNotifications } from '../../api/notifications.js'

const notifications = ref([])
const loading = ref(false)
const unreadCount = ref(0)

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadNotifications() {
  loading.value = true
  try {
    const { data } = await getNotifications({ since: 'week' })
    const list = Array.isArray(data) ? data : (data.items || [])
    notifications.value = list.slice(0, 20)
    unreadCount.value = list.filter(n => n.unread || n.status === 'pending').length
  } catch {
    notifications.value = []
    unreadCount.value = 0
  } finally {
    loading.value = false
  }
}

function onPopoverToggle(show) {
  if (show && !notifications.value.length) loadNotifications()
}

onMounted(loadNotifications)
</script>

<style scoped>
.bell-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: var(--transition);
}

.bell-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.notification-panel__header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.notification-panel__title {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
}

.notification-panel__count {
  font-size: var(--fs-base);
  color: var(--color-primary);
}

.notification-panel__body {
  max-height: 360px;
  overflow-y: auto;
}

.notification-item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: var(--transition);
}

.notification-item:hover {
  background: var(--color-bg-alt);
}

.notification-item--unread {
  border-left: 3px solid var(--color-primary);
}

.notification-item__title {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
  margin-bottom: 2px;
}

.notification-item__summary {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-item__time {
  font-size: var(--fs-sm);
  color: var(--color-text-muted);
  margin-top: 4px;
}

.notification-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--fs-base);
}
</style>
