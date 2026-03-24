<template>
  <div class="activity-feed">
    <h3 class="activity-feed__title">最近动态</h3>
    <div v-if="items.length === 0" class="activity-feed__empty">暂无动态</div>
    <div v-else class="activity-feed__list">
      <div
        v-for="(group, dateKey) in groupedItems"
        :key="dateKey"
        class="activity-feed__group"
      >
        <div class="activity-feed__date">{{ dateKey }}</div>
        <div
          v-for="(item, idx) in group"
          :key="idx"
          class="activity-feed__item"
        >
          <span :class="['activity-feed__dot', `activity-feed__dot--${item.type}`]" />
          <span class="activity-feed__time">{{ item.time }}</span>
          <span class="activity-feed__text">{{ item.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
    // Each item: { time: string, text: string, type: 'system'|'exam'|'grading'|'info' }
  },
})

const groupedItems = computed(() => {
  const groups = {}
  for (const item of props.items) {
    // Extract date portion: e.g. "今天 14:30" → "今天"
    const parts = item.time.split(' ')
    const dateKey = parts.length > 1 ? parts[0] : '今天'
    if (!groups[dateKey]) groups[dateKey] = []
    groups[dateKey].push(item)
  }
  return groups
})
</script>

<style scoped>
.activity-feed {
  margin-top: 40px;
}

.activity-feed__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 20px;
}

.activity-feed__empty {
  font-size: 14px;
  color: var(--color-text-muted);
  padding: 24px 0;
}

.activity-feed__group {
  margin-bottom: 16px;
}

.activity-feed__date {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: 8px;
  padding-left: 20px;
}

.activity-feed__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  padding-left: 8px;
  position: relative;
}

.activity-feed__item + .activity-feed__item {
  border-top: 1px solid var(--color-border-light);
}

.activity-feed__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.activity-feed__dot--system { background: var(--macaron-mint); }
.activity-feed__dot--exam { background: var(--macaron-coral); }
.activity-feed__dot--grading { background: var(--macaron-yellow); }
.activity-feed__dot--info { background: var(--macaron-purple); }

.activity-feed__time {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
  min-width: 80px;
}

.activity-feed__text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>
