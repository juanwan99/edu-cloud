<template>
  <div
    :class="['dashboard-card', { 'dashboard-card--planned': planned }]"
    @click="handleClick"
  >
    <div class="dashboard-card__header">
      <span class="dashboard-card__icon"><AppIcon :name="icon" :size="24" /></span>
      <h3 class="dashboard-card__title">{{ title }}</h3>
    </div>
    <div class="dashboard-card__body">
      <slot />
    </div>
    <span v-if="planned" class="dashboard-card__badge">规划中</span>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import AppIcon from '../AppIcon.vue'

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: '' },
  route: { type: String, default: '' },
  planned: { type: Boolean, default: false },
})

const router = useRouter()

function handleClick() {
  if (props.planned || !props.route) return
  router.push(props.route)
}
</script>

<style scoped>
.dashboard-card {
  background: var(--color-bg-card);
  border-radius: var(--r-md);
  border: 1px solid var(--color-border-light);
  padding: 24px;
  cursor: pointer;
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}

.dashboard-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-border);
}

/* Planned state */
.dashboard-card--planned {
  cursor: default;
  filter: grayscale(0.6);
  opacity: 0.7;
}

.dashboard-card--planned:hover {
  transform: none;
  box-shadow: none;
  border-color: var(--color-border-light);
}

.dashboard-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.dashboard-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--color-primary);
}

.dashboard-card__title {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
  margin: 0;
}

.dashboard-card__body {
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
}

.dashboard-card__badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: var(--macaron-yellow);
  color: var(--color-warning-text);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  padding: 2px 10px;
  border-radius: var(--radius-pill);
}
</style>
