<template>
  <div class="parent-empty">
    <component :is="icon" v-if="icon" :size="48" :stroke-width="1" class="parent-empty__icon" />
    <div v-else class="parent-empty__icon-default">
      <Inbox :size="48" :stroke-width="1" />
    </div>
    <p class="parent-empty__message">{{ message }}</p>
    <div v-if="$slots.action" class="parent-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
import { Inbox } from 'lucide-vue-next'
defineProps({
  message: { type: String, default: '暂无数据' },
  icon: { type: [Object, null], default: null },
})
</script>

<style scoped>
.parent-empty { display: flex; flex-direction: column; align-items: center; padding: 48px 24px; }
.parent-empty__icon-default, .parent-empty__icon { color: var(--p-text-3, #9B93B5); margin-bottom: 16px; }
.parent-empty__message { font-size: var(--p-fs-body, 15px); color: var(--p-text-3, #9B93B5); text-align: center; margin: 0 0 16px; }
.parent-empty__action { margin-top: 8px; }
</style>
